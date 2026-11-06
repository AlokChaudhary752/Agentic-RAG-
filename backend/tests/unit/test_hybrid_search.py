"""Unit tests for HybridRetriever coordination."""

import pytest

from app.domain.models import ClassificationLevel, DocumentACL, DocumentChunk, UserPrincipal
from app.retrieval.hybrid_search import HybridRetriever
from app.retrieval.qdrant_client import QdrantService


@pytest.fixture
def test_chunks() -> list[DocumentChunk]:
    base_acl = DocumentACL(
        allowed_groups=["group_engineering"],
        classification_level=ClassificationLevel.INTERNAL,
    )
    return [
        DocumentChunk(
            id="c1",
            doc_id="doc1",
            chunk_index=1,
            title="Leave Policy",
            content="Employees receive twenty-five days of annual PTO vacation leave.",
            author="HR",
            owner_group="group_hr",
            acl=base_acl,
        ),
        DocumentChunk(
            id="c2",
            doc_id="doc2",
            chunk_index=1,
            title="Hardware Policy",
            content="Laptops are refreshed every 36 months for engineering developers.",
            author="IT",
            owner_group="group_it",
            acl=base_acl,
        ),
    ]


@pytest.mark.unit
async def test_hybrid_retriever_pipeline(test_chunks: list[DocumentChunk]) -> None:
    """Verify HybridRetriever executes query transformation, sparse indexing, and fusion."""
    qdrant = QdrantService()
    await qdrant.upsert_chunks(test_chunks)

    retriever = HybridRetriever(qdrant_service=qdrant)
    retriever.index_corpus_for_sparse_search(test_chunks)

    alice = UserPrincipal(
        user_id="emp_alice",
        email="alice@nimbus.com",
        full_name="Alice Smith",
        groups=["group_engineering"],
        clearance=ClassificationLevel.INTERNAL,
    )

    bundle = retriever.retrieve(
        query="What is the laptop hardware refresh policy?",
        principal=alice,
        strategy="hybrid",
        top_k=2,
    )

    assert len(bundle.chunks) > 0
    assert bundle.metadata.strategy == "hybrid"
    assert bundle.metadata.latency_ms > 0
    assert any("Laptops are refreshed" in c.content for c in bundle.chunks)
