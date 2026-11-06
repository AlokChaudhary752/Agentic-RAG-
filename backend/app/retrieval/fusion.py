"""Reciprocal Rank Fusion (RRF) for merging dense semantic and sparse lexical rankings."""

from pydantic import BaseModel, Field

from app.domain.models import DocumentChunk


class FusedChunk(BaseModel):
    """Fused retrieval candidate with combined reciprocal rank score and source ranks."""

    chunk: DocumentChunk
    rrf_score: float = Field(..., description="Combined Reciprocal Rank Fusion score")
    dense_rank: int | None = Field(
        default=None, description="Rank position in dense results (1-based)"
    )
    sparse_rank: int | None = Field(
        default=None, description="Rank position in sparse results (1-based)"
    )


class ReciprocalRankFusion:
    """Merges disparate ranking lists into a unified, balanced relevance score."""

    def __init__(self, k: int = 60) -> None:
        self.k = k

    def fuse(
        self,
        dense_results: list[DocumentChunk],
        sparse_results: list[DocumentChunk],
        dense_weight: float = 1.0,
        sparse_weight: float = 1.0,
        top_k: int = 10,
    ) -> list[FusedChunk]:
        """Combine dense and sparse lists using weighted RRF."""
        chunk_map: dict[str, DocumentChunk] = {}
        rrf_scores: dict[str, float] = {}
        dense_ranks: dict[str, int] = {}
        sparse_ranks: dict[str, int] = {}

        # 1. Process dense rankings
        for rank, chunk in enumerate(dense_results, start=1):
            chunk_map[chunk.id] = chunk
            dense_ranks[chunk.id] = rank
            score = dense_weight * (1.0 / (self.k + rank))
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + score

        # 2. Process sparse BM25 rankings
        for rank, chunk in enumerate(sparse_results, start=1):
            chunk_map[chunk.id] = chunk
            sparse_ranks[chunk.id] = rank
            score = sparse_weight * (1.0 / (self.k + rank))
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + score

        # 3. Sort descending by combined RRF score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)
        top_ids = sorted_ids[:top_k]

        fused: list[FusedChunk] = []
        for cid in top_ids:
            fused.append(
                FusedChunk(
                    chunk=chunk_map[cid],
                    rrf_score=round(rrf_scores[cid], 6),
                    dense_rank=dense_ranks.get(cid),
                    sparse_rank=sparse_ranks.get(cid),
                )
            )

        return fused
