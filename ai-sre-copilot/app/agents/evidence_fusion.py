"""
Evidence Fusion
===============
MetricsAgent + LogsAgent + TracesAgent ke outputs ko
ek coherent summary mein combine karta hai.

Yeh Claude ko poora picture deta hai RCA ke liye.
"""
import structlog
from app.orchestrator.state import IncidentState
from app.services.claude_service import ClaudeService

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are a senior SRE correlating evidence from multiple sources during an incident.
You have metrics data, logs, and distributed traces.
Your job is to:
1. Find correlations across all three data sources
2. Build a timeline of what happened
3. Identify the most likely root cause area (not full RCA yet)
4. Highlight the strongest evidence pieces

Write a clear, structured paragraph (5-8 sentences).
Be specific with timestamps, numbers, and error messages.
Output plain text, no markdown headers."""


class EvidenceFusion:

    def __init__(self):
        self.claude = ClaudeService()

    async def __call__(self, state: IncidentState) -> IncidentState:
        logger.info(
            "EvidenceFusion starting",
            incident_id=state.get("incident_id"),
        )

        try:
            user_message = f"""
Incident: {state.get('alert_name')} | Severity: {state.get('severity')}
Service: {state.get('labels', {}).get('service', 'unknown')}

=== METRICS ANALYSIS ===
{state.get('metrics_summary', 'Not available')}

=== LOGS ANALYSIS ===
{state.get('logs_summary', 'Not available')}

=== TRACES ANALYSIS ===
{state.get('traces_summary', 'Not available')}

Please correlate all three sources and build a unified picture of what happened.
What is the sequence of events? What do all three sources agree on?
"""
            fused = await self.claude.analyze(SYSTEM_PROMPT, user_message)

            state["fused_evidence"] = fused
            state["current_step"]   = "fusion_done"

            logger.info("EvidenceFusion done", incident_id=state.get("incident_id"))

        except Exception as e:
            logger.error("EvidenceFusion failed", error=str(e))
            state.setdefault("errors", []).append(f"EvidenceFusion: {str(e)}")
            # Fallback: teeno summaries concatenate kar do
            state["fused_evidence"] = "\n\n".join(filter(None, [
                state.get("metrics_summary"),
                state.get("logs_summary"),
                state.get("traces_summary"),
            ]))

        return state
