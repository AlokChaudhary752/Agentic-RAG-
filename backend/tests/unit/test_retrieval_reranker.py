"""Unit tests for Cross-Encoder Reranker."""

from datetime import UTC, datetime

import pytest

from app.domain.models import ClassificationLevel, DocStatus, DocumentACL, DocumentChunk
from app.retrieval.reranker import CrossEncoderReranker


@pytest.mark.unit
def test_reranker_prefers_approved_over_deprecated() -> None:
    """Verify reranker penalizes deprecated policies in favor of approved ones."""
    deprecated_chunk = DocumentChunk(
        id="c_dep",
        doc_id="d_dep",
        chunk_index=1,
        title="Leave Policy 2024",
        content="Employees receive 15 days of annual paid time off PTO.",
        author="HR",
        owner_group="group_hr",
        doc_status=DocStatus.DEPRECATED,
        authority_score=0.30,
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        acl=DocumentACL(classification_level=ClassificationLevel.INTERNAL),
    )

    approved_chunk = DocumentChunk(
        id="c_app",
        doc_id="d_app",
        chunk_index=1,
        title="Leave Policy 2026",
        content="Employees receive 25 days of annual paid time off PTO.",
        author="HR",
        owner_group="group_hr",
        doc_status=DocStatus.APPROVED,
        authority_score=0.98,
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        acl=DocumentACL(classification_level=ClassificationLevel.INTERNAL),
    )

    reranker = CrossEncoderReranker()
    reranked = reranker.rerank(
        query="What is the annual PTO allocation?",
        candidates=[deprecated_chunk, approved_chunk],
        top_k=2,
    )

    assert len(reranked) == 2
    assert reranked[0].chunk.id == "c_app"
    assert reranked[0].final_score > reranked[1].final_score
    assert reranked[0].authority_score >= 0.80
    assert reranked[1].authority_score <= 0.20


@pytest.mark.unit
def test_reranker_empty_candidates_returns_empty() -> None:
    """Verify reranker handles empty candidate lists gracefully."""
    reranker = CrossEncoderReranker()
    assert reranker.rerank(query="anything", candidates=[]) == []


@pytest.mark.unit
def test_reranker_relevance_ranking() -> None:
    """Verify reranker ranks exact match queries higher when status and recency are equal."""
    chunk_relevant = DocumentChunk(
        id="c_rel",
        doc_id="d_rel",
        chunk_index=1,
        title="Engineering Coding Standards",
        content="Python code must adhere to Black formatting and Ruff linting rules.",
        author="Architecture",
        doc_status=DocStatus.APPROVED,
        authority_score=0.90,
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        acl=DocumentACL(classification_level=ClassificationLevel.INTERNAL),
    )

    chunk_less_relevant = DocumentChunk(
        id="c_less",
        doc_id="d_less",
        chunk_index=1,
        title="Kitchen Cleaning Schedule",
        content="Please clean coffee mugs after use in the 4th floor pantry.",
        author="Facilities",
        doc_status=DocStatus.APPROVED,
        authority_score=0.90,
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        acl=DocumentACL(classification_level=ClassificationLevel.INTERNAL),
    )

    reranker = CrossEncoderReranker()
    results = reranker.rerank(
        query="What are our Python linting rules?",
        candidates=[chunk_less_relevant, chunk_relevant],
        top_k=2,
    )

    assert len(results) == 2
    assert results[0].chunk.id == "c_rel"
    assert results[0].cross_score > results[1].cross_score

