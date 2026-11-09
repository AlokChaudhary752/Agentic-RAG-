"""Chat completions endpoint with streaming and stateful multi-step agent orchestration."""

import asyncio
import json
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.graph import get_agent_graph
from app.agent.state import AgentState
from app.core.cost_tracker import get_cost_tracker
from app.core.rate_limit import verify_rate_limit
from app.core.telemetry import AGENT_QUERY_COUNT, AGENT_REASONING_LATENCY
from app.domain.models import UserPrincipal

router = APIRouter(prefix="/chat", tags=["Chat & Agent"])


class ChatRequest(BaseModel):
    """User conversation request payload."""

    query: str = Field(..., description="Employee question or action command")
    thread_id: str | None = Field(default=None, description="Conversation session ID")
    stream: bool = Field(default=False, description="Whether to stream execution via SSE")
    approval_granted: bool | None = Field(
        default=None, description="User decision for pending tool action approval"
    )


class CitationPayload(BaseModel):
    """Inline citation referencing exact document section."""

    doc_id: str
    title: str
    section_path: str = ""
    source: str = "knowledge_base"
    source_url: str = ""


class ChatResponse(BaseModel):
    """Structured response payload returned by Enterprise Knowledge Agent."""

    query: str
    answer: str
    citations: list[CitationPayload] = Field(default_factory=list)
    confidence: float = 0.95
    conflict_notices: list[str] = Field(default_factory=list)
    steps_executed: list[str] = Field(default_factory=list)
    approval_required: bool = False
    thread_id: str


@router.post("/completions", response_model=ChatResponse)
async def chat_completions(
    req: ChatRequest,
    principal: Annotated[UserPrincipal, Depends(verify_rate_limit)],
    request: Request,
    response: Response,
) -> Any:
    """Execute stateful agent pipeline over authorized knowledge base with rate limiting and telemetry."""
    start_time = time.perf_counter()
    thread_id = req.thread_id or str(uuid.uuid4())
    graph: Any = get_agent_graph()

    # Apply rate limit headers to response
    rl_headers = getattr(request.state, "rate_limit_headers", {})
    for k, v in rl_headers.items():
        response.headers[k] = v

    initial_state: AgentState = {
        "messages": [{"role": "user", "content": req.query}],
        "principal": principal,
        "thread_id": thread_id,
        "tenant_id": principal.tenant_id,
        "query": req.query,
        "steps_executed": [],
        "approval_granted": req.approval_granted,
    }

    config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

    if req.stream:

        async def event_generator() -> AsyncGenerator[str, None]:
            stream_iter: Any = graph.stream(initial_state, config=config, stream_mode="updates")
            for event in stream_iter:
                for node_name, output in event.items():
                    data = {
                        "event": "step",
                        "node": node_name,
                        "steps": output.get("steps_executed", [node_name]),
                    }
                    if "draft_answer" in output:
                        data["draft_answer"] = output["draft_answer"]
                    if "final_response" in output:
                        data["final_response"] = output["final_response"]
                        data["citations"] = output.get("citations", [])
                    yield f"data: {json.dumps(data)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers=rl_headers,
        )

    # Execute graph off the event loop thread to prevent event loop blocking
    final_state: dict[str, Any] = dict(
        await asyncio.to_thread(graph.invoke, initial_state, config=config)
    )

    elapsed_seconds = time.perf_counter() - start_time
    intent = final_state.get("intent", "factual_lookup")
    status_label = "success" if final_state.get("final_response") else "error"

    # Record Prometheus metrics
    AGENT_QUERY_COUNT.labels(
        tenant_id=principal.tenant_id,
        intent=intent,
        status=status_label,
    ).inc()
    AGENT_REASONING_LATENCY.labels(intent=intent).observe(elapsed_seconds)

    # Track token usage & cost
    cost_tracker = get_cost_tracker()
    estimated_prompt_tokens = max(10, len(req.query.split()) * 2)
    estimated_completion_tokens = max(15, len(final_state.get("final_response", "").split()) * 2)
    cost_tracker.track_usage(
        tenant_id=principal.tenant_id,
        model=cost_tracker.route_model("synthesis"),
        prompt_tokens=estimated_prompt_tokens,
        completion_tokens=estimated_completion_tokens,
    )

    citations = [
        CitationPayload(
            doc_id=c.get("doc_id", "unknown"),
            title=c.get("title", "Document"),
            section_path=c.get("section_path", ""),
            source=c.get("source", "knowledge_base"),
            source_url=c.get("source_url", ""),
        )
        for c in final_state.get("citations", [])
    ]

    return ChatResponse(
        query=req.query,
        answer=final_state.get("final_response", ""),
        citations=citations,
        confidence=final_state.get("confidence", 0.9),
        conflict_notices=final_state.get("conflict_notices", []),
        steps_executed=final_state.get("steps_executed", []),
        approval_required=final_state.get("approval_required", False),
        thread_id=thread_id,
    )
