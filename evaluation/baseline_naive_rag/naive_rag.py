"""Naive RAG baseline implementation used for benchmark ablations.

Deliberately implements simple top-k dense similarity retrieval without
vector ACL pre-filtering, query expansion, hybrid fusion, reranking,
or claim-level verification. Kept permanently for ablation benchmarking.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.retrieval.qdrant_client import QdrantService


class NaiveRetrievalResult(BaseModel):
    """Result payload from the naive retrieval baseline."""

    model_config = {"protected_namespaces": ()}

    query: str = Field(..., description="Original un-transformed query")
    chunks: list[dict[str, Any]] = Field(
        ..., description="Top-k retrieved chunks without ACL filtering"
    )
    context_text: str = Field(..., description="Raw concatenated context string")
    model_prompt: str = Field(..., description="Naive un-grounded prompt constructed for LLM")


class NaiveRAGBaseline:
    """Baseline RAG engine representing standard un-governed retrieval."""

    def __init__(
        self,
        qdrant_service: QdrantService | None = None,
        top_k: int = 5,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.qdrant = qdrant_service or QdrantService(self.settings)
        self.top_k = top_k

    def retrieve(self, query: str) -> NaiveRetrievalResult:
        """Execute un-filtered dense similarity search against the vector database."""
        # 1. Generate dense query embedding
        query_vector = self.qdrant._generate_synthetic_vector(query)

        # 2. Naive search: NO ACL pre-filter applied, purely top-k distance
        search_hits = self.qdrant.client.query_points(
            collection_name=self.qdrant.collection_name,
            query=query_vector,
            limit=self.top_k,
        ).points

        retrieved_chunks: list[dict[str, Any]] = []
        context_parts: list[str] = []

        for hit in search_hits:
            payload = hit.payload or {}
            retrieved_chunks.append(
                {
                    "chunk_id": hit.id,
                    "score": hit.score,
                    "title": payload.get("title", ""),
                    "content": payload.get("content", ""),
                    "doc_id": payload.get("doc_id", ""),
                    "classification_level": payload.get("classification_level", "INTERNAL"),
                    "allowed_users": payload.get("allowed_users", []),
                    "allowed_groups": payload.get("allowed_groups", []),
                }
            )
            content_snippet = payload.get("content", "")
            context_parts.append(f"Document [{payload.get('title', '')}]:\n{content_snippet}")

        concatenated_context = "\n\n---\n\n".join(context_parts)
        naive_prompt = (
            f"You are a helpful assistant. Use the following context to answer the question:\n\n"
            f"{concatenated_context}\n\n"
            f"Question: {query}\n"
            f"Answer:"
        )

        return NaiveRetrievalResult(
            query=query,
            chunks=retrieved_chunks,
            context_text=concatenated_context,
            model_prompt=naive_prompt,
        )
