"""LangGraph node execution functions for the Enterprise Knowledge Agent."""

from typing import Any

from app.agent.llm_client import LLMService
from app.agent.state import AgentState
from app.core.logging import get_logger
from app.governance.conflict_resolver import ConflictResolver
from app.governance.prompt_injection import PromptInjectionDefense
from app.retrieval.hybrid_search import HybridRetriever
from app.retrieval.query_transforms import QueryTransformer

logger = get_logger(__name__)


class AgentNodeExecutor:
    """Encapsulates node execution logic and dependencies for the multi-step agent graph."""

    def __init__(
        self,
        retriever: HybridRetriever | None = None,
        llm_service: LLMService | None = None,
        conflict_resolver: ConflictResolver | None = None,
        injection_defense: PromptInjectionDefense | None = None,
        query_transformer: QueryTransformer | None = None,
    ) -> None:
        self.retriever = retriever or HybridRetriever()
        self.llm = llm_service or LLMService()
        self.conflict_resolver = conflict_resolver or ConflictResolver()
        self.defense = injection_defense or PromptInjectionDefense()
        self.transformer = query_transformer or QueryTransformer()

    def understand(self, state: AgentState) -> dict[str, Any]:
        """Classify user query intent into factual_lookup, multi_hop, action_request, or chit_chat."""
        query = state.get("query") or (state.get("messages", [{}])[-1].get("content", ""))
        intent = self.llm.classify_intent(query)
        logger.info("Agent Node: understand", query=query, intent=intent)

        return {
            "query": query,
            "intent": intent,
            "steps_executed": ["understand"],
        }

    def rewrite_and_plan(self, state: AgentState) -> dict[str, Any]:
        """Formulate search queries, rewrite acronyms, and plan retrieval strategy."""
        query = state["query"]
        intent = state.get("intent", "factual_lookup")

        if intent in {"chit_chat", "out_of_scope"}:
            return {
                "sub_queries": [],
                "retrieval_strategy": "none",
                "retrieval_iteration": 0,
                "max_retrieval_iterations": 2,
                "steps_executed": ["rewrite_and_plan"],
            }

        rewritten = self.transformer.rewrite(query)
        sub_queries = [rewritten]
        if intent == "multi_hop":
            sub_queries = self.transformer.expand(query)

        return {
            "sub_queries": sub_queries,
            "retrieval_strategy": "hybrid",
            "retrieval_iteration": 0,
            "max_retrieval_iterations": 2,
            "steps_executed": ["rewrite_and_plan"],
        }

    def retrieve(self, state: AgentState) -> dict[str, Any]:
        """Execute hybrid retrieval with vector-level ACL pre-filtering and defense-in-depth."""
        search_query = state.get("reformulated_query") or state.get("sub_queries", [state["query"]])[0]
        principal = state["principal"]
        current_iter = state.get("retrieval_iteration", 0) + 1

        logger.info(
            "Agent Node: retrieve",
            search_query=search_query,
            iteration=current_iter,
            user_id=principal.user_id,
        )

        bundle = self.retriever.retrieve(query=search_query, principal=principal)

        return {
            "retrieved_chunks": bundle.chunks,
            "retrieval_iteration": current_iter,
            "steps_executed": ["retrieve"],
        }

    def grade_evidence(self, state: AgentState) -> dict[str, Any]:
        """Assess relevance of retrieved chunks (Self-RAG reflection loop)."""
        chunks = state.get("retrieved_chunks", [])
        query = state["query"]
        grade, score = self.llm.grade_evidence(query, chunks)

        reformulated = None
        current_iter = state.get("retrieval_iteration", 1)
        max_iter = state.get("max_retrieval_iterations", 2)

        if grade in {"ambiguous", "irrelevant"} and current_iter < max_iter:
            # Step back or reformulate query to find better evidence
            reformulated = self.transformer.step_back(query)
            logger.info("Agent reflection: reformulating query", new_query=reformulated)

        return {
            "evidence_grade": grade,
            "reformulated_query": reformulated,
            "steps_executed": ["grade_evidence"],
        }

    def resolve_conflicts(self, state: AgentState) -> dict[str, Any]:
        """Analyze cross-document contradictions and prioritize authoritative versions."""
        chunks = state.get("retrieved_chunks", [])
        conflict_res = self.conflict_resolver.resolve(chunks)

        # Sanitize and scan for prompt injections
        clean_chunks = [self.defense.scan_and_quarantine_chunk(c) for c in conflict_res.resolved_chunks]

        return {
            "resolved_chunks": clean_chunks,
            "conflict_notices": [n.message for n in conflict_res.notices],
            "steps_executed": ["resolve_conflicts"],
        }

    def generate(self, state: AgentState) -> dict[str, Any]:
        """Synthesize grounded answer with inline citations."""
        resolved = state.get("resolved_chunks", [])
        query = state["query"]
        notices = state.get("conflict_notices", [])

        draft_answer, citations, confidence = self.llm.generate_grounded_answer(
            query=query,
            chunks=resolved,
            conflict_notices=notices,
        )

        return {
            "draft_answer": draft_answer,
            "citations": citations,
            "confidence": confidence,
            "steps_executed": ["generate"],
        }

    def verify(self, state: AgentState) -> dict[str, Any]:
        """Verify claim-level faithfulness against retrieved context."""
        draft = state.get("draft_answer", "")
        chunks = state.get("resolved_chunks", [])
        v_result = self.llm.verify_faithfulness(draft, chunks)

        return {
            "faithfulness_score": v_result.faithfulness_score,
            "unsupported_claims": v_result.unsupported_claims,
            "steps_executed": ["verify"],
        }

    def decide_action(self, state: AgentState) -> dict[str, Any]:
        """Inspect intent and query to determine if MCP tool call is required."""
        intent = state.get("intent", "factual_lookup")
        query = state.get("query", "").lower()

        tool_request = None
        tool_risk_level = None
        approval_required = False

        if intent == "action_request":
            if "jira" in query or "ticket" in query:
                tool_request = {
                    "tool": "create_jira_ticket",
                    "arguments": {"summary": state["query"], "project": "ENG", "priority": "High"},
                }
                tool_risk_level = "write_high"
                approval_required = True
            elif "email" in query:
                tool_request = {
                    "tool": "send_summary_email",
                    "arguments": {"subject": "Knowledge Summary", "recipient": state["principal"].email},
                }
                tool_risk_level = "write_low"
                approval_required = False

        return {
            "tool_request": tool_request,
            "tool_risk_level": tool_risk_level,
            "approval_required": approval_required,
            "steps_executed": ["decide_action"],
        }

    def human_approval(self, state: AgentState) -> dict[str, Any]:
        """Handle human-in-the-loop approval or resumption for high-risk actions."""
        granted = state.get("approval_granted")
        tool_req = state.get("tool_request") or {}
        tool_name = tool_req.get("tool", "unknown_tool")

        tool_result = None
        if granted is True:
            tool_result = {"status": "success", "message": f"Tool '{tool_name}' executed successfully."}
        elif granted is False:
            tool_result = {"status": "rejected", "message": f"Action '{tool_name}' was denied by user."}

        return {
            "tool_result": tool_result,
            "steps_executed": ["human_approval"],
        }

    def respond(self, state: AgentState) -> dict[str, Any]:
        """Formulate final agent response payload with confidence and suggestions."""
        intent = state.get("intent", "factual_lookup")

        if intent == "chit_chat":
            final_response = "Hello! I am your Enterprise Knowledge Agent. How can I assist you with company documents today?"
            suggestions = ["What is the PTO leave policy?", "Where are the engineering coding standards?"]
            confidence = 1.0
        elif state.get("tool_result"):
            final_response = (state.get("tool_result") or {}).get("message", "Action completed.")
            suggestions = ["Show recent audit logs", "Check ticket status"]
            confidence = 1.0
        else:
            final_response = state.get("draft_answer") or "No answer could be generated."
            suggestions = ["Explain travel reimbursement", "View source documents"]
            confidence = state.get("confidence", 0.9)

        return {
            "final_response": final_response,
            "confidence": confidence,
            "follow_up_suggestions": suggestions,
            "steps_executed": ["respond"],
        }
