"""
AI SRE Copilot — FastAPI Entry Point
app is starting from here:
  1. DB connection
  2. Start Kafka consumer 
  3. REST API endpoints
"""
import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import init_db, close_db
from app.kafka.consumer import KafkaAlertConsumer
from app.api.routes import router as api_router
from app.api.webhook import router as webhook_router

setup_logging()
logger = structlog.get_logger()

kafka_consumer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global kafka_consumer
    logger.info("AI SRE Copilot starting up...")

    await init_db()
    logger.info("PostgreSQL connected")

    kafka_consumer = KafkaAlertConsumer()
    asyncio.create_task(kafka_consumer.start())
    logger.info("Kafka consumer started", topic=settings.KAFKA_TOPIC_ALERTS)

    yield

    logger.info("Shutting down...")
    if kafka_consumer:
        await kafka_consumer.stop()
    await close_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title="AI SRE Copilot",
    description="Automated incident investigation platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
Instrumentator().instrument(app).expose(app)
app.include_router(api_router,     prefix="/api/v1")
app.include_router(webhook_router, prefix="/webhook")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai-sre-copilot"}

@app.get("/")
async def root():
    return {"service": "AI SRE Copilot", "version": "0.1.0", "docs": "/docs"}
