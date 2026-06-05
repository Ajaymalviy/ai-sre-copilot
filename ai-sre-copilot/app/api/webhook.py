"""
Webhook Endpoint — AlertManager → Kafka
AlertManager yahan POST karta hai,
hum Kafka topic pe publish karte hain.
"""
import json
import structlog
from fastapi import APIRouter, Request, HTTPException
from aiokafka import AIOKafkaProducer

from app.core.config import settings

router = APIRouter(tags=["webhook"])
logger = structlog.get_logger()


@router.post("/alertmanager")
async def alertmanager_webhook(request: Request):
    """
    webhook receiver of AlertManager.
    Payload is published on Kafka incident.alerts topic 
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    alert_count = len(payload.get("alerts", []))
    logger.info(
        "AlertManager webhook received",
        alert_count=alert_count,
        status=payload.get("status"),
    )

    # publish on Kafka   
    try:
        producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await producer.start()
        await producer.send_and_wait(
            settings.KAFKA_TOPIC_ALERTS,
            value=payload,
        )
        await producer.stop()

        logger.info("Alert published to Kafka", topic=settings.KAFKA_TOPIC_ALERTS)
        return {"status": "ok", "alerts_received": alert_count}

    except Exception as e:
        logger.error("Failed to publish to Kafka", error=str(e))
        raise HTTPException(status_code=500, detail=f"Kafka publish failed: {str(e)}")

@router.post("/test-alert")
async def test_alert(request: Request):
    """
    send a  fake alert just for development.
    curl -X POST http://localhost:8000/webhook/test-alert \
         -H 'Content-Type: application/json' \
         -d '{"alertname": "HighCPUUsage", "severity": "warning"}'
    """
    body = await request.json()

    # wrap the body in AlertManager format
    fake_payload = {
        "receiver": "kafka-webhook",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": body.get("alertname", "TestAlert"),
                    "severity":  body.get("severity", "warning"),
                    "instance":  body.get("instance", "localhost:8000"),
                    "job":       body.get("job", "test"),
                },
                "annotations": {
                    "summary":     f"Test alert: {body.get('alertname', 'TestAlert')}",
                    "description": "This is a test alert from /webhook/test-alert",
                },
                "startsAt": "2024-01-01T00:00:00Z",
            }
        ],
    }

    # call the same Kafka publish logic as the main webhook
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await producer.start()
    await producer.send_and_wait(settings.KAFKA_TOPIC_ALERTS, value=fake_payload)
    await producer.stop()

    return {"status": "ok", "message": "Test alert sent to Kafka", "payload": fake_payload}
