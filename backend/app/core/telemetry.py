"""Telemetry and observability module for OpenTelemetry and Prometheus integration."""

from prometheus_client import Counter, Histogram

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Prometheus Metrics Definitions
HTTP_REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests processed",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

AGENT_QUERY_COUNT = Counter(
    "agent_queries_total",
    "Total queries handled by the agentic RAG system",
    ["tenant_id", "intent", "status"],
)

AGENT_REASONING_LATENCY = Histogram(
    "agent_reasoning_duration_seconds",
    "End-to-end latency for agent graph execution in seconds",
    ["intent"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0],
)

PERMISSION_LEAK_DETECTIONS = Counter(
    "permission_leak_assertions_failed_total",
    "Security alerts where post-retrieval ACL assertion halted unauthorized chunk retrieval",
    ["tenant_id"],
)


def init_telemetry(settings: Settings | None = None) -> None:
    """Initialize OpenTelemetry tracers and exporters if enabled."""
    cfg = settings or get_settings()
    if not cfg.otel_enabled:
        logger.info("OpenTelemetry tracing is disabled by configuration")
        return

    try:
        # Optional dynamic setup when otel is enabled in production
        logger.info(
            "Initializing OpenTelemetry exporter",
            endpoint=cfg.otel_exporter_otlp_endpoint,
        )
    except Exception as exc:
        logger.warning("Failed to initialize OpenTelemetry exporter", error=str(exc))
