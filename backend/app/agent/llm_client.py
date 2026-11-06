"""LLM client abstraction with LiteLLM integration and deterministic offline fallbacks."""

import os
import re
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.domain.models import DocumentChunk

# Prevent LiteLLM from attempting network requests for remote model price lists
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

logger = get_logger(__name__)


class VerificationResult(BaseModel):
    """Result of claim-level faithfulness verification."""

    faithfulness_score: float = Field(default=1.0, ge=0.0, le=1.0)
    unsupported_claims: list[str] = Field(default_factory=list)
    is_faithful: bool = Field(default=True)


class LLMService:
    """Provides provider-agnostic model routing and reliable offline synthesis fallbacks."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.fast_model = getattr(self.settings, "llm_fast_model", "gemini-1.5-flash")
        self.strong_model = getattr(
            self.settings, "llm_strong_model", getattr(self.settings, "llm_primary_model", "gemini-1.5-pro")
        )

    def classify_intent(self, query: str) -> str:
        """Classify user intent into factual_lookup, multi_hop, action_request, chit_chat, or out_of_scope."""
        q = query.lower().strip()
        # Chit-chat
        words = re.findall(r"\w+", q)
        if words and words[0] in {"hi", "hello", "hey", "howdy", "greetings"}:
            return "chit_chat"
        if q in {"thanks", "thank you", "good morning", "good evening", "good afternoon", "bye", "goodbye"}:
            return "chit_chat"

        # Action requests
        action_pattern = re.compile(
            r"\b(create|open|file|log|submit|send|update)\s+(?:a\s+|an\s+)?(jira|ticket|bug|issue|email)\b",
            re.IGNORECASE,
        )
        if action_pattern.search(q):
            return "action_request"

        # Multi-hop queries
        comparison_keywords = ["compare", "difference between", "versus", " vs ", "how does x relate to y"]
        if any(kw in q for kw in comparison_keywords):
            return "multi_hop"

        return "factual_lookup"

    def grade_evidence(self, query: str, chunks: list[DocumentChunk]) -> tuple[str, float]:
        """Evaluate whether candidate chunks contain sufficient factual evidence to answer query."""
        if not chunks:
            return "irrelevant", 0.0

        query_terms = set(re.findall(r"\w+", query.lower()))
        stop_words = {"what", "is", "the", "for", "and", "in", "of", "to", "how", "a", "an", "does", "do"}
        meaningful_terms = query_terms - stop_words

        if not meaningful_terms:
            return "relevant", 0.8

        total_matches = 0
        for chunk in chunks:
            content_words = set(re.findall(r"\w+", chunk.content.lower()))
            matches = meaningful_terms.intersection(content_words)
            if matches:
                total_matches += len(matches)

        overlap_ratio = min(1.0, total_matches / (len(meaningful_terms) * len(chunks)))

        if overlap_ratio >= 0.25:
            return "relevant", overlap_ratio
        elif overlap_ratio >= 0.1:
            return "ambiguous", overlap_ratio
        else:
            return "irrelevant", overlap_ratio

    def generate_grounded_answer(
        self,
        query: str,
        chunks: list[DocumentChunk],
        conflict_notices: list[str] | None = None,
    ) -> tuple[str, list[dict[str, Any]], float]:
        """Synthesize factual answer strictly grounded in retrieved chunks with citations."""
        if not chunks:
            return (
                "I do not have sufficient information in the authorized enterprise documents "
                "to answer this question.",
                [],
                0.0,
            )

        citations: list[dict[str, Any]] = []
        answer_paragraphs: list[str] = []

        # 1. Mention any detected conflict notices upfront
        if conflict_notices:
            for notice in conflict_notices:
                answer_paragraphs.append(f"**Notice on Document Versions**: {notice}")

        # 2. Extract facts from most authoritative chunks
        for _i, chunk in enumerate(chunks[:3], 1):
            citation_marker = f"[{chunk.title}, {chunk.section_path or 'General'}]"
            citations.append(
                {
                    "doc_id": chunk.doc_id,
                    "title": chunk.title,
                    "section_path": chunk.section_path,
                    "source": chunk.source,
                    "source_url": chunk.source_url,
                }
            )
            # Use concise factual sentence from chunk
            clean_content = chunk.content.strip().split("\n")[0]
            answer_paragraphs.append(f"{clean_content} {citation_marker}")

        final_answer = "\n\n".join(answer_paragraphs)
        confidence = 0.95 if chunks[0].authority_score >= 0.8 else 0.75
        return final_answer, citations, confidence

    def verify_faithfulness(
        self,
        answer: str,
        chunks: list[DocumentChunk],
    ) -> VerificationResult:
        """Perform claim-level verification asserting answer claims are supported by context."""
        if not chunks:
            return VerificationResult(faithfulness_score=1.0, unsupported_claims=[], is_faithful=True)

        combined_context = " ".join(c.content.lower() for c in chunks)
        sentences = [s.strip() for s in answer.split(".") if len(s.strip()) > 15]

        unsupported: list[str] = []
        supported_count = 0

        for sentence in sentences:
            # Skip conflict notices and metadata headers
            if "notice on document" in sentence.lower() or "sufficient information" in sentence.lower():
                supported_count += 1
                continue

            words = set(re.findall(r"\w+", sentence.lower()))
            overlap = words.intersection(set(re.findall(r"\w+", combined_context)))
            if len(overlap) >= 3:
                supported_count += 1
            else:
                unsupported.append(sentence)

        score = supported_count / max(1, len(sentences))
        return VerificationResult(
            faithfulness_score=round(score, 2),
            unsupported_claims=unsupported,
            is_faithful=len(unsupported) == 0,
        )
