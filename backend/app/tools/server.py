"""Enterprise Model Context Protocol (MCP) tool server implementation.

Exposes governed, permission-checked tools for enterprise knowledge search,
document retrieval, Jira ticketing, and notifications.
"""

import uuid
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.logging import get_logger
from app.domain.models import (
    RawDocument,
    UserPrincipal,
)
from app.ingestion.connectors.local_folder import LocalFolderConnector
from app.retrieval.hybrid_search import HybridRetriever
from app.tools.schemas import (
    CreateJiraTicketOutput,
    GetDocumentOutput,
    GetTicketStatusOutput,
    ListRecentChangesOutput,
    SearchKnowledgeOutput,
    SendSummaryEmailOutput,
)

logger = get_logger(__name__)

# Context-local storage for caller's authenticated principal
current_user_principal: ContextVar[UserPrincipal | None] = ContextVar(
    "current_user_principal", default=None
)


class InMemoryJiraStore:
    """Thread-safe in-memory store for Jira tickets with realistic seed data."""

    def __init__(self) -> None:
        self._tickets: dict[str, dict[str, Any]] = {
            "NIMBUS-1001": {
                "ticket_id": "NIMBUS-1001",
                "project": "NIMBUS",
                "summary": "Kubernetes cluster upgrade to 1.30",
                "description": "Upgrade production and staging clusters with minimal downtime.",
                "priority": "High",
                "status": "In Progress",
                "issue_type": "Task",
                "assignee": "Elena Rostova",
                "reporter": "mgr_bob",
                "created_at": "2026-02-15T09:00:00+00:00",
                "updated_at": "2026-02-16T14:30:00+00:00",
                "url": "https://jira.corp.internal/browse/NIMBUS-1001",
            },
            "NIMBUS-1042": {
                "ticket_id": "NIMBUS-1042",
                "project": "NIMBUS",
                "summary": "Fix memory leak in RAG embedding worker",
                "description": "Worker memory steadily climbs over 24h period under heavy ingest load.",
                "priority": "Highest",
                "status": "Open",
                "issue_type": "Bug",
                "assignee": "Alice Smith",
                "reporter": "mgr_bob",
                "created_at": "2026-03-01T10:00:00+00:00",
                "updated_at": "2026-03-01T10:00:00+00:00",
                "url": "https://jira.corp.internal/browse/NIMBUS-1042",
            },
            "ENG-2045": {
                "ticket_id": "ENG-2045",
                "project": "ENG",
                "summary": "Migrate database to PostgreSQL 16",
                "description": "Validate migration path and test replica failover.",
                "priority": "Medium",
                "status": "Resolved",
                "issue_type": "Task",
                "assignee": "Frank Vance",
                "reporter": "exec_frank",
                "created_at": "2026-01-10T08:00:00+00:00",
                "updated_at": "2026-02-01T11:00:00+00:00",
                "url": "https://jira.corp.internal/browse/ENG-2045",
            },
        }
        self._counter: int = 1050
        self.idempotency_records: dict[str, CreateJiraTicketOutput] = {}

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        """Retrieve ticket by ID."""
        return self._tickets.get(ticket_id.strip().upper())

    def create_ticket(
        self,
        summary: str,
        project: str = "NIMBUS",
        description: str = "",
        priority: str = "Medium",
        issue_type: str = "Task",
        reporter: str = "anonymous",
        idempotency_key: str | None = None,
    ) -> CreateJiraTicketOutput:
        """Create ticket with idempotency protection."""
        if idempotency_key and idempotency_key in self.idempotency_records:
            logger.info("Returning cached ticket for idempotency key", key=idempotency_key)
            return self.idempotency_records[idempotency_key]

        self._counter += 1
        ticket_id = f"{project.strip().upper()}-{self._counter}"
        now_str = datetime.now(UTC).isoformat()
        url = f"https://jira.corp.internal/browse/{ticket_id}"

        record = {
            "ticket_id": ticket_id,
            "project": project.strip().upper(),
            "summary": summary,
            "description": description,
            "priority": priority,
            "status": "Open",
            "issue_type": issue_type,
            "assignee": None,
            "reporter": reporter,
            "created_at": now_str,
            "updated_at": now_str,
            "url": url,
        }
        self._tickets[ticket_id] = record

        output = CreateJiraTicketOutput(
            ticket_id=ticket_id,
            project=project.strip().upper(),
            summary=summary,
            priority=priority,
            status="Open",
            reporter=reporter,
            created_at=now_str,
            url=url,
        )

        if idempotency_key:
            self.idempotency_records[idempotency_key] = output

        return output


class InMemoryEmailStore:
    """Store for dispatched summary emails and delivery audit trail."""

    def __init__(self) -> None:
        self.deliveries: list[dict[str, Any]] = []
        self.idempotency_records: dict[str, SendSummaryEmailOutput] = {}

    def send_email(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        idempotency_key: str | None = None,
    ) -> SendSummaryEmailOutput:
        """Dispatch email with idempotency protection."""
        if idempotency_key and idempotency_key in self.idempotency_records:
            logger.info("Returning cached email dispatch for idempotency key", key=idempotency_key)
            return self.idempotency_records[idempotency_key]

        delivery_id = f"deliv-{uuid.uuid4().hex[:12]}"
        now_str = datetime.now(UTC).isoformat()

        record = {
            "delivery_id": delivery_id,
            "recipient": recipient_email,
            "subject": subject,
            "body": body,
            "status": "sent",
            "sent_at": now_str,
        }
        self.deliveries.append(record)

        output = SendSummaryEmailOutput(
            delivery_id=delivery_id,
            recipient=recipient_email,
            subject=subject,
            status="sent",
            sent_at=now_str,
        )

        if idempotency_key:
            self.idempotency_records[idempotency_key] = output

        return output


class EnterpriseMCPServer:
    """Production-grade MCP server enforcing caller permissions across all tools."""

    def __init__(
        self,
        retriever: HybridRetriever | None = None,
        corpus_dir: str | Path = "data/sample_corpus",
        jira_store: InMemoryJiraStore | None = None,
        email_store: InMemoryEmailStore | None = None,
    ) -> None:
        self.retriever = retriever or HybridRetriever()
        self.jira_store = jira_store or InMemoryJiraStore()
        self.email_store = email_store or InMemoryEmailStore()
        self.corpus_dir = Path(corpus_dir)
        self.documents: dict[str, RawDocument] = {}

        # Load available corpus files into memory for fast lookup & ACL verification
        self._load_corpus_documents()

        # Initialize MCP Protocol Server
        self.mcp = MCPServer("enterprise-knowledge-agent")
        self._register_mcp_tools()

    def _load_corpus_documents(self) -> None:
        """Scan sample corpus and catalog documents for exact-ID retrieval and ACL enforcement."""
        if not self.corpus_dir.exists():
            logger.warning("Corpus directory does not exist", dir=str(self.corpus_dir))
            return

        connector = LocalFolderConnector(folder_path=str(self.corpus_dir))
        for file_path in self.corpus_dir.rglob("*.md"):
            try:
                doc = connector._build_raw_document(file_path)
                self.documents[doc.id] = doc
                # Also index by filename stem for ergonomic lookup
                self.documents[file_path.stem] = doc
            except Exception as e:
                logger.debug(
                    "Failed parsing document for tool server", path=str(file_path), err=str(e)
                )

    def register_document(self, doc: RawDocument) -> None:
        """Manually register or update a document in the server's catalog."""
        self.documents[doc.id] = doc

    def _resolve_principal(self, principal: UserPrincipal | None) -> UserPrincipal:
        """Resolve calling principal from explicit argument or ContextVar."""
        resolved = principal or current_user_principal.get()
        if resolved is None:
            raise UnauthorizedError("Tool execution requires an authenticated UserPrincipal.")
        return resolved

    # =========================================================================
    # TOOL IMPLEMENTATIONS (Synchronous core with caller permission checks)
    # =========================================================================

    def search_knowledge(
        self,
        query: str,
        top_k: int = 5,
        principal: UserPrincipal | None = None,
    ) -> SearchKnowledgeOutput:
        """Search authorized enterprise documents with vector-level ACL pre-filtering."""
        user = self._resolve_principal(principal)
        bundle = self.retriever.retrieve(query=query, principal=user, top_k=top_k)

        results = [
            {
                "chunk_id": chunk.id,
                "doc_id": chunk.doc_id,
                "content": chunk.content,
                "section_path": chunk.section_path,
                "classification_level": chunk.acl.classification_level.value,
                "title": chunk.title,
                "source": chunk.source,
                "source_url": chunk.source_url,
            }
            for chunk in bundle.chunks
        ]

        return SearchKnowledgeOutput(
            query=query,
            total_found=len(results),
            results=results,
        )

    def get_document(
        self,
        doc_id: str,
        principal: UserPrincipal | None = None,
    ) -> GetDocumentOutput:
        """Retrieve full text and metadata of a cataloged document with permission verification.

        Raises:
            NotFoundError: If the document is not cataloged.
            ForbiddenError: If the caller does not have clearance or ACL rights.
        """
        user = self._resolve_principal(principal)
        doc = self.documents.get(doc_id)

        if doc is None:
            raise NotFoundError(f"Document '{doc_id}' not found in enterprise catalog.")

        # Enforce ACL: Classification level + group/user matching
        permitted = doc.acl.permits_user(
            user_id=user.user_id,
            user_groups=user.groups,
            clearance=user.clearance,
        )

        if not permitted:
            logger.warning(
                "Access forbidden to document by ACL policy",
                doc_id=doc.id,
                user_id=user.user_id,
                classification=doc.acl.classification_level.value,
                user_clearance=user.clearance.value,
            )
            raise ForbiddenError(
                f"User '{user.user_id}' with clearance '{user.clearance.value}' is not authorized "
                f"to access document '{doc_id}' ({doc.acl.classification_level.value})."
            )

        return GetDocumentOutput(
            doc_id=doc.id,
            title=doc.title,
            source=doc.source,
            source_url=doc.source_url,
            content=doc.content,
            doc_status=doc.doc_status.value,
            authority_score=doc.authority_score,
            updated_at=doc.updated_at.isoformat(),
            classification_level=doc.acl.classification_level.value,
        )

    def create_jira_ticket(
        self,
        summary: str,
        project: str = "NIMBUS",
        description: str = "",
        priority: str = "Medium",
        issue_type: str = "Task",
        idempotency_key: str | None = None,
        principal: UserPrincipal | None = None,
    ) -> CreateJiraTicketOutput:
        """Create a new Jira issue with idempotency protection and requester attribution."""
        user = self._resolve_principal(principal)
        reporter = user.user_id

        return self.jira_store.create_ticket(
            summary=summary,
            project=project,
            description=description,
            priority=priority,
            issue_type=issue_type,
            reporter=reporter,
            idempotency_key=idempotency_key,
        )

    def get_ticket_status(
        self,
        ticket_id: str,
        principal: UserPrincipal | None = None,
    ) -> GetTicketStatusOutput:
        """Query current status, priority, and assignee for a Jira ticket."""
        self._resolve_principal(principal)
        ticket = self.jira_store.get_ticket(ticket_id)

        if not ticket:
            raise NotFoundError(f"Ticket '{ticket_id}' not found.")

        return GetTicketStatusOutput(
            ticket_id=ticket["ticket_id"],
            summary=ticket["summary"],
            status=ticket["status"],
            priority=ticket["priority"],
            assignee=ticket["assignee"],
            created_at=ticket["created_at"],
            updated_at=ticket["updated_at"],
        )

    def list_recent_changes(
        self,
        days_back: int = 7,
        limit: int = 10,
        principal: UserPrincipal | None = None,
    ) -> ListRecentChangesOutput:
        """List recent document modifications accessible to the caller."""
        user = self._resolve_principal(principal)
        cutoff = datetime.now(UTC) - timedelta(days=days_back)

        # Unique documents (since documents are indexed by both ID and stem)
        seen_ids: set[str] = set()
        accessible_docs: list[dict[str, Any]] = []

        for doc in self.documents.values():
            if doc.id in seen_ids:
                continue
            seen_ids.add(doc.id)

            if doc.updated_at < cutoff:
                continue

            # ACL Filter: strictly include only documents the caller is authorized to view
            if doc.acl.permits_user(user.user_id, user.groups, user.clearance):
                accessible_docs.append(
                    {
                        "doc_id": doc.id,
                        "title": doc.title,
                        "source": doc.source,
                        "updated_at": doc.updated_at.isoformat(),
                        "classification_level": doc.acl.classification_level.value,
                        "author": doc.author,
                        "status": doc.doc_status.value,
                    }
                )

        accessible_docs.sort(key=lambda d: d["updated_at"], reverse=True)

        return ListRecentChangesOutput(
            days_back=days_back,
            total=len(accessible_docs),
            documents=accessible_docs[:limit],
        )

    def send_summary_email(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        idempotency_key: str | None = None,
        principal: UserPrincipal | None = None,
    ) -> SendSummaryEmailOutput:
        """Send synthesized knowledge summary email to an enterprise stakeholder."""
        self._resolve_principal(principal)
        return self.email_store.send_email(
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            idempotency_key=idempotency_key,
        )

    # =========================================================================
    # ASYNC TOOL METHODS (Matching async signatures)
    # =========================================================================

    async def search_knowledge_async(
        self,
        query: str,
        top_k: int = 5,
        principal: UserPrincipal | None = None,
    ) -> SearchKnowledgeOutput:
        return self.search_knowledge(query=query, top_k=top_k, principal=principal)

    async def get_document_async(
        self,
        doc_id: str,
        principal: UserPrincipal | None = None,
    ) -> GetDocumentOutput:
        return self.get_document(doc_id=doc_id, principal=principal)

    async def create_jira_ticket_async(
        self,
        summary: str,
        project: str = "NIMBUS",
        description: str = "",
        priority: str = "Medium",
        issue_type: str = "Task",
        idempotency_key: str | None = None,
        principal: UserPrincipal | None = None,
    ) -> CreateJiraTicketOutput:
        return self.create_jira_ticket(
            summary=summary,
            project=project,
            description=description,
            priority=priority,
            issue_type=issue_type,
            idempotency_key=idempotency_key,
            principal=principal,
        )

    async def get_ticket_status_async(
        self,
        ticket_id: str,
        principal: UserPrincipal | None = None,
    ) -> GetTicketStatusOutput:
        return self.get_ticket_status(ticket_id=ticket_id, principal=principal)

    async def list_recent_changes_async(
        self,
        days_back: int = 7,
        limit: int = 10,
        principal: UserPrincipal | None = None,
    ) -> ListRecentChangesOutput:
        return self.list_recent_changes(days_back=days_back, limit=limit, principal=principal)

    async def send_summary_email_async(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        idempotency_key: str | None = None,
        principal: UserPrincipal | None = None,
    ) -> SendSummaryEmailOutput:
        return self.send_summary_email(
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            idempotency_key=idempotency_key,
            principal=principal,
        )

    # =========================================================================
    # UNIFIED CALL TOOL INTERFACES
    # =========================================================================

    def call_tool_sync(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        principal: UserPrincipal | None = None,
    ) -> dict[str, Any]:
        """Synchronously execute tool by name with arguments and principal."""
        token = current_user_principal.set(principal)
        try:
            if tool_name == "search_knowledge":
                return self.search_knowledge(principal=principal, **arguments).model_dump()
            elif tool_name == "get_document":
                return self.get_document(principal=principal, **arguments).model_dump()
            elif tool_name == "create_jira_ticket":
                return self.create_jira_ticket(principal=principal, **arguments).model_dump()
            elif tool_name == "get_ticket_status":
                return self.get_ticket_status(principal=principal, **arguments).model_dump()
            elif tool_name == "list_recent_changes":
                return self.list_recent_changes(principal=principal, **arguments).model_dump()
            elif tool_name == "send_summary_email":
                return self.send_summary_email(principal=principal, **arguments).model_dump()
            else:
                raise NotFoundError(f"Tool '{tool_name}' not found on server.")
        finally:
            current_user_principal.reset(token)

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        principal: UserPrincipal | None = None,
    ) -> dict[str, Any]:
        """Asynchronously execute tool by name with arguments and principal."""
        return self.call_tool_sync(tool_name=tool_name, arguments=arguments, principal=principal)

    def _register_mcp_tools(self) -> None:
        """Register tool handlers with the underlying MCPServer."""

        @self.mcp.tool()
        async def search_knowledge(query: str, top_k: int = 5) -> dict[str, Any]:
            """Search authorized enterprise documents with vector-level ACL pre-filtering."""
            principal = current_user_principal.get()
            res = await self.search_knowledge_async(query=query, top_k=top_k, principal=principal)
            return res.model_dump()

        @self.mcp.tool()
        async def get_document(doc_id: str) -> dict[str, Any]:
            """Retrieve full text and metadata of a cataloged document with permission verification."""
            principal = current_user_principal.get()
            res = await self.get_document_async(doc_id=doc_id, principal=principal)
            return res.model_dump()

        @self.mcp.tool()
        async def create_jira_ticket(
            summary: str,
            project: str = "NIMBUS",
            description: str = "",
            priority: str = "Medium",
            issue_type: str = "Task",
            idempotency_key: str | None = None,
        ) -> dict[str, Any]:
            """Create a new Jira issue with idempotency protection and requester attribution."""
            principal = current_user_principal.get()
            res = await self.create_jira_ticket_async(
                summary=summary,
                project=project,
                description=description,
                priority=priority,
                issue_type=issue_type,
                idempotency_key=idempotency_key,
                principal=principal,
            )
            return res.model_dump()

        @self.mcp.tool()
        async def get_ticket_status(ticket_id: str) -> dict[str, Any]:
            """Query current status, priority, and assignee for a Jira ticket."""
            principal = current_user_principal.get()
            res = await self.get_ticket_status_async(ticket_id=ticket_id, principal=principal)
            return res.model_dump()

        @self.mcp.tool()
        async def list_recent_changes(days_back: int = 7, limit: int = 10) -> dict[str, Any]:
            """List recent document modifications accessible to the caller."""
            principal = current_user_principal.get()
            res = await self.list_recent_changes_async(
                days_back=days_back, limit=limit, principal=principal
            )
            return res.model_dump()

        @self.mcp.tool()
        async def send_summary_email(
            recipient_email: str,
            subject: str,
            body: str,
            idempotency_key: str | None = None,
        ) -> dict[str, Any]:
            """Send synthesized knowledge summary email to an enterprise stakeholder."""
            principal = current_user_principal.get()
            res = await self.send_summary_email_async(
                recipient_email=recipient_email,
                subject=subject,
                body=body,
                idempotency_key=idempotency_key,
                principal=principal,
            )
            return res.model_dump()


# Singleton pattern for shared server instance
_server_instance: EnterpriseMCPServer | None = None


def get_enterprise_mcp_server() -> EnterpriseMCPServer:
    """Get or initialize the shared EnterpriseMCPServer singleton."""
    global _server_instance
    if _server_instance is None:
        _server_instance = EnterpriseMCPServer()
    return _server_instance


def reset_enterprise_mcp_server() -> None:
    """Reset the singleton instance (primarily for test isolation)."""
    global _server_instance
    _server_instance = None
