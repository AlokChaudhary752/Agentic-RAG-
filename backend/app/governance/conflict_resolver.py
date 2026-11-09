"""Cross-document conflict resolution engine detecting contradictions and authoritative recency."""

import re

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.domain.models import DocStatus, DocumentChunk

logger = get_logger(__name__)


class ConflictNotice(BaseModel):
    """Detailed metadata describing a detected contradiction or supersede relationship."""

    topic_or_entity: str = Field(..., description="Subject or section where conflict occurs")
    deprecated_or_older_title: str = Field(..., description="Title of the superseded source")
    deprecated_or_older_doc_id: str = Field(..., description="ID of superseded document")
    authoritative_title: str = Field(..., description="Title of the authoritative source")
    authoritative_doc_id: str = Field(..., description="ID of authoritative document")
    authoritative_year: int = Field(..., description="Publication or update year of newer source")
    message: str = Field(..., description="Explicit human-readable resolution notice")


class ConflictResolutionResult(BaseModel):
    """Result of cross-document conflict analysis and re-ranking."""

    resolved_chunks: list[DocumentChunk] = Field(
        ..., description="Re-ordered chunks favoring authority"
    )
    notices: list[ConflictNotice] = Field(
        default_factory=list, description="Explicit conflict notices"
    )
    has_conflicts: bool = Field(
        default=False, description="Whether conflicting versions were detected"
    )


class ConflictResolver:
    """Analyzes retrieved candidate chunks across documents to resolve policy/version contradictions."""

    def resolve(self, chunks: list[DocumentChunk]) -> ConflictResolutionResult:
        """Identify contradicting versions across documents and re-rank prioritizing authoritative sources."""
        if not chunks:
            return ConflictResolutionResult(resolved_chunks=[], notices=[], has_conflicts=False)

        # 1. Group chunks by base topic/title key
        groups: dict[str, list[DocumentChunk]] = {}
        for chunk in chunks:
            key = self._extract_topic_key(chunk)
            groups.setdefault(key, []).append(chunk)

        notices: list[ConflictNotice] = []
        resolved_chunks: list[DocumentChunk] = []

        for topic, group_chunks in groups.items():
            # Check for multi-document presence under the same topic
            doc_ids = {c.doc_id for c in group_chunks}
            if len(doc_ids) > 1:
                group_notices, sorted_group = self._resolve_group_conflicts(topic, group_chunks)
                notices.extend(group_notices)
                resolved_chunks.extend(sorted_group)
            else:
                resolved_chunks.extend(group_chunks)

        # Sort all chunks globally by authority score, status priority, and recency
        resolved_chunks.sort(key=self._chunk_sort_key, reverse=True)

        return ConflictResolutionResult(
            resolved_chunks=resolved_chunks,
            notices=notices,
            has_conflicts=len(notices) > 0,
        )

    def _extract_topic_key(self, chunk: DocumentChunk) -> str:
        """Extract a canonical topic key based on section path or title keywords."""
        if chunk.section_path:
            clean_sec = re.sub(r"\d{4}", "", chunk.section_path).lower().strip()
            if clean_sec:
                return clean_sec
        # Fallback to normalized title without year digits
        norm_title = re.sub(r"20\d{2}", "", chunk.title).lower()
        norm_title = re.sub(r"[^\w\s]", "", norm_title).strip()
        return norm_title or chunk.title.lower()

    def _resolve_group_conflicts(
        self, topic: str, group_chunks: list[DocumentChunk]
    ) -> tuple[list[ConflictNotice], list[DocumentChunk]]:
        """Compare distinct documents covering the same topic and declare the authoritative version."""
        # Find best document in this group
        # Sort documents by status (APPROVED > DRAFT > DEPRECATED), authority_score, updated_at
        docs_map: dict[str, list[DocumentChunk]] = {}
        for c in group_chunks:
            docs_map.setdefault(c.doc_id, []).append(c)

        sorted_doc_ids = sorted(
            docs_map.keys(),
            key=lambda d_id: self._chunk_sort_key(docs_map[d_id][0]),
            reverse=True,
        )

        authoritative_doc_id = sorted_doc_ids[0]
        auth_sample = docs_map[authoritative_doc_id][0]
        notices: list[ConflictNotice] = []

        for other_doc_id in sorted_doc_ids[1:]:
            other_sample = docs_map[other_doc_id][0]
            # Detect contradiction condition:
            # - One is deprecated
            # - Or significant timestamp/version difference
            is_deprecated = other_sample.doc_status == DocStatus.DEPRECATED
            is_older = other_sample.updated_at < auth_sample.updated_at
            lower_authority = other_sample.authority_score < auth_sample.authority_score

            if is_deprecated or is_older or lower_authority:
                older_year = other_sample.updated_at.year
                auth_year = auth_sample.updated_at.year
                notice = ConflictNotice(
                    topic_or_entity=topic,
                    deprecated_or_older_title=other_sample.title,
                    deprecated_or_older_doc_id=other_sample.doc_id,
                    authoritative_title=auth_sample.title,
                    authoritative_doc_id=auth_sample.doc_id,
                    authoritative_year=auth_year,
                    message=(
                        f"Doc '{other_sample.title}' ({older_year}) states conflicting policy, "
                        f"but newer/approved Doc '{auth_sample.title}' ({auth_year}, "
                        f"status: {auth_sample.doc_status.value}, "
                        f"authority: {auth_sample.authority_score}) is authoritative."
                    ),
                )
                notices.append(notice)
                logger.info("Cross-document conflict identified", notice=notice.message)

        # Return sorted chunks for this group
        group_sorted = sorted(group_chunks, key=self._chunk_sort_key, reverse=True)
        return notices, group_sorted

    def _chunk_sort_key(self, chunk: DocumentChunk) -> tuple[int, float, float]:
        """Compute sorting priority: status weight (APPROVED=3, DRAFT=2, DEPRECATED=1), authority, timestamp."""
        status_weights = {
            DocStatus.APPROVED: 3,
            DocStatus.DRAFT: 2,
            DocStatus.DEPRECATED: 1,
        }
        status_weight = status_weights.get(chunk.doc_status, 2)
        timestamp_weight = chunk.updated_at.timestamp()
        return (status_weight, chunk.authority_score, timestamp_weight)
