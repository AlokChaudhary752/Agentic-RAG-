"""Integration tests for chat completions API endpoint with streaming and stateful execution."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.domain.models import ClassificationLevel
from app.main import app


@pytest.fixture
def alice_auth_header() -> dict[str, str]:
    token = create_access_token(
        {
            "sub": "emp_alice",
            "user_id": "emp_alice",
            "email": "alice@nimbus.com",
            "full_name": "Alice Smith",
            "roles": ["employee"],
            "groups": ["group_engineering"],
            "clearance": ClassificationLevel.INTERNAL.value,
            "tenant_id": "tenant-nimbus-default",
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
async def test_chat_completions_synchronous(alice_auth_header: dict[str, str]) -> None:
    """Verify synchronous chat completions returns structured answer with citations."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/chat/completions",
            json={"query": "Hello there!", "stream": False},
            headers=alice_auth_header,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["query"] == "Hello there!"
        assert "Enterprise Knowledge Agent" in data["answer"]
        assert "understand" in data["steps_executed"]
        assert "thread_id" in data


@pytest.mark.integration
async def test_chat_completions_streaming_sse(alice_auth_header: dict[str, str]) -> None:
    """Verify stream=True returns Server-Sent Events stream with node events."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/chat/completions",
            json={"query": "Hello there!", "stream": True},
            headers=alice_auth_header,
        )
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        body = res.text
        assert "data: " in body
        assert "[DONE]" in body

