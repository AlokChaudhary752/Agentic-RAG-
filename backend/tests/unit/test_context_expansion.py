"""Unit tests for parent-document context expansion and chunk stitching."""

import pytest

from app.domain.models import ClassificationLevel, DocumentACL, DocumentChunk
from app.retrieval.context_expansion import ContextExpander


@pytest.mark.unit
def test_parent_content_expansion() -> None:
    """Verify child chunk content is replaced by parent section text."""
    expander = ContextExpander()
    base_acl = DocumentACL(classification_level=ClassificationLevel.INTERNAL)

    chunk = DocumentChunk(
        id="c1",
        doc_id="doc1",
        parent_chunk_id="parent-01",
        chunk_index=1,
        title="Engineering Standards",
        content="Child text snippet.",
        parent_content="## Comprehensive Parent Section\nDetailed full paragraph.",
        author="Architect",
        owner_group="group_engineering",
        acl=base_acl,
    )

    expanded = expander.expand_and_stitch([chunk])
    assert len(expanded) == 1
    assert "Comprehensive Parent Section" in expanded[0].content


@pytest.mark.unit
def test_contiguous_neighbor_stitching() -> None:
    """Verify neighboring chunks with consecutive indices from same document are stitched."""
    expander = ContextExpander(max_context_chars=2000)
    base_acl = DocumentACL(classification_level=ClassificationLevel.INTERNAL)

    c1 = DocumentChunk(
        id="c1",
        doc_id="doc1",
        parent_chunk_id=None,
        chunk_index=1,
        title="API Guide",
        content="First paragraph of API rules.",
        author="API Lead",
        owner_group="group_engineering",
        acl=base_acl,
    )
    c2 = DocumentChunk(
        id="c2",
        doc_id="doc1",
        parent_chunk_id=None,
        chunk_index=2,
        title="API Guide",
        content="Second contiguous paragraph of API rules.",
        author="API Lead",
        owner_group="group_engineering",
        acl=base_acl,
    )

    stitched = expander.expand_and_stitch([c1, c2])
    assert len(stitched) == 1
    assert "First paragraph of API rules." in stitched[0].content
    assert "Second contiguous paragraph of API rules." in stitched[0].content
