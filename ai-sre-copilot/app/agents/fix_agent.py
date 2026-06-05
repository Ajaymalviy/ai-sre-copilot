"""
Fix Agent
=========
RCA ke basis pe actual fix steps generate karta hai.

Kubernetes commands, code fixes, config changes, etc.
Jo steps suggest karega wo human approve karega (HITL).
"""
import structlog
import re
from app.orchestrator.state import IncidentState
from app.services.claude_service import ClaudeService

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are an expert DevOps/SRE engineer creating a detailed remediation plan.

Your job is to:
1. Suggest specific, actionable fix steps for the root cause
2. Provide actual commands (kubectl, bash, config changes, etc.)
3. Order steps by priority and safety
4. Estimate risk level (low/medium/high)
5. Provide rollback steps in case of failure

Format your response with clear STEP sections and Command: lines.
For example:

STEP 1: Increase memory limit
Command: kubectl set resources deployment/myapp --limits=memory=3Gi

STEP 2: Restart the deployment
Command: kubectl rollout restart deployment/myapp

STEP 3: Monitor recovery
Command: kubectl logs -f deployment/myapp

SUMMARY: Brief summary of the fix
ESTIMATED_TIME: 5 minutes
RISK_LEVEL: low
"""


class FixAgent:

    def __init__(self):
        self.llm = ClaudeService()

    async def __call__(self, state: IncidentState) -> IncidentState:
        logger.info(
            "FixAgent starting",
            incident_id=state.get("incident_id"),
            root_cause=state.get("root_cause", "Unknown")[:100],
        )

        try:
            # Build fix prompt from RCA
            user_message = self._build_prompt(state)

            # Get fix plan from LLM
            fix_response = await self.llm.analyze(SYSTEM_PROMPT, user_message)

            # Parse fix steps and commands
            commands, risk_level = self._parse_response(fix_response)

            logger.info(
                "Fix plan parsed",
                commands_found=len(commands),
                risk_level=risk_level,
            )

            # Update state
            state["fix_plan"]      = fix_response
            state["fix_commands"]  = commands
            state["current_step"]  = "fix_generated"

            logger.info(
                "FixAgent done",
                incident_id=state.get("incident_id"),
                command_count=len(commands),
                risk_level=risk_level,
            )

        except Exception as e:
            logger.error("FixAgent failed", error=str(e))
            state.setdefault("errors", []).append(f"FixAgent: {str(e)}")
            state["fix_plan"] = "Fix generation failed."
            state["fix_commands"] = []

        return state

    def _build_prompt(self, state: IncidentState) -> str:
        """Build fix prompt from RCA and incident context"""
        prompt = f"""
INCIDENT: {state.get('alert_name')} (Severity: {state.get('severity')})
Service: {state.get('labels', {}).get('service', 'unknown')}
Namespace: {state.get('labels', {}).get('namespace', 'default')}

═══════════════════════════════════════════════════════════

ROOT CAUSE ANALYSIS:
{state.get('root_cause', 'Not available')}
(Confidence: {state.get('confidence', 0.0):.0%})

═══════════════════════════════════════════════════════════

METRICS BASELINE:
{state.get('metrics_summary', 'Not available')}

═══════════════════════════════════════════════════════════

RELEVANT RUNBOOKS:
"""
        for rb in state.get('relevant_runbooks', [])[:2]:
            prompt += f"\n### {rb.get('title')}\n"
            prompt += rb.get('content', '')[:300] + "...\n"

        prompt += """

═══════════════════════════════════════════════════════════

Based on the root cause analysis above, provide a detailed remediation plan.
Include specific kubectl commands, code changes, or configuration updates.
Format each step clearly with "Command:" lines.
Prioritize quick fixes first, then deeper fixes.
For each step, provide rollback instructions.
"""
        return prompt

    def _parse_response(self, response: str) -> tuple[list, str]:
        """
        Parse fix response to extract commands and risk level.
        Much more flexible parsing to handle various LLM formats.
        
        Returns:
            (commands_list, risk_level)
        """
        commands = []
        risk_level = "medium"

        lines = response.split("\n")

        # Look for risk level
        for line in lines:
            line_lower = line.lower()
            if "risk_level:" in line_lower or "risk level:" in line_lower:
                for risk in ["low", "medium", "high", "critical"]:
                    if risk in line_lower:
                        risk_level = risk
                        break

        # Extract commands - multiple strategies
        commands.extend(self._extract_commands_by_keyword(lines))
        commands.extend(self._extract_commands_by_pattern(lines))

        # Remove duplicates while preserving order
        seen = set()
        unique_commands = []
        for cmd in commands:
            if cmd and cmd.strip() not in seen:
                seen.add(cmd.strip())
                unique_commands.append({
                    "command": cmd.strip(),
                    "description": "Command to fix the issue"
                })

        logger.info(
            "Commands extracted",
            count=len(unique_commands),
            strategies_used=2,
        )

        return unique_commands, risk_level

    def _extract_commands_by_keyword(self, lines: list) -> list:
        """Extract commands that follow 'Command:' keyword"""
        commands = []
        for i, line in enumerate(lines):
            if "command:" in line.lower():
                # Get everything after "Command:"
                cmd = line.split(":", 1)[-1].strip()
                if cmd:
                    commands.append(cmd)

        return commands

    def _extract_commands_by_pattern(self, lines: list) -> list:
        """Extract commands that look like kubectl, bash, docker, etc."""
        commands = []
        command_patterns = [
            r"(kubectl\s+.+)",
            r"(docker\s+.+)",
            r"(bash\s+.+)",
            r"(sh\s+.+)",
            r"(git\s+.+)",
            r"(helm\s+.+)",
            r"(curl\s+.+)",
            r"(rm\s+.+)",
            r"(mkdir\s+.+)",
            r"(cp\s+.+)",
        ]

        for line in lines:
            line = line.strip()
            # Skip lines that are obviously comments or descriptions
            if line.startswith("#") or line.startswith("//"):
                continue
            if len(line) < 5 or len(line) > 500:
                continue

            for pattern in command_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    cmd = match.group(1).strip()
                    # Clean up common markdown/formatting
                    cmd = cmd.strip("`'\"")
                    if cmd and not any(skip in cmd for skip in ["example", "example:", "like this"]):
                        commands.append(cmd)
                        break

        return commands