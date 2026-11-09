"""Integration tests for Agent orchestration with Model Context Protocol (MCP) tool execution."""

import pytest
from httpx import AsyncClient

from app.agent.graph import create_agent_graph
from app.agent.nodes import AgentNodeExecutor
from app.agent.state import AgentState
from app.core.security import create_access_token
from app.domain.models import ClassificationLevel, UserPrincipal
from app.tools.client import MCPClient
from app.tools.server import EnterpriseMCPServer


@pytest.fixture
def principal_bob() -> UserPrincipal:
    return UserPrincipal(
        user_id="mgr_bob",
        email="bob@nimbus.com",
        full_name="Bob Jones",
        roles=["manager"],
        groups=["group_engineering", "group_managers"],
        clearance=ClassificationLevel.CONFIDENTIAL,
        tenant_id="tenant-nimbus-default",
    )


@pytest.fixture
def executor_with_tools() -> AgentNodeExecutor:
    server = EnterpriseMCPServer()
    client = MCPClient(server=server)
    return AgentNodeExecutor(mcp_client=client)


def test_agent_graph_get_ticket_status_workflow(
    executor_with_tools: AgentNodeExecutor, principal_bob: UserPrincipal
) -> None:
    """Validate end-to-end ticket status query through LangGraph agent and MCP."""
    graph = create_agent_graph(executor=executor_with_tools)

    state: AgentState = {
        "messages": [{"role": "user", "content": "Check status of ticket NIMBUS-1001"}],
        "principal": principal_bob,
        "query": "Check status of ticket NIMBUS-1001",
        "thread_id": "thread-status-001",
        "tenant_id": principal_bob.tenant_id,
        "steps_executed": [],
    }

    result = graph.invoke(state, config={"configurable": {"thread_id": "thread-status-001"}})

    assert "decide_action" in result["steps_executed"]
    assert "respond" in result["steps_executed"]
    assert result.get("tool_result") is not None
    assert result["tool_result"]["success"] is True

    answer = result["final_response"]
    assert "NIMBUS-1001" in answer
    assert "In Progress" in answer


def test_agent_graph_create_jira_ticket_with_approval(
    executor_with_tools: AgentNodeExecutor, principal_bob: UserPrincipal
) -> None:
    """Validate high-risk Jira creation requiring and executing upon human approval."""
    graph = create_agent_graph(executor=executor_with_tools)

    # 1. First invocation without approval: approval_required should be True
    state_pending: AgentState = {
        "messages": [
            {"role": "user", "content": "Create a Jira ticket to patch OpenSSL vulnerability"}
        ],
        "principal": principal_bob,
        "query": "Create a Jira ticket to patch OpenSSL vulnerability",
        "thread_id": "thread-create-jira-001",
        "tenant_id": principal_bob.tenant_id,
        "steps_executed": [],
        "approval_granted": None,
    }

    result_pending = graph.invoke(
        state_pending, config={"configurable": {"thread_id": "thread-create-jira-001"}}
    )

    assert result_pending.get("approval_required") is True
    assert result_pending.get("tool_risk_level") == "write_high"

    # 2. Resumed invocation with human approval granted
    state_approved: AgentState = {
        **result_pending,
        "approval_granted": True,
        "steps_executed": [],
    }

    result_approved = graph.invoke(
        state_approved, config={"configurable": {"thread_id": "thread-create-jira-001"}}
    )

    assert result_approved.get("tool_result") is not None
    assert result_approved["tool_result"]["success"] is True
    assert "NIMBUS-" in result_approved["final_response"]
    assert "jira.corp.internal" in result_approved["final_response"]


def test_agent_graph_create_jira_ticket_rejection(
    executor_with_tools: AgentNodeExecutor, principal_bob: UserPrincipal
) -> None:
    """Validate user rejection stops tool execution and informs the user."""
    graph = create_agent_graph(executor=executor_with_tools)

    state_rejected: AgentState = {
        "messages": [
            {"role": "user", "content": "Create a Jira ticket to reboot production redis"}
        ],
        "principal": principal_bob,
        "query": "Create a Jira ticket to reboot production redis",
        "thread_id": "thread-reject-jira-001",
        "tenant_id": principal_bob.tenant_id,
        "steps_executed": [],
        "approval_granted": False,
    }

    result = graph.invoke(
        state_rejected, config={"configurable": {"thread_id": "thread-reject-jira-001"}}
    )

    assert result.get("tool_result") is not None
    assert result["tool_result"]["status"] == "rejected"
    assert (
        "denied" in result["final_response"].lower()
        or "rejected" in result["final_response"].lower()
    )


def test_agent_graph_send_summary_email_auto_executes(
    executor_with_tools: AgentNodeExecutor, principal_bob: UserPrincipal
) -> None:
    """Validate low-risk email tool auto-executes without requiring human approval."""
    graph = create_agent_graph(executor=executor_with_tools)

    state: AgentState = {
        "messages": [
            {"role": "user", "content": "Send email summary of the leave policy to manager"}
        ],
        "principal": principal_bob,
        "query": "Send email summary of the leave policy to manager",
        "thread_id": "thread-email-001",
        "tenant_id": principal_bob.tenant_id,
        "steps_executed": [],
    }

    result = graph.invoke(state, config={"configurable": {"thread_id": "thread-email-001"}})

    assert result.get("approval_required") is False
    assert result.get("tool_result") is not None
    assert result["tool_result"]["success"] is True
    assert "delivered to bob@nimbus.com" in result["final_response"]


@pytest.mark.asyncio
async def test_chat_completions_api_with_mcp_action(async_client: AsyncClient) -> None:
    """Validate full FastAPI HTTP chat completion pipeline dispatching MCP actions."""
    # Generate authentic JWT token for manager Bob
    token = create_access_token(
        data={
            "sub": "mgr_bob",
            "email": "bob@nimbus.com",
            "full_name": "Bob Jones",
            "roles": ["manager"],
            "groups": ["group_engineering", "group_managers"],
            "clearance": "CONFIDENTIAL",
            "tenant_id": "tenant-nimbus-default",
        }
    )

    headers = {"Authorization": f"Bearer {token}"}

    # Query ticket status via HTTP API
    response = await async_client.post(
        "/api/v1/chat/completions",
        json={"query": "What is the status of ticket NIMBUS-1001?"},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert "NIMBUS-1001" in payload["answer"]
    assert "In Progress" in payload["answer"]
