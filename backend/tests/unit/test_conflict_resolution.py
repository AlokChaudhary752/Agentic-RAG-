"""Unit tests for cross-document conflict resolution engine."""

from datetime import UTC, datetime

import pytest

from app.domain.models import ClassificationLevel, DocStatus, DocumentACL, DocumentChunk
from app.governance.conflict_resolver import ConflictResolver


@pytest.fixture
def base_acl() -> DocumentACL:
    return DocumentACL(
        allowed_groups=["group_all"],
        classification_level=ClassificationLevel.INTERNAL,
    )


@pytest.mark.unit
def test_resolve_deprecated_vs_approved_conflict(base_acl: DocumentACL) -> None:
    """Verify ConflictResolver flags deprecated policy and prioritizes approved source."""
    resolver = ConflictResolver()

    chunk_dep = DocumentChunk(
        id="c_dep",
        doc_id="hr-travel-2024",
        chunk_index=1,
        title="Travel & Expense Policy 2024",
        section_path="Finance > Travel > Daily Per Diem",
        content="The daily per diem for domestic meal expenses is $60 USD per day.",
        doc_status=DocStatus.DEPRECATED,
        authority_score=0.3,
        updated_at=datetime(2024, 1, 15, tzinfo=UTC),
        acl=base_acl,
    )

    chunk_approved = DocumentChunk(
        id="c_app",
        doc_id="hr-travel-2026",
        chunk_index=1,
        title="Travel & Expense Policy 2026",
        section_path="Finance > Travel > Daily Per Diem",
        content="The daily per diem for domestic meal expenses has been updated to $85 USD per day.",
        doc_status=DocStatus.APPROVED,
        authority_score=0.95,
        updated_at=datetime(2026, 2, 1, tzinfo=UTC),
        acl=base_acl,
    )

    result = resolver.resolve([chunk_dep, chunk_approved])

    assert result.has_conflicts is True
    assert len(result.notices) == 1

    notice = result.notices[0]
    assert notice.authoritative_doc_id == "hr-travel-2026"
    assert notice.deprecated_or_older_doc_id == "hr-travel-2024"
    assert "is authoritative" in notice.message
    assert "Travel & Expense Policy 2026" in notice.authoritative_title

    # Authoritative chunk should be ranked first
    assert result.resolved_chunks[0].id == "c_app"
    assert result.resolved_chunks[1].id == "c_dep"


@pytest.mark.unit
def test_resolve_higher_authority_score_priority(base_acl: DocumentACL) -> None:
    """Verify source with higher authority score takes precedence when dates are close."""
    resolver = ConflictResolver()

    wiki_chunk = DocumentChunk(
        id="c_wiki",
        doc_id="eng-wiki-deploy",
        chunk_index=1,
        title="Production Deployment Guide",
        section_path="Engineering > Deployments",
        content="Deployments are permitted on Friday afternoons after peer review.",
        doc_status=DocStatus.APPROVED,
        authority_score=0.5,
        updated_at=datetime(2026, 3, 1, tzinfo=UTC),
        acl=base_acl,
    )

    official_soc2_chunk = DocumentChunk(
        id="c_soc2",
        doc_id="sec-compliance-deploy",
        chunk_index=1,
        title="Production Deployment Guide",
        section_path="Engineering > Deployments",
        content="Friday afternoon production deployments are strictly prohibited by SOC-2 policy.",
        doc_status=DocStatus.APPROVED,
        authority_score=0.98,
        updated_at=datetime(2026, 3, 5, tzinfo=UTC),
        acl=base_acl,
    )

    result = resolver.resolve([wiki_chunk, official_soc2_chunk])

    assert result.resolved_chunks[0].id == "c_soc2"
    assert result.resolved_chunks[0].authority_score == 0.98


@pytest.mark.unit
def test_no_conflicts_on_distinct_topics(base_acl: DocumentACL) -> None:
    """Verify distinct documents on non-overlapping topics generate no conflict notices."""
    resolver = ConflictResolver()

    chunk_a = DocumentChunk(
        id="c_a",
        doc_id="hr-pto",
        chunk_index=1,
        title="PTO Leave Policy",
        section_path="HR > Benefits",
        content="Annual PTO is 20 days.",
        acl=base_acl,
    )

    chunk_b = DocumentChunk(
        id="c_b",
        doc_id="it-hardware",
        chunk_index=1,
        title="Laptop Refresh Policy",
        section_path="IT > Equipment",
        content="MacBooks are refreshed every 3 years.",
        acl=base_acl,
    )

    result = resolver.resolve([chunk_a, chunk_b])
    assert result.has_conflicts is False
    assert len(result.notices) == 0
    assert len(result.resolved_chunks) == 2
