"""Qdrant vector database client wrapper supporting hybrid vectors and ACL pre-filtering."""

import contextlib
import uuid
from datetime import UTC
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.domain.models import DocumentChunk, UserPrincipal

logger = get_logger(__name__)


class QdrantService:
    """Manages Qdrant collection lifecycle, payload indexes, and pre-filtered retrieval."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.collection_name = self.settings.qdrant_collection
        self.vector_size = self.settings.qdrant_vector_size

        if self.settings.qdrant_use_in_memory or self.settings.app_env == "test":
            self.client = QdrantClient(":memory:")
            logger.info("Initialized Qdrant in-memory client for testing/offline execution")
        else:
            try:
                remote_client = QdrantClient(
                    host=self.settings.qdrant_host,
                    port=self.settings.qdrant_port,
                    api_key=self.settings.qdrant_api_key,
                    timeout=2,
                )
                # Verify active connection to remote service
                remote_client.get_collections()
                self.client = remote_client
                logger.info("Connected to live Qdrant service", host=self.settings.qdrant_host)
            except Exception as exc:
                logger.warning(
                    "Live Qdrant service unreachable, initializing in-memory Qdrant fallback",
                    error=str(exc),
                )
                self.client = QdrantClient(":memory:")

        # Initialize collection and indexes idempotently
        with contextlib.suppress(Exception):
            self.init_collection()

    def init_collection(self) -> None:
        """Create Qdrant collection and payload indexes for ACL fields idempotently."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(
                    size=self.vector_size,
                    distance=qmodels.Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection", collection=self.collection_name)

        # Ensure ACL payload fields are indexed for fast boolean pre-filtering
        fields_to_index = [
            ("tenant_id", qmodels.PayloadSchemaType.KEYWORD),
            ("allowed_users", qmodels.PayloadSchemaType.KEYWORD),
            ("allowed_groups", qmodels.PayloadSchemaType.KEYWORD),
            ("classification_level", qmodels.PayloadSchemaType.KEYWORD),
            ("doc_id", qmodels.PayloadSchemaType.KEYWORD),
            ("owner_group", qmodels.PayloadSchemaType.KEYWORD),
            ("doc_status", qmodels.PayloadSchemaType.KEYWORD),
        ]

        for field_name, field_type in fields_to_index:
            with contextlib.suppress(Exception):
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=field_type,
                )

    def _generate_synthetic_vector(self, text: str) -> list[float]:
        """Deterministic fallback embedding generator when external neural model is offline."""
        import hashlib
        import math

        hash_bytes = hashlib.sha512(text.encode("utf-8")).digest()
        vec: list[float] = []
        for i in range(self.vector_size):
            byte_val = hash_bytes[i % len(hash_bytes)]
            val = (byte_val / 128.0) - 1.0
            vec.append(val)

        # Normalize vector to unit length
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    async def upsert_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Upsert a batch of document chunks with vectors and ACL metadata into Qdrant."""
        if not chunks:
            return 0

        self.init_collection()
        points: list[qmodels.PointStruct] = []

        for chunk in chunks:
            # Use provided dense vector or calculate deterministic synthetic embedding
            vec = chunk.dense_vector or self._generate_synthetic_vector(chunk.content)

            try:
                uuid.UUID(chunk.id)
                point_id = chunk.id
            except ValueError:
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.id))

            payload: dict[str, Any] = {
                "chunk_id": chunk.id,
                "doc_id": chunk.doc_id,
                "parent_chunk_id": chunk.parent_chunk_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "parent_content": chunk.parent_content,
                "section_path": chunk.section_path,
                "title": chunk.title,
                "source": chunk.source,
                "source_url": chunk.source_url,
                "author": chunk.author,
                "created_at": chunk.created_at.isoformat(),
                "updated_at": chunk.updated_at.isoformat(),
                "version": chunk.version,
                "doc_status": chunk.doc_status.value,
                "authority_score": chunk.authority_score,
                "language": chunk.language,
                "owner_group": chunk.owner_group,
                "allowed_users": chunk.acl.allowed_users,
                "allowed_groups": chunk.acl.allowed_groups,
                "classification_level": chunk.acl.classification_level.value,
                "pii_flags": chunk.pii_flags,
                "tenant_id": chunk.tenant_id,
            }

            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=vec,
                    payload=payload,
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        return len(points)

    def delete_by_doc_id(self, doc_id: str) -> None:
        """Purge all chunks associated with a document ID from Qdrant."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="doc_id",
                            match=qmodels.MatchValue(value=doc_id),
                        )
                    ]
                )
            ),
        )

    def build_acl_filter(self, principal: UserPrincipal) -> qmodels.Filter:
        """Compile a UserPrincipal into a strict vector-store level boolean ACL filter."""
        # Allowed classifications based on user clearance
        allowed_classifications: list[str] = []
        for level in ("PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"):
            from app.domain.models import ClassificationLevel

            lvl = ClassificationLevel[level]
            if principal.clearance.is_accessible_by(lvl):
                allowed_classifications.append(level)

        classification_condition = qmodels.FieldCondition(
            key="classification_level",
            match=qmodels.MatchAny(any=allowed_classifications),
        )

        tenant_condition = qmodels.FieldCondition(
            key="tenant_id",
            match=qmodels.MatchValue(value=principal.tenant_id),
        )

        # Access clauses:
        # Document is accessible if:
        # 1. No group restrictions (is_empty) -> open to everyone with that clearance
        # 2. OR principal.user_id is in allowed_users
        # 3. OR any of principal.groups is in allowed_groups
        access_conditions: list[qmodels.Condition] = [
            qmodels.IsEmptyCondition(is_empty=qmodels.PayloadField(key="allowed_groups")),
            qmodels.FieldCondition(
                key="allowed_users",
                match=qmodels.MatchValue(value=principal.user_id),
            ),
        ]

        if principal.groups:
            access_conditions.append(
                qmodels.FieldCondition(
                    key="allowed_groups",
                    match=qmodels.MatchAny(any=principal.groups),
                )
            )

        filter_clause = qmodels.Filter(
            must=[
                tenant_condition,
                classification_condition,
            ],
            should=access_conditions,
        )

        return filter_clause

    def search_with_acl(
        self,
        query_vector: list[float],
        principal: UserPrincipal,
        top_k: int = 10,
    ) -> list[DocumentChunk]:
        """Execute nearest neighbor vector search with HNSW-level ACL pre-filtering."""
        from datetime import datetime

        from app.domain.models import ClassificationLevel, DocStatus, DocumentACL

        self.init_collection()
        acl_filter = self.build_acl_filter(principal)

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=acl_filter,
            limit=top_k,
        )

        chunks: list[DocumentChunk] = []
        for point in response.points:
            payload = point.payload or {}
            acl = DocumentACL(
                allowed_users=payload.get("allowed_users", []),
                allowed_groups=payload.get("allowed_groups", []),
                classification_level=ClassificationLevel.from_str(
                    payload.get("classification_level", "INTERNAL")
                ),
            )
            created_at = datetime.fromisoformat(
                payload.get("created_at", datetime.now(UTC).isoformat())
            )
            updated_at = datetime.fromisoformat(
                payload.get("updated_at", datetime.now(UTC).isoformat())
            )

            chunks.append(
                DocumentChunk(
                    id=str(point.id),
                    doc_id=payload.get("doc_id", ""),
                    parent_chunk_id=payload.get("parent_chunk_id"),
                    chunk_index=int(payload.get("chunk_index", 0)),
                    content=payload.get("content", ""),
                    parent_content=payload.get("parent_content"),
                    section_path=payload.get("section_path", ""),
                    title=payload.get("title", ""),
                    source=payload.get("source", "qdrant"),
                    source_url=payload.get("source_url", ""),
                    author=payload.get("author", ""),
                    created_at=created_at,
                    updated_at=updated_at,
                    version=payload.get("version", "1.0"),
                    doc_status=DocStatus(payload.get("doc_status", "approved")),
                    authority_score=float(payload.get("authority_score", 0.8)),
                    language=payload.get("language", "en"),
                    owner_group=payload.get("owner_group", "group_general"),
                    acl=acl,
                    pii_flags=payload.get("pii_flags", []),
                    tenant_id=payload.get("tenant_id", "tenant-nimbus-default"),
                )
            )

        return chunks
