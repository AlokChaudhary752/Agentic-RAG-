"""Permission-aware semantic cache enforcing strict ACL-scoped cache keys to prevent data leaks."""

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.domain.models import UserPrincipal

logger = get_logger(__name__)


class CachedResponse(BaseModel):
    """Payload stored in the permission-aware semantic cache."""

    query: str = Field(..., description="Normalized user query")
    answer: str = Field(..., description="Generated answer text")
    retrieved_chunk_ids: list[str] = Field(
        default_factory=list, description="IDs of chunks that supported this answer"
    )
    citations: list[dict[str, Any]] = Field(
        default_factory=list, description="Inline citation references"
    )
    confidence: float = Field(default=1.0, description="Confidence score")
    cached_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tenant_id: str = Field(..., description="Tenant scope")


class SemanticCacheService:
    """Provides high-speed caching with strictly isolated ACL-scoped keys."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._memory_cache: dict[
            str, tuple[str, float]
        ] = {}  # key -> (serialized_json, expire_timestamp)
        self.default_ttl = 3600

    def compute_cache_key(self, query: str, principal: UserPrincipal) -> str:
        """Derive a deterministic cache key binding query to the user's specific security clearance & groups."""
        norm_query = self._normalize_query(query)
        query_hash = hashlib.sha256(norm_query.encode("utf-8")).hexdigest()[:16]

        # Security context vector: tenant, clearance, sorted groups
        # Note: If private user ACLs are in use, principal.user_id can also be bound
        sorted_groups = ",".join(sorted(principal.groups))
        acl_context = f"{principal.tenant_id}|{principal.clearance.value}|{sorted_groups}"
        acl_hash = hashlib.sha256(acl_context.encode("utf-8")).hexdigest()[:16]

        return f"semantic_cache:{principal.tenant_id}:{acl_hash}:{query_hash}"

    async def get(self, query: str, principal: UserPrincipal) -> CachedResponse | None:
        """Retrieve cached response if available and not expired for the given principal."""
        cache_key = self.compute_cache_key(query, principal)

        entry = self._memory_cache.get(cache_key)
        if not entry:
            return None

        raw_json, expires_at = entry
        if datetime.now(UTC).timestamp() > expires_at:
            # Expired
            self._memory_cache.pop(cache_key, None)
            return None

        try:
            data = json.loads(raw_json)
            cached_obj = CachedResponse.model_validate(data)
            logger.info("Semantic cache HIT", key=cache_key, user_id=principal.user_id)
            return cached_obj
        except Exception as exc:
            logger.warning("Failed to deserialize cached response", error=str(exc))
            self._memory_cache.pop(cache_key, None)
            return None

    async def set(
        self,
        query: str,
        principal: UserPrincipal,
        response: CachedResponse,
        ttl_seconds: int | None = None,
    ) -> str:
        """Store response in cache isolated to the user's tenant and security principal context."""
        cache_key = self.compute_cache_key(query, principal)
        ttl = ttl_seconds or self.default_ttl
        expires_at = datetime.now(UTC).timestamp() + ttl

        serialized = response.model_dump_json()
        self._memory_cache[cache_key] = (serialized, expires_at)

        logger.info(
            "Semantic cache STORED",
            key=cache_key,
            user_id=principal.user_id,
            ttl=ttl,
        )
        return cache_key

    def clear(self) -> None:
        """Purge all entries from the in-memory cache."""
        self._memory_cache.clear()

    def _normalize_query(self, query: str) -> str:
        """Normalize query string for semantic cache matching."""
        q = query.lower().strip()
        q = re.sub(r"[^\w\s]", "", q)
        return re.sub(r"\s+", " ", q)
