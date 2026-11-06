"""Unit tests for permission-aware semantic caching with ACL key isolation."""

import asyncio

import pytest

from app.domain.models import ClassificationLevel, UserPrincipal
from app.governance.semantic_cache import CachedResponse, SemanticCacheService


@pytest.fixture
def cache_service() -> SemanticCacheService:
    return SemanticCacheService()


@pytest.fixture
def alice_principal() -> UserPrincipal:
    return UserPrincipal(
        user_id="emp_alice",
        email="alice@nimbus.com",
        full_name="Alice Smith",
        roles=["employee"],
        groups=["group_engineering"],
        clearance=ClassificationLevel.INTERNAL,
    )


@pytest.fixture
def bob_principal() -> UserPrincipal:
    return UserPrincipal(
        user_id="mgr_bob",
        email="bob@nimbus.com",
        full_name="Bob Jones",
        roles=["manager"],
        groups=["group_engineering", "group_managers"],
        clearance=ClassificationLevel.CONFIDENTIAL,
    )


@pytest.mark.unit
def test_acl_scoped_cache_key_isolation(
    cache_service: SemanticCacheService,
    alice_principal: UserPrincipal,
    bob_principal: UserPrincipal,
) -> None:
    """Verify identical queries from users with different ACLs generate strictly isolated cache keys."""
    query = "What is the engineering salary band and promotion criteria?"

    alice_key = cache_service.compute_cache_key(query, alice_principal)
    bob_key = cache_service.compute_cache_key(query, bob_principal)

    assert alice_key != bob_key, "CRITICAL: Cache keys for Alice and Bob must be strictly distinct!"
    assert "semantic_cache:tenant-nimbus-default:" in alice_key
    assert "semantic_cache:tenant-nimbus-default:" in bob_key


@pytest.mark.unit
async def test_semantic_cache_set_and_hit(
    cache_service: SemanticCacheService,
    alice_principal: UserPrincipal,
) -> None:
    """Verify storing and retrieving responses from cache."""
    query = "What is the Nimbus vacation leave policy?"
    cached_payload = CachedResponse(
        query=query,
        answer="Nimbus provides 25 days of annual vacation leave.",
        retrieved_chunk_ids=["chunk_pto_1"],
        citations=[{"doc_id": "hr-pto", "title": "PTO Policy"}],
        confidence=0.98,
        tenant_id=alice_principal.tenant_id,
    )

    await cache_service.set(query, alice_principal, cached_payload, ttl_seconds=60)

    # Cache hit
    hit = await cache_service.get(query, alice_principal)
    assert hit is not None
    assert hit.answer == "Nimbus provides 25 days of annual vacation leave."
    assert hit.retrieved_chunk_ids == ["chunk_pto_1"]

    # Cache miss on different query
    miss = await cache_service.get("How do I expense equipment?", alice_principal)
    assert miss is None


@pytest.mark.unit
async def test_cache_expiration(
    cache_service: SemanticCacheService,
    alice_principal: UserPrincipal,
) -> None:
    """Verify expired cache entries return None."""
    query = "Temporary policy update"
    cached_payload = CachedResponse(
        query=query,
        answer="Short lived response",
        tenant_id=alice_principal.tenant_id,
    )

    # Set TTL to 1 second
    await cache_service.set(query, alice_principal, cached_payload, ttl_seconds=1)

    # Wait for expiration
    await asyncio.sleep(1.1)

    res = await cache_service.get(query, alice_principal)
    assert res is None
