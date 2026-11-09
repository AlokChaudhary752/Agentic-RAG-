"""LangGraph stateful workflow definition and compiler for Enterprise Knowledge Agent."""

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.agent.memory import ConversationMemoryManager
from app.agent.nodes import AgentNodeExecutor
from app.agent.state import AgentState
from app.core.logging import get_logger

logger = get_logger(__name__)


def route_after_planning(state: AgentState) -> Literal["respond", "retrieve"]:
    """Route directly to respond for chit-chat, otherwise proceed to knowledge retrieval."""
    if state.get("intent") in {"chit_chat", "out_of_scope"}:
        return "respond"
    return "retrieve"


def route_after_grading(state: AgentState) -> Literal["retrieve", "resolve_conflicts"]:
    """Reflective loop: re-retrieve with reformulated query if evidence is weak and budget remains."""
    grade = state.get("evidence_grade", "relevant")
    current_iter = state.get("retrieval_iteration", 1)
    max_iter = state.get("max_retrieval_iterations", 2)

    if grade in {"ambiguous", "irrelevant"} and current_iter < max_iter:
        logger.info("Self-RAG loop: evidence insufficient, re-retrieving", iteration=current_iter)
        return "retrieve"
    return "resolve_conflicts"


def route_after_action_decision(state: AgentState) -> Literal["human_approval", "respond"]:
    """Route to human approval checkpoint if high-risk action requires confirmation."""
    if state.get("tool_request") and state.get("approval_required"):
        return "human_approval"
    return "respond"


def create_agent_graph(
    executor: AgentNodeExecutor | None = None,
    checkpointer: Any | None = None,
    interrupt_on_approval: bool = False,
) -> Any:
    """Build and compile the multi-step stateful LangGraph agent with checkpointing."""
    node_executor = executor or AgentNodeExecutor()
    workflow = StateGraph(AgentState)

    # 1. Add all graph nodes
    workflow.add_node("understand", node_executor.understand)
    workflow.add_node("rewrite_and_plan", node_executor.rewrite_and_plan)
    workflow.add_node("retrieve", node_executor.retrieve)
    workflow.add_node("grade_evidence", node_executor.grade_evidence)
    workflow.add_node("resolve_conflicts", node_executor.resolve_conflicts)
    workflow.add_node("generate", node_executor.generate)
    workflow.add_node("verify", node_executor.verify)
    workflow.add_node("decide_action", node_executor.decide_action)
    workflow.add_node("human_approval", node_executor.human_approval)
    workflow.add_node("respond", node_executor.respond)

    # 2. Add edges and conditional branches
    workflow.add_edge(START, "understand")
    workflow.add_edge("understand", "rewrite_and_plan")

    workflow.add_conditional_edges(
        "rewrite_and_plan",
        route_after_planning,
        {"respond": "respond", "retrieve": "retrieve"},
    )

    workflow.add_edge("retrieve", "grade_evidence")

    workflow.add_conditional_edges(
        "grade_evidence",
        route_after_grading,
        {"retrieve": "retrieve", "resolve_conflicts": "resolve_conflicts"},
    )

    workflow.add_edge("resolve_conflicts", "generate")
    workflow.add_edge("generate", "verify")
    workflow.add_edge("verify", "decide_action")

    workflow.add_conditional_edges(
        "decide_action",
        route_after_action_decision,
        {"human_approval": "human_approval", "respond": "respond"},
    )

    workflow.add_edge("human_approval", "respond")
    workflow.add_edge("respond", END)

    interrupt_nodes = ["human_approval"] if interrupt_on_approval else []

    memory_saver = checkpointer or ConversationMemoryManager().get_checkpointer()
    return workflow.compile(
        checkpointer=memory_saver,
        interrupt_before=interrupt_nodes,
    )


_shared_graph: Any | None = None


def get_agent_graph(
    executor: AgentNodeExecutor | None = None,
    checkpointer: Any | None = None,
) -> Any:
    """Get or lazily initialize the shared compiled agent graph with indexed corpus."""
    global _shared_graph
    if _shared_graph is None or executor is not None:
        exec_instance = executor or AgentNodeExecutor()
        exec_instance.ensure_corpus_indexed()
        _shared_graph = create_agent_graph(
            executor=exec_instance,
            checkpointer=checkpointer,
        )
    return _shared_graph

