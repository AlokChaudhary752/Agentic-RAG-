"""Unit tests for Reciprocal Rank Fusion (RRF)."""

import pytest

from app.domain.models import ClassificationLevel, DocumentACL, DocumentChunk
from app.retrieval.fusion import ReciprocalRankFusion


@pytest.mark.unit
def test_rrf_scoring_and_rank_merging() -> None:
    """Verify RRF correctly boosts documents appearing in both dense and sparse rankings."""
    c1 = DocumentChunk(
        id="c1",
        doc_id="d1",
        chunk_index=1,
        title="Doc 1",
        content="Content 1",
        author="Author",
        owner_group="group_engineering",
        acl=DocumentACL(classification_level=ClassificationLevel.INTERNAL),
    )
    c2 = DocumentChunk(
        id="c2",
        doc_id="d2",
        chunk_index=1,
        title="Doc 2",
        content="Content 2",
        author="Author",
        owner_group="group_engineering",
        acl=DocumentACL(classification_level=ClassificationLevel.INTERNAL),
    )
    c3 = DocumentChunk(
        id="c3",
        doc_id="d3",
        chunk_index=1,
        title="Doc 3",
        content="Content 3",
        author="Author",
        owner_group="group_engineering",
        acl=DocumentACL(classification_level=ClassificationLevel.INTERNAL),
    )

    # c2 appears at rank 1 in dense and rank 1 in sparse -> should win rank 1 in fusion
    dense_list = [c2, c1]
    sparse_list = [c2, c3]

    fusion = ReciprocalRankFusion(k=60)
    fused = fusion.fuse(dense_results=dense_list, sparse_results=sparse_list, top_k=3)

    assert len(fused) == 3
    assert fused[0].chunk.id == "c2"
    assert fused[0].dense_rank == 1
    assert fused[0].sparse_rank == 1
    assert fused[0].rrf_score > fused[1].rrf_score
