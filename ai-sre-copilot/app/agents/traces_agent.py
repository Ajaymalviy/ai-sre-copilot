"""
TracesAgent
===========
Kya karta hai:
  1. Tempo se slow/error traces fetch karta hai
  2. Latency patterns dhundta hai
  3. Claude se analysis karwata hai
  4. State mein traces_data aur traces_summary save karta hai
"""
import structlog
from app.orchestrator.state import IncidentState
from app.services.tempo_service import TempoService
from app.services.claude_service import ClaudeService

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are a Site Reliability Engineer analyzing distributed traces during an incident.
Your job is to:
1. Identify slow spans (high latency operations)
2. Find error spans and failed requests
3. Spot cascade failures — which service caused others to slow down?
4. Identify the critical path bottleneck
5. Give a concise 3-5 sentence summary

Focus on latency numbers and service dependencies.
Output plain text, no markdown."""


class TracesAgent:

    def __init__(self):
        self.tempo  = TempoService()
        self.claude = ClaudeService()

    async def __call__(self, state: IncidentState) -> IncidentState:
        logger.info(
            "TracesAgent starting",
            incident_id=state.get("incident_id"),
        )

        try:
            # Step 1: Tempo se traces fetch karo
            traces = await self.tempo.fetch_incident_traces(
                labels=state.get("labels", {})
            )

            # Step 2: Traces ko readable format mein convert karo
            trace_text = self._format_traces(traces)

            # Step 3: Claude se analysis karwao
            user_message = f"""
Incident: {state.get('alert_name')} (severity: {state.get('severity')})
Service: {state.get('labels', {}).get('service', 'unknown')}
Total traces found: {len(traces)}

Trace Summary:
{trace_text}

Please analyze these traces and identify:
1. Which operations are slowest?
2. Are there timeout errors?
3. What is the latency trend?
4. Which downstream service is the bottleneck?
"""
            summary = await self.claude.analyze(SYSTEM_PROMPT, user_message)

            # Step 4: State update karo
            state["traces_data"]    = traces
            state["traces_summary"] = summary
            state["current_step"]   = "traces_done"

            logger.info(
                "TracesAgent done",
                incident_id=state.get("incident_id"),
                trace_count=len(traces),
            )

        except Exception as e:
            logger.error("TracesAgent failed", error=str(e))
            state.setdefault("errors", []).append(f"TracesAgent: {str(e)}")
            state["traces_summary"] = "Trace analysis failed."

        return state

    def _format_traces(self, traces: list) -> str:
        """Traces ko readable string mein convert karo"""
        if not traces:
            return "No traces found."

        lines = []
        for t in traces:
            trace_id = t.get("traceID", "unknown")[:16]
            name     = t.get("rootTraceName", "unknown")
            service  = t.get("rootServiceName", "unknown")
            duration = t.get("durationMs", 0)
            spans    = t.get("spanSets", [{}])
            span_count = spans[0].get("spans", "?") if spans else "?"

            # Latency ke basis pe status
            if duration > 10000:
                status = "TIMEOUT"
            elif duration > 3000:
                status = "SLOW"
            elif duration > 1000:
                status = "DEGRADED"
            else:
                status = "OK"

            lines.append(
                f"[{status}] {service} → {name} | "
                f"duration={duration}ms | spans={span_count} | id={trace_id}"
            )

        return "\n".join(lines)
