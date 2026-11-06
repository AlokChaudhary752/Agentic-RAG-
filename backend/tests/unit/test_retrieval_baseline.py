"""Unit tests for Naive RAG baseline retrieval."""

import uuid

import pytest

from app.domain.models import ClassificationLevel, DocumentACL, DocumentChunk
from app.retrieval.qdrant_client import QdrantService
from evaluation.baseline_naive_rag.naive_rag import NaiveRAGBaseline


@pytest.mark.unit
async def test_naive_rag_baseline_execution() -> None:
    """Verify NaiveRAGBaseline retrieves top-k vectors without ACL filtering."""
    qdrant = QdrantService()
    chunk = DocumentChunk(
        id=str(uuid.uuid4()),
        doc_id="hr-policy-1",
        chunk_index=0,
        content="The Nimbus Technologies PTO leave policy grants 20 days paid leave.",
        title="Nimbus PTO Policy",
        source="local_folder",
        source_url="http://intranet/pto",
        author="HR Team",
        owner_group="group_hr",
        acl=DocumentACL(
            allowed_groups=["group_all"],
            classification_level=ClassificationLevel.INTERNAL,
        ),
    )
    await qdrant.upsert_chunks([chunk])
    baseline = NaiveRAGBaseline(qdrant_service=qdrant, top_k=3)

    result = baseline.retrieve("What is the PTO leave policy?")
    assert result.query == "What is the PTO leave policy?"
    assert isinstance(result.chunks, list)
    assert len(result.chunks) == 1
    assert len(result.context_text) > 0
    assert "You are a helpful assistant" in result.model_prompt
