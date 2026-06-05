"""
RCA Agent (Root Cause Analysis)
================================
Teeno sources (metrics, logs, traces) ke data + runbooks
ko analyze karke root cause find karta hai.

Groq/Claude/OpenAI se advanced reasoning karwata hai.
"""
import structlog
from app.orchestrator.state import IncidentState
from app.services.claude_service import ClaudeService

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are an expert Site Reliability Engineer performing root cause analysis on a production incident.

Your job is to:
1. Analyze all available evidence (metrics, logs, traces, correlated findings)
2. Identify the PRIMARY root cause (not symptoms)
3. Explain the chain of events that led to the incident
4. Rate your confidence level (0.0 to 1.0)
5. Identify any contributing factors

Be specific and technical. Use exact metrics, timestamps, and error messages.
Output format:
- ROOT CAUSE: [One sentence summary]
- EXPLANATION: [2-3 sentences with chain of events]
- EVIDENCE: [Key supporting facts from metrics/logs/traces]
- CONTRIBUTING FACTORS: [Other issues that made it worse]
- CONFIDENCE: [0.0-1.0]
"""


class RCAAgent:

    def __init__(self):
        self.llm = ClaudeService()

    async def __call__(self, state: IncidentState) -> IncidentState:
        logger.info(
            "RCAAgent starting",
            incident_id=state.get("incident_id"),
        )

        try:
            # Build comprehensive context
            user_message = self._build_prompt(state)

            # Get RCA from LLM
            rca_response = await self.llm.analyze(SYSTEM_PROMPT, user_message)

            # Parse response
            root_cause, confidence = self._parse_response(rca_response)

            # Update state
            state["root_cause"]   = rca_response
            state["confidence"]   = confidence
            state["current_step"] = "rca_done"

            logger.info(
                "RCAAgent done",
                incident_id=state.get("incident_id"),
                confidence=confidence,
            )

        except Exception as e:
            logger.error("RCAAgent failed", error=str(e))
            state.setdefault("errors", []).append(f"RCAAgent: {str(e)}")
            state["root_cause"] = "RCA analysis failed."
            state["confidence"] = 0.0

        return state

    def _build_prompt(self, state: IncidentState) -> str:
        """Build comprehensive RCA prompt from all evidence"""
        runbooks_text = ""
        if state.get("relevant_runbooks"):
            runbooks_text = "\n## RELEVANT RUNBOOKS:\n"
            for rb in state.get("relevant_runbooks", [])[:3]:
                runbooks_text += f"\n### {rb.get('title', 'Untitled')}\n"
                runbooks_text += rb.get("content", "")[:500] + "...\n"

        prompt = f"""
INCIDENT SUMMARY:
- Alert: {state.get('alert_name')}
- Severity: {state.get('severity')}
- Service: {state.get('labels', {}).get('service', 'unknown')}
- Status: {state.get('status')}

═══════════════════════════════════════════════════════════

METRICS ANALYSIS:
{state.get('metrics_summary', 'Not available')}

═══════════════════════════════════════════════════════════

LOGS ANALYSIS:
{state.get('logs_summary', 'Not available')}

═══════════════════════════════════════════════════════════

TRACES ANALYSIS:
{state.get('traces_summary', 'Not available')}

═══════════════════════════════════════════════════════════

CORRELATED EVIDENCE:
{state.get('fused_evidence', 'Not available')}

═══════════════════════════════════════════════════════════
{runbooks_text}

═══════════════════════════════════════════════════════════

Based on ALL the evidence above, what is the ROOT CAUSE of this incident?
Be specific and technical in your analysis.
"""
        return prompt

    def _parse_response(self, response: str) -> tuple[str, float]:
        """
        Parse RCA response to extract root cause and confidence.
        
        Expected format:
        - ROOT CAUSE: ...
        - CONFIDENCE: 0.85
        """
        confidence = 0.7  # Default

        # Try to extract confidence
        for line in response.split("\n"):
            if "CONFIDENCE:" in line.upper():
                try:
                    # Extract number from line
                    parts = line.split(":")
                    if len(parts) > 1:
                        conf_str = parts[1].strip().split("\n")[0]
                        confidence = float(conf_str)
                        confidence = max(0.0, min(1.0, confidence))  # Clamp 0-1
                except Exception:
                    pass

        return response, confidence