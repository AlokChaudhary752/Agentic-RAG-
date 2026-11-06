"""Shared pytest fixtures for Enterprise Knowledge Agent test suites."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
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


@pytest.fixture
def override_settings(test_settings: Settings) -> None:
    """Apply test settings to the lru_cache."""
    get_settings.cache_clear()


@pytest.fixture
async def async_client(override_settings: None) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client bound to the FastAPI ASGI application."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
