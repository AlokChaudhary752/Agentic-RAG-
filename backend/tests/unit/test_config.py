"""Unit tests for configuration loading and validation."""

import pytest

from app.core.config import Settings, get_settings


@pytest.mark.unit
def test_default_settings_instantiation() -> None:
    """Verify default settings instantiation has expected default values."""
    settings = Settings()
    assert settings.app_name == "Enterprise Knowledge Agent"
    assert settings.app_port == 8000
    assert settings.default_tenant_id == "tenant-nimbus-default"
    assert settings.qdrant_vector_size == 1024
    assert settings.agent_max_iterations == 5


@pytest.mark.unit
def test_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify environment variables override default settings correctly."""
    monkeypatch.setenv("APP_NAME", "Custom Knowledge Agent")
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("QDRANT_PORT", "9999")
    monkeypatch.setenv("AGENT_MAX_ITERATIONS", "10")

    settings = Settings()
    assert settings.app_name == "Custom Knowledge Agent"
    assert settings.app_env == "staging"
    assert settings.qdrant_port == 9999
    assert settings.agent_max_iterations == 10


@pytest.mark.unit
def test_get_settings_cached() -> None:
    """Verify get_settings returns a cached singleton."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
