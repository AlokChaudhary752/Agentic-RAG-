"""Unit tests for Enterprise MCPClient governance, schema validation, and risk gating."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.models import (
    ClassificationLevel,
    DocStatus,
    DocumentACL,
    RawDocument,
    UserPrincipal,
)
from app.tools.client import MCPClient
from app.tools.schemas import ToolRiskLevel
from app.tools.server import EnterpriseMCPServer


@pytest.fixture
def principal_alice() -> UserPrincipal:
    return UserPrincipal(
        user_id="emp_alice",
        email="alice@nimbus.com",
        full_name="Alice Smith",
        roles=["employee"],
        groups=["group_engineering"],
        clearance=ClassificationLevel.INTERNAL,
        tenant_id="tenant-nimbus-default",
    )


@pytest.fixture
def principal_frank() -> UserPrincipal:
    return UserPrincipal(
        user_id="exec_frank",
        email="frank@nimbus.com",
        full_name="Frank Vance",
        roles=["executive"],
        groups=["group_executives", "group_managers", "group_engineering"],
        clearance=ClassificationLevel.RESTRICTED,
        tenant_id="tenant-nimbus-default",
    )


@pytest.fixture
def configured_server() -> EnterpriseMCPServer:
    server = EnterpriseMCPServer()
    server.register_document(
        RawDocument(
            id="vpn-guidelines",
            source="local_folder",
            source_url="file:///docs/it/vpn.md",
            title="Corporate VPN Guidelines",
            content="Use WireGuard or OpenVPN client with hardware token.",
            author="IT Security",
            owner_group="group_engineering",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            version="1.0",
            doc_status=DocStatus.APPROVED,
            authority_score=0.9,
            acl=DocumentACL(
                allowed_users=[],
                allowed_groups=["group_engineering"],
                classification_level=ClassificationLevel.INTERNAL,
            ),
        )
    )
    return server


def test_mcp_client_tool_risk_classification() -> None:
    client = MCPClient()
    assert client.get_tool_risk("search_knowledge") == ToolRiskLevel.READ
    assert client.get_tool_risk("get_document") == ToolRiskLevel.READ
    assert client.get_tool_risk("get_ticket_status") == ToolRiskLevel.READ
    assert client.get_tool_risk("list_recent_changes") == ToolRiskLevel.READ
    assert client.get_tool_risk("send_summary_email") == ToolRiskLevel.WRITE_LOW
    assert client.get_tool_risk("create_jira_ticket") == ToolRiskLevel.WRITE_HIGH


def test_mcp_client_allow_list_blocking(
    configured_server: EnterpriseMCPServer, principal_alice: UserPrincipal
) -> None:
    # Restrict allow-list to only read tools
    client = MCPClient(
        server=configured_server,
        allowed_tools={"search_knowledge", "get_document"},
    )

    # Attempting to execute create_jira_ticket should be blocked immediately
    result = client.execute_sync(
        tool_name="create_jira_ticket",
        arguments={"summary": "Test summary", "project": "NIMBUS", "description": "Valid description length"},
        principal=principal_alice,
        approval_granted=True,
    )
    assert not result.success
    assert "not in the allowed tools list" in (result.error or "")


def test_mcp_client_schema_validation_failure(
    configured_server: EnterpriseMCPServer, principal_alice: UserPrincipal
) -> None:
    client = MCPClient(server=configured_server)

    # Invalid summary: too short (< 5 chars)
    result = client.execute_sync(
        tool_name="create_jira_ticket",
        arguments={"summary": "Bad", "description": "This is a valid long description"},
        principal=principal_alice,
        approval_granted=True,
    )
    assert not result.success
    assert "validation error" in (result.error or "").lower()


def test_mcp_client_human_approval_gate_for_write_high(
    configured_server: EnterpriseMCPServer, principal_alice: UserPrincipal
) -> None:
    client = MCPClient(server=configured_server)

    # 1. High risk tool without approval -> Execution blocked
    blocked = client.execute_sync(
        tool_name="create_jira_ticket",
        arguments={
            "summary": "Deploy cluster autoscaler",
            "project": "ENG",
            "description": "Configure HPA and cluster autoscaler for staging.",
        },
        principal=principal_alice,
        approval_granted=False,
    )
    assert not blocked.success
    assert blocked.risk_level == ToolRiskLevel.WRITE_HIGH
    assert "requires human approval" in (blocked.error or "").lower()
    assert (blocked.data or {}).get("approval_required") is True

    # 2. High risk tool with approval granted -> Execution succeeds
    approved = client.execute_sync(
        tool_name="create_jira_ticket",
        arguments={
            "summary": "Deploy cluster autoscaler",
            "project": "ENG",
            "description": "Configure HPA and cluster autoscaler for staging.",
        },
        principal=principal_alice,
        approval_granted=True,
    )
    assert approved.success
    assert approved.data is not None
    assert approved.data["project"] == "ENG"
    assert approved.data["reporter"] == "emp_alice"


def test_mcp_client_auto_executes_write_low(
    configured_server: EnterpriseMCPServer, principal_alice: UserPrincipal
) -> None:
    client = MCPClient(server=configured_server)

    # Low-risk write tool should execute without prior human-in-the-loop gate
    res = client.execute_sync(
        tool_name="send_summary_email",
        arguments={
            "recipient_email": "bob@nimbus.com",
            "subject": "Weekly Knowledge Digest",
            "body": "Here is the RAG synthesis report for the engineering team.",
        },
        principal=principal_alice,
        approval_granted=False,
    )
    assert res.success
    assert res.data is not None
    assert res.data["recipient"] == "bob@nimbus.com"
    assert res.data["status"] == "sent"


def test_mcp_client_idempotency_cache(
    configured_server: EnterpriseMCPServer, principal_alice: UserPrincipal
) -> None:
    client = MCPClient(server=configured_server)

    key = "idem-ticket-uniq-999"
    args = {
        "summary": "Fix flaky integration test",
        "project": "NIMBUS",
        "description": "Address race condition in hybrid search tests.",
        "idempotency_key": key,
    }

    first_call = client.execute_sync(
        tool_name="create_jira_ticket",
        arguments=args,
        principal=principal_alice,
        approval_granted=True,
    )
    assert first_call.success
    first_ticket_id = (first_call.data or {})["ticket_id"]

    # Replay with same idempotency key: should hit client cache
    second_call = client.execute_sync(
        tool_name="create_jira_ticket",
        arguments=args,
        principal=principal_alice,
        approval_granted=True,
    )
    assert second_call.success
    assert (second_call.data or {})["ticket_id"] == first_ticket_id


@pytest.mark.asyncio
async def test_mcp_client_async_execution_and_audit_logging(
    configured_server: EnterpriseMCPServer, principal_alice: UserPrincipal
) -> None:
    mock_audit = MagicMock()
    mock_audit.record_tool_call = AsyncMock()

    client = MCPClient(
        server=configured_server,
        audit_service=mock_audit,
    )

    result = await client.execute(
        tool_name="send_summary_email",
        arguments={
            "recipient_email": "carol@nimbus.com",
            "subject": "Benefits Notice",
            "body": "Updated health insurance policy document is now available.",
        },
        principal=principal_alice,
        approval_granted=True,
        correlation_id="corr-mcp-test-1",
    )

    assert result.success
    assert mock_audit.record_tool_call.called
    call_kwargs = mock_audit.record_tool_call.call_args.kwargs
    assert call_kwargs["tool_name"] == "send_summary_email"
    assert call_kwargs["correlation_id"] == "corr-mcp-test-1"

