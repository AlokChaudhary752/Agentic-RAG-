"""Unit tests for telemetry initialization and metric counters."""

import pytest

from app.core.config import Settings
from app.core.telemetry import (
    AGENT_QUERY_COUNT,
    HTTP_REQUEST_COUNT,
    PERMISSION_LEAK_DETECTIONS,
    init_telemetry,
)


@pytest.mark.unit
def test_init_telemetry_disabled() -> None:
    """Verify init_telemetry handles disabled state cleanly."""
    settings = Settings(otel_enabled=False)
    # Should not raise exception
    init_telemetry(settings)


@pytest.mark.unit
def test_init_telemetry_enabled() -> None:
    """Verify init_telemetry handles enabled state cleanly."""
    settings = Settings(otel_enabled=True, otel_exporter_otlp_endpoint="http://localhost:4317")
    init_telemetry(settings)


@pytest.mark.unit
def test_prometheus_metric_counters() -> None:
    """Verify metrics can be incremented without error."""
    HTTP_REQUEST_COUNT.labels(method="GET", endpoint="/api/v1/health", status_code="200").inc()
    AGENT_QUERY_COUNT.labels(tenant_id="tenant-1", intent="factual", status="success").inc()
    PERMISSION_LEAK_DETECTIONS.labels(tenant_id="tenant-1").inc()
