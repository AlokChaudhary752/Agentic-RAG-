"""State definition for LangGraph Enterprise Knowledge Agent."""

from typing import Annotated, Any, TypedDict

from pydantic import BaseModel, Field

from app.domain.models import DocumentChunk, UserPrincipal


def add_messages(existing: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reducer combining existing and new conversation messages."""
    return existing + new


def append_steps(existing: list[str], new: list[str]) -> list[str]:
    """Reducer tracking sequence of executed graph nodes."""
    return existing + new


class Citation(BaseModel):
    """Inline citation referencing a specific retrieved document chunk."""

    doc_id: str = Field(..., description="Document identifier")
    title: str = Field(..., description="Document title")
    section_path: str = Field(default="", description="Hierarchical section path")
    source: str = Field(default="knowledge_base", description="Connector origin")
    source_url: str = Field(default="", description="Link to source")


class AgentState(TypedDict, total=False):
    """Full state dict passed between nodes in the LangGraph workflow."""

    # Session & identity
    messages: Annotated[list[dict[str, Any]], add_messages]
    principal: UserPrincipal
    thread_id: str
    tenant_id: str
    correlation_id: str

    # Intent understanding & decomposition
    query: str
    intent: str  # factual_lookup, multi_hop, action_request, chit_chat, out_of_scope
    sub_queries: list[str]
    retrieval_strategy: str

    # Retrieval & Reflection (Self-RAG loop)
    retrieval_iteration: int
    max_retrieval_iterations: int
    retrieved_chunks: list[DocumentChunk]
    evidence_grade: str  # relevant, ambiguous, irrelevant
    reformulated_query: str | None

    # Governance & Conflict resolution
    resolved_chunks: list[DocumentChunk]
    conflict_notices: list[str]
    quarantined_chunks: list[str]

    # Generation & Faithfulness verification
    draft_answer: str
    faithfulness_score: float
    unsupported_claims: list[str]
    citations: list[dict[str, Any]]

    # Tool execution & Human-in-the-loop
    tool_request: dict[str, Any] | None
    tool_risk_level: str | None  # read, write_low, write_high
    approval_required: bool
    approval_granted: bool | None
    tool_result: dict[str, Any] | None

    # Final response & Telemetry
    final_response: str
    confidence: float
    follow_up_suggestions: list[str]
    steps_executed: Annotated[list[str], append_steps]
    token_usage: dict[str, int]

