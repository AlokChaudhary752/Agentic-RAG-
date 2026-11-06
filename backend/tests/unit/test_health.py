"""Unit and API route tests for health, readiness, and metrics endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.unit
async def test_health_liveness_endpoint(async_client: AsyncClient) -> None:
    """Verify /api/v1/health returns 200 OK with correct schema."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data
    assert "X-Correlation-ID" in response.headers


@pytest.mark.unit
async def test_health_readiness_endpoint(async_client: AsyncClient) -> None:
    """Verify /api/v1/health/ready returns 200 OK and component statuses."""
    response = await async_client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert "components" in data
    assert "database" in data["components"]
    assert "vector_store" in data["components"]
    assert "cache" in data["components"]


@pytest.mark.unit
async def test_metrics_endpoint(async_client: AsyncClient) -> None:
    """Verify /api/v1/metrics returns Prometheus metrics exposition."""
    response = await async_client.get("/api/v1/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
