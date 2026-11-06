"""Enterprise audit logging service providing non-repudiation and compliance tracking."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import AuditLogEntity
from app.db.repositories.audit_repo import AuditRepository
from app.domain.models import UserPrincipal

logger = get_logger(__name__)


class AuditService:
    """Orchestrates structured compliance auditing across user queries, retrievals, and tools."""

    def __init__(self, session: AsyncSession) -> None:
        self.repo = AuditRepository(session)

    async def record_query_and_retrieval(
        self,
        principal: UserPrincipal,
        query: str,
        retrieved_chunk_ids: list[str],
        correlation_id: str | None = None,
        client_ip: str | None = None,
    ) -> AuditLogEntity:
        """Log a successful retrieval event with user principal and retrieved chunk IDs."""
        logger.info(
            "Audit: Retrieval executed",
            user_id=principal.user_id,
            chunk_count=len(retrieved_chunk_ids),
            correlation_id=correlation_id,
        )
        return await self.repo.log_event(
            user_id=principal.user_id,
            user_email=principal.email,
            tenant_id=principal.tenant_id,
            query=query,
            retrieved_chunk_ids=retrieved_chunk_ids,
            severity="INFO",
            correlation_id=correlation_id,
            client_ip=client_ip,
            metadata_payload={"groups": principal.groups, "clearance": principal.clearance.value},
        )

    async def record_tool_call(
        self,
        principal: UserPrincipal,
        query: str,
        tool_name: str,
        risk_level: str,
        approved: bool,
        tool_args: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> AuditLogEntity:
        """Log an MCP or internal tool call with approval status and risk profile."""
        severity = "WARNING" if risk_level == "write_high" and not approved else "INFO"
        logger.info(
            "Audit: Tool execution recorded",
            user_id=principal.user_id,
            tool=tool_name,
            risk_level=risk_level,
            approved=approved,
        )
        return await self.repo.log_event(
            user_id=principal.user_id,
            user_email=principal.email,
            tenant_id=principal.tenant_id,
            query=query,
            tool_called=tool_name,
            tool_risk_level=risk_level,
            action_approved=approved,
            severity=severity,
            correlation_id=correlation_id,
            metadata_payload=tool_args or {},
        )

    async def record_security_alert(
        self,
        principal: UserPrincipal,
        event_type: str,
        details: str,
        query: str = "",
        correlation_id: str | None = None,
    ) -> AuditLogEntity:
        """Log critical security events (permission leaks, injection attempts, policy violations)."""
        logger.error(
            "Audit: Security alert triggered",
            user_id=principal.user_id,
            event_type=event_type,
            details=details,
        )
        return await self.repo.log_event(
            user_id=principal.user_id,
            user_email=principal.email,
            tenant_id=principal.tenant_id,
            query=query or f"[SECURITY ALERT: {event_type}]",
            severity="CRITICAL",
            correlation_id=correlation_id,
            metadata_payload={"event_type": event_type, "details": details},
        )

