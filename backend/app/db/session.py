"""Database engine and asynchronous session management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import Base

logger = get_logger(__name__)

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Obtain or initialize the cached SQLAlchemy async engine."""
    global _engine, _session_maker
    if _engine is None:
        settings = get_settings()
        db_url = settings.database_url

        # Check if running in test environment or fallback
        if settings.app_env == "test" or "sqlite" in db_url:
            connect_args: dict[str, Any] = {"check_same_thread": False}
        else:
            connect_args = {}

        _engine = create_async_engine(
            db_url,
            echo=settings.app_debug,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        _session_maker = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Obtain the session maker factory."""
    global _session_maker
    if _session_maker is None:
        get_engine()
    assert _session_maker is not None
    return _session_maker


async def init_db() -> None:
    """Create all relational database tables idempotently."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Relational database schemas initialized successfully")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    session_factory = get_session_maker()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for standalone background workers and seed scripts."""
    session_factory = get_session_maker()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
