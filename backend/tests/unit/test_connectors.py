"""Unit tests for enterprise data source connectors."""

import pytest

from app.domain.models import ClassificationLevel, DocStatus
from app.ingestion.connectors.confluence import ConfluenceConnector, JiraConnector, SlackConnector
from app.ingestion.connectors.google_drive import GoogleDriveConnector
from app.ingestion.connectors.local_folder import LocalFolderConnector
from app.ingestion.connectors.notion import NotionConnector


@pytest.mark.unit
async def test_local_folder_connector_parses_frontmatter() -> None:
    """Verify LocalFolderConnector extracts YAML frontmatter, ACLs, and content."""
    connector = LocalFolderConnector("data/sample_corpus/hr")
    assert await connector.test_connection() is True

    docs = await connector.fetch_documents()
    assert len(docs) >= 5

    # Find the approved leave policy 2026
    policy_2026 = next((d for d in docs if d.id == "hr-leave-policy-2026"), None)
    assert policy_2026 is not None
    assert policy_2026.doc_status == DocStatus.APPROVED
    assert policy_2026.authority_score == 0.98
    assert policy_2026.version == "2026.1"
    assert policy_2026.acl.classification_level == ClassificationLevel.INTERNAL
    assert "group_engineering" in policy_2026.acl.allowed_groups
    assert "25 days of annual paid time off" in policy_2026.content


@pytest.mark.unit
async def test_google_drive_mock_connector() -> None:
    """Verify GoogleDriveConnector resolves mock files and reformats URLs."""
    gdrive_conn = GoogleDriveConnector(mock_dir="data/sample_corpus/it")
    assert await gdrive_conn.test_connection() is True

    docs = await gdrive_conn.fetch_documents()
    assert len(docs) > 0
    assert docs[0].source == "google_drive"
    assert docs[0].source_url.startswith("https://drive.google.com/file/d/")


@pytest.mark.unit
async def test_notion_mock_connector() -> None:
    """Verify NotionConnector resolves mock files and builds notion URLs."""
    notion_conn = NotionConnector(mock_dir="data/sample_corpus/finance")
    assert await notion_conn.test_connection() is True

    docs = await notion_conn.fetch_documents()
    assert len(docs) > 0
    assert docs[0].source == "notion"
    assert docs[0].source_url.startswith("https://notion.so/nimbus/")


@pytest.mark.unit
async def test_atlassian_and_slack_connectors() -> None:
    """Verify Confluence, Slack, and Jira connectors."""
    confluence = ConfluenceConnector(mock_dir="data/sample_corpus/engineering")
    slack = SlackConnector(mock_dir="data/sample_corpus/hr")
    jira = JiraConnector(mock_dir="data/sample_corpus/legal")

    assert await confluence.test_connection() is True
    assert await slack.test_connection() is True
    assert await jira.test_connection() is True

    c_docs = await confluence.fetch_documents()
    assert len(c_docs) > 0
    assert c_docs[0].source == "confluence"
