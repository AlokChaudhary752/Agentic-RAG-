"""Query transformation and reformulation engine for complex enterprise retrieval."""

import re

from pydantic import BaseModel, Field


class TransformedQueries(BaseModel):
    """Collection of reformulated queries produced by transformation strategies."""

    original_query: str = Field(..., description="Raw input query from user")
    rewritten_query: str = Field(..., description="Cleaned, de-aliased, and explicit query")
    expanded_queries: list[str] = Field(
        default_factory=list, description="Sub-queries and perspective variations"
    )
    step_back_query: str | None = Field(
        default=None, description="High-level abstract background query"
    )
    hypothetical_document: str | None = Field(
        default=None, description="Synthesized hypothetical answer snippet (HyDE)"
    )


class QueryTransformer:
    """Transforms raw user questions into optimized representations for vector and hybrid search."""

    def __init__(self) -> None:
        pass

    def rewrite_query(
        self, query: str, conversation_history: list[dict[str, str]] | None = None
    ) -> str:
        """Resolve pronouns and append enterprise context if missing."""
        cleaned = query.strip()
        # If query has vague references like 'it', 'the policy', 'they', inject company context
        if re.search(r"\b(it|its|their|the policy|the company|here)\b", cleaned, re.IGNORECASE) and "nimbus" not in cleaned.lower():
            cleaned = f"Nimbus Technologies {cleaned}"
        return cleaned

    def expand_query(self, query: str) -> list[str]:
        """Generate complementary query variations covering synonyms and phrasing."""
        variations = [query]
        q_lower = query.lower()

        # Domain-specific synonym expansions
        if "pto" in q_lower or "vacation" in q_lower or "leave" in q_lower:
            variations.append("Nimbus paid time off PTO carryover and sick leave policy")
            variations.append("Employee annual leave entitlement and recharge wellness days")
        elif "salary" in q_lower or "compensation" in q_lower or "pay" in q_lower:
            variations.append("Engineering compensation salary bands L3 L4 L5 L6 equity targets")
            variations.append("Total rewards base pay and annual bonus multiplier guidelines")
        elif "password" in q_lower or "login" in q_lower or "auth" in q_lower:
            variations.append("Passkey FIDO2 multi-factor authentication MFA standard")
            variations.append("Password rotation NIST SP 800-63B identity guidelines")
        elif "sla" in q_lower or "incident" in q_lower or "outage" in q_lower:
            variations.append("IT incident response priority levels P0 P1 P2 resolution SLA")
            variations.append("PagerDuty on-call escalation procedures and emergency downtime")
        elif "travel" in q_lower or "flight" in q_lower or "hotel" in q_lower:
            variations.append("Corporate travel meal per diem lodging entitlement Navan")
            variations.append("Business expense reimbursement guidelines and flight class rules")

        return list(dict.fromkeys(variations))  # Preserve unique order

    def generate_step_back_query(self, query: str) -> str:
        """Formulate a step-back question capturing high-level background knowledge."""
        q_lower = query.lower()
        if "leave" in q_lower or "pto" in q_lower:
            return "What are the overall HR employee time off, benefits, and absence policies?"
        if "salary" in q_lower or "compensation" in q_lower:
            return "What is the corporate compensation, leveling structure, and equity framework?"
        if "password" in q_lower or "mfa" in q_lower or "auth" in q_lower:
            return "What are the core information security and identity authentication standards?"
        if "sla" in q_lower or "p0" in q_lower or "incident" in q_lower:
            return "What are the general IT operations, support tiers, and incident SLAs?"
        return f"General enterprise guidelines and procedures regarding {query}"

    def generate_hyde(self, query: str) -> str:
        """Produce a pseudo-document snippet reflecting expected authoritative structure."""
        return (
            f"According to Nimbus Technologies corporate guidelines for {query}: "
            f"The active approved policy specifies standard procedures, eligibility criteria, "
            f"and compliance thresholds for all personnel."
        )

    def transform(
        self,
        query: str,
        enable_expansion: bool = True,
        enable_step_back: bool = True,
        enable_hyde: bool = False,
    ) -> TransformedQueries:
        """Run all configured transformations returning a cohesive query bundle."""
        rewritten = self.rewrite_query(query)
        expanded = self.expand_query(rewritten) if enable_expansion else [rewritten]
        step_back = self.generate_step_back_query(query) if enable_step_back else None
        hyde_doc = self.generate_hyde(rewritten) if enable_hyde else None

        return TransformedQueries(
            original_query=query,
            rewritten_query=rewritten,
            expanded_queries=expanded,
            step_back_query=step_back,
            hypothetical_document=hyde_doc,
        )
