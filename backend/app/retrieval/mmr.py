"""Maximal Marginal Relevance (MMR) for result diversity and deduplication."""

import re

from app.domain.models import DocumentChunk


class MaximalMarginalRelevance:
    """Selects diverse, non-redundant chunks balancing query relevance with novelty."""

    def __init__(self, lambda_mult: float = 0.7) -> None:
        self.lambda_mult = lambda_mult

    def _jaccard_similarity(self, text_a: str, text_b: str) -> float:
        """Compute lexical Jaccard similarity between two chunk contents."""
        set_a = set(re.findall(r"\w+", text_a.lower()))
        set_b = set(re.findall(r"\w+", text_b.lower()))
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        return intersection / union if union > 0 else 0.0

    def select(
        self,
        query: str,
        candidates: list[DocumentChunk],
        top_k: int = 5,
    ) -> list[DocumentChunk]:
        """Iteratively select chunks using the MMR selection formula."""
        if len(candidates) <= top_k:
            return candidates

        # Initial relevance scores
        relevance_scores: list[float] = [
            self._jaccard_similarity(query, c.content + " " + c.title) for c in candidates
        ]

        selected_indices: list[int] = []
        unselected_indices: list[int] = list(range(len(candidates)))

        # Pick the most relevant item first
        first_idx = max(range(len(candidates)), key=lambda i: relevance_scores[i])
        selected_indices.append(first_idx)
        unselected_indices.remove(first_idx)

        # Iteratively select subsequent items maximizing MMR criterion
        while len(selected_indices) < top_k and unselected_indices:
            best_mmr_score = -float("inf")
            best_candidate_idx = unselected_indices[0]

            for c_idx in unselected_indices:
                rel = relevance_scores[c_idx]

                # Max similarity to any already-selected chunk
                max_sim_to_selected = max(
                    self._jaccard_similarity(candidates[c_idx].content, candidates[s_idx].content)
                    for s_idx in selected_indices
                )

                mmr_score = self.lambda_mult * rel - (1.0 - self.lambda_mult) * max_sim_to_selected

                if mmr_score > best_mmr_score:
                    best_mmr_score = mmr_score
                    best_candidate_idx = c_idx

            selected_indices.append(best_candidate_idx)
            unselected_indices.remove(best_candidate_idx)

        return [candidates[i] for i in selected_indices]
