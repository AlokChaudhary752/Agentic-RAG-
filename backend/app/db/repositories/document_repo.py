"""Repository for Documents and Document Chunks."""

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DocumentChunkEntity, DocumentEntity
from app.domain.models import DocumentChunk, RawDocument


class DocumentRepository:
    """Data access methods for cataloged documents and parsed chunks."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, doc_id: str) -> DocumentEntity | None:
        """Retrieve document with all associated chunks."""
        result = await self.session.execute(
            select(DocumentEntity).where(DocumentEntity.id == doc_id)
        )
        return result.scalar_one_or_none()

    async def get_content_hash(self, doc_id: str) -> str | None:
        """Retrieve existing content hash for change detection."""
        doc = await self.get_by_id(doc_id)
        return doc.content_hash if doc else None

    async def upsert_document_and_chunks(
        self, raw_doc: RawDocument, chunks: list[DocumentChunk]
    ) -> DocumentEntity:
        """Idempotently upsert a document and replace its chunks transactionally."""
        existing = await self.get_by_id(raw_doc.id)
        now = datetime.now(UTC)

        if existing:
            existing.title = raw_doc.title
            existing.source = raw_doc.source
            existing.source_url = raw_doc.source_url
            existing.author = raw_doc.author
            existing.version = raw_doc.version
            existing.doc_status = raw_doc.doc_status.value
            existing.authority_score = raw_doc.authority_score
            existing.language = raw_doc.language
            existing.owner_group = raw_doc.owner_group
            existing.content_hash = raw_doc.content_hash
            existing.allowed_users = raw_doc.acl.allowed_users
            existing.allowed_groups = raw_doc.acl.allowed_groups
            existing.classification_level = raw_doc.acl.classification_level.value
            existing.updated_at = now
            doc_entity = existing
            # Remove previous chunks
            await self.session.execute(
                delete(DocumentChunkEntity).where(DocumentChunkEntity.doc_id == raw_doc.id)
            )
        else:
            doc_entity = DocumentEntity(
                id=raw_doc.id,
                tenant_id=raw_doc.metadata.get("tenant_id", "tenant-nimbus-default"),
                source=raw_doc.source,
                source_url=raw_doc.source_url,
                title=raw_doc.title,
                author=raw_doc.author,
                version=raw_doc.version,
                doc_status=raw_doc.doc_status.value,
                authority_score=raw_doc.authority_score,
                language=raw_doc.language,
                owner_group=raw_doc.owner_group,
                content_hash=raw_doc.content_hash,
                allowed_users=raw_doc.acl.allowed_users,
                allowed_groups=raw_doc.acl.allowed_groups,
                classification_level=raw_doc.acl.classification_level.value,
                created_at=raw_doc.created_at,
                updated_at=now,
            )
            self.session.add(doc_entity)

        # Insert new chunks
        for chunk in chunks:
            chunk_entity = DocumentChunkEntity(
                id=chunk.id,
                doc_id=raw_doc.id,
                parent_chunk_id=chunk.parent_chunk_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                section_path=chunk.section_path,
                allowed_users=chunk.acl.allowed_users,
                allowed_groups=chunk.acl.allowed_groups,
                classification_level=chunk.acl.classification_level.value,
                pii_flags=chunk.pii_flags,
                created_at=chunk.created_at,
            )
            self.session.add(chunk_entity)

        await self.session.flush()
        return doc_entity

    async def list_documents(
        self, tenant_id: str = "tenant-nimbus-default", limit: int = 100, offset: int = 0
    ) -> list[DocumentEntity]:
        """List cataloged documents with pagination."""
        result = await self.session.execute(
            select(DocumentEntity)
            .where(DocumentEntity.tenant_id == tenant_id)
            .order_by(DocumentEntity.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document and all related chunks."""
        existing = await self.get_by_id(doc_id)
        if not existing:
            return False
        await self.session.delete(existing)
        await self.session.flush()
        return True
