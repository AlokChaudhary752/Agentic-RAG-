"""Abstract base connector interface for enterprise knowledge sources."""

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.models import RawDocument


class BaseConnector(ABC):
    """Abstract interface defining the lifecycle for all enterprise data source connectors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier name for the connector."""
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        """Verify credentials and connectivity to the underlying data source."""
        ...

    @abstractmethod
    async def fetch_documents(self) -> list[RawDocument]:
        """Fetch all available documents from the source."""
        ...

    @abstractmethod
    async def get_changes_since(self, checkpoint: datetime | None) -> list[RawDocument]:
        """Fetch documents created or modified after the given timestamp checkpoint."""
        ...
