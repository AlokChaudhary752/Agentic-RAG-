"""Connectors package exposing enterprise data source interfaces and implementations."""

from app.ingestion.connectors.base import BaseConnector
from app.ingestion.connectors.confluence import ConfluenceConnector, JiraConnector, SlackConnector
from app.ingestion.connectors.google_drive import GoogleDriveConnector
from app.ingestion.connectors.local_folder import LocalFolderConnector
from app.ingestion.connectors.notion import NotionConnector

__all__ = [
    "BaseConnector",
    "LocalFolderConnector",
    "GoogleDriveConnector",
    "NotionConnector",
    "ConfluenceConnector",
    "SlackConnector",
    "JiraConnector",
]
