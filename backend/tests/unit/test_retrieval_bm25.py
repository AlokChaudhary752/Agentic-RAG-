"""Unit tests for sparse BM25 retrieval and multilingual tokenization."""

import pytest

from app.domain.models import ClassificationLevel, DocumentACL, DocumentChunk, UserPrincipal
from app.retrieval.bm25 import BM25Retriever


@pytest.fixture
def sample_bm25_chunks() -> list[DocumentChunk]:
    return [
        DocumentChunk(
            id="c1",
            doc_id="d1",
            chunk_index=1,
            title="Leave Policy",
            content="Employees receive twenty five days of annual paid time off and vacation leave.",
            author="HR",
            owner_group="group_hr",
            acl=DocumentACL(
                allowed_groups=["group_engineering"],
                classification_level=ClassificationLevel.INTERNAL,
            ),
        ),
        DocumentChunk(
            id="c2",
            doc_id="d2",
            chunk_index=1,
            title="Password Security",
            content="FIDO2 WebAuthn passkeys are mandatory for logging into Active Directory.",
            author="IT",
            owner_group="group_it",
            acl=DocumentACL(
                allowed_groups=["group_engineering"],
                classification_level=ClassificationLevel.INTERNAL,
            ),
        ),
        DocumentChunk(
            id="c3",
            doc_id="d3",
            chunk_index=1,
            title="Executive Compensation",
            content="Chief Executive Officer base salary compensation package and equity retention.",
            author="Board",
            owner_group="group_executives",
            acl=DocumentACL(
                allowed_groups=["group_executives"],
                classification_level=ClassificationLevel.RESTRICTED,
            ),
        ),
    ]


@pytest.mark.unit
def test_bm25_keyword_ranking(sample_bm25_chunks: list[DocumentChunk]) -> None:
    """Verify BM25 ranks document with exact keyword match at rank 1."""
    retriever = BM25Retriever()
    retriever.index_chunks(sample_bm25_chunks)

    results = retriever.search("passkeys Active Directory WebAuthn", top_k=2)
    assert len(results) > 0
    assert results[0].chunk.id == "c2"
    assert results[0].score > 0.0


@pytest.mark.unit
def test_bm25_acl_pre_filtering(sample_bm25_chunks: list[DocumentChunk]) -> None:
    """Verify BM25 search does not return chunks violating calling user's ACL."""
    retriever = BM25Retriever()
    retriever.index_chunks(sample_bm25_chunks)

    # Alice is in group_engineering with INTERNAL clearance
    alice = UserPrincipal(
        user_id="emp_alice",
        email="alice@nimbus.com",
        full_name="Alice Smith",
        groups=["group_engineering"],
        clearance=ClassificationLevel.INTERNAL,
    )

    # Searching for executive compensation should yield 0 results for Alice
    results = retriever.search("Executive Officer base salary compensation", principal=alice)
    for r in results:
        assert r.chunk.id != "c3"
