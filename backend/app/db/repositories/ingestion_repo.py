"""Repository for Ingestion Jobs, Dead Letter Queue items, and Audit Logs."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLogEntity, DeadLetterEntity, IngestionJobEntity


class IngestionRepository:
    """Data access methods for ingestion lifecycle and audit trails."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_job(
        self, source: str, tenant_id: str = "tenant-nimbus-default"
    ) -> IngestionJobEntity:
        """Create a new ingestion job tracker."""
        job = IngestionJobEntity(
            id=f"job-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            source=source,
            status="running",
            docs_total=0,
            docs_indexed=0,
            docs_failed=0,
            started_at=datetime.now(UTC),
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        docs_total: int | None = None,
        docs_indexed: int | None = None,
        docs_failed: int | None = None,
        error_log: str | None = None,
    ) -> IngestionJobEntity | None:
        """Update progress counters and completion state of an ingestion job."""
        result = await self.session.execute(
            select(IngestionJobEntity).where(IngestionJobEntity.id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            return None

        job.status = status
        if docs_total is not None:
            job.docs_total = docs_total
        if docs_indexed is not None:
            job.docs_indexed = docs_indexed
        if docs_failed is not None:
            job.docs_failed = docs_failed
        if error_log is not None:
            job.error_log = error_log

        if status in ("completed", "failed", "cancelled"):
            job.finished_at = datetime.now(UTC)

        await self.session.flush()
        return job

    async def record_dead_letter(
        self,
        job_id: str,
        source: str,
        doc_id: str,
        error_message: str,
        payload: dict[str, Any] | None = None,
    ) -> DeadLetterEntity:
        """Persist a failed document payload into the Dead-Letter Queue (DLQ)."""
        dlq_item = DeadLetterEntity(
            id=f"dlq-{uuid.uuid4().hex[:12]}",
            job_id=job_id,
            source=source,
            doc_id=doc_id,
            error_message=error_message,
            payload=payload or {},
            retry_count=0,
            created_at=datetime.now(UTC),
        )
        self.session.add(dlq_item)
        await self.session.flush()
        return dlq_item

    async def record_audit_log(
        self,
        user_id: str,
        query: str,
        retrieved_chunk_ids: list[str],
        tool_called: str | None = None,
        tool_risk_level: str | None = None,
        action_approved: bool | None = None,
        severity: str = "INFO",
        tenant_id: str = "tenant-nimbus-default",
    ) -> AuditLogEntity:
        """Persist an immutable audit log record."""
        audit_entry = AuditLogEntity(
            id=f"audit-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            user_id=user_id,
            query=query,
            retrieved_chunk_ids=retrieved_chunk_ids,
            tool_called=tool_called,
            tool_risk_level=tool_risk_level,
            action_approved=action_approved,
            severity=severity,
            timestamp=datetime.now(UTC),
        )
        self.session.add(audit_entry)
        await self.session.flush()
        return audit_entry
