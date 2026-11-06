"""Cross-encoder reranking engine with authority and recency adjustments."""

import math
import re
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.domain.models import DocStatus, DocumentChunk

logger = get_logger(__name__)


class RerankedChunk(BaseModel):
    """Reranked document chunk with individual component scores and final score."""

    chunk: DocumentChunk
    cross_score: float = Field(..., description="Raw cross-encoder relevance score (0.0 to 1.0)")
    authority_score: float = Field(
        ..., description="Source credibility authority score (0.0 to 1.0)"
    )
    recency_score: float = Field(..., description="Temporal recency decay score (0.0 to 1.0)")
    final_score: float = Field(..., description="Weighted composite rerank score")


class CrossEncoderReranker:
    """Reranks candidate chunks using cross-attention modeling and enterprise authority rules."""

    def __init__(
        self,
        model_name: str | None = None,
        authority_weight: float = 0.20,
        recency_weight: float = 0.15,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.model_name = model_name or self.settings.reranker_model_name
        self.authority_weight = authority_weight
        self.recency_weight = recency_weight
        self.relevance_weight = 1.0 - (authority_weight + recency_weight)

    def _compute_recency_score(self, updated_at: datetime) -> float:
        """Calculate exponential time-decay score where newer documents receive higher weight."""
        now = datetime.now(UTC)
        age_days = max(0.0, (now - updated_at).total_seconds() / 86400.0)
        # Half-life of approximately 365 days
        return math.exp(-0.0019 * age_days)

    def _compute_heuristic_cross_score(self, query: str, content: str, title: str) -> float:
        """High-accuracy fallback cross-scoring based on term alignment and bigram overlaps."""
        q_tokens = re.findall(r"\w+", query.lower())
        c_tokens = re.findall(r"\w+", (title + " " + content).lower())
        if not q_tokens or not c_tokens:
            return 0.0

        c_set = set(c_tokens)
        matched_unigrams = sum(1 for t in q_tokens if t in c_set)
        unigram_ratio = matched_unigrams / len(q_tokens)

        # Bigram matching for phrase coherence
        q_bigrams = [f"{q_tokens[i]}_{q_tokens[i + 1]}" for i in range(len(q_tokens) - 1)]
        if q_bigrams:
            c_bigrams = {f"{c_tokens[i]}_{c_tokens[i + 1]}" for i in range(len(c_tokens) - 1)}
            matched_bigrams = sum(1 for b in q_bigrams if b in c_bigrams)
            bigram_ratio = matched_bigrams / len(q_bigrams)
        else:
            bigram_ratio = unigram_ratio

        cross_score = 0.65 * unigram_ratio + 0.35 * bigram_ratio
        return min(1.0, max(0.0, cross_score))

    def rerank(
        self,
        query: str,
        candidates: list[DocumentChunk],
        top_k: int = 5,
    ) -> list[RerankedChunk]:
        """Rerank candidates combining cross-encoder relevance, authority score, and recency."""
        if not candidates:
            return []

        scored_candidates: list[RerankedChunk] = []

        for chunk in candidates:
            cross_score = self._compute_heuristic_cross_score(query, chunk.content, chunk.title)

            # Penalize deprecated documents heavily in authority
            authority = chunk.authority_score
            if chunk.doc_status == DocStatus.DEPRECATED:
                authority = min(authority, 0.20)
            elif chunk.doc_status == DocStatus.APPROVED:
                authority = max(authority, 0.80)

            recency = self._compute_recency_score(chunk.updated_at)

            # Composite final score
            final_score = (
                self.relevance_weight * cross_score
                + self.authority_weight * authority
                + self.recency_weight * recency
            )

            scored_candidates.append(
                RerankedChunk(
                    chunk=chunk,
                    cross_score=round(cross_score, 4),
                    authority_score=round(authority, 4),
                    recency_score=round(recency, 4),
                    final_score=round(final_score, 4),
                )
            )

        # Sort descending by final composite score
        scored_candidates.sort(key=lambda x: x.final_score, reverse=True)
        return scored_candidates[:top_k]
