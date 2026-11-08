"""Shared pytest fixtures for Enterprise Knowledge Agent test suites."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.db.models import Base
from app.main import create_app


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Fixture providing dedicated test settings."""
    return Settings(
        app_env="test",
        app_debug=True,
        jwt_secret_key="test-secret-key-must-be-at-least-32-chars-long",
        database_url="sqlite+aiosqlite:///:memory:",
        qdrant_use_in_memory=True,
        otel_enabled=False,
        langfuse_enabled=False,
    )


@pytest.fixture(autouse=True)
def override_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure test environment is set across all settings instances."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("QDRANT_USE_IN_MEMORY", "true")
    monkeypatch.setenv("OTEL_ENABLED", "false")
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    get_settings.cache_clear()


@pytest.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated, in-memory SQLite async database session."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
        await session.rollback()

    await engine.dispose()


@pytest.fixture
async def async_client(override_settings: None) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client bound to the FastAPI ASGI application."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
