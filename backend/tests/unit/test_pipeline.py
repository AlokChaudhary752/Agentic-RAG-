"""Unit tests for the IngestionPipeline error handling, hashing, and DLQ."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import ClassificationLevel, DocumentACL, RawDocument
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.qdrant_client import QdrantService


@pytest.mark.unit
async def test_pipeline_incremental_change_hashing(async_session: AsyncSession) -> None:
    """Verify unchanged documents are skipped on second sync run."""
    qdrant = QdrantService()
    pipeline = IngestionPipeline(async_session, qdrant_service=qdrant)

    doc = RawDocument(
        id="test-hash-doc",
        source="local_folder",
        source_url="file:///test.md",
        title="Test Document",
        content="First version content.",
        author="Tester",
        owner_group="group_engineering",
        acl=DocumentACL(
            allowed_users=[],
            allowed_groups=["group_engineering"],
            classification_level=ClassificationLevel.INTERNAL,
        ),
    )

    # First run: should index
    indexed, reason = await pipeline.process_document(doc)
    assert indexed is True
    assert reason == "indexed"

    # Second run with same content: should skip
    indexed_again, reason_again = await pipeline.process_document(doc)
    assert indexed_again is False
    assert reason_again == "skipped_unchanged"

    # Third run with modified content: should re-index
    doc.content = "Second updated version content."
    indexed_third, reason_third = await pipeline.process_document(doc)
    assert indexed_third is True
    assert reason_third == "indexed"
