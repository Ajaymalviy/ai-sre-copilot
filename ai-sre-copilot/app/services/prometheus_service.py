"""
Prometheus Service
==================
MetricsAgent yeh use karta hai Prometheus se
data fetch karne ke liye.

Agar Prometheus mein real data nahi hai to
mock data return karta hai taaki agents test ho sakein.
"""
import httpx
import structlog
from datetime import datetime, timezone, timedelta
from app.core.config import settings

logger = structlog.get_logger()


class PrometheusService:

    def __init__(self):
        self.base_url = settings.PROMETHEUS_URL
        self.timeout  = 10

    async def query(self, promql: str) -> dict:
        """Instant query — abhi ki value"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.base_url}/api/v1/query",
                    params={"query": promql}
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning("Prometheus query failed, using mock", error=str(e), query=promql)
            return self._mock_response(promql)

    async def query_range(self, promql: str, minutes: int = 30) -> dict:
        """Range query — last N minutes ka data"""
        end   = datetime.now(timezone.utc)
        start = end - timedelta(minutes=minutes)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.base_url}/api/v1/query_range",
                    params={
                        "query": promql,
                        "start": start.timestamp(),
                        "end":   end.timestamp(),
                        "step":  "60s",
                    }
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning("Prometheus range query failed, using mock", error=str(e))
            return self._mock_range_response(promql, minutes)

    async def fetch_incident_metrics(self, labels: dict) -> dict:
        """
        Ek incident ke liye saari relevant metrics fetch karo.
        Labels se service/namespace automatically detect hota hai.
        """
        service   = labels.get("service",   labels.get("job", "unknown"))
        namespace = labels.get("namespace", "default")
        instance  = labels.get("instance",  "localhost:8000")

        results = {}

        # CPU usage
        cpu = await self.query(
            f'100 - (avg by(instance) (rate(node_cpu_seconds_total{{mode="idle"}}[5m])) * 100)'
        )
        results["cpu_usage_percent"] = self._extract_value(cpu)

        # Memory usage
        mem = await self.query(
            '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100'
        )
        results["memory_usage_percent"] = self._extract_value(mem)

        # HTTP error rate
        err = await self.query(
            f'rate(http_requests_total{{status=~"5..",job="{service}"}}[5m]) * 100'
        )
        results["http_error_rate"] = self._extract_value(err)

        # Request rate
        req = await self.query(
            f'rate(http_requests_total{{job="{service}"}}[5m])'
        )
        results["request_rate_per_sec"] = self._extract_value(req)

        # CPU trend (last 30 min)
        trend = await self.query_range(
            f'100 - (avg(rate(node_cpu_seconds_total{{mode="idle"}}[5m])) * 100)',
            minutes=30
        )
        results["cpu_trend_30m"] = self._extract_trend(trend)

        results["service"]   = service
        results["namespace"] = namespace
        results["queried_at"] = datetime.now(timezone.utc).isoformat()

        return results

    # ── Helpers ───────────────────────────────

    def _extract_value(self, response: dict) -> float:
        """Prometheus response se single float nikalo"""
        try:
            results = response.get("data", {}).get("result", [])
            if results:
                return float(results[0]["value"][1])
        except Exception:
            pass
        return 0.0

    def _extract_trend(self, response: dict) -> list:
        """Range query se [timestamp, value] pairs nikalo"""
        try:
            results = response.get("data", {}).get("result", [])
            if results:
                return [[v[0], float(v[1])] for v in results[0].get("values", [])]
        except Exception:
            pass
        return []

    # ── Mock Data (jab Prometheus available nahi) ─

    def _mock_response(self, query: str) -> dict:
        """Realistic fake data for testing"""
        import random

        # Query ke basis pe realistic values
        if "cpu" in query.lower():
            value = str(random.uniform(75, 95))   # High CPU to trigger alert
        elif "memory" in query.lower():
            value = str(random.uniform(60, 88))
        elif "error" in query.lower():
            value = str(random.uniform(5, 25))
        else:
            value = str(random.uniform(1, 100))

        return {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [{
                    "metric": {"instance": "localhost:9090", "job": "mock"},
                    "value":  [1704067200, value]
                }]
            }
        }

    def _mock_range_response(self, query: str, minutes: int) -> dict:
        """Fake range data — gradually badhta hua CPU spike"""
        import random
        import time

        now    = time.time()
        step   = 60
        values = []

        for i in range(minutes):
            ts    = now - (minutes - i) * step
            # Spike simulate karo: pehle normal, phir high
            if i < minutes * 0.6:
                val = random.uniform(20, 40)   # Normal
            else:
                val = random.uniform(75, 95)   # Spike

            values.append([ts, str(round(val, 2))])

        return {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [{
                    "metric": {"instance": "localhost:9090"},
                    "values": values
                }]
            }
        }
