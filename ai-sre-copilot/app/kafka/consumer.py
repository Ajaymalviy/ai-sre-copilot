"""
Kafka Alert Consumer
====================
incident.alerts topic ko sunता है।
Har message ek AlertManager payload hota hai.
Message aate hi pipeline trigger hoti hai.

NOTE: Is phase mein hum sirf message receive kar ke
      PostgreSQL mein save karte hain. Agent pipeline
      baad mein add hogi.
"""
import json
import asyncio
import structlog
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.incident import Incident

logger = structlog.get_logger()


class KafkaAlertConsumer:
    def __init__(self):
        self._consumer: AIOKafkaConsumer | None = None
        self._running = False

    async def start(self):
        """Consumer start karo, retry with backoff"""
        self._running = True
        retry_delay = 5

        while self._running:
            try:
                await self._connect()
                await self._consume()
            except KafkaConnectionError as e:
                logger.warning(
                    "Kafka connection failed, retrying...",
                    error=str(e),
                    retry_in=retry_delay,
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)  # Exponential backoff, max 60s
            except Exception as e:
                logger.error("Unexpected consumer error", error=str(e))
                await asyncio.sleep(retry_delay)

    async def _connect(self):
        """Kafka se connect karo"""
        self._consumer = AIOKafkaConsumer(
            settings.KAFKA_TOPIC_ALERTS,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_CONSUMER_GROUP,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        await self._consumer.start()
        logger.info(
            "Kafka consumer connected",
            topic=settings.KAFKA_TOPIC_ALERTS,
            group=settings.KAFKA_CONSUMER_GROUP,
        )

    async def _consume(self):
        """Messages process karo"""
        async for msg in self._consumer:
            if not self._running:
                break
            try:
                await self._handle_message(msg.value)
            except Exception as e:
                logger.error(
                    "Failed to process message",
                    error=str(e),
                    offset=msg.offset,
                )

    async def _handle_message(self, payload: dict):
        """
        AlertManager webhook payload ko parse karo.

        Typical AlertManager payload structure:
        {
          "receiver": "kafka-webhook",
          "status": "firing",
          "alerts": [
            {
              "status": "firing",
              "labels": {"alertname": "HighCPUUsage", "severity": "warning", ...},
              "annotations": {"summary": "...", "description": "..."},
              "startsAt": "2024-01-01T00:00:00Z",
            }
          ]
        }
        """
        alerts = payload.get("alerts", [])
        logger.info("Received alert payload", alert_count=len(alerts))

        for alert in alerts:
            if alert.get("status") != "firing":
                continue  # Resolved alerts skip karo abhi ke liye

            labels      = alert.get("labels", {})
            annotations = alert.get("annotations", {})

            incident_data = {
                "alert_name": labels.get("alertname", "UnknownAlert"),
                "severity":   labels.get("severity", "warning"),
                "source":     labels.get("job", "prometheus"),
                "labels":     labels,
                "annotations": annotations,
                "status":     "open",
            }

            # DB mein save karo
            incident_id = await self._save_incident(incident_data)

            logger.info(
                "Incident created",
                incident_id=str(incident_id),
                alert=incident_data["alert_name"],
                severity=incident_data["severity"],
            )

            # TODO: Yahan agent pipeline trigger hogi (next phase mein)
            # await orchestrator.run(incident_id, alert)

    async def _save_incident(self, data: dict) -> str:
        """Incident PostgreSQL mein save karo"""
        async with AsyncSessionLocal() as session:
            incident = Incident(**data)
            session.add(incident)
            await session.commit()
            await session.refresh(incident)
            return incident.id

    async def stop(self):
        """Consumer gracefully stop karo"""
        self._running = False
        if self._consumer:
            await self._consumer.stop()
            logger.info("Kafka consumer stopped")
