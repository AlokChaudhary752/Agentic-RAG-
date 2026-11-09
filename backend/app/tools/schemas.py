"""Pydantic schemas and metadata specifications for Model Context Protocol (MCP) tools."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ToolRiskLevel(StrEnum):
    """Tool risk categorization determining execution policy and approval gates."""

    READ = "read"  # Pure read-only: automatic execution
    WRITE_LOW = "write_low"  # Low-impact write: auto-execute with compliance audit log
    WRITE_HIGH = "write_high"  # High-impact write: requires human-in-the-loop approval


class SearchKnowledgeInput(BaseModel):
    """Input payload for searching enterprise knowledge base."""

    query: str = Field(..., description="Search query string")
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum chunks to retrieve")


class SearchKnowledgeOutput(BaseModel):
    """Output results from permission-filtered knowledge retrieval."""

    query: str
    total_found: int
    results: list[dict[str, Any]] = Field(default_factory=list)


class GetDocumentInput(BaseModel):
    """Input payload for retrieving a specific document by its unique ID."""

    doc_id: str = Field(..., description="Unique document identifier")


class GetDocumentOutput(BaseModel):
    """Output representation of an authorized document."""

    doc_id: str
    title: str
    source: str
    source_url: str
    content: str
    doc_status: str
    authority_score: float
    updated_at: str
    classification_level: str


class CreateJiraTicketInput(BaseModel):
    """Input payload for creating a Jira issue."""

    project: str = Field(default="NIMBUS", description="Jira project key (e.g. NIMBUS, ENG, SEC)")
    summary: str = Field(..., min_length=5, max_length=255, description="Short issue summary")
    description: str = Field(..., min_length=10, description="Detailed problem description")
    priority: str = Field(
        default="Medium", description="Priority level: Lowest, Low, Medium, High, Highest"
    )
    issue_type: str = Field(default="Task", description="Issue type: Bug, Task, Story, Incident")
    idempotency_key: str | None = Field(
        default=None, description="Optional unique client token to prevent duplicate creation"
    )


class CreateJiraTicketOutput(BaseModel):
    """Result of Jira ticket creation."""

    ticket_id: str
    project: str
    summary: str
    priority: str
    status: str
    reporter: str
    created_at: str
    url: str


class GetTicketStatusInput(BaseModel):
    """Input payload for checking ticket progress."""

    ticket_id: str = Field(..., description="Issue identifier (e.g. NIMBUS-1042)")


class GetTicketStatusOutput(BaseModel):
    """Current status and metadata of an enterprise ticket."""

    ticket_id: str
    summary: str
    status: str
    priority: str
    assignee: str | None
    created_at: str
    updated_at: str


class ListRecentChangesInput(BaseModel):
    """Input payload for querying recently modified documents."""

    days_back: int = Field(default=7, ge=1, le=90, description="Lookback window in days")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum documents to return")


class ListRecentChangesOutput(BaseModel):
    """List of recently updated documents accessible to the calling user."""

    days_back: int
    total: int
    documents: list[dict[str, Any]] = Field(default_factory=list)


class SendSummaryEmailInput(BaseModel):
    """Input payload for dispatching a synthesis email to an employee."""

    recipient_email: str = Field(..., description="Destination corporate email address")
    subject: str = Field(..., min_length=3, max_length=255, description="Email subject line")
    body: str = Field(..., min_length=10, description="Formatted email content")
    idempotency_key: str | None = Field(default=None, description="Idempotency token")


class SendSummaryEmailOutput(BaseModel):
    """Confirmation receipt of dispatched email."""

    delivery_id: str
    recipient: str
    subject: str
    status: str = "sent"
    sent_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class ToolCallResult(BaseModel):
    """Standardized response container for all MCP tool invocations."""

    tool_name: str
    risk_level: ToolRiskLevel
    caller_user_id: str
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    execution_time_ms: float = 0.0
    idempotency_key: str | None = None
