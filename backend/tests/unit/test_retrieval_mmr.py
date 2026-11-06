"""Unit tests for Maximal Marginal Relevance (MMR) diversity selection."""

import pytest

from app.domain.models import ClassificationLevel, DocumentACL, DocumentChunk
from app.retrieval.mmr import MaximalMarginalRelevance


@pytest.mark.unit
def test_mmr_deduplication_and_diversity() -> None:
    """Verify MMR filters out near-duplicate candidates in favor of diverse content."""
    mmr = MaximalMarginalRelevance(lambda_mult=0.5)

    base_acl = DocumentACL(classification_level=ClassificationLevel.INTERNAL)

    # Chunk A and Chunk B are almost identical duplicates
    c_dup1 = DocumentChunk(
        id="d1",
        doc_id="doc1",
        chunk_index=1,
        title="SLA Guidelines",
        content="Incident response SLA for P0 outages is 15 minutes to respond and 2 hours to resolve.",
        author="IT",
        owner_group="group_it",
        acl=base_acl,
    )
    c_dup2 = DocumentChunk(
        id="d2",
        doc_id="doc1",
        chunk_index=2,
        title="SLA Guidelines Duplicate",
        content="Incident response SLA for P0 outages is 15 minutes to respond and two hours to resolve.",
        author="IT",
        owner_group="group_it",
        acl=base_acl,
    )
    # Chunk C discusses a different but relevant topic (hardware)
    c_diverse = DocumentChunk(
        id="d3",
        doc_id="doc2",
        chunk_index=1,
        title="Hardware Allocation",
        content="Laptops for engineering team are refreshed every 36 months with MacBook Pro.",
        author="IT",
        owner_group="group_it",
        acl=base_acl,
    )

    selected = mmr.select(
        query="What is the IT SLA and hardware guidelines?",
        candidates=[c_dup1, c_dup2, c_diverse],
        top_k=2,
    )

    assert len(selected) == 2
    selected_ids = [c.id for c in selected]
    # Should select one of the duplicates and the diverse hardware chunk
    assert "d3" in selected_ids
    assert ("d1" in selected_ids and "d2" not in selected_ids) or (
        "d2" in selected_ids and "d1" not in selected_ids
    )
