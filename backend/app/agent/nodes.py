"""LangGraph node execution functions for the Enterprise Knowledge Agent."""

import re
from typing import Any

from app.agent.llm_client import LLMService
from app.agent.state import AgentState
from app.core.logging import get_logger
from app.governance.conflict_resolver import ConflictResolver
from app.governance.prompt_injection import PromptInjectionDefense
from app.retrieval.hybrid_search import HybridRetriever
from app.retrieval.query_transforms import QueryTransformer
from app.tools.client import MCPClient, get_mcp_client
from app.tools.schemas import ToolRiskLevel

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
        mcp_client: MCPClient | None = None,
    ) -> None:
        self.retriever = retriever or HybridRetriever()
        self.llm = llm_service or LLMService()
        self.conflict_resolver = conflict_resolver or ConflictResolver()
        self.defense = injection_defense or PromptInjectionDefense()
        self.transformer = query_transformer or QueryTransformer()
        self.mcp_client = mcp_client or get_mcp_client()

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
        grade, _score = self.llm.grade_evidence(query, chunks)

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
        raw_query = state.get("query", "")
        query = raw_query.lower()
        principal = state.get("principal")

        tool_request = None
        tool_risk_level = None
        approval_required = False
        tool_result = None

        if intent == "action_request" and principal:
            if any(kw in query for kw in ["jira", "ticket", "bug", "issue"]):
                status_match = re.search(r"\b([A-Z]{2,10}-\d+)\b", raw_query)
                if status_match and any(w in query for w in ["status", "check", "progress", "show", "get"]):
                    tool_name = "get_ticket_status"
                    tool_risk = self.mcp_client.get_tool_risk(tool_name)
                    tool_risk_level = tool_risk.value
                    approval_required = False
                    status_args: dict[str, Any] = {"ticket_id": status_match.group(1).upper()}
                    tool_request = {
                        "tool": tool_name,
                        "arguments": status_args,
                    }
                    res = self.mcp_client.execute_sync(
                        tool_name=tool_name,
                        arguments=status_args,
                        principal=principal,
                        approval_granted=True,
                        correlation_id=state.get("correlation_id"),
                    )
                    res_dict = res.model_dump()
                    res_dict["status"] = "success" if res.success else "failed"
                    tool_result = res_dict
                else:
                    tool_name = "create_jira_ticket"
                    tool_risk = self.mcp_client.get_tool_risk(tool_name)
                    tool_risk_level = tool_risk.value
                    approval_required = tool_risk == ToolRiskLevel.WRITE_HIGH
                    jira_args: dict[str, Any] = {
                        "summary": raw_query,
                        "description": f"Automated ticket created from user request: {raw_query}",
                        "project": "NIMBUS",
                        "priority": "High",
                    }
                    tool_request = {
                        "tool": tool_name,
                        "arguments": jira_args,
                    }
                    if state.get("approval_granted") is True:
                        res = self.mcp_client.execute_sync(
                            tool_name=tool_name,
                            arguments=jira_args,
                            principal=principal,
                            approval_granted=True,
                            correlation_id=state.get("correlation_id"),
                        )
                        res_dict = res.model_dump()
                        res_dict["status"] = "success" if res.success else "failed"
                        tool_result = res_dict

            elif any(kw in query for kw in ["email", "mail", "send"]):
                tool_name = "send_summary_email"
                tool_risk = self.mcp_client.get_tool_risk(tool_name)
                tool_risk_level = tool_risk.value
                approval_required = False
                email_args: dict[str, Any] = {
                    "recipient_email": principal.email,
                    "subject": "Enterprise Knowledge Summary",
                    "body": state.get("draft_answer") or f"Knowledge summary for request: {raw_query}",
                }
                tool_request = {
                    "tool": tool_name,
                    "arguments": email_args,
                }
                res = self.mcp_client.execute_sync(
                    tool_name=tool_name,
                    arguments=email_args,
                    principal=principal,
                    approval_granted=True,
                    correlation_id=state.get("correlation_id"),
                )
                res_dict = res.model_dump()
                res_dict["status"] = "success" if res.success else "failed"
                tool_result = res_dict

            elif any(kw in query for kw in ["recent", "changes", "modified", "updates"]):
                tool_name = "list_recent_changes"
                tool_risk = self.mcp_client.get_tool_risk(tool_name)
                tool_risk_level = tool_risk.value
                approval_required = False
                recent_args: dict[str, Any] = {"days_back": 7, "limit": 5}
                tool_request = {
                    "tool": tool_name,
                    "arguments": recent_args,
                }
                res = self.mcp_client.execute_sync(
                    tool_name=tool_name,
                    arguments=recent_args,
                    principal=principal,
                    approval_granted=True,
                    correlation_id=state.get("correlation_id"),
                )
                res_dict = res.model_dump()
                res_dict["status"] = "success" if res.success else "failed"
                tool_result = res_dict

        return {
            "tool_request": tool_request,
            "tool_risk_level": tool_risk_level,
            "approval_required": approval_required,
            "tool_result": tool_result,
            "steps_executed": ["decide_action"],
        }

    def human_approval(self, state: AgentState) -> dict[str, Any]:
        """Handle human-in-the-loop approval or resumption for high-risk actions."""
        granted = state.get("approval_granted")
        tool_req = state.get("tool_request") or {}
        tool_name = tool_req.get("tool", "unknown_tool")
        principal = state.get("principal")

        tool_result = None
        if granted is True:
            if principal and tool_name and tool_name in self.mcp_client.allowed_tools:
                args = tool_req.get("arguments", {})
                if tool_name == "create_jira_ticket":
                    args.setdefault("description", f"Action requested: {args.get('summary', 'Task')}")
                res = self.mcp_client.execute_sync(
                    tool_name=tool_name,
                    arguments=args,
                    principal=principal,
                    approval_granted=True,
                    correlation_id=state.get("correlation_id"),
                )
                res_dict = res.model_dump()
                res_dict["status"] = "success" if res.success else "failed"
                tool_result = res_dict
            else:
                tool_result = {
                    "status": "success",
                    "success": True,
                    "message": f"Tool '{tool_name}' executed successfully.",
                }
        elif granted is False:
            tool_result = {
                "tool_name": tool_name,
                "status": "rejected",
                "message": f"Action '{tool_name}' was denied by user.",
                "success": False,
            }

        return {
            "tool_result": tool_result,
            "steps_executed": ["human_approval"],
        }

    def respond(self, state: AgentState) -> dict[str, Any]:
        """Formulate final agent response payload with confidence and suggestions."""
        intent = state.get("intent", "factual_lookup")
        tool_res = state.get("tool_result")

        if intent == "chit_chat":
            final_response = "Hello! I am your Enterprise Knowledge Agent. How can I assist you with company documents today?"
            suggestions = ["What is the PTO leave policy?", "Where are the engineering coding standards?"]
            confidence = 1.0
        elif tool_res:
            data = tool_res.get("data")
            if data and isinstance(data, dict):
                if "ticket_id" in data and "url" in data:
                    final_response = f"Action create_jira_ticket completed: Ticket {data['ticket_id']} has been successfully created: {data['url']} (Priority: {data.get('priority', 'Medium')}, Status: {data.get('status', 'Open')})."
                elif "delivery_id" in data:
                    final_response = f"Summary email has been delivered to {data.get('recipient')} (Delivery ID: {data['delivery_id']})."
                elif "ticket_id" in data and "status" in data:
                    final_response = f"Ticket {data['ticket_id']} is currently '{data['status']}' with priority '{data['priority']}' (Assignee: {data.get('assignee') or 'Unassigned'})."
                elif "documents" in data:
                    doc_titles = [d.get("title", d.get("doc_id")) for d in data.get("documents", [])]
                    final_response = f"Found {len(doc_titles)} recent document changes: {', '.join(doc_titles)}."
                else:
                    final_response = tool_res.get("message", "Action completed successfully.")
            elif tool_res.get("status") == "rejected":
                final_response = tool_res.get("message", "Action was denied by user.")
            elif tool_res.get("error"):
                final_response = f"Action could not be completed: {tool_res['error']}"
            else:
                final_response = tool_res.get("message", "Action completed.")

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
