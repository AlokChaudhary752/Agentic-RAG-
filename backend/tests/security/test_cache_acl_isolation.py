"""Security verification of zero cache permission leaks across role boundaries."""

import pytest

from app.domain.models import ClassificationLevel, UserPrincipal
from app.governance.semantic_cache import CachedResponse, SemanticCacheService


@pytest.mark.security
async def test_zero_cache_permission_leak_across_users() -> None:
    """Verify confidential information cached by a manager is NEVER accessible to an employee."""
    cache = SemanticCacheService()

    alice_employee = UserPrincipal(
        user_id="emp_alice",
        email="alice@nimbus.com",
        full_name="Alice Smith",
        roles=["employee"],
        groups=["group_engineering"],
        clearance=ClassificationLevel.INTERNAL,
    )

    bob_manager = UserPrincipal(
        user_id="mgr_bob",
        email="bob@nimbus.com",
        full_name="Bob Jones",
        roles=["manager"],
        groups=["group_engineering", "group_managers"],
        clearance=ClassificationLevel.CONFIDENTIAL,
    )

    query = "What is the engineering salary band for senior staff engineers?"

    # 1. Bob executes query and system caches confidential answer
    confidential_payload = CachedResponse(
        query=query,
        answer="CONFIDENTIAL: Senior Staff Engineer salary band is $280,000 - $340,000 base + equity.",
        retrieved_chunk_ids=["fin-eng-salary-bands-2026-c1"],
        tenant_id=bob_manager.tenant_id,
    )
    await cache.set(query, bob_manager, confidential_payload)

    # 2. Verify Bob gets a cache HIT
    bob_hit = await cache.get(query, bob_manager)
    assert bob_hit is not None
    assert "280,000" in bob_hit.answer

    # 3. Alice asks the EXACT SAME query
    alice_hit = await cache.get(query, alice_employee)

    # 4. ASSERTION: Alice MUST get a cache MISS (Zero cache permission leak)
    assert alice_hit is None, (
        "CRITICAL SECURITY LEAK: Alice was able to access Bob's cached confidential response!"
    )

