"""Enterprise Model Context Protocol (MCP) Client.

Provides governed client-side invocation with tool allow-lists, schema validation,
risk gating, execution timeouts, retries, idempotency caching, and compliance auditing.
"""

import asyncio
import time
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.errors import ForbiddenError, NotFoundError, PermissionLeakError
from app.core.logging import get_logger
from app.domain.models import UserPrincipal
from app.governance.audit_service import AuditService
from app.tools.schemas import (
    CreateJiraTicketInput,
    GetDocumentInput,
    GetTicketStatusInput,
    ListRecentChangesInput,
    SearchKnowledgeInput,
    SendSummaryEmailInput,
    ToolCallResult,
    ToolRiskLevel,
)
from app.tools.server import EnterpriseMCPServer, get_enterprise_mcp_server

logger = get_logger(__name__)

# Schema map for input argument validation
TOOL_INPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "search_knowledge": SearchKnowledgeInput,
    "get_document": GetDocumentInput,
    "create_jira_ticket": CreateJiraTicketInput,
    "get_ticket_status": GetTicketStatusInput,
    "list_recent_changes": ListRecentChangesInput,
    "send_summary_email": SendSummaryEmailInput,
}

# Policy-defined risk levels for enterprise tools
TOOL_RISK_MAP: dict[str, ToolRiskLevel] = {
    "search_knowledge": ToolRiskLevel.READ,
    "get_document": ToolRiskLevel.READ,
    "get_ticket_status": ToolRiskLevel.READ,
    "list_recent_changes": ToolRiskLevel.READ,
    "send_summary_email": ToolRiskLevel.WRITE_LOW,
    "create_jira_ticket": ToolRiskLevel.WRITE_HIGH,
}

# Default permitted tool allow-list
DEFAULT_ALLOWED_TOOLS: set[str] = {
    "search_knowledge",
    "get_document",
    "create_jira_ticket",
    "get_ticket_status",
    "list_recent_changes",
    "send_summary_email",
}


class MCPClient:
    """Enterprise client managing tool invocations with strict governance and safety checks."""

    def __init__(
        self,
        server: EnterpriseMCPServer | None = None,
        allowed_tools: set[str] | None = None,
        default_timeout_seconds: float = 10.0,
        max_retries: int = 2,
        audit_service: AuditService | None = None,
    ) -> None:
        self.server = server or get_enterprise_mcp_server()
        self.allowed_tools = set(allowed_tools or DEFAULT_ALLOWED_TOOLS)
        self.default_timeout_seconds = default_timeout_seconds
        self.max_retries = max_retries
        self.audit_service = audit_service
        self._idempotency_cache: dict[str, ToolCallResult] = {}

    def get_tool_risk(self, tool_name: str) -> ToolRiskLevel:
        """Retrieve risk classification level for a given tool name."""
        return TOOL_RISK_MAP.get(tool_name, ToolRiskLevel.WRITE_HIGH)

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check whether a tool exists in the active client allow-list."""
        return tool_name in self.allowed_tools

    def validate_input(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Validate input arguments against the registered Pydantic schema."""
        schema_cls = TOOL_INPUT_SCHEMAS.get(tool_name)
        if schema_cls:
            validated = schema_cls.model_validate(arguments)
            return validated.model_dump()
        return arguments

    # =========================================================================
    # SYNCHRONOUS EXECUTION INTERFACE
    # =========================================================================

    def execute_sync(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        principal: UserPrincipal,
        approval_granted: bool = False,
        correlation_id: str | None = None,
    ) -> ToolCallResult:
        """Synchronously execute an MCP tool with full governance pipeline."""
        start_time = time.perf_counter()
        risk_level = self.get_tool_risk(tool_name)

        # 1. Allow-list check
        if not self.is_tool_allowed(tool_name):
            logger.warning("Tool execution blocked by allow-list", tool=tool_name, user=principal.user_id)
            return ToolCallResult(
                tool_name=tool_name,
                risk_level=risk_level,
                caller_user_id=principal.user_id,
                success=False,
                error=f"Tool '{tool_name}' is not in the allowed tools list.",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 2. Input Schema Validation
        try:
            validated_args = self.validate_input(tool_name, arguments)
        except ValidationError as e:
            logger.warning("Tool schema validation failed", tool=tool_name, err=str(e))
            return ToolCallResult(
                tool_name=tool_name,
                risk_level=risk_level,
                caller_user_id=principal.user_id,
                success=False,
                error=f"Input validation error for tool '{tool_name}': {e.errors()}",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 3. Risk-level human approval gate
        if risk_level == ToolRiskLevel.WRITE_HIGH and not approval_granted:
            logger.info("Human approval required before executing tool", tool=tool_name, user=principal.user_id)
            return ToolCallResult(
                tool_name=tool_name,
                risk_level=risk_level,
                caller_user_id=principal.user_id,
                success=False,
                error=f"Execution blocked: High-risk action '{tool_name}' requires human approval.",
                data={"approval_required": True, "tool_name": tool_name, "arguments": validated_args},
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 4. Idempotency Check
        idempotency_key = validated_args.get("idempotency_key")
        cache_key = None
        if idempotency_key:
            cache_key = f"{tool_name}:{principal.user_id}:{idempotency_key}"
            if cache_key in self._idempotency_cache:
                logger.info("Returning cached tool call result from idempotency key", key=cache_key)
                return self._idempotency_cache[cache_key]

        # 5. Execution with retry logic
        attempts = 0
        last_error: Exception | None = None
        result_data: dict[str, Any] | None = None

        while attempts <= self.max_retries:
            attempts += 1
            try:
                result_data = self.server.call_tool_sync(
                    tool_name=tool_name,
                    arguments=validated_args,
                    principal=principal,
                )
                last_error = None
                break
            except (ForbiddenError, NotFoundError, PermissionLeakError) as e:
                # Do not retry non-transient authorization or resource errors
                last_error = e
                break
            except Exception as e:
                last_error = e
                logger.warning(
                    "Transient tool execution failure, retrying",
                    attempt=attempts,
                    tool=tool_name,
                    err=str(e),
                )
                if attempts <= self.max_retries:
                    time.sleep(0.05 * (2 ** (attempts - 1)))

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        if last_error is not None:
            return ToolCallResult(
                tool_name=tool_name,
                risk_level=risk_level,
                caller_user_id=principal.user_id,
                success=False,
                error=str(last_error),
                execution_time_ms=elapsed_ms,
                idempotency_key=idempotency_key,
            )

        call_result = ToolCallResult(
            tool_name=tool_name,
            risk_level=risk_level,
            caller_user_id=principal.user_id,
            success=True,
            data=result_data,
            execution_time_ms=elapsed_ms,
            idempotency_key=idempotency_key,
        )

        if cache_key:
            self._idempotency_cache[cache_key] = call_result

        return call_result

    # =========================================================================
    # ASYNCHRONOUS EXECUTION INTERFACE
    # =========================================================================

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        principal: UserPrincipal,
        approval_granted: bool = False,
        correlation_id: str | None = None,
    ) -> ToolCallResult:
        """Asynchronously execute an MCP tool with full governance pipeline."""
        start_time = time.perf_counter()
        risk_level = self.get_tool_risk(tool_name)

        # 1. Allow-list check
        if not self.is_tool_allowed(tool_name):
            logger.warning("Tool execution blocked by allow-list", tool=tool_name, user=principal.user_id)
            return ToolCallResult(
                tool_name=tool_name,
                risk_level=risk_level,
                caller_user_id=principal.user_id,
                success=False,
                error=f"Tool '{tool_name}' is not in the allowed tools list.",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 2. Input Schema Validation
        try:
            validated_args = self.validate_input(tool_name, arguments)
        except ValidationError as e:
            logger.warning("Tool schema validation failed", tool=tool_name, err=str(e))
            return ToolCallResult(
                tool_name=tool_name,
                risk_level=risk_level,
                caller_user_id=principal.user_id,
                success=False,
                error=f"Input validation error for tool '{tool_name}': {e.errors()}",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 3. Risk-level human approval gate
        if risk_level == ToolRiskLevel.WRITE_HIGH and not approval_granted:
            logger.info("Human approval required before executing tool", tool=tool_name, user=principal.user_id)
            return ToolCallResult(
                tool_name=tool_name,
                risk_level=risk_level,
                caller_user_id=principal.user_id,
                success=False,
                error=f"Execution blocked: High-risk action '{tool_name}' requires human approval.",
                data={"approval_required": True, "tool_name": tool_name, "arguments": validated_args},
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 4. Idempotency Check
        idempotency_key = validated_args.get("idempotency_key")
        cache_key = None
        if idempotency_key:
            cache_key = f"{tool_name}:{principal.user_id}:{idempotency_key}"
            if cache_key in self._idempotency_cache:
                logger.info("Returning cached tool call result from idempotency key", key=cache_key)
                return self._idempotency_cache[cache_key]

        # 5. Execution with timeout & retry logic
        attempts = 0
        last_error: Exception | None = None
        result_data: dict[str, Any] | None = None

        while attempts <= self.max_retries:
            attempts += 1
            try:
                result_data = await asyncio.wait_for(
                    self.server.call_tool(
                        tool_name=tool_name,
                        arguments=validated_args,
                        principal=principal,
                    ),
                    timeout=self.default_timeout_seconds,
                )
                last_error = None
                break
            except (ForbiddenError, NotFoundError, PermissionLeakError) as e:
                last_error = e
                break
            except Exception as e:
                last_error = e
                logger.warning(
                    "Transient async tool execution failure, retrying",
                    attempt=attempts,
                    tool=tool_name,
                    err=str(e),
                )
                if attempts <= self.max_retries:
                    await asyncio.sleep(0.05 * (2 ** (attempts - 1)))

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # 6. Audit logging for write operations if AuditService is configured
        if self.audit_service and risk_level in (ToolRiskLevel.WRITE_LOW, ToolRiskLevel.WRITE_HIGH):
            try:
                await self.audit_service.record_tool_call(
                    principal=principal,
                    query=validated_args.get("summary") or validated_args.get("subject") or tool_name,
                    tool_name=tool_name,
                    risk_level=risk_level.value,
                    approved=approval_granted,
                    tool_args=validated_args,
                    correlation_id=correlation_id,
                )
            except Exception as audit_err:
                logger.error("Failed recording audit log for tool call", err=str(audit_err))

        if last_error is not None:
            return ToolCallResult(
                tool_name=tool_name,
                risk_level=risk_level,
                caller_user_id=principal.user_id,
                success=False,
                error=str(last_error),
                execution_time_ms=elapsed_ms,
                idempotency_key=idempotency_key,
            )

        call_result = ToolCallResult(
            tool_name=tool_name,
            risk_level=risk_level,
            caller_user_id=principal.user_id,
            success=True,
            data=result_data,
            execution_time_ms=elapsed_ms,
            idempotency_key=idempotency_key,
        )

        if cache_key:
            self._idempotency_cache[cache_key] = call_result

        return call_result


# Singleton pattern for shared MCPClient instance
_client_instance: MCPClient | None = None


def get_mcp_client() -> MCPClient:
    """Get or initialize the shared MCPClient singleton."""
    global _client_instance
    if _client_instance is None:
        _client_instance = MCPClient()
    return _client_instance


def reset_mcp_client() -> None:
    """Reset the client singleton instance (primarily for test isolation)."""
    global _client_instance
    _client_instance = None

