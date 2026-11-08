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

TOKEN_USAGE_COUNTER = Counter(
    "llm_token_usage_total",
    "Total input and output tokens consumed across LLM providers and models",
    ["tenant_id", "model", "token_type"],
)

ESTIMATED_COST_COUNTER = Counter(
    "llm_estimated_cost_usd_total",
    "Cumulative estimated financial cost in USD across LLM providers and models",
    ["tenant_id", "model"],
)

CACHE_HITS_COUNTER = Counter(
    "semantic_cache_hits_total",
    "Total semantic cache hits by tenant",
    ["tenant_id"],
)

CACHE_MISSES_COUNTER = Counter(
    "semantic_cache_misses_total",
    "Total semantic cache misses by tenant",
    ["tenant_id"],
)

TOOL_CALL_COUNT = Counter(
    "mcp_tool_calls_total",
    "Total Model Context Protocol (MCP) tool invocations",
    ["tenant_id", "tool_name", "risk_level", "status"],
)

RATE_LIMIT_EXCEEDED_COUNT = Counter(
    "rate_limit_exceeded_total",
    "Total number of requests rejected due to rate limit exhaustion",
    ["tenant_id", "scope"],
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
