"""Hybrid Retrieval Coordinator combining dense vector search, sparse BM25, RRF, MMR, and reranking."""

import time
from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.domain.models import DocumentChunk, UserPrincipal
from app.governance.acl_assertion import ACLAssertionValidator
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.context_expansion import ContextExpander
from app.retrieval.fusion import ReciprocalRankFusion
from app.retrieval.mmr import MaximalMarginalRelevance
from app.retrieval.qdrant_client import QdrantService
from app.retrieval.query_transforms import QueryTransformer
from app.retrieval.reranker import CrossEncoderReranker, RerankedChunk

logger = get_logger(__name__)


class RetrievalMetadata(BaseModel):
    """Execution telemetry and diagnostic metadata for a retrieval request."""

    strategy: str = Field(..., description="hybrid, dense, or sparse")
    original_query: str = Field(...)
    rewritten_query: str = Field(...)
    dense_candidates_count: int = Field(default=0)
    sparse_candidates_count: int = Field(default=0)
    fused_candidates_count: int = Field(default=0)
    reranked_count: int = Field(default=0)
    latency_ms: float = Field(default=0.0)


class HybridRetrievalBundle(BaseModel):
    """Final verified response bundle produced by the Hybrid Search engine."""

    chunks: list[DocumentChunk] = Field(
        ..., description="ACL-verified, reranked, and expanded chunks"
    )
    reranked_details: list[RerankedChunk] = Field(
        default_factory=list, description="Score breakdowns per chunk"
    )
    metadata: RetrievalMetadata = Field(...)


RetrievalBundle = HybridRetrievalBundle


class HybridRetriever:
    """Enterprise hybrid search engine enforcing vector-level ACLs and defense-in-depth."""

    def __init__(
        self,
        qdrant_service: QdrantService | None = None,
        bm25_retriever: BM25Retriever | None = None,
        reranker: CrossEncoderReranker | None = None,
        mmr: MaximalMarginalRelevance | None = None,
        transformer: QueryTransformer | None = None,
        expander: ContextExpander | None = None,
        acl_validator: ACLAssertionValidator | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.qdrant = qdrant_service or QdrantService(self.settings)
        self.bm25 = bm25_retriever or BM25Retriever()
        self.reranker = reranker or CrossEncoderReranker(settings=self.settings)
        self.mmr = mmr or MaximalMarginalRelevance()
        self.transformer = transformer or QueryTransformer()
        self.expander = expander or ContextExpander()
        self.acl_validator = acl_validator or ACLAssertionValidator()
        self.fusion = ReciprocalRankFusion()

    def index_corpus_for_sparse_search(self, chunks: list[DocumentChunk]) -> None:
        """Populate the in-memory BM25 index with candidate chunks."""
        self.bm25.index_chunks(chunks)

    def retrieve(
        self,
        query: str,
        principal: UserPrincipal,
        strategy: Literal["hybrid", "dense", "sparse"] = "hybrid",
        top_k: int = 5,
        enable_expansion: bool = True,
        enable_rerank: bool = True,
    ) -> HybridRetrievalBundle:
        """Execute governed multi-stage hybrid retrieval.

        Pipeline:
        1. Query Transformation (Rewrite & Expand)
        2. Vector Dense Retrieval (HNSW ACL Pre-Filter)
        3. Sparse BM25 Retrieval (ACL Filtered)
        4. Reciprocal Rank Fusion (RRF)
        5. Maximal Marginal Relevance (MMR Diversity)
        6. Cross-Encoder Reranker (Authority + Recency)
        7. Defense-in-Depth Secondary ACL Assertion (Fail Closed)
        8. Parent-Document Context Expansion & Stitching
        """
        start_time = time.perf_counter()

        # 1. Query Transformation
        transformed = self.transformer.transform(query)
        effective_query = transformed.rewritten_query

        dense_chunks: list[DocumentChunk] = []
        sparse_chunks: list[DocumentChunk] = []

        # 2. Dense Retrieval with ACL Pre-Filtering
        if strategy in ("hybrid", "dense"):
            q_vec = self.qdrant._generate_synthetic_vector(effective_query)
            dense_chunks = self.qdrant.search_with_acl(
                query_vector=q_vec,
                principal=principal,
                top_k=top_k * 3,
            )

        # 3. Sparse BM25 Retrieval with ACL Pre-Filtering
        if strategy in ("hybrid", "sparse"):
            bm25_scored = self.bm25.search(
                query=effective_query,
                principal=principal,
                top_k=top_k * 3,
            )
            sparse_chunks = [item.chunk for item in bm25_scored]

        # 4. Fusion
        candidates: list[DocumentChunk] = []
        if strategy == "hybrid":
            fused = self.fusion.fuse(
                dense_results=dense_chunks,
                sparse_results=sparse_chunks,
                top_k=top_k * 2,
            )
            candidates = [f.chunk for f in fused]
        elif strategy == "dense":
            candidates = dense_chunks[: top_k * 2]
        else:
            candidates = sparse_chunks[: top_k * 2]

        # 5. Maximal Marginal Relevance (Diversity)
        if len(candidates) > top_k:
            candidates = self.mmr.select(
                query=effective_query,
                candidates=candidates,
                top_k=top_k + 2,
            )

        # 6. Cross-Encoder Reranking
        reranked_details: list[RerankedChunk] = []
        if enable_rerank and candidates:
            reranked_details = self.reranker.rerank(
                query=effective_query,
                candidates=candidates,
                top_k=top_k,
            )
            candidates = [item.chunk for item in reranked_details]
        else:
            candidates = candidates[:top_k]

        # 7. Defense-in-Depth Secondary ACL Assertion (Fails closed on any violation)
        verified_chunks = self.acl_validator.assert_compliance(
            chunks=candidates,
            principal=principal,
        )

        # 8. Parent-Document Expansion & Neighbor Stitching
        if enable_expansion:
            final_chunks = self.expander.expand_and_stitch(verified_chunks)
        else:
            final_chunks = verified_chunks

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        meta = RetrievalMetadata(
            strategy=strategy,
            original_query=query,
            rewritten_query=effective_query,
            dense_candidates_count=len(dense_chunks),
            sparse_candidates_count=len(sparse_chunks),
            fused_candidates_count=len(candidates),
            reranked_count=len(reranked_details),
            latency_ms=elapsed_ms,
        )

        return HybridRetrievalBundle(
            chunks=final_chunks,
            reranked_details=reranked_details,
            metadata=meta,
        )
