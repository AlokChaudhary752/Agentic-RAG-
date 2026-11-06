"""Confluence, Slack, and Jira enterprise connectors."""

from datetime import datetime
from pathlib import Path

from app.domain.models import RawDocument
from app.ingestion.connectors.base import BaseConnector
from app.ingestion.connectors.local_folder import LocalFolderConnector


class ConfluenceConnector(BaseConnector):
    """Confluence wiki connector with mock directory support."""

    def __init__(
        self, mock_dir: str | None = None, tenant_id: str = "tenant-nimbus-default"
    ) -> None:
        self.mock_dir = Path(mock_dir) if mock_dir else None
        self.tenant_id = tenant_id

    @property
    def name(self) -> str:
        return "confluence"

    async def test_connection(self) -> bool:
        return bool(self.mock_dir and self.mock_dir.exists())

    async def fetch_documents(self) -> list[RawDocument]:
        if not self.mock_dir or not self.mock_dir.exists():
            return []
        docs = await LocalFolderConnector(str(self.mock_dir), self.tenant_id).fetch_documents()
        for doc in docs:
            doc.source = self.name
            doc.source_url = f"https://confluence.nimbus.internal/display/SPACE/{doc.id}"
        return docs

    async def get_changes_since(self, checkpoint: datetime | None) -> list[RawDocument]:
        docs = await self.fetch_documents()
        if not checkpoint:
            return docs
        return [d for d in docs if d.updated_at > checkpoint]


class SlackConnector(BaseConnector):
    """Slack conversation and canvas connector with mock directory support."""

    def __init__(
        self, mock_dir: str | None = None, tenant_id: str = "tenant-nimbus-default"
    ) -> None:
        self.mock_dir = Path(mock_dir) if mock_dir else None
        self.tenant_id = tenant_id

    @property
    def name(self) -> str:
        return "slack"

    async def test_connection(self) -> bool:
        return bool(self.mock_dir and self.mock_dir.exists())

    async def fetch_documents(self) -> list[RawDocument]:
        if not self.mock_dir or not self.mock_dir.exists():
            return []
        docs = await LocalFolderConnector(str(self.mock_dir), self.tenant_id).fetch_documents()
        for doc in docs:
            doc.source = self.name
            doc.source_url = f"https://nimbus.slack.com/archives/C012345/{doc.id}"
        return docs

    async def get_changes_since(self, checkpoint: datetime | None) -> list[RawDocument]:
        docs = await self.fetch_documents()
        if not checkpoint:
            return docs
        return [d for d in docs if d.updated_at > checkpoint]


class JiraConnector(BaseConnector):
    """Jira issues and project knowledge connector with mock directory support."""

    def __init__(
        self, mock_dir: str | None = None, tenant_id: str = "tenant-nimbus-default"
    ) -> None:
        self.mock_dir = Path(mock_dir) if mock_dir else None
        self.tenant_id = tenant_id

    @property
    def name(self) -> str:
        return "jira"

    async def test_connection(self) -> bool:
        return bool(self.mock_dir and self.mock_dir.exists())

    async def fetch_documents(self) -> list[RawDocument]:
        if not self.mock_dir or not self.mock_dir.exists():
            return []
        docs = await LocalFolderConnector(str(self.mock_dir), self.tenant_id).fetch_documents()
        for doc in docs:
            doc.source = self.name
            doc.source_url = f"https://nimbus.atlassian.net/browse/{doc.id}"
        return docs

    async def get_changes_since(self, checkpoint: datetime | None) -> list[RawDocument]:
        docs = await self.fetch_documents()
        if not checkpoint:
            return docs
        return [d for d in docs if d.updated_at > checkpoint]
