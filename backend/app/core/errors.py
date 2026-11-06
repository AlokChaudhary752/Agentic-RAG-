"""Consistent enterprise error handling and typed exceptions.

Defines an application-wide exception hierarchy and FastAPI exception handlers
producing uniform JSON responses adhering to enterprise API standards.
"""

from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.logging import get_correlation_id, get_logger

logger = get_logger(__name__)


class ErrorDetail(BaseModel):
    """Detailed error object returned within standard error payloads."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable description of the error")
    details: dict[str, Any] | Sequence[Any] | None = Field(
        default=None, description="Optional granular diagnostics or field errors"
    )


class ErrorResponse(BaseModel):
    """Standardized top-level API error envelope."""

    success: bool = Field(default=False, description="Always false for error envelopes")
    error: ErrorDetail = Field(..., description="Error detail object")
    correlation_id: str = Field(..., description="Tracing correlation ID")


class AppException(Exception):
    """Base class for all managed enterprise application exceptions."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppException):
    """Raised when a requested resource is not found."""

    def __init__(
        self, message: str = "Resource not found", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class UnauthorizedError(AppException):
    """Raised when authentication credentials are missing or invalid."""

    def __init__(
        self, message: str = "Authentication required", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class ForbiddenError(AppException):
    """Raised when user lacks permission to access a resource."""

    def __init__(
        self, message: str = "Access forbidden", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class PermissionLeakError(AppException):
    """High-severity security exception raised if unauthorized content leaks past pre-filter."""

    def __init__(
        self,
        message: str = "Permission boundary assertion failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="SECURITY_PERMISSION_LEAK_PREVENTED",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class PromptInjectionDetectedError(AppException):
    """Raised when adversarial prompt injection is detected in query or documents."""

    def __init__(
        self,
        message: str = "Adversarial prompt injection detected",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="PROMPT_INJECTION_DETECTED",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


PromptInjectionError = PromptInjectionDetectedError


class BudgetExceededError(AppException):
    """Raised when request execution exceeds permitted financial or token limits."""

    def __init__(
        self,
        message: str = "Query cost or token budget exceeded",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="BUDGET_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
        )


class ToolExecutionError(AppException):
    """Raised when an external MCP tool execution fails."""

    def __init__(
        self, message: str = "Tool execution failure", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            message=message,
            code="TOOL_EXECUTION_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details,
        )


def register_error_handlers(app: FastAPI) -> None:
    """Register uniform exception handlers on the FastAPI application instance."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        cid = get_correlation_id()
        logger.error(
            "Application exception occurred",
            error_code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=exc.code,
                    message=exc.message,
                    details=exc.details,
                ),
                correlation_id=cid,
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        cid = get_correlation_id()
        logger.warning(
            "Request validation error",
            path=request.url.path,
            errors=exc.errors(),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code="VALIDATION_ERROR",
                    message="Request payload validation failed",
                    details=exc.errors(),
                ),
                correlation_id=cid,
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        cid = get_correlation_id()
        logger.exception(
            "Unhandled server exception",
            path=request.url.path,
            error=str(exc),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code="INTERNAL_SERVER_ERROR",
                    message="An unexpected server error occurred",
                ),
                correlation_id=cid,
            ).model_dump(),
        )
