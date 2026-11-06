"""Integration tests for end-to-end ingestion, user seeding, and Qdrant indexing."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.document_repo import DocumentRepository
from app.db.repositories.user_repo import UserRepository
from app.domain.models import ClassificationLevel
from app.ingestion.connectors.local_folder import LocalFolderConnector
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.qdrant_client import QdrantService


@pytest.mark.integration
async def test_user_repository_and_principal_expansion(async_session: AsyncSession) -> None:
    """Verify user upsert and principal expansion with groups and clearance."""
    repo = UserRepository(async_session)

    # Upsert groups
    await repo.upsert_group("group_engineering", "Engineering", "Software Dev")
    await repo.upsert_group("group_managers", "Managers", "People Managers")

    # Upsert user with multiple groups
    user = await repo.upsert_user(
        user_id="test_bob",
        email="bob.test@nimbus.com",
        full_name="Bob Test",
        hashed_password="hashed_pw",
        role="manager",
        clearance="CONFIDENTIAL",
        group_ids=["group_engineering", "group_managers"],
    )
    assert user.id == "test_bob"

    # Resolve principal
    principal = await repo.get_principal("test_bob")
    assert principal is not None
    assert principal.email == "bob.test@nimbus.com"
    assert principal.clearance == ClassificationLevel.CONFIDENTIAL
    assert "group_engineering" in principal.groups
    assert "group_managers" in principal.groups


@pytest.mark.integration
async def test_end_to_end_corpus_ingestion(async_session: AsyncSession) -> None:
    """Verify ingestion pipeline indexes documents into relational repo and Qdrant."""
    qdrant = QdrantService()
    pipeline = IngestionPipeline(async_session, qdrant_service=qdrant)
    connector = LocalFolderConnector("data/sample_corpus/hr")

    result = await pipeline.run_sync(connector)
    assert result["total"] >= 10
    assert result["failed"] == 0
    assert result["indexed"] >= 10

    # Query relational document repo
    doc_repo = DocumentRepository(async_session)
    docs = await doc_repo.list_documents(limit=50)
    assert len(docs) >= 10

    # Check leave policy 2026
    leave_doc = await doc_repo.get_by_id("hr-leave-policy-2026")
    assert leave_doc is not None
    assert leave_doc.version == "2026.1"
    assert len(leave_doc.chunks) >= 3
