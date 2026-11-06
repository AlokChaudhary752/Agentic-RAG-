"""Structured logging configuration for Enterprise Knowledge Agent.

Provides JSON-formatted structured logging with correlation IDs, tenant awareness,
and contextvars support for async tracing across request lifecycles.
"""

import contextvars
import logging
import sys
import uuid
from typing import Any, cast

import structlog

# Context variable holding correlation ID for the active async task
correlation_id_ctx_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)
tenant_id_ctx_var: contextvars.ContextVar[str] = contextvars.ContextVar("tenant_id", default="")
user_id_ctx_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="")


def get_correlation_id() -> str:
    """Retrieve the current correlation ID or generate a fallback."""
    cid = correlation_id_ctx_var.get()
    if not cid:
        cid = str(uuid.uuid4())
        correlation_id_ctx_var.set(cid)
    return cid


def add_correlation_fields(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Inject contextual tracing identifiers into every structured log event."""
    cid = correlation_id_ctx_var.get()
    if cid:
        event_dict["correlation_id"] = cid

    tid = tenant_id_ctx_var.get()
    if tid:
        event_dict["tenant_id"] = tid

    uid = user_id_ctx_var.get()
    if uid:
        event_dict["user_id"] = uid

    return event_dict


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure system-wide structlog and standard logging handlers."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        add_correlation_fields,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    formatter_processor: Any
    if log_format.lower() == "json":
        formatter_processor = structlog.processors.JSONRenderer()
    else:
        formatter_processor = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            formatter_processor,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)

    # Silence overly verbose external loggers
    for verbose_logger in ("uvicorn.access", "httpcore", "httpx"):
        logging.getLogger(verbose_logger).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Obtain a structured logger bound to a given namespace."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


class CorrelationIdMiddleware:
    """Pure ASGI middleware extracting or generating X-Correlation-ID for every incoming request."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        header_corr_id = headers.get(b"x-correlation-id")
        correlation_id = (
            header_corr_id.decode("latin1") if header_corr_id else str(uuid.uuid4())
        )
        correlation_id_ctx_var.set(correlation_id)

        header_tenant_id = headers.get(b"x-tenant-id")
        tenant_id = (
            header_tenant_id.decode("latin1")
            if header_tenant_id
            else "tenant-nimbus-default"
        )
        tenant_id_ctx_var.set(tenant_id)

        async def send_with_correlation(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers.append(
                    (b"x-correlation-id", correlation_id.encode("latin1"))
                )
                message["headers"] = response_headers
            await send(message)

        await self.app(scope, receive, send_with_correlation)
