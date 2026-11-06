"""Classification-aware redaction engine ensuring content sanitization based on user clearance."""

from app.domain.models import ClassificationLevel, DocumentChunk, UserPrincipal
from app.ingestion.pii.masker import PIIMasker


class ClassificationRedactor:
    """Enforces fine-grained content masking and classification-level redaction."""

    def __init__(self, pii_masker: PIIMasker | None = None) -> None:
        self.masker = pii_masker or PIIMasker()

    def redact_chunk(
        self,
        chunk: DocumentChunk,
        principal: UserPrincipal,
    ) -> DocumentChunk:
        """Redact or mask chunk content if principal clearance is insufficient or PII is restricted."""
        chunk_level = chunk.acl.classification_level
        user_level = principal.clearance

        # Check classification hierarchy: if user clearance is lower than chunk classification
        if not chunk_level.is_accessible_by(user_level):
            return chunk.model_copy(
                update={
                    "content": (
                        f"[REDACTED: CLEARANCE INSUFFICIENT - "
                        f"Requires {chunk_level.value}, current: {user_level.value}]"
                    ),
                    "parent_content": None,
                }
            )

        # Apply PII masking for users without executive or HR elevated clearance
        is_hr_or_exec = (
            user_level == ClassificationLevel.RESTRICTED
            or "group_hr" in principal.groups
            or "group_executives" in principal.groups
            or "admin" in principal.roles
        )

        if chunk.pii_flags and not is_hr_or_exec:
            masked_content, _ = self.masker.mask(chunk.content, classification=user_level)
            updated_parent = None
            if chunk.parent_content:
                updated_parent, _ = self.masker.mask(chunk.parent_content, classification=user_level)

            return chunk.model_copy(
                update={
                    "content": masked_content,
                    "parent_content": updated_parent,
                }
            )

        return chunk

    def redact_bundle(
        self,
        chunks: list[DocumentChunk],
        principal: UserPrincipal,
    ) -> list[DocumentChunk]:
        """Apply classification-aware redaction over a list of retrieved chunks."""
        return [self.redact_chunk(chunk, principal) for chunk in chunks]
