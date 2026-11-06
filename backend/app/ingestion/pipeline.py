"""Enterprise Ingestion Pipeline orchestrator.

Implements incremental sync, content hashing, layout parsing, structure-aware chunking,
classification-based PII masking, transactional dual-store indexing (PostgreSQL + Qdrant),
and dead-letter queue (DLQ) error containment.
"""

import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.repositories.document_repo import DocumentRepository
from app.db.repositories.ingestion_repo import IngestionRepository
from app.domain.models import DocumentChunk, RawDocument
from app.ingestion.chunkers.structure_chunker import StructureChunker
from app.ingestion.connectors.base import BaseConnector
from app.ingestion.pii.masker import PIIMasker
from app.retrieval.qdrant_client import QdrantService

logger = get_logger(__name__)


class IngestionPipeline:
    """Orchestrates end-to-end ingestion and indexing with strict error boundaries."""

    def __init__(
        self,
        session: AsyncSession,
        qdrant_service: QdrantService | None = None,
        chunker: StructureChunker | None = None,
        pii_masker: PIIMasker | None = None,
    ) -> None:
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self.ingestion_repo = IngestionRepository(session)
        self.qdrant_service = qdrant_service or QdrantService()
        self.chunker = chunker or StructureChunker()
        self.pii_masker = pii_masker or PIIMasker()

    def _compute_content_hash(self, doc: RawDocument) -> str:
        """Compute SHA-256 fingerprint over content, version, and ACL configuration."""
        data_to_hash = (
            f"{doc.id}|{doc.version}|{doc.doc_status.value}|{doc.authority_score}|"
            f"{doc.acl.classification_level.value}|{','.join(sorted(doc.acl.allowed_groups))}|"
            f"{doc.content}"
        )
        return hashlib.sha256(data_to_hash.encode("utf-8")).hexdigest()

    async def process_document(self, doc: RawDocument) -> tuple[bool, str]:
        """Ingest a single document: hash check, PII masking, chunking, and dual indexing."""
        calculated_hash = self._compute_content_hash(doc)
        doc.content_hash = calculated_hash

        # 1. Incremental change check
        existing_hash = await self.doc_repo.get_content_hash(doc.id)
        if existing_hash == calculated_hash:
            logger.info("Document content unchanged, skipping re-index", doc_id=doc.id)
            return False, "skipped_unchanged"

        # 2. PII Detection and Masking based on document classification
        masked_content, pii_flags = self.pii_masker.mask(doc.content, doc.acl.classification_level)
        doc.content = masked_content

        # 3. Structure-aware Parent-Child Chunking
        raw_chunks: list[DocumentChunk] = self.chunker.chunk_document(doc)

        # 4. Enrich chunk PII flags
        for chunk in raw_chunks:
            chunk_pii = self.pii_masker.detect_pii(chunk.content)
            chunk.pii_flags = sorted(set(pii_flags + chunk_pii))

        # 5. Index into Qdrant Vector Store
        await self.qdrant_service.upsert_chunks(raw_chunks)

        # 6. Upsert into Relational Document Repository
        await self.doc_repo.upsert_document_and_chunks(doc, raw_chunks)

        logger.info(
            "Document successfully indexed",
            doc_id=doc.id,
            chunks_count=len(raw_chunks),
            pii_flags=pii_flags,
        )
        return True, "indexed"

    async def run_sync(
        self,
        connector: BaseConnector,
        checkpoint: datetime | None = None,
        tenant_id: str = "tenant-nimbus-default",
    ) -> dict[str, Any]:
        """Execute a full or incremental ingestion sync cycle for a connector."""
        job = await self.ingestion_repo.create_job(source=connector.name, tenant_id=tenant_id)
        logger.info("Starting ingestion sync job", job_id=job.id, source=connector.name)

        docs_indexed = 0
        docs_skipped = 0
        docs_failed = 0

        try:
            documents = await connector.get_changes_since(checkpoint)
            await self.ingestion_repo.update_job_status(
                job.id, status="running", docs_total=len(documents)
            )

            for doc in documents:
                try:
                    indexed, status_reason = await self.process_document(doc)
                    if indexed:
                        docs_indexed += 1
                    else:
                        docs_skipped += 1
                except Exception as doc_err:
                    docs_failed += 1
                    logger.error(
                        "Document indexing failure, routing to DLQ",
                        doc_id=doc.id,
                        error=str(doc_err),
                    )
                    await self.ingestion_repo.record_dead_letter(
                        job_id=job.id,
                        source=connector.name,
                        doc_id=doc.id,
                        error_message=str(doc_err),
                        payload=doc.model_dump(mode="json"),
                    )

            final_status = "completed" if docs_failed == 0 else "degraded"
            await self.ingestion_repo.update_job_status(
                job_id=job.id,
                status=final_status,
                docs_indexed=docs_indexed,
                docs_failed=docs_failed,
            )

            return {
                "job_id": job.id,
                "status": final_status,
                "total": len(documents),
                "indexed": docs_indexed,
                "skipped": docs_skipped,
                "failed": docs_failed,
            }

        except Exception as exc:
            logger.exception("Ingestion job failed catastrophically", job_id=job.id, error=str(exc))
            await self.ingestion_repo.update_job_status(
                job_id=job.id,
                status="failed",
                error_log=str(exc),
            )
            raise
