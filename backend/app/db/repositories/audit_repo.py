"""Immutable repository for recording and querying security and retrieval audit events."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLogEntity


class AuditRepository:
    """Provides append-only persistence and query capabilities for enterprise audit events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log_event(
        self,
        user_id: str,
        query: str,
        tenant_id: str = "tenant-nimbus-default",
        user_email: str | None = None,
        retrieved_chunk_ids: list[str] | None = None,
        tool_called: str | None = None,
        tool_risk_level: str | None = None,
        action_approved: bool | None = None,
        severity: str = "INFO",
        correlation_id: str | None = None,
        client_ip: str | None = None,
        metadata_payload: dict[str, Any] | None = None,
    ) -> AuditLogEntity:
        """Append an immutable audit entry to the persistent audit log."""
        entity = AuditLogEntity(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            user_email=user_email,
            query=query,
            retrieved_chunk_ids=retrieved_chunk_ids or [],
            tool_called=tool_called,
            tool_risk_level=tool_risk_level,
            action_approved=action_approved,
            severity=severity,
            correlation_id=correlation_id,
            client_ip=client_ip,
            metadata_payload=metadata_payload or {},
        )
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def list_logs(
        self,
        tenant_id: str,
        user_id: str | None = None,
        severity: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLogEntity]:
        """Query audit log history with optional user and severity filtering."""
        stmt = (
            select(AuditLogEntity)
            .where(AuditLogEntity.tenant_id == tenant_id)
            .order_by(AuditLogEntity.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        if user_id:
            stmt = stmt.where(AuditLogEntity.user_id == user_id)
        if severity:
            stmt = stmt.where(AuditLogEntity.severity == severity)

        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    def update(self, *args: Any, **kwargs: Any) -> None:
        """Enforce append-only constraint: updates are strictly forbidden."""
        raise PermissionError("Audit logs are strictly immutable and cannot be updated.")

    def delete(self, *args: Any, **kwargs: Any) -> None:
        """Enforce append-only constraint: deletions are strictly forbidden."""
        raise PermissionError("Audit logs are strictly immutable and cannot be deleted.")

