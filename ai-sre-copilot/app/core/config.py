"""
App Configuration — .env se values load hoti hain
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────
    APP_ENV:  str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # ── PostgreSQL ────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://sre_user:sre_pass@localhost:5432/sre_copilot"

    # ── Redis ─────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_HITL_TTL: int = 3600

    # ── Kafka ─────────────────────────────────
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_ALERTS: str = "incident.alerts"
    KAFKA_TOPIC_STATUS: str = "incident.status"
    KAFKA_TOPIC_HITL:   str = "hitl.decisions"
    KAFKA_CONSUMER_GROUP: str = "sre-copilot-group"

    # ── Qdrant ────────────────────────────────
    QDRANT_HOST:       str = "localhost"
    QDRANT_PORT:       int = 6333
    QDRANT_COLLECTION: str = "runbooks"
    QDRANT_VECTOR_SIZE: int = 384

    # ── Observability backends ────────────────
    PROMETHEUS_URL: str = "http://localhost:9090"
    LOKI_URL:       str = "http://localhost:3100"
    TEMPO_URL:      str = "http://localhost:3200"

    # ── LLM (Ollama local) ────────────────────
    OLLAMA_URL:     str = "http://localhost:11434"
    OLLAMA_MODEL:   str = "qwen2.5:7b"
    OLLAMA_TIMEOUT: int = 120

    # ── Notifications ─────────────────────────
    SLACK_WEBHOOK_URL: str = ""
    JIRA_URL:          str = ""
    JIRA_EMAIL:        str = ""
    JIRA_API_TOKEN:    str = ""
    JIRA_PROJECT_KEY:  str = "SRE"


# Singleton — poore app mein yahi use hoga
settings = Settings()
