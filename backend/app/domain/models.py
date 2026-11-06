"""Domain models and value objects for Enterprise Knowledge Agent.

Defines entities for identity, permissions, document lifecycle, parent-child chunks,
and ingestion jobs.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ClassificationLevel(StrEnum):
    """Enterprise document classification levels according to security policy."""

    PUBLIC = "PUBLIC"  # Accessible to all employees and contractors
    INTERNAL = "INTERNAL"  # Standard internal company knowledge
    CONFIDENTIAL = "CONFIDENTIAL"  # Department or role-restricted (e.g. Finance, HR, Execs)
    RESTRICTED = "RESTRICTED"  # Highly sensitive (Executive committee, legal holds)

    @classmethod
    def from_str(cls, val: str) -> "ClassificationLevel":
        try:
            return cls[val.upper()]
        except KeyError:
            return cls.INTERNAL

    @property
    def level_rank(self) -> int:
        """Numeric rank for clearance comparisons (higher requires greater clearance)."""
        ranks = {
            self.PUBLIC: 1,
            self.INTERNAL: 2,
            self.CONFIDENTIAL: 3,
            self.RESTRICTED: 4,
        }
        return ranks[self]

    def is_accessible_by(self, clearance: "ClassificationLevel") -> bool:
        """Return True if user with given clearance can access this classification."""
        return clearance.level_rank >= self.level_rank


class DocStatus(StrEnum):
    """Document lifecycle state for authority and conflict resolution."""

    DRAFT = "draft"
    APPROVED = "approved"
    DEPRECATED = "deprecated"


class DocumentACL(BaseModel):
    """Access Control List (ACL) attached to documents and individual chunks."""

    allowed_users: list[str] = Field(
        default_factory=list,
        description="Explicit user IDs permitted to retrieve this entity",
    )
    allowed_groups: list[str] = Field(
        default_factory=list,
        description="Group or department IDs permitted to retrieve this entity",
    )
    classification_level: ClassificationLevel = Field(
        default=ClassificationLevel.INTERNAL,
        description="Minimum security clearance level required",
    )

    def permits_user(
        self, user_id: str, user_groups: list[str], clearance: ClassificationLevel
    ) -> bool:
        """Verify if a user's principal satisfies the ACL conditions."""
        # 1. Classification check: clearance must be >= document classification
        if not self.classification_level.is_accessible_by(clearance):
            return False

        # 2. If no specific user or group restrictions exist, document is open to clearance
        if not self.allowed_users and not self.allowed_groups:
            return True

        # 3. Direct user match
        if user_id in self.allowed_users:
            return True

        # 4. Group intersection
        user_group_set = set(user_groups)
        allowed_group_set = set(self.allowed_groups)
        return bool(user_group_set.intersection(allowed_group_set))


class UserPrincipal(BaseModel):
    """Security principal representing an authenticated user session."""

    user_id: str = Field(..., description="Unique user identifier")
    email: str = Field(..., description="Corporate email address")
    full_name: str = Field(..., description="Employee full name")
    roles: list[str] = Field(
        default_factory=list, description="RBAC roles (e.g. employee, manager, admin)"
    )
    groups: list[str] = Field(default_factory=list, description="Department and functional groups")
    clearance: ClassificationLevel = Field(
        default=ClassificationLevel.INTERNAL, description="User security clearance"
    )
    tenant_id: str = Field(default="tenant-nimbus-default", description="Tenant scope")


class RawDocument(BaseModel):
    """Normalized document representation extracted from an enterprise connector."""

    id: str = Field(..., description="Stable unique document identifier (e.g. gdrive-file-123)")
    source: str = Field(..., description="Connector source name (google_drive, notion, jira, etc.)")
    source_url: str = Field(..., description="Deep link or web URL to source document")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Full text or structured markdown content")
    author: str = Field(..., description="Document author or owner")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: str = Field(default="1.0", description="Semantic or revision version string")
    doc_status: DocStatus = Field(
        default=DocStatus.APPROVED, description="Draft, approved, or deprecated"
    )
    authority_score: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Source credibility score (0.0 to 1.0)"
    )
    language: str = Field(default="en", description="ISO 639-1 language code (e.g. en, hi)")
    owner_group: str = Field(..., description="Owning business unit/group (e.g. group_hr)")
    acl: DocumentACL = Field(..., description="Document-level access control list")
    content_hash: str = Field(
        default="", description="SHA-256 hash of content and metadata for change detection"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary connector metadata"
    )


class DocumentChunk(BaseModel):
    """Atomic text chunk enriched with parent section and retrieval metadata."""

    id: str = Field(..., description="Globally unique chunk identifier")
    doc_id: str = Field(..., description="Parent document identifier")
    parent_chunk_id: str | None = Field(
        default=None, description="Optional parent section chunk ID for context expansion"
    )
    chunk_index: int = Field(..., description="Ordinal position of chunk within document")
    content: str = Field(..., description="Chunk text content used for retrieval and synthesis")
    parent_content: str | None = Field(
        default=None, description="Enriched parent section content providing broader context"
    )
    section_path: str = Field(
        default="", description="Hierarchical section path (e.g. HR > Leaves > Sick Leave)"
    )
    title: str = Field(default="Untitled Document", description="Parent document title")
    source: str = Field(default="local_folder", description="Source system connector name")
    source_url: str = Field(default="", description="Deep link URL to document or section")
    author: str = Field(default="System", description="Document author")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: str = Field(default="1.0", description="Document version string")
    doc_status: DocStatus = Field(default=DocStatus.APPROVED, description="Lifecycle status")
    authority_score: float = Field(default=0.8, description="Credibility score")
    language: str = Field(default="en", description="Language code")
    owner_group: str = Field(default="group_all", description="Owning group")
    acl: DocumentACL = Field(..., description="Chunk-level ACL inherited from document/section")
    pii_flags: list[str] = Field(
        default_factory=list, description="PII categories detected in this chunk"
    )
    dense_vector: list[float] | None = Field(default=None, description="Dense embedding vector")
    sparse_vector: dict[int, float] | None = Field(
        default=None, description="Sparse vector (token_id -> weight)"
    )
    tenant_id: str = Field(default="tenant-nimbus-default", description="Tenant scope")


class SyncStatus(StrEnum):
    """Ingestion sync job status states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeadLetterItem(BaseModel):
    """Failed item record stored in dead-letter queue for inspection and replay."""

    id: str = Field(..., description="DLQ entry ID")
    job_id: str = Field(..., description="Ingestion job ID")
    source: str = Field(..., description="Connector source")
    doc_id: str = Field(..., description="Document identifier that failed")
    error_message: str = Field(..., description="Root cause error details")
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Raw document or task payload"
    )
    retry_count: int = Field(default=0, description="Number of retry attempts")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
