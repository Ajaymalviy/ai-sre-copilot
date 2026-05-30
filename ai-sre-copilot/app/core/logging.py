"""
Structured Logging Setup — structlog
JSON format mein logs → Loki easily parse kar sakta hai
"""
import logging
import structlog
from app.core.config import settings


def setup_logging():
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # Dev mein pretty print, prod mein JSON
            structlog.dev.ConsoleRenderer()
            if settings.APP_ENV == "development"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
