"""
Loki Service
============
LogsAgent yeh use karta hai logs fetch karne ke liye.
Mock data bhi support karta hai.
"""
import httpx
import structlog
from datetime import datetime, timezone, timedelta
from app.core.config import settings

logger = structlog.get_logger()


class LokiService:

    def __init__(self):
        self.base_url = settings.LOKI_URL
        self.timeout  = 10

    async def query(self, logql: str, limit: int = 100, minutes: int = 30) -> list:
        """Loki se logs fetch karo"""
        end   = datetime.now(timezone.utc)
        start = end - timedelta(minutes=minutes)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.base_url}/loki/api/v1/query_range",
                    params={
                        "query": logql,
                        "start": str(int(start.timestamp() * 1e9)),  # nanoseconds
                        "end":   str(int(end.timestamp() * 1e9)),
                        "limit": limit,
                        "direction": "backward",
                    }
                )
                resp.raise_for_status()
                data = resp.json()
                return self._parse_logs(data)

        except Exception as e:
            logger.warning("Loki query failed, using mock", error=str(e))
            return self._mock_logs(logql)

    async def fetch_incident_logs(self, labels: dict) -> list:
        """
        Incident ke related logs fetch karo.
        Service name se container logs dhundho.
        """
        service   = labels.get("service", labels.get("job", ""))
        namespace = labels.get("namespace", "")

        all_logs = []

        # Container logs by service name
        if service:
            logs = await self.query(
                f'{{service="{service}"}} |= "error" or {{{service}}} |= "ERROR"',
                limit=50,
                minutes=30
            )
            all_logs.extend(logs)

        # Exception/panic logs
        exception_logs = await self.query(
            '{job=~".+"} |~ "(?i)(exception|panic|fatal|traceback|oom|killed)"',
            limit=50,
            minutes=30
        )
        all_logs.extend(exception_logs)

        # Deduplicate
        seen = set()
        unique_logs = []
        for log in all_logs:
            key = log.get("message", "")[:100]
            if key not in seen:
                seen.add(key)
                unique_logs.append(log)

        return unique_logs[:80]  # Max 80 log lines

    # ── Helpers ───────────────────────────────

    def _parse_logs(self, response: dict) -> list:
        """Loki response se clean log lines nikalo"""
        logs = []
        try:
            streams = response.get("data", {}).get("result", [])
            for stream in streams:
                labels  = stream.get("stream", {})
                for ts, line in stream.get("values", []):
                    logs.append({
                        "timestamp": ts,
                        "message":   line,
                        "labels":    labels,
                    })
        except Exception as e:
            logger.error("Log parse failed", error=str(e))
        return logs

    def _mock_logs(self, query: str) -> list:
        """Realistic fake logs for testing"""
        import time

        now = int(time.time() * 1e9)
        sec = 1_000_000_000

        # CPU spike se related realistic logs
        return [
            {
                "timestamp": str(now - 25 * sec),
                "message": 'level=info msg="Request received" method=GET path=/api/checkout latency=45ms',
                "labels": {"service": "payment-api", "level": "info"}
            },
            {
                "timestamp": str(now - 20 * sec),
                "message": 'level=warn msg="High memory usage detected" used_mb=1842 limit_mb=2048',
                "labels": {"service": "payment-api", "level": "warn"}
            },
            {
                "timestamp": str(now - 15 * sec),
                "message": 'level=error msg="Database connection pool exhausted" pool_size=20 waiting=47',
                "labels": {"service": "payment-api", "level": "error"}
            },
            {
                "timestamp": str(now - 12 * sec),
                "message": 'level=error msg="Request timeout" path=/api/checkout timeout=30s attempts=3',
                "labels": {"service": "payment-api", "level": "error"}
            },
            {
                "timestamp": str(now - 10 * sec),
                "message": 'level=error msg="Unhandled exception" error="runtime: out of memory" goroutine=2847',
                "labels": {"service": "payment-api", "level": "error"}
            },
            {
                "timestamp": str(now - 8 * sec),
                "message": 'level=fatal msg="OOM Killer invoked" pid=1 container=payment-api memory_limit=2Gi',
                "labels": {"service": "payment-api", "level": "fatal"}
            },
            {
                "timestamp": str(now - 5 * sec),
                "message": 'level=info msg="Pod restarting after OOMKill" restart_count=3',
                "labels": {"service": "payment-api", "level": "info"}
            },
            {
                "timestamp": str(now - 2 * sec),
                "message": 'level=error msg="Readiness probe failed" consecutive_failures=3',
                "labels": {"service": "payment-api", "level": "error"}
            },
        ]
