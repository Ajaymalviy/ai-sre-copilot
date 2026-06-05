"""
LogsAgent
=========
Kya karta hai:
  1. Loki se incident ke related logs fetch karta hai
  2. Error patterns, stack traces dhundta hai
  3. Claude se analysis karwata hai
  4. State mein logs_data aur logs_summary save karta hai
"""
import structlog
from app.orchestrator.state import IncidentState
from app.services.loki_service import LokiService
from app.services.claude_service import ClaudeService

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are a Site Reliability Engineer analyzing application logs during an incident.
Your job is to:
1. Find ERROR and FATAL level messages
2. Identify exception types and stack traces
3. Spot the timeline — what happened first?
4. Find patterns (repeated errors, cascading failures)
5. Give a concise 3-5 sentence summary

Be specific. Quote actual error messages when relevant.
Output plain text, no markdown."""


class LogsAgent:

    def __init__(self):
        self.loki   = LokiService()
        self.claude = ClaudeService()

    async def __call__(self, state: IncidentState) -> IncidentState:
        logger.info(
            "LogsAgent starting",
            incident_id=state.get("incident_id"),
        )

        try:
            # Step 1: Loki se logs fetch karo
            logs = await self.loki.fetch_incident_logs(
                labels=state.get("labels", {})
            )

            # Step 2: Logs ko readable format mein convert karo
            log_text = self._format_logs(logs)

            # Step 3: Claude se analysis karwao
            user_message = f"""
Incident: {state.get('alert_name')} (severity: {state.get('severity')})
Service: {state.get('labels', {}).get('service', 'unknown')}
Total log lines fetched: {len(logs)}

Log Lines (newest first):
{log_text}

Please analyze these logs and identify:
1. What errors are occurring?
2. What is the sequence of events?
3. Any OOM, timeout, or connection issues?
"""
            summary = await self.claude.analyze(SYSTEM_PROMPT, user_message)

            # Step 4: State update karo
            state["logs_data"]    = logs
            state["logs_summary"] = summary
            state["current_step"] = "logs_done"

            logger.info(
                "LogsAgent done",
                incident_id=state.get("incident_id"),
                log_count=len(logs),
            )

        except Exception as e:
            logger.error("LogsAgent failed", error=str(e))
            state.setdefault("errors", []).append(f"LogsAgent: {str(e)}")
            state["logs_summary"] = "Log analysis failed."

        return state

    def _format_logs(self, logs: list) -> str:
        """Logs ko readable string mein convert karo"""
        if not logs:
            return "No logs found."

        lines = []
        for log in logs[:30]:  # Max 30 lines Claude ko bhejo
            ts  = log.get("timestamp", "")[:19]   # Truncate nanoseconds
            msg = log.get("message", "").strip()
            lines.append(f"[{ts}] {msg}")

        return "\n".join(lines)
