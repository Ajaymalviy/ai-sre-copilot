"""
MetricsAgent
============
Kya karta hai:
  1. Prometheus se incident ke related metrics fetch karta hai
  2. Claude se analysis karwata hai
  3. State mein metrics_data aur metrics_summary save karta hai
"""
import structlog
from app.orchestrator.state import IncidentState
from app.services.prometheus_service import PrometheusService
from app.services.claude_service import ClaudeService

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are a Site Reliability Engineer analyzing Prometheus metrics during an incident.
Your job is to:
1. Identify anomalies in the metrics data
2. Spot the timeline of the issue
3. Highlight which metrics are most concerning
4. Give a concise 3-5 sentence summary

Be specific with numbers. Focus on what's abnormal.
Output plain text, no markdown."""


class MetricsAgent:

    def __init__(self):
        self.prometheus = PrometheusService()
        self.claude     = ClaudeService()

    async def __call__(self, state: IncidentState) -> IncidentState:
        logger.info(
            "MetricsAgent starting",
            incident_id=state.get("incident_id"),
            alert=state.get("alert_name"),
        )

        try:
            # Step 1: Prometheus se metrics fetch karo
            metrics = await self.prometheus.fetch_incident_metrics(
                labels=state.get("labels", {})
            )

            # Step 2: Claude se analysis karwao
            user_message = f"""
Incident: {state.get('alert_name')} (severity: {state.get('severity')})
Service: {metrics.get('service')} in namespace: {metrics.get('namespace')}

Current Metrics:
- CPU Usage:          {metrics.get('cpu_usage_percent', 0):.1f}%
- Memory Usage:       {metrics.get('memory_usage_percent', 0):.1f}%
- HTTP Error Rate:    {metrics.get('http_error_rate', 0):.1f}%
- Request Rate:       {metrics.get('request_rate_per_sec', 0):.2f} req/sec

CPU Trend (last 30 min): {self._format_trend(metrics.get('cpu_trend_30m', []))}

Alert Labels: {state.get('labels')}
Alert Annotations: {state.get('annotations')}

Please analyze these metrics and identify what's happening.
"""
            summary = await self.claude.analyze(SYSTEM_PROMPT, user_message)

            # Step 3: State update karo
            state["metrics_data"]    = metrics
            state["metrics_summary"] = summary
            state["current_step"]    = "metrics_done"

            logger.info("MetricsAgent done", incident_id=state.get("incident_id"))

        except Exception as e:
            logger.error("MetricsAgent failed", error=str(e))
            state.setdefault("errors", []).append(f"MetricsAgent: {str(e)}")
            state["metrics_summary"] = "Metrics analysis failed."

        return state

    def _format_trend(self, trend: list) -> str:
        """Trend data ko readable string mein convert karo"""
        if not trend:
            return "No trend data"
        values = [v for _, v in trend]
        if not values:
            return "No trend data"
        return (
            f"min={min(values):.1f}% → max={max(values):.1f}% "
            f"(avg={sum(values)/len(values):.1f}%)"
        )
