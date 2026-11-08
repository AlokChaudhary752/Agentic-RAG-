"""Unit and integration tests for sliding-window rate limiting."""

import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.core.rate_limit import RateLimiter, get_rate_limiter
from app.core.security import create_access_token


@pytest.fixture
def clean_limiter() -> RateLimiter:
    limiter = get_rate_limiter()
    limiter.reset()
    return limiter


def test_rate_limiter_sliding_window_within_limit(clean_limiter: RateLimiter) -> None:
    """Verify requests under quota are permitted with decreasing remaining allowance."""
    key = "test:user:alice"
    max_reqs = 3

    allowed1, rem1, reset1 = clean_limiter.is_allowed(key, max_requests=max_reqs, window_seconds=60)
    assert allowed1 is True
    assert rem1 == 2
    assert reset1 > 0

    allowed2, rem2, reset2 = clean_limiter.is_allowed(key, max_requests=max_reqs, window_seconds=60)
    assert allowed2 is True
    assert rem2 == 1

    allowed3, rem3, reset3 = clean_limiter.is_allowed(key, max_requests=max_reqs, window_seconds=60)
    assert allowed3 is True
    assert rem3 == 0

    # 4th request should be blocked
    allowed4, rem4, reset4 = clean_limiter.is_allowed(key, max_requests=max_reqs, window_seconds=60)
    assert allowed4 is False
    assert rem4 == 0
    assert reset4 > 0


def test_rate_limiter_tenant_exhaustion(clean_limiter: RateLimiter) -> None:
    """Verify tenant-level limit triggers when collective user queries exceed quota."""
    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_requests_per_minute=10,
        rate_limit_tenant_requests_per_minute=2,
    )
    limiter = RateLimiter(settings=settings)

    # First query from user 1
    allowed1, headers1 = limiter.check_limits(user_id="user1", tenant_id="tenant-acme")
    assert allowed1 is True

    # Second query from user 2
    allowed2, headers2 = limiter.check_limits(user_id="user2", tenant_id="tenant-acme")
    assert allowed2 is True

    # Third query from user 3 exceeds tenant limit
    allowed3, headers3 = limiter.check_limits(user_id="user3", tenant_id="tenant-acme")
    assert allowed3 is False
    assert headers3["X-RateLimit-Remaining"] == "0"


@pytest.mark.unit
async def test_api_rate_limit_headers_and_rejection(
    async_client: AsyncClient, clean_limiter: RateLimiter
) -> None:
    """Verify API returns X-RateLimit headers and raises 429 upon quota exhaustion."""
    clean_limiter.reset()
    clean_limiter.settings.rate_limit_requests_per_minute = 2

    token = create_access_token(
        {
            "sub": "rate_user",
            "email": "rate_user@nimbus.com",
            "full_name": "Rate User",
            "roles": ["employee"],
            "groups": [],
            "clearance": "INTERNAL",
            "tenant_id": "tenant-rate-test",
        }
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Request 1: OK
    res1 = await async_client.post(
        "/api/v1/chat/completions",
        json={"query": "Hello"},
        headers=headers,
    )
    assert res1.status_code == 200
    assert "X-RateLimit-Limit" in res1.headers
    assert res1.headers["X-RateLimit-Remaining"] == "1"

    # Request 2: OK
    res2 = await async_client.post(
        "/api/v1/chat/completions",
        json={"query": "Hello again"},
        headers=headers,
    )
    assert res2.status_code == 200
    assert res2.headers["X-RateLimit-Remaining"] == "0"

    # Request 3: Blocked (429 Too Many Requests)
    res3 = await async_client.post(
        "/api/v1/chat/completions",
        json={"query": "Hello once more"},
        headers=headers,
    )
    assert res3.status_code == 429
    data3 = res3.json()
    assert data3["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    # Restore default rate limit
    clean_limiter.settings.rate_limit_requests_per_minute = 60
    clean_limiter.reset()
