"""Rate limiting engine supporting sliding window counters with in-memory and Redis backends."""

import threading
import time
from collections import defaultdict
from typing import Annotated, Any

from fastapi import Depends, Request

from app.api.auth import get_current_principal
from app.core.config import Settings, get_settings
from app.core.errors import RateLimitExceededError
from app.core.logging import get_logger
from app.core.telemetry import RATE_LIMIT_EXCEEDED_COUNT
from app.domain.models import UserPrincipal

logger = get_logger(__name__)


class RateLimiter:
    """Sliding-window rate limiter per user and tenant."""

    def __init__(
        self,
        settings: Settings | None = None,
        redis_client: Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.redis = redis_client
        self._lock = threading.Lock()
        self._window_records: dict[str, list[float]] = defaultdict(list)

    def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int = 60,
    ) -> tuple[bool, int, int]:
        """Check if request is permitted under sliding window quota.

        Returns:
            (is_allowed, remaining_quota, reset_seconds)
        """
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            # Prune expired timestamps
            timestamps = [ts for ts in self._window_records[key] if ts > window_start]
            current_count = len(timestamps)

            if current_count >= max_requests:
                # Quota exhausted: reset when oldest timestamp expires
                oldest = timestamps[0] if timestamps else now
                reset_seconds = max(1, int(oldest + window_seconds - now))
                self._window_records[key] = timestamps
                return False, 0, reset_seconds

            # Append current timestamp
            timestamps.append(now)
            self._window_records[key] = timestamps
            remaining = max(0, max_requests - len(timestamps))
            oldest = timestamps[0]
            reset_seconds = max(1, int(oldest + window_seconds - now))
            return True, remaining, reset_seconds

    def check_limits(
        self,
        user_id: str,
        tenant_id: str,
    ) -> tuple[bool, dict[str, str]]:
        """Verify user and tenant quotas, returning rate limit headers.

        Returns:
            (is_allowed, response_headers)
        """
        if not self.settings.rate_limit_enabled:
            return True, {
                "X-RateLimit-Limit": str(self.settings.rate_limit_requests_per_minute),
                "X-RateLimit-Remaining": str(self.settings.rate_limit_requests_per_minute),
                "X-RateLimit-Reset": "60",
            }

        user_key = f"ratelimit:user:{user_id}"
        tenant_key = f"ratelimit:tenant:{tenant_id}"

        user_allowed, user_rem, user_reset = self.is_allowed(
            key=user_key,
            max_requests=self.settings.rate_limit_requests_per_minute,
            window_seconds=60,
        )

        tenant_allowed, tenant_rem, tenant_reset = self.is_allowed(
            key=tenant_key,
            max_requests=self.settings.rate_limit_tenant_requests_per_minute,
            window_seconds=60,
        )

        headers = {
            "X-RateLimit-Limit": str(self.settings.rate_limit_requests_per_minute),
            "X-RateLimit-Remaining": str(user_rem),
            "X-RateLimit-Reset": str(user_reset),
        }

        if not user_allowed:
            RATE_LIMIT_EXCEEDED_COUNT.labels(tenant_id=tenant_id, scope="user").inc()
            logger.warning("User rate limit exceeded", user_id=user_id, tenant_id=tenant_id)
            return False, headers

        if not tenant_allowed:
            RATE_LIMIT_EXCEEDED_COUNT.labels(tenant_id=tenant_id, scope="tenant").inc()
            logger.warning("Tenant rate limit exceeded", tenant_id=tenant_id)
            headers["X-RateLimit-Remaining"] = str(tenant_rem)
            headers["X-RateLimit-Reset"] = str(tenant_reset)
            return False, headers

        return True, headers

    def reset(self) -> None:
        """Clear all active in-memory rate limit tracking (primarily for test fixtures)."""
        with self._lock:
            self._window_records.clear()


_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Retrieve or initialize singleton RateLimiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


async def verify_rate_limit(
    request: Request,
    principal: Annotated[UserPrincipal, Depends(get_current_principal)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> UserPrincipal:
    """FastAPI dependency enforcing user and tenant rate limits."""
    allowed, headers = limiter.check_limits(principal.user_id, principal.tenant_id)

    # Store rate limit headers on request state for injection into response
    request.state.rate_limit_headers = headers

    if not allowed:
        raise RateLimitExceededError(
            details={
                "user_id": principal.user_id,
                "tenant_id": principal.tenant_id,
                "retry_after_seconds": headers.get("X-RateLimit-Reset", "60"),
            }
        )

    return principal
