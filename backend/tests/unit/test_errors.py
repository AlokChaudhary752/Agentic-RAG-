"""Unit tests for enterprise error hierarchy and exception serialization."""

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient

from app.core.errors import (
    ForbiddenError,
    NotFoundError,
    PermissionLeakError,
    PromptInjectionDetectedError,
    register_error_handlers,
)
from app.core.logging import CorrelationIdMiddleware


@pytest.fixture
def error_test_app() -> FastAPI:
    """Create a minimal test FastAPI app with registered error handlers."""
    test_app = FastAPI()
    test_app.add_middleware(CorrelationIdMiddleware)
    register_error_handlers(test_app)

    @test_app.get("/trigger-not-found")
    async def trigger_not_found() -> None:
        raise NotFoundError("Test document not found", details={"doc_id": "doc-99"})

    @test_app.get("/trigger-forbidden")
    async def trigger_forbidden() -> None:
        raise ForbiddenError("User lacks clearance for this classification level")

    @test_app.get("/trigger-permission-leak")
    async def trigger_permission_leak() -> None:
        raise PermissionLeakError("Unauthorized chunk detected in retrieved set")

    @test_app.get("/trigger-prompt-injection")
    async def trigger_prompt_injection() -> None:
        raise PromptInjectionDetectedError("Jailbreak pattern matched in prompt")

    return test_app


@pytest.mark.unit
async def test_not_found_error_handler(error_test_app: FastAPI) -> None:
    """Verify NotFoundError is mapped to HTTP 404 with standard envelope."""
    transport = ASGITransport(app=error_test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/trigger-not-found")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "NOT_FOUND"
        assert data["error"]["details"] == {"doc_id": "doc-99"}
        assert len(data["correlation_id"]) > 0


@pytest.mark.unit
async def test_permission_leak_error_handler(error_test_app: FastAPI) -> None:
    """Verify PermissionLeakError produces security alert error envelope."""
    transport = ASGITransport(app=error_test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/trigger-permission-leak")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "SECURITY_PERMISSION_LEAK_PREVENTED"


@pytest.mark.unit
async def test_prompt_injection_error_handler(error_test_app: FastAPI) -> None:
    """Verify PromptInjectionDetectedError is mapped to HTTP 400 Bad Request."""
    transport = ASGITransport(app=error_test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/trigger-prompt-injection")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "PROMPT_INJECTION_DETECTED"
