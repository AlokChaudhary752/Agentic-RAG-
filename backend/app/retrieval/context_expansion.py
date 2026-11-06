"""Parent-document expansion and contiguous chunk stitching for context enrichment."""

from app.domain.models import DocumentChunk


class ContextExpander:
    """Enriches retrieved chunks with parent section text and merges neighboring passages."""

    def __init__(self, max_context_chars: int = 4000) -> None:
        self.max_context_chars = max_context_chars

    def expand_and_stitch(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        """Expand child chunks into parent sections and deduplicate shared parents."""
        if not chunks:
            return []

        expanded: list[DocumentChunk] = []
        seen_parent_ids: set[str] = set()

        # Sort chunks primarily by doc_id and chunk_index to find neighbors
        sorted_chunks = sorted(chunks, key=lambda c: (c.doc_id, c.chunk_index))

        for chunk in sorted_chunks:
            # If chunk has parent content and parent hasn't been added yet, prioritize parent
            if chunk.parent_chunk_id and chunk.parent_content:
                if chunk.parent_chunk_id not in seen_parent_ids:
                    seen_parent_ids.add(chunk.parent_chunk_id)
                    # Replace child content with rich parent section
                    cloned_chunk = chunk.model_copy()
                    cloned_chunk.content = chunk.parent_content
                    expanded.append(cloned_chunk)
            else:
                expanded.append(chunk)

        # Stitch contiguous chunks from the same document
        stitched: list[DocumentChunk] = []
        i = 0
        while i < len(expanded):
            current = expanded[i].model_copy()
            # Look ahead for adjacent neighbor chunk from same document
            while i + 1 < len(expanded):
                nxt = expanded[i + 1]
                if (
                    nxt.doc_id == current.doc_id
                    and nxt.chunk_index == current.chunk_index + 1
                    and len(current.content) + len(nxt.content) <= self.max_context_chars
                ):
                    current.content += "\n\n" + nxt.content
                    i += 1
                    continue
                break
            stitched.append(current)
            i += 1

        return stitched
