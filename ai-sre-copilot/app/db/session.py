"""
Database Session — SQLAlchemy Async
PostgreSQL ke saath async connection pool
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# ── Engine ────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,       # Connection alive check
    echo=(settings.APP_ENV == "development"),
)

# ── Session Factory ───────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# ── Base Model ────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Lifecycle Functions ───────────────────────
async def init_db():
    """App startup pe call hota hai"""
    async with engine.begin() as conn:
        # Tables already init.sql se bani hain,
        # but agar ORM models use karo to yeh kaam aata hai
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")


async def close_db():
    """App shutdown pe call hota hai"""
    await engine.dispose()
    logger.info("Database connection closed")


# ── Dependency (FastAPI routes mein use hoga) ─
async def get_db() -> AsyncSession:
    """
    FastAPI dependency injection ke liye.
    Usage:
        @app.get("/incidents")
        async def get_incidents(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
