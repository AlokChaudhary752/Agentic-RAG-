"""Unit tests for immutable audit logging repository and service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.audit_repo import AuditRepository
from app.domain.models import ClassificationLevel, UserPrincipal
from app.governance.audit_service import AuditService


@pytest.fixture
def test_principal() -> UserPrincipal:
    return UserPrincipal(
        user_id="emp_alice",
        email="alice@nimbus.com",
        full_name="Alice Smith",
        roles=["employee"],
        groups=["group_engineering"],
        clearance=ClassificationLevel.INTERNAL,
    )


@pytest.mark.unit
async def test_audit_repository_append_and_query(async_session: AsyncSession) -> None:
    """Verify audit entries can be appended and queried by user and severity."""
    repo = AuditRepository(async_session)

    entry = await repo.log_event(
        user_id="emp_alice",
        query="What is the remote work policy?",
        retrieved_chunk_ids=["chunk_1", "chunk_2"],
        severity="INFO",
    )
    assert entry.id is not None
    assert entry.user_id == "emp_alice"
    assert entry.retrieved_chunk_ids == ["chunk_1", "chunk_2"]

    logs = await repo.list_logs(tenant_id="tenant-nimbus-default", user_id="emp_alice")
    assert len(logs) >= 1
    assert logs[0].query == "What is the remote work policy?"


@pytest.mark.unit
def test_audit_repository_immutability(async_session: AsyncSession) -> None:
    """Verify audit entries cannot be mutated or deleted."""
    repo = AuditRepository(async_session)

    with pytest.raises(PermissionError, match="immutable and cannot be updated"):
        repo.update(id="test_id")

    with pytest.raises(PermissionError, match="immutable and cannot be deleted"):
        repo.delete(id="test_id")


@pytest.mark.unit
async def test_audit_service_operations(
    async_session: AsyncSession,
    test_principal: UserPrincipal,
) -> None:
    """Verify AuditService records retrievals, tool invocations, and security alerts."""
    service = AuditService(async_session)

    # 1. Retrieval audit
    retrieval_entry = await service.record_query_and_retrieval(
        principal=test_principal,
        query="What is my stock vesting schedule?",
        retrieved_chunk_ids=["equity_chunk_1"],
        correlation_id="corr_vesting_101",
    )
    assert retrieval_entry.user_email == "alice@nimbus.com"
    assert retrieval_entry.severity == "INFO"

    # 2. Tool call audit
    tool_entry = await service.record_tool_call(
        principal=test_principal,
        query="Create high priority bug ticket",
        tool_name="create_jira_ticket",
        risk_level="write_high",
        approved=False,
    )
    assert tool_entry.tool_called == "create_jira_ticket"
    assert tool_entry.action_approved is False
    assert tool_entry.severity == "WARNING"

    # 3. Security alert audit
    alert_entry = await service.record_security_alert(
        principal=test_principal,
        event_type="UNAUTHORIZED_CHUNK_RETRIEVAL_ATTEMPT",
        details="Attempted access to hr-exec-comp-2026 without executive clearance",
    )
    assert alert_entry.severity == "CRITICAL"

