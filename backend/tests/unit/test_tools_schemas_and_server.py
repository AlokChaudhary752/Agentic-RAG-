"""Unit tests for MCP tool schemas, server stores, and permission-checked tool implementations."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.domain.models import (
    ClassificationLevel,
    DocStatus,
    DocumentACL,
    RawDocument,
    UserPrincipal,
)
from app.tools.schemas import (
    CreateJiraTicketInput,
    GetDocumentInput,
    SearchKnowledgeInput,
    SendSummaryEmailInput,
)
from app.tools.server import (
    EnterpriseMCPServer,
    InMemoryEmailStore,
    InMemoryJiraStore,
)


@pytest.fixture
def sample_principals() -> dict[str, UserPrincipal]:
    """Provide realistic enterprise principals across different clearance levels."""
    return {
        "alice": UserPrincipal(
            user_id="emp_alice",
            email="alice@nimbus.com",
            full_name="Alice Smith",
            roles=["employee"],
            groups=["group_engineering"],
            clearance=ClassificationLevel.INTERNAL,
            tenant_id="tenant-nimbus-default",
        ),
        "bob": UserPrincipal(
            user_id="mgr_bob",
            email="bob@nimbus.com",
            full_name="Bob Jones",
            roles=["manager"],
            groups=["group_engineering", "group_managers"],
            clearance=ClassificationLevel.CONFIDENTIAL,
            tenant_id="tenant-nimbus-default",
        ),
        "frank": UserPrincipal(
            user_id="exec_frank",
            email="frank@nimbus.com",
            full_name="Frank Vance",
            roles=["executive"],
            groups=["group_executives", "group_managers", "group_engineering"],
            clearance=ClassificationLevel.RESTRICTED,
            tenant_id="tenant-nimbus-default",
        ),
    }


@pytest.fixture
def sample_server() -> EnterpriseMCPServer:
    """Provide a configured EnterpriseMCPServer with registered test documents."""
    server = EnterpriseMCPServer()

    # Register an INTERNAL document open to engineering
    server.register_document(
        RawDocument(
            id="eng-coding-standards",
            source="local_folder",
            source_url="file:///docs/engineering/standards.md",
            title="Nimbus Engineering Coding Standards",
            content="Standard style guide: Python 3.11+, typed, strict ruff and mypy.",
            author="Architecture Board",
            owner_group="group_engineering",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            version="2.0",
            doc_status=DocStatus.APPROVED,
            authority_score=0.95,
            acl=DocumentACL(
                allowed_users=[],
                allowed_groups=["group_engineering"],
                classification_level=ClassificationLevel.INTERNAL,
            ),
        )
    )

    # Register a RESTRICTED document limited to executive committee
    server.register_document(
        RawDocument(
            id="exec-compensation-2026",
            source="local_folder",
            source_url="file:///docs/finance/exec_comp.md",
            title="Executive Compensation and Equity Allocations 2026",
            content="Highly confidential: Executive bonus targets and equity tranches.",
            author="Compensation Committee",
            owner_group="group_executives",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            version="1.0",
            doc_status=DocStatus.APPROVED,
            authority_score=0.99,
            acl=DocumentACL(
                allowed_users=["exec_frank"],
                allowed_groups=["group_executives"],
                classification_level=ClassificationLevel.RESTRICTED,
            ),
        )
    )

    return server


# =============================================================================
# SCHEMA TESTS
# =============================================================================


def test_schema_search_knowledge_validation() -> None:
    valid = SearchKnowledgeInput(query="What is the travel policy?", top_k=10)
    assert valid.query == "What is the travel policy?"
    assert valid.top_k == 10

    with pytest.raises(ValidationError):
        SearchKnowledgeInput(query="test", top_k=50)  # ge=1, le=20


def test_schema_get_document_validation() -> None:
    valid = GetDocumentInput(doc_id="fin-eng-salary-bands-2026")
    assert valid.doc_id == "fin-eng-salary-bands-2026"

    with pytest.raises(ValidationError):
        GetDocumentInput()  # type: ignore[call-arg]


def test_schema_create_jira_ticket_validation() -> None:
    valid = CreateJiraTicketInput(
        project="NIMBUS",
        summary="Fix auth token leak in logging",
        description="Detailed description with more than 10 characters.",
        priority="High",
        idempotency_key="req-12345",
    )
    assert valid.project == "NIMBUS"
    assert valid.priority == "High"
    assert valid.idempotency_key == "req-12345"

    with pytest.raises(ValidationError):
        # Summary too short (< 5 chars)
        CreateJiraTicketInput(summary="Fix", description="Some long description goes here.")


def test_schema_send_summary_email_validation() -> None:
    valid = SendSummaryEmailInput(
        recipient_email="alice@nimbus.com",
        subject="Weekly RAG Update",
        body="Here is the summarized knowledge report from the platform.",
    )
    assert valid.recipient_email == "alice@nimbus.com"

    with pytest.raises(ValidationError):
        SendSummaryEmailInput(recipient_email="alice@nimbus.com", subject="Hi", body="short")


# =============================================================================
# IN-MEMORY STORES TESTS
# =============================================================================


def test_jira_store_retrieval_and_idempotency() -> None:
    store = InMemoryJiraStore()

    # Pre-seeded ticket check
    ticket = store.get_ticket("NIMBUS-1001")
    assert ticket is not None
    assert ticket["summary"] == "Kubernetes cluster upgrade to 1.30"
    assert ticket["status"] == "In Progress"

    # Non-existent ticket
    assert store.get_ticket("NONEXISTENT-9999") is None

    # Create ticket
    created = store.create_ticket(
        summary="Automate vulnerability scanning",
        project="SEC",
        description="Integrate Trivy in CI pipeline.",
        priority="High",
        reporter="emp_alice",
        idempotency_key="sec-scan-001",
    )
    assert created.ticket_id.startswith("SEC-")
    assert created.reporter == "emp_alice"
    assert created.status == "Open"

    # Idempotency replay check: must return the exact same ticket
    replay = store.create_ticket(
        summary="Automate vulnerability scanning",
        project="SEC",
        description="Integrate Trivy in CI pipeline.",
        reporter="emp_alice",
        idempotency_key="sec-scan-001",
    )
    assert replay.ticket_id == created.ticket_id
    assert replay.created_at == created.created_at


def test_email_store_dispatch_and_idempotency() -> None:
    store = InMemoryEmailStore()

    receipt = store.send_email(
        recipient_email="bob@nimbus.com",
        subject="Security Advisory",
        body="Please review updated authentication standards.",
        idempotency_key="advisory-001",
    )
    assert receipt.recipient == "bob@nimbus.com"
    assert receipt.status == "sent"
    assert len(store.deliveries) == 1

    # Idempotent replay
    replay = store.send_email(
        recipient_email="bob@nimbus.com",
        subject="Security Advisory",
        body="Please review updated authentication standards.",
        idempotency_key="advisory-001",
    )
    assert replay.delivery_id == receipt.delivery_id
    assert len(store.deliveries) == 1


# =============================================================================
# SERVER PERMISSION & TOOL TESTS
# =============================================================================


def test_get_document_permission_enforcement(
    sample_server: EnterpriseMCPServer, sample_principals: dict[str, UserPrincipal]
) -> None:
    alice = sample_principals["alice"]
    frank = sample_principals["frank"]

    # 1. Alice accessing INTERNAL engineering doc -> Allowed
    doc_eng = sample_server.get_document("eng-coding-standards", principal=alice)
    assert doc_eng.doc_id == "eng-coding-standards"
    assert doc_eng.classification_level == "INTERNAL"

    # 2. Alice accessing RESTRICTED executive doc -> FORBIDDEN
    with pytest.raises(ForbiddenError) as exc_info:
        sample_server.get_document("exec-compensation-2026", principal=alice)
    assert "not authorized" in str(exc_info.value).lower()

    # 3. Frank accessing RESTRICTED executive doc -> Allowed
    doc_exec = sample_server.get_document("exec-compensation-2026", principal=frank)
    assert doc_exec.doc_id == "exec-compensation-2026"
    assert doc_exec.classification_level == "RESTRICTED"

    # 4. Unknown document -> NotFoundError
    with pytest.raises(NotFoundError):
        sample_server.get_document("does-not-exist", principal=frank)

    # 5. Missing principal -> UnauthorizedError
    with pytest.raises(UnauthorizedError):
        sample_server.get_document("eng-coding-standards", principal=None)


def test_list_recent_changes_permission_filtering(
    sample_server: EnterpriseMCPServer, sample_principals: dict[str, UserPrincipal]
) -> None:
    alice = sample_principals["alice"]
    frank = sample_principals["frank"]

    # Alice should only see authorized docs (eng-coding-standards, NOT exec-compensation-2026)
    alice_changes = sample_server.list_recent_changes(days_back=30, limit=10, principal=alice)
    alice_doc_ids = {d["doc_id"] for d in alice_changes.documents}
    assert "eng-coding-standards" in alice_doc_ids
    assert "exec-compensation-2026" not in alice_doc_ids

    # Frank has RESTRICTED clearance and group_executives -> sees exec-compensation-2026
    frank_changes = sample_server.list_recent_changes(days_back=30, limit=10, principal=frank)
    frank_doc_ids = {d["doc_id"] for d in frank_changes.documents}
    assert "exec-compensation-2026" in frank_doc_ids


def test_create_jira_ticket_and_status(
    sample_server: EnterpriseMCPServer, sample_principals: dict[str, UserPrincipal]
) -> None:
    bob = sample_principals["bob"]

    created = sample_server.create_jira_ticket(
        summary="Implement telemetry exporter",
        project="NIMBUS",
        description="Send OpenTelemetry traces to collector endpoint.",
        priority="High",
        principal=bob,
        idempotency_key="telemetry-task-01",
    )
    assert created.reporter == "mgr_bob"
    assert created.project == "NIMBUS"
    assert "https://jira.corp.internal/browse/" in created.url

    # Check status of created ticket
    status_info = sample_server.get_ticket_status(created.ticket_id, principal=bob)
    assert status_info.ticket_id == created.ticket_id
    assert status_info.status == "Open"
    assert status_info.priority == "High"


def test_send_summary_email(
    sample_server: EnterpriseMCPServer, sample_principals: dict[str, UserPrincipal]
) -> None:
    bob = sample_principals["bob"]

    result = sample_server.send_summary_email(
        recipient_email="alice@nimbus.com",
        subject="Architecture Decision Record",
        body="ADR-0004 for MCP tools has been approved.",
        principal=bob,
    )
    assert result.recipient == "alice@nimbus.com"
    assert result.status == "sent"


def test_server_call_tool_sync_unified(
    sample_server: EnterpriseMCPServer, sample_principals: dict[str, UserPrincipal]
) -> None:
    alice = sample_principals["alice"]

    result = sample_server.call_tool_sync(
        tool_name="get_ticket_status",
        arguments={"ticket_id": "NIMBUS-1042"},
        principal=alice,
    )
    assert result["ticket_id"] == "NIMBUS-1042"
    assert result["priority"] == "Highest"


@pytest.mark.asyncio
async def test_server_call_tool_async_unified(
    sample_server: EnterpriseMCPServer, sample_principals: dict[str, UserPrincipal]
) -> None:
    bob = sample_principals["bob"]

    result = await sample_server.call_tool(
        tool_name="create_jira_ticket",
        arguments={
            "summary": "Async ticket creation test",
            "project": "ENG",
            "description": "Validating async MCP handler dispatch.",
        },
        principal=bob,
    )
    assert result["project"] == "ENG"
    assert result["reporter"] == "mgr_bob"

