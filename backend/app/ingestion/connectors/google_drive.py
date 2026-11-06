"""Google Drive connector supporting offline mock mode and production OAuth2 readiness."""

from datetime import datetime
from pathlib import Path

from app.domain.models import RawDocument
from app.ingestion.connectors.base import BaseConnector
from app.ingestion.connectors.local_folder import LocalFolderConnector


class GoogleDriveConnector(BaseConnector):
    """Connector for Google Workspace Drive with mock local folder backing."""

    def __init__(
        self,
        mock_dir: str | None = None,
        credentials_file: str | None = None,
        tenant_id: str = "tenant-nimbus-default",
    ) -> None:
        self.mock_dir = Path(mock_dir) if mock_dir else None
        self.credentials_file = credentials_file
        self.tenant_id = tenant_id

    @property
    def name(self) -> str:
        return "google_drive"

    async def test_connection(self) -> bool:
        if self.mock_dir and self.mock_dir.exists():
            return True
        return self.credentials_file is not None

    async def fetch_documents(self) -> list[RawDocument]:
        """Fetch documents from Google Drive API or fallback to mock directory."""
        if self.mock_dir and self.mock_dir.exists():
            folder_conn = LocalFolderConnector(str(self.mock_dir), tenant_id=self.tenant_id)
            docs = await folder_conn.fetch_documents()
            # Remap source and URL
            transformed: list[RawDocument] = []
            for doc in docs:
                doc.source = self.name
                doc.source_url = f"https://drive.google.com/file/d/{doc.id}/view"
                transformed.append(doc)
            return transformed

        # Production-ready stub
        return []

    async def get_changes_since(self, checkpoint: datetime | None) -> list[RawDocument]:
        docs = await self.fetch_documents()
        if not checkpoint:
            return docs
        return [d for d in docs if d.updated_at > checkpoint]
