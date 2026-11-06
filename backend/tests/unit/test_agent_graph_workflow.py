"""Unit tests for compiled LangGraph agent workflow execution."""

import uuid

import pytest

from app.agent.graph import create_agent_graph
from app.agent.nodes import AgentNodeExecutor
from app.agent.state import AgentState
from app.domain.models import ClassificationLevel, DocumentACL, DocumentChunk, UserPrincipal
from app.retrieval.hybrid_search import RetrievalBundle, RetrievalMetadata


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


class MockRetriever:
    """Mock retriever returning deterministic candidate chunks."""

    def retrieve(self, query: str, principal: UserPrincipal) -> RetrievalBundle:
        chunk = DocumentChunk(
            id=str(uuid.uuid4()),
            doc_id="hr-policy-vacation",
            chunk_index=1,
            title="Annual Vacation Policy",
            section_path="HR > Benefits > Leaves",
            content="Employees at Nimbus Technologies receive 25 days of annual paid vacation.",
            authority_score=0.9,
            source="local_folder",
            acl=DocumentACL(
                allowed_groups=["group_engineering"],
                classification_level=ClassificationLevel.INTERNAL,
            ),
        )
        return RetrievalBundle(
            chunks=[chunk],
            metadata=RetrievalMetadata(
                strategy="hybrid",
                original_query=query,
                rewritten_query=query,
                latency_ms=10.0,
            ),
        )


@pytest.mark.unit
def test_agent_graph_factual_lookup(test_principal: UserPrincipal) -> None:
    """Verify end-to-end execution of factual question through all stateful graph nodes."""
    executor = AgentNodeExecutor(retriever=MockRetriever())  # type: ignore[arg-type]
    graph = create_agent_graph(executor=executor)

    thread_id = str(uuid.uuid4())
    input_state: AgentState = {
        "messages": [{"role": "user", "content": "How many days of annual vacation do employees get?"}],
        "principal": test_principal,
        "thread_id": thread_id,
        "tenant_id": test_principal.tenant_id,
        "query": "How many days of annual vacation do employees get?",
        "steps_executed": [],
    }

    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(input_state, config=config)

    assert "understand" in result["steps_executed"]
    assert "rewrite_and_plan" in result["steps_executed"]
    assert "retrieve" in result["steps_executed"]
    assert "grade_evidence" in result["steps_executed"]
    assert "resolve_conflicts" in result["steps_executed"]
    assert "generate" in result["steps_executed"]
    assert "verify" in result["steps_executed"]
    assert "respond" in result["steps_executed"]

    assert "25 days" in result["final_response"]
    assert len(result["citations"]) >= 1
    assert result["citations"][0]["title"] == "Annual Vacation Policy"
    assert result["confidence"] >= 0.8


@pytest.mark.unit
def test_agent_graph_chit_chat_shortcut(test_principal: UserPrincipal) -> None:
    """Verify chit-chat routes directly to respond, skipping retrieval."""
    executor = AgentNodeExecutor(retriever=MockRetriever())  # type: ignore[arg-type]
    graph = create_agent_graph(executor=executor)

    thread_id = str(uuid.uuid4())
    input_state: AgentState = {
        "messages": [{"role": "user", "content": "Hello!"}],
        "principal": test_principal,
        "thread_id": thread_id,
        "tenant_id": test_principal.tenant_id,
        "query": "Hello!",
        "steps_executed": [],
    }

    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(input_state, config=config)

    assert "understand" in result["steps_executed"]
    assert "rewrite_and_plan" in result["steps_executed"]
    assert "retrieve" not in result["steps_executed"], "Retrieval should be skipped for chit-chat"
    assert "respond" in result["steps_executed"]
    assert "Enterprise Knowledge Agent" in result["final_response"]


@pytest.mark.unit
def test_agent_graph_action_approval_workflow(test_principal: UserPrincipal) -> None:
    """Verify tool action request routes through approval node."""
    executor = AgentNodeExecutor(retriever=MockRetriever())  # type: ignore[arg-type]
    graph = create_agent_graph(executor=executor)

    thread_id = str(uuid.uuid4())
    input_state: AgentState = {
        "messages": [{"role": "user", "content": "Create a Jira ticket for the payment outage"}],
        "principal": test_principal,
        "thread_id": thread_id,
        "tenant_id": test_principal.tenant_id,
        "query": "Create a Jira ticket for the payment outage",
        "approval_granted": True,
        "steps_executed": [],
    }

    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(input_state, config=config)

    assert "decide_action" in result["steps_executed"]
    assert "human_approval" in result["steps_executed"]
    assert "create_jira_ticket" in result["final_response"]
