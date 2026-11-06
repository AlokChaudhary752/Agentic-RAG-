# ADR 0002: Stateful Agent Orchestration with LangGraph

## Status
Accepted

## Date
2026-11-06

## Context
The Enterprise Knowledge Agent must execute a complex, non-linear reasoning workflow including:
1. Intent understanding and query decomposition.
2. Parallel sub-question retrieval.
3. Self-RAG evidence grading with conditional refinement loops.
4. Cross-document conflict resolution.
5. Claim-level verification before response delivery.
6. Human-in-the-loop approval interrupts for high-risk MCP tool execution (e.g. Jira ticket creation).
7. Streaming state updates to the UI.

## Decision
We adopt **LangGraph** as the state machine and agent orchestration framework. The agent state is explicitly modeled as a typed Pydantic structure with persistent checkpointing.

## Rationale
- **LangGraph**: Supports cyclical graphs (retrieval -> grading -> reformulation loop), explicit checkpointing (critical for human approval where an agent must pause for hours or days and resume without losing context), and fine-grained state inspection for observability.
- **Sequential Chains / AutoGen / CrewAI (Discarded)**: Sequential chains cannot model conditional cycles or human interrupt/resume cleanly. Higher-level multi-agent frameworks often obscure control flow, making deterministic security enforcement and claim verification difficult to audit and test.

## Consequences
### Positive
- Fully deterministic graph topology with auditable state transitions.
- Native interrupt and resume capabilities for tool approvals.
- Seamless OpenTelemetry and Langfuse tracing of every node step.

### Negative / Trade-offs
- More verbose code structure compared to simple prompting chains.

### Mitigations
- Define strict Pydantic models for `AgentState`, node inputs, and node outputs to maintain compile-time type safety.
