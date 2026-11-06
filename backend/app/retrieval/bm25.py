"""Sparse lexical search engine implementing Okapi BM25 with ACL awareness."""

import math
import re

from pydantic import BaseModel, Field

from app.domain.models import DocumentChunk, UserPrincipal


class ScoredChunk(BaseModel):
    """Chunk result with associated lexical or semantic match score."""

    chunk: DocumentChunk
    score: float = Field(..., description="BM25 or dense retrieval relevance score")


class BM25Retriever:
    """Okapi BM25 sparse retriever for exact keyword and terminology matching."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus: list[DocumentChunk] = []
        self.doc_lengths: list[int] = []
        self.avg_doc_len: float = 0.0
        self.doc_freqs: dict[str, int] = {}
        self.idf: dict[str, float] = {}
        self.doc_token_counts: list[dict[str, int]] = []

    def _tokenize(self, text: str) -> list[str]:
        """Multilingual tokenization extracting alphanumeric words and unicode scripts."""
        # Handles English, Hindi (Devanagari \u0900-\u097F), digits, and underscores
        tokens = re.findall(r"[\w\u0900-\u097F]+", text.lower())
        return [t for t in tokens if len(t) > 1]

    def index_chunks(self, chunks: list[DocumentChunk]) -> None:
        """Build term frequencies, document frequencies, and IDF tables over chunk corpus."""
        self.corpus = chunks
        self.doc_lengths = []
        self.doc_token_counts = []
        self.doc_freqs = {}
        total_len = 0

        for chunk in chunks:
            tokens = self._tokenize(chunk.content + " " + chunk.title)
            doc_len = len(tokens)
            self.doc_lengths.append(doc_len)
            total_len += doc_len

            counts: dict[str, int] = {}
            for t in tokens:
                counts[t] = counts.get(t, 0) + 1
            self.doc_token_counts.append(counts)

            for unique_token in counts:
                self.doc_freqs[unique_token] = self.doc_freqs.get(unique_token, 0) + 1

        n_docs = len(chunks)
        self.avg_doc_len = (total_len / n_docs) if n_docs > 0 else 1.0

        # Compute IDF using standard Okapi BM25 formula
        self.idf = {}
        for term, freq in self.doc_freqs.items():
            self.idf[term] = math.log((n_docs - freq + 0.5) / (freq + 0.5) + 1.0)

    def search(
        self,
        query: str,
        principal: UserPrincipal | None = None,
        top_k: int = 10,
    ) -> list[ScoredChunk]:
        """Score all matching chunks using BM25 with vector-compatible ACL filtering."""
        if not self.corpus:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores: list[tuple[int, float]] = []

        for idx, token_counts in enumerate(self.doc_token_counts):
            chunk = self.corpus[idx]

            # ACL Pre-Filtering in BM25: Verify if calling user has access
            if principal:
                if not chunk.acl.permits_user(
                    user_id=principal.user_id,
                    user_groups=principal.groups,
                    clearance=principal.clearance,
                ):
                    continue

                if chunk.tenant_id != principal.tenant_id:
                    continue

            # Calculate BM25 score for this document
            doc_len = self.doc_lengths[idx]
            score = 0.0

            for q_term in query_tokens:
                if q_term not in token_counts:
                    continue

                tf = token_counts[q_term]
                idf = self.idf.get(q_term, 0.0)
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
                score += idf * (numerator / denominator)

            if score > 0.0:
                scores.append((idx, score))

        # Sort descending by relevance score
        scores.sort(key=lambda x: x[1], reverse=True)
        top_results = scores[:top_k]

        return [ScoredChunk(chunk=self.corpus[idx], score=round(s, 4)) for idx, s in top_results]
