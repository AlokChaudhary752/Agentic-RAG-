"""Unit tests for structure-aware parent-child chunking."""

import uuid

import pytest

from app.domain.models import ClassificationLevel, DocumentACL, RawDocument
from app.ingestion.chunkers.structure_chunker import StructureChunker


@pytest.mark.unit
def test_parent_child_chunking_generation() -> None:
    """Verify StructureChunker creates child chunks linked to parent sections."""
    chunker = StructureChunker(target_chunk_size=150, chunk_overlap=30)
    raw_doc = RawDocument(
        id="test-doc-01",
        source="local_folder",
        source_url="file:///test.md",
        title="Engineering Standards",
        content="""# Section One
This is the first paragraph with some initial technical explanation.

This is a secondary paragraph that extends the explanation further to verify chunk size thresholds.

## Section Two
A shorter section that should generate a clean concise chunk.
""",
        author="Architect",
        owner_group="group_engineering",
        acl=DocumentACL(
            allowed_users=["emp_alice"],
            allowed_groups=["group_engineering"],
            classification_level=ClassificationLevel.INTERNAL,
        ),
    )

    chunks = chunker.chunk_document(raw_doc)
    assert len(chunks) >= 2

    # Verify chunk properties
    for c in chunks:
        assert c.doc_id == "test-doc-01"
        assert c.parent_chunk_id is not None
        assert c.parent_content is not None
        # Must be valid UUID for Qdrant compatibility
        parsed_uuid = uuid.UUID(c.id)
        assert str(parsed_uuid) == c.id
        # ACL inheritance
        assert c.acl.allowed_users == ["emp_alice"]
        assert c.acl.classification_level == ClassificationLevel.INTERNAL
