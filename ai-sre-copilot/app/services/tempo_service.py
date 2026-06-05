"""
Tempo Service
=============
TracesAgent yeh use karta hai traces fetch karne ke liye.
Mock data bhi support karta hai.
"""
import httpx
import structlog
from datetime import datetime, timezone, timedelta
from app.core.config import settings

logger = structlog.get_logger()


class TempoService:

    def __init__(self):
        self.base_url = settings.TEMPO_URL
        self.timeout  = 10

    async def search(self, service: str = "", limit: int = 20, minutes: int = 30) -> list:
        """Recent traces search karo"""
        end   = datetime.now(timezone.utc)
        start = end - timedelta(minutes=minutes)

        params = {
            "start": str(int(start.timestamp())),
            "end":   str(int(end.timestamp())),
            "limit": limit,
        }
        if service:
            params["tags"] = f"service.name={service}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.base_url}/api/search",
                    params=params
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("traces", [])

        except Exception as e:
            logger.warning("Tempo search failed, using mock", error=str(e))
            return self._mock_traces(service)

    async def get_trace(self, trace_id: str) -> dict:
        """Specific trace ID se detail fetch karo"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.base_url}/api/traces/{trace_id}")
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning("Tempo get_trace failed", error=str(e), trace_id=trace_id)
            return {}

    async def fetch_incident_traces(self, labels: dict) -> list:
        """Incident ke related slow/error traces fetch karo"""
        service = labels.get("service", labels.get("job", ""))
        traces  = await self.search(service=service, limit=20, minutes=30)

        # Slow traces filter karo (> 1000ms)
        slow = [
            t for t in traces
            if int(t.get("durationMs", 0)) > 1000
        ]

        return slow if slow else traces[:10]

    # ── Mock Data ─────────────────────────────

    def _mock_traces(self, service: str) -> list:
        """Realistic fake traces — CPU spike scenario"""
        import random
        import time

        now = int(time.time() * 1000)

        return [
            {
                "traceID":    "abc123def456",
                "rootServiceName": service or "payment-api",
                "rootTraceName":   "POST /api/checkout",
                "startTimeUnixNano": str((now - 25000) * 1_000_000),
                "durationMs": 45,
                "spanSets": [{"spans": 3}]
            },
            {
                "traceID":    "def789ghi012",
                "rootServiceName": service or "payment-api",
                "rootTraceName":   "POST /api/checkout",
                "startTimeUnixNano": str((now - 15000) * 1_000_000),
                "durationMs": 3420,   # Slow! DB connection issue
                "spanSets": [{"spans": 8}],
                "spanCount": 8,
            },
            {
                "traceID":    "ghi345jkl678",
                "rootServiceName": service or "payment-api",
                "rootTraceName":   "GET /api/products",
                "startTimeUnixNano": str((now - 10000) * 1_000_000),
                "durationMs": 8750,   # Very slow!
                "spanSets": [{"spans": 12}],
            },
            {
                "traceID":    "jkl901mno234",
                "rootServiceName": service or "payment-api",
                "rootTraceName":   "POST /api/checkout",
                "startTimeUnixNano": str((now - 5000) * 1_000_000),
                "durationMs": 30004,  # Timeout!
                "spanSets": [{"spans": 5}],
                "rootSpanNotFound": True,
            },
        ]
