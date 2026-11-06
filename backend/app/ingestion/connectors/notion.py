"""Notion connector supporting offline mock mode and production integration readiness."""

from datetime import datetime
from pathlib import Path

from app.domain.models import RawDocument
from app.ingestion.connectors.base import BaseConnector
from app.ingestion.connectors.local_folder import LocalFolderConnector


class NotionConnector(BaseConnector):
    """Connector for Notion workspace with mock directory backing."""

    def __init__(
        self,
        mock_dir: str | None = None,
        api_token: str | None = None,
        tenant_id: str = "tenant-nimbus-default",
    ) -> None:
        self.mock_dir = Path(mock_dir) if mock_dir else None
        self.api_token = api_token
        self.tenant_id = tenant_id

    @property
    def name(self) -> str:
        return "notion"

    async def test_connection(self) -> bool:
        if self.mock_dir and self.mock_dir.exists():
            return True
        return bool(self.api_token)

    async def fetch_documents(self) -> list[RawDocument]:
        if self.mock_dir and self.mock_dir.exists():
            folder_conn = LocalFolderConnector(str(self.mock_dir), tenant_id=self.tenant_id)
            docs = await folder_conn.fetch_documents()
            for doc in docs:
                doc.source = self.name
                doc.source_url = f"https://notion.so/nimbus/{doc.id}"
            return docs
        return []

    async def get_changes_since(self, checkpoint: datetime | None) -> list[RawDocument]:
        docs = await self.fetch_documents()
        if not checkpoint:
            return docs
        return [d for d in docs if d.updated_at > checkpoint]

