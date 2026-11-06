"""SQLAlchemy ORM models for PostgreSQL and SQLite persistence."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy entities."""

    type_annotation_map = {
        dict[str, Any]: JSON().with_variant(JSONB, "postgresql"),
        list[str]: JSON().with_variant(JSONB, "postgresql"),
    }


# Association table for User-Group Many-to-Many
user_groups = Table(
    "user_group_memberships",
    Base.metadata,
    Column("user_id", String(64), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", String(64), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
)


class UserEntity(Base):
    """User account entity storing corporate credentials, roles, and clearance level."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="employee")
    clearance: Mapped[str] = mapped_column(String(32), nullable=False, default="INTERNAL")
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="tenant-nimbus-default", index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    groups: Mapped[list["GroupEntity"]] = relationship(
        "GroupEntity", secondary=user_groups, back_populates="users", lazy="selectin"
    )


class GroupEntity(Base):
    """Organizational group or department entity."""

    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="tenant-nimbus-default", index=True
    )

    users: Mapped[list[UserEntity]] = relationship(
        "UserEntity", secondary=user_groups, back_populates="groups", lazy="selectin"
    )


class DocumentEntity(Base):
    """Cataloged corporate document tracking provenance, versioning, and ACLs."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="tenant-nimbus-default", index=True
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(String(1024), default="")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    author: Mapped[str] = mapped_column(String(255), default="")
    version: Mapped[str] = mapped_column(String(32), default="1.0")
    doc_status: Mapped[str] = mapped_column(String(32), default="approved", index=True)
    authority_score: Mapped[float] = mapped_column(Float, default=0.8)
    language: Mapped[str] = mapped_column(String(16), default="en")
    owner_group: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    allowed_users: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_groups: Mapped[list[str]] = mapped_column(JSON, default=list)
    classification_level: Mapped[str] = mapped_column(String(32), default="INTERNAL", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    chunks: Mapped[list["DocumentChunkEntity"]] = relationship(
        "DocumentChunkEntity",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class DocumentChunkEntity(Base):
    """Relational chunk tracking content, section path, and inherited ACL metadata."""

    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    doc_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_chunk_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    section_path: Mapped[str] = mapped_column(String(512), default="")
    allowed_users: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_groups: Mapped[list[str]] = mapped_column(JSON, default=list)
    classification_level: Mapped[str] = mapped_column(String(32), default="INTERNAL")
    pii_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    document: Mapped[DocumentEntity] = relationship("DocumentEntity", back_populates="chunks")


class IngestionJobEntity(Base):
    """Audit record of connector ingestion runs."""

    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="tenant-nimbus-default", index=True
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    docs_total: Mapped[int] = mapped_column(Integer, default=0)
    docs_indexed: Mapped[int] = mapped_column(Integer, default=0)
    docs_failed: Mapped[int] = mapped_column(Integer, default=0)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeadLetterEntity(Base):
    """Dead-letter queue table for failed document sync items."""

    __tablename__ = "dead_letter_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_id: Mapped[str] = mapped_column(String(128), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class AuditLogEntity(Base):
    """Immutable audit trail logging all query, retrieval, and tool execution events."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="tenant-nimbus-default", index=True
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    tool_called: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action_approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    severity: Mapped[str] = mapped_column(String(32), default="INFO", index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


# Composite indexes for high performance querying
Index("ix_documents_tenant_owner", DocumentEntity.tenant_id, DocumentEntity.owner_group)
Index("ix_chunks_doc_index", DocumentChunkEntity.doc_id, DocumentChunkEntity.chunk_index)
Index("ix_audit_tenant_time", AuditLogEntity.tenant_id, AuditLogEntity.timestamp.desc())
