"""Unit tests for LangGraph node execution functions and state transitions."""


import pytest

from app.agent.nodes import AgentNodeExecutor
from app.agent.state import AgentState
from app.domain.models import ClassificationLevel, DocumentACL, DocumentChunk, UserPrincipal


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


@pytest.fixture
def node_executor() -> AgentNodeExecutor:
    return AgentNodeExecutor()


@pytest.mark.unit
def test_understand_node_classifications(
    node_executor: AgentNodeExecutor,
    test_principal: UserPrincipal,
) -> None:
    """Verify understand node classifies intents correctly."""
    # 1. Chit-chat
    state_chat: AgentState = {
        "query": "Hello there!",
        "principal": test_principal,
        "steps_executed": [],
    }
    out_chat = node_executor.understand(state_chat)
    assert out_chat["intent"] == "chit_chat"
    assert "understand" in out_chat["steps_executed"]

    # 2. Action request
    state_act: AgentState = {
        "query": "Please create a Jira ticket for the API bug",
        "principal": test_principal,
        "steps_executed": [],
    }
    out_act = node_executor.understand(state_act)
    assert out_act["intent"] == "action_request"

    # 3. Factual lookup
    state_fact: AgentState = {
        "query": "What is the policy for annual vacation leave?",
        "principal": test_principal,
        "steps_executed": [],
    }
    out_fact = node_executor.understand(state_fact)
    assert out_fact["intent"] == "factual_lookup"


@pytest.mark.unit
def test_rewrite_and_plan_node(
    node_executor: AgentNodeExecutor,
    test_principal: UserPrincipal,
) -> None:
    """Verify rewrite_and_plan formulates sub-queries or skips retrieval for chit-chat."""
    # Factual lookup
    state_fact: AgentState = {
        "query": "What are the PTO guidelines?",
        "intent": "factual_lookup",
        "principal": test_principal,
        "steps_executed": [],
    }
    res_fact = node_executor.rewrite_and_plan(state_fact)
    assert len(res_fact["sub_queries"]) >= 1
    assert res_fact["retrieval_strategy"] == "hybrid"

    # Chit-chat
    state_chat: AgentState = {
        "query": "Hi",
        "intent": "chit_chat",
        "principal": test_principal,
        "steps_executed": [],
    }
    res_chat = node_executor.rewrite_and_plan(state_chat)
    assert len(res_chat["sub_queries"]) == 0
    assert res_chat["retrieval_strategy"] == "none"


@pytest.mark.unit
def test_grade_evidence_and_reflection(
    node_executor: AgentNodeExecutor,
    test_principal: UserPrincipal,
) -> None:
    """Verify grading marks relevant evidence and triggers query reformulation when insufficient."""
    chunk = DocumentChunk(
        id="c1",
        doc_id="hr-pto",
        chunk_index=1,
        title="PTO Policy",
        content="Employees receive twenty-five days of paid annual vacation leave.",
        acl=DocumentACL(allowed_groups=["group_all"], classification_level=ClassificationLevel.INTERNAL),
    )

    # Relevant query
    state_rel: AgentState = {
        "query": "What is the annual vacation leave?",
        "retrieved_chunks": [chunk],
        "retrieval_iteration": 1,
        "max_retrieval_iterations": 2,
        "principal": test_principal,
        "steps_executed": [],
    }
    out_rel = node_executor.grade_evidence(state_rel)
    assert out_rel["evidence_grade"] == "relevant"
    assert out_rel["reformulated_query"] is None

    # Irrelevant query triggering reformulation
    state_irrel: AgentState = {
        "query": "How do I configure quantum kubernetes clusters?",
        "retrieved_chunks": [chunk],
        "retrieval_iteration": 1,
        "max_retrieval_iterations": 2,
        "principal": test_principal,
        "steps_executed": [],
    }
    out_irrel = node_executor.grade_evidence(state_irrel)
    assert out_irrel["evidence_grade"] in {"ambiguous", "irrelevant"}
    assert out_irrel["reformulated_query"] is not None


@pytest.mark.unit
def test_decide_action_and_human_approval(
    node_executor: AgentNodeExecutor,
    test_principal: UserPrincipal,
) -> None:
    """Verify decide_action flags high-risk tool calls for approval."""
    state_action: AgentState = {
        "query": "Create Jira ticket to reboot production servers",
        "intent": "action_request",
        "principal": test_principal,
        "steps_executed": [],
    }
    out_action = node_executor.decide_action(state_action)
    assert out_action["approval_required"] is True
    assert out_action["tool_risk_level"] == "write_high"
    assert out_action["tool_request"]["tool"] == "create_jira_ticket"

    # Human approval granted
    state_approved: AgentState = {
        **state_action,
        **out_action,
        "approval_granted": True,
    }
    out_app = node_executor.human_approval(state_approved)
    assert out_app["tool_result"]["status"] == "success"

    # Human approval denied
    state_denied: AgentState = {
        **state_action,
        **out_action,
        "approval_granted": False,
    }
    out_den = node_executor.human_approval(state_denied)
    assert out_den["tool_result"]["status"] == "rejected"
