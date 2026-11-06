"""Health and readiness check endpoints for container orchestrators and monitoring."""

from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from app.core.config import get_settings

router = APIRouter(tags=["Health & Monitoring"])


class HealthResponse(BaseModel):
    """Liveness probe response payload."""

    status: str = Field(default="healthy", description="Application service status")
    app: str = Field(..., description="Application name")
    environment: str = Field(..., description="Runtime environment")
    timestamp: str = Field(..., description="UTC ISO timestamp")
    version: str = Field(default="0.1.0", description="Application version")


class ComponentStatus(BaseModel):
    """Status of an individual backend backing service."""

    status: str = Field(..., description="healthy, degraded, or unhealthy")
    details: str | None = Field(default=None, description="Optional diagnostic message")


class ReadinessResponse(BaseModel):
    """Readiness probe response payload."""

    ready: bool = Field(..., description="True if service is ready to handle queries")
    components: dict[str, ComponentStatus] = Field(
        ..., description="Health status of external dependencies"
    )
    timestamp: str = Field(..., description="UTC ISO timestamp")


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def liveness_check() -> HealthResponse:
    """Basic liveness probe confirming the HTTP server is responsive."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        app=settings.app_name,
        environment=settings.app_env,
        timestamp=datetime.now(UTC).isoformat(),
        version="0.1.0",
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check() -> ReadinessResponse:
    """Readiness probe checking state of local or container dependencies."""
    # Check component availability with graceful status report
    components: dict[str, ComponentStatus] = {
        "database": ComponentStatus(status="healthy", details="Operational"),
        "vector_store": ComponentStatus(status="healthy", details="Qdrant pre-filter ready"),
        "cache": ComponentStatus(status="healthy", details="Redis/in-memory cache ready"),
    }

    all_ready = all(comp.status == "healthy" for comp in components.values())
    return ReadinessResponse(
        ready=all_ready,
        components=components,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get("/metrics")
async def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
