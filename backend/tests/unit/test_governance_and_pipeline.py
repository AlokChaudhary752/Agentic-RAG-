"""Comprehensive unit tests for ACL assertion validator, ingestion pipeline,
repositories, connectors, and application factory.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import PermissionLeakError
from app.db.models import GroupEntity, IngestionJobEntity, UserEntity
from app.db.repositories.ingestion_repo import IngestionRepository
from app.db.repositories.user_repo import UserRepository
from app.domain.models import (
    ClassificationLevel,
    DocStatus,
    DocumentACL,
    DocumentChunk,
    RawDocument,
    UserPrincipal,
)
from app.governance.acl_assertion import ACLAssertionValidator
from app.ingestion.connectors.confluence import ConfluenceConnector
from app.ingestion.connectors.google_drive import GoogleDriveConnector
from app.ingestion.connectors.notion import NotionConnector
from app.ingestion.pipeline import IngestionPipeline
from app.main import create_app


def test_acl_assertion_validator_success():
    validator = ACLAssertionValidator()
    user = UserPrincipal(
        user_id="user-1",
        email="user1@example.com",
        full_name="User One",
        tenant_id="tenant-alpha",
        roles=["employee"],
        groups=["group-all"],
        clearance=ClassificationLevel.INTERNAL,
    )
    acl = DocumentACL(
        classification_level=ClassificationLevel.INTERNAL,
        allowed_groups=["group-all"],
        allowed_users=[],
    )
    chunk = DocumentChunk(
        id="chk-1",
        doc_id="doc-1",
        tenant_id="tenant-alpha",
        content="Internal content",
        title="Title",
        section_path="Section 1",
        chunk_index=0,
        token_count=10,
        acl=acl,
        doc_status=DocStatus.APPROVED,
        authority_score=1.0,
        version="1.0",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    result = validator.assert_compliance([chunk], user)
    assert len(result) == 1
    assert result[0].id == "chk-1"


def test_acl_assertion_validator_cross_tenant_violation():
    validator = ACLAssertionValidator()
    user = UserPrincipal(
        user_id="user-1",
        email="user1@example.com",
        full_name="User One",
        tenant_id="tenant-alpha",
        roles=["employee"],
        groups=["group-all"],
        clearance=ClassificationLevel.PUBLIC,
    )
    acl = DocumentACL(
        classification_level=ClassificationLevel.PUBLIC,
        allowed_groups=["group-all"],
        allowed_users=[],
    )
    chunk = DocumentChunk(
        id="chk-foreign",
        doc_id="doc-foreign",
        tenant_id="tenant-bravo",  # Different tenant!
        content="Foreign tenant content",
        title="Foreign Doc",
        section_path="Section 1",
        chunk_index=0,
        token_count=10,
        acl=acl,
        doc_status=DocStatus.APPROVED,
        authority_score=1.0,
        version="1.0",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    with pytest.raises(PermissionLeakError, match="Cross-tenant isolation violation"):
        validator.assert_compliance([chunk], user)


def test_acl_assertion_validator_permission_leak_violation():
    validator = ACLAssertionValidator()
    user = UserPrincipal(
        user_id="user-low",
        email="low@example.com",
        full_name="Low User",
        tenant_id="tenant-alpha",
        roles=["employee"],
        groups=["group-eng"],
        clearance=ClassificationLevel.INTERNAL,
    )
    # Chunk is CONFIDENTIAL (higher clearance than user)
    acl = DocumentACL(
        classification_level=ClassificationLevel.CONFIDENTIAL,
        allowed_groups=["group-exec"],
        allowed_users=["exec-1"],
    )
    chunk = DocumentChunk(
        id="chk-secret",
        doc_id="doc-secret",
        tenant_id="tenant-alpha",
        content="Executive salary bands",
        title="Salaries",
        section_path="Section 1",
        chunk_index=0,
        token_count=10,
        acl=acl,
        doc_status=DocStatus.APPROVED,
        authority_score=1.0,
        version="1.0",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    with pytest.raises(PermissionLeakError, match="Permission assertion failed"):
        validator.assert_compliance([chunk], user)


@pytest.mark.asyncio
async def test_ingestion_pipeline_skips_unchanged_content():
    mock_session = AsyncMock()
    mock_qdrant = MagicMock()
    pipeline = IngestionPipeline(session=mock_session, qdrant_service=mock_qdrant)

    doc = RawDocument(
        id="doc-1",
        source="google_drive",
        source_url="https://drive.google.com/doc-1",
        title="Policy Document",
        content="This is the unchanged policy content.",
        author="HR Team",
        owner_group="group-all",
        version="1.0",
        doc_status=DocStatus.APPROVED,
        authority_score=1.0,
        acl=DocumentACL(
            classification_level=ClassificationLevel.INTERNAL,
            allowed_groups=["group-all"],
            allowed_users=[],
        ),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    expected_hash = pipeline._compute_content_hash(doc)
    pipeline.doc_repo.get_content_hash = AsyncMock(return_value=expected_hash)

    success, status = await pipeline.process_document(doc)
    assert success is False
    assert status == "skipped_unchanged"


@pytest.mark.asyncio
async def test_ingestion_pipeline_indexes_new_document():
    mock_session = AsyncMock()
    mock_qdrant = MagicMock()
    mock_qdrant.upsert_chunks = AsyncMock()
    pipeline = IngestionPipeline(session=mock_session, qdrant_service=mock_qdrant)

    doc = RawDocument(
        id="doc-new",
        source="confluence",
        source_url="https://confluence.corp.internal/doc-new",
        title="New Architecture Standard",
        content="## Section 1\nArchitecture details with email test@company.com.",
        author="Eng Team",
        owner_group="group-eng",
        version="1.0",
        doc_status=DocStatus.APPROVED,
        authority_score=0.9,
        acl=DocumentACL(
            classification_level=ClassificationLevel.INTERNAL,
            allowed_groups=["group-eng"],
            allowed_users=[],
        ),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    pipeline.doc_repo.get_content_hash = AsyncMock(return_value=None)
    pipeline.doc_repo.upsert_document_and_chunks = AsyncMock()

    success, status = await pipeline.process_document(doc)
    assert success is True
    assert status == "indexed"
    assert doc.content_hash != ""
    mock_qdrant.upsert_chunks.assert_called_once()
    pipeline.doc_repo.upsert_document_and_chunks.assert_called_once()


@pytest.mark.asyncio
async def test_ingestion_pipeline_run_sync_dlq_on_error():
    mock_session = AsyncMock()
    mock_qdrant = MagicMock()
    pipeline = IngestionPipeline(session=mock_session, qdrant_service=mock_qdrant)

    doc = RawDocument(
        id="doc-err",
        source="notion",
        source_url="https://notion.so/doc-err",
        title="Failing Document",
        content="Content triggering exception",
        author="Product Team",
        owner_group="group-all",
        version="1.0",
        doc_status=DocStatus.APPROVED,
        authority_score=0.8,
        acl=DocumentACL(
            classification_level=ClassificationLevel.INTERNAL,
            allowed_groups=["group-all"],
            allowed_users=[],
        ),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    connector = MagicMock()
    connector.name = "notion"
    connector.get_changes_since = AsyncMock(return_value=[doc])

    mock_job = IngestionJobEntity(
        id="job-dlq-1",
        tenant_id="tenant-nimbus-default",
        source="notion",
        status="running",
        docs_total=0,
        docs_indexed=0,
        docs_failed=0,
        started_at=datetime.now(UTC),
    )
    pipeline.ingestion_repo.create_job = AsyncMock(return_value=mock_job)
    pipeline.ingestion_repo.update_job_status = AsyncMock()
    pipeline.ingestion_repo.record_dead_letter = AsyncMock()
    pipeline.process_document = AsyncMock(side_effect=RuntimeError("Parsing failure"))

    result = await pipeline.run_sync(connector)
    assert result["status"] == "degraded"
    assert result["failed"] == 1
    assert result["indexed"] == 0
    pipeline.ingestion_repo.record_dead_letter.assert_called_once()


@pytest.mark.asyncio
async def test_ingestion_repository_lifecycle():
    mock_session = AsyncMock()
    repo = IngestionRepository(mock_session)

    # create_job
    job = await repo.create_job(source="gdrive", tenant_id="tenant-test")
    assert job.source == "gdrive"
    assert job.status == "running"
    mock_session.flush.assert_called()

    # update_job_status
    mock_job = IngestionJobEntity(
        id="job-1",
        tenant_id="tenant-test",
        source="gdrive",
        status="running",
        docs_total=10,
        docs_indexed=0,
        docs_failed=0,
        started_at=datetime.now(UTC),
    )
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: mock_job))
    updated = await repo.update_job_status(
        job_id="job-1",
        status="completed",
        docs_total=10,
        docs_indexed=10,
        docs_failed=0,
        error_log="none",
    )
    assert updated is not None
    assert updated.status == "completed"
    assert updated.docs_indexed == 10

    # record_dead_letter
    dlq = await repo.record_dead_letter(
        job_id="job-1",
        source="gdrive",
        doc_id="doc-bad",
        error_message="Parse error",
        payload={"raw": "corrupted"},
    )
    assert dlq.doc_id == "doc-bad"
    assert dlq.error_message == "Parse error"

    # record_audit_log
    audit = await repo.record_audit_log(
        user_id="user-1",
        query="What is the policy?",
        retrieved_chunk_ids=["chk-1", "chk-2"],
        tool_called=None,
    )
    assert audit.user_id == "user-1"
    assert len(audit.retrieved_chunk_ids) == 2


@pytest.mark.asyncio
async def test_user_repository_principal_resolution():
    mock_session = AsyncMock()
    repo = UserRepository(mock_session)

    # Inactive user returns None
    inactive_user = UserEntity(
        id="user-inactive",
        tenant_id="tenant-test",
        email="inactive@example.com",
        hashed_password="hash",
        full_name="Inactive User",
        role="employee",
        clearance="INTERNAL",
        is_active=False,
    )
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=lambda: inactive_user)
    )
    principal = await repo.get_principal("user-inactive")
    assert principal is None

    # Active user returns full UserPrincipal
    group = GroupEntity(id="group-eng", tenant_id="tenant-test", name="Engineering")
    active_user = UserEntity(
        id="user-active",
        tenant_id="tenant-test",
        email="active@example.com",
        hashed_password="hash",
        full_name="Active User",
        role="employee",
        clearance="INTERNAL",
        is_active=True,
        groups=[group],
    )
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: active_user))
    principal = await repo.get_principal("user-active")
    assert principal is not None
    assert principal.user_id == "user-active"
    assert "group-eng" in principal.groups
    assert principal.clearance == ClassificationLevel.INTERNAL


def test_connectors_initialization_and_mock_fetch():
    gdrive = GoogleDriveConnector(credentials_file="mock_creds.json")
    assert gdrive.name == "google_drive"

    confluence = ConfluenceConnector()
    assert confluence.name == "confluence"

    notion = NotionConnector(api_token="mock_token")
    assert notion.name == "notion"


def test_app_factory_creates_fastapi_app():
    app = create_app()
    assert app.title == "Enterprise Knowledge Agent"
    routes = [route.path for route in app.routes]
    assert "/api/v1/health" in routes
    assert "/api/v1/chat/completions" in routes
