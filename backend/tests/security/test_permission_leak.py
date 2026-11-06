"""Security test suite verifying zero permission leaks across user roles and defense-in-depth."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PermissionLeakError
from app.domain.models import ClassificationLevel, DocumentACL, DocumentChunk, UserPrincipal
from app.governance.acl_assertion import ACLAssertionValidator
from app.ingestion.connectors.local_folder import LocalFolderConnector
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.hybrid_search import HybridRetriever
from app.retrieval.qdrant_client import QdrantService


@pytest.fixture
def seeded_principals() -> dict[str, UserPrincipal]:
    return {
        "alice": UserPrincipal(
            user_id="emp_alice",
            email="alice@nimbus.com",
            full_name="Alice Smith",
            roles=["employee"],
            groups=["group_engineering"],
            clearance=ClassificationLevel.INTERNAL,
        ),
        "bob": UserPrincipal(
            user_id="mgr_bob",
            email="bob@nimbus.com",
            full_name="Bob Jones",
            roles=["manager"],
            groups=["group_engineering", "group_managers"],
            clearance=ClassificationLevel.CONFIDENTIAL,
        ),
        "frank": UserPrincipal(
            user_id="exec_frank",
            email="frank@nimbus.com",
            full_name="Frank Vance",
            roles=["executive"],
            groups=["group_executives", "group_managers", "group_engineering"],
            clearance=ClassificationLevel.RESTRICTED,
        ),
    }


@pytest.mark.security
async def test_zero_permission_leak_matrix(
    async_session: AsyncSession,
    seeded_principals: dict[str, UserPrincipal],
) -> None:
    """Verify different users asking the same sensitive query receive strictly isolated results."""
    qdrant = QdrantService()
    pipeline = IngestionPipeline(async_session, qdrant_service=qdrant)

    # Ingest HR and Finance corpora
    hr_conn = LocalFolderConnector("data/sample_corpus/hr")
    fin_conn = LocalFolderConnector("data/sample_corpus/finance")
    await pipeline.run_sync(hr_conn)
    await pipeline.run_sync(fin_conn)

    retriever = HybridRetriever(qdrant_service=qdrant)

    # Query 1: Executive compensation and retention bonuses (RESTRICTED)
    query_exec = "What are the executive base salaries, retention bonuses, and severance?"

    # Alice (INTERNAL) MUST NOT retrieve executive records
    alice_bundle = retriever.retrieve(query=query_exec, principal=seeded_principals["alice"])
    for chunk in alice_bundle.chunks:
        assert chunk.doc_id != "hr-exec-comp-2026", (
            "LEAK DETECTED: Alice saw executive compensation!"
        )
        assert chunk.acl.classification_level != ClassificationLevel.RESTRICTED

    # Bob (CONFIDENTIAL) MUST NOT retrieve executive records
    bob_bundle = retriever.retrieve(query=query_exec, principal=seeded_principals["bob"])
    for chunk in bob_bundle.chunks:
        assert chunk.doc_id != "hr-exec-comp-2026", "LEAK DETECTED: Bob saw executive compensation!"
        assert chunk.acl.classification_level != ClassificationLevel.RESTRICTED

    # Frank (RESTRICTED) CAN retrieve executive compensation
    frank_bundle = retriever.retrieve(query=query_exec, principal=seeded_principals["frank"])
    assert any(chunk.doc_id == "hr-exec-comp-2026" for chunk in frank_bundle.chunks), (
        "Frank should see executive record"
    )


@pytest.mark.security
async def test_manager_vs_employee_salary_bands_leak_prevention(
    async_session: AsyncSession,
    seeded_principals: dict[str, UserPrincipal],
) -> None:
    """Verify individual contributor cannot retrieve confidential engineering salary bands."""
    qdrant = QdrantService()
    pipeline = IngestionPipeline(async_session, qdrant_service=qdrant)
    await pipeline.run_sync(LocalFolderConnector("data/sample_corpus/finance"))

    retriever = HybridRetriever(qdrant_service=qdrant)
    salary_query = "What is the engineering salary band for L5 senior software engineer?"

    # Alice (Engineer, INTERNAL)
    alice_results = retriever.retrieve(query=salary_query, principal=seeded_principals["alice"])
    for chunk in alice_results.chunks:
        assert chunk.doc_id != "fin-eng-salary-bands-2026", (
            "LEAK DETECTED: Alice saw confidential salary bands!"
        )

    # Bob (Engineering Manager, CONFIDENTIAL)
    bob_results = retriever.retrieve(query=salary_query, principal=seeded_principals["bob"])
    assert any(chunk.doc_id == "fin-eng-salary-bands-2026" for chunk in bob_results.chunks), (
        "Bob should see salary bands"
    )


@pytest.mark.security
def test_defense_in_depth_assertion_fails_closed(
    seeded_principals: dict[str, UserPrincipal],
) -> None:
    """Verify ACLAssertionValidator catches an unauthorized chunk and raises PermissionLeakError."""
    validator = ACLAssertionValidator()

    # Create a deliberately forged/leaked restricted chunk
    restricted_chunk = DocumentChunk(
        id="forged-leak-chunk",
        doc_id="hr-exec-comp-2026",
        chunk_index=1,
        title="Executive Compensation",
        content="CEO base salary: $650,000",
        author="Board",
        owner_group="group_executives",
        acl=DocumentACL(
            allowed_groups=["group_executives"],
            classification_level=ClassificationLevel.RESTRICTED,
        ),
    )

    # Passing to Alice MUST trigger PermissionLeakError and fail closed
    with pytest.raises(PermissionLeakError, match="Permission assertion failed"):
        validator.assert_compliance([restricted_chunk], principal=seeded_principals["alice"])
