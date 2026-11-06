"""Structure-aware parent-child document chunker.

Produces granular child chunks for dense/sparse retrieval paired with
cohesive parent sections for expanded context synthesis.
"""

import uuid

from app.domain.models import DocumentChunk, RawDocument
from app.ingestion.parsers.layout_parser import LayoutParser, ParsedSection


class StructureChunker:
    """Chunks documents hierarchically preserving parent-child context relationships."""

    def __init__(
        self,
        target_chunk_size: int = 500,
        chunk_overlap: int = 80,
    ) -> None:
        self.target_chunk_size = target_chunk_size
        self.chunk_overlap = chunk_overlap
        self.parser = LayoutParser()

    def _split_text(self, text: str, chunk_size: int, overlap: int) -> list[str]:
        """Split text by sentences or paragraphs respecting maximum length."""
        paragraphs = text.split("\n\n")
        chunks: list[str] = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If adding paragraph exceeds chunk size and current_chunk is non-empty
            if len(current_chunk) + len(para) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                # Maintain overlap by taking tail of current chunk
                overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else ""
                current_chunk = (overlap_text + "\n\n" + para).strip()
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks if chunks else [text]

    def chunk_document(self, doc: RawDocument) -> list[DocumentChunk]:
        """Convert RawDocument into parent and child chunks with inherited ACLs."""
        sections: list[ParsedSection] = self.parser.parse_into_sections(doc.content, doc.title)
        document_chunks: list[DocumentChunk] = []
        chunk_counter = 0

        for sec_idx, section in enumerate(sections):
            parent_chunk_id = f"parent-{doc.id}-{sec_idx}"
            parent_text = (
                f"## {section.heading_title}\nSection: {section.section_path}\n\n{section.content}"
            )

            # Tables should never be fragmented if reasonably sized
            if section.is_table or len(section.content) <= self.target_chunk_size:
                child_texts = [section.content]
            else:
                child_texts = self._split_text(
                    section.content, self.target_chunk_size, self.chunk_overlap
                )

            for child_text in child_texts:
                chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc.id}:{chunk_counter}"))
                chunk_counter += 1

                document_chunks.append(
                    DocumentChunk(
                        id=chunk_id,
                        doc_id=doc.id,
                        parent_chunk_id=parent_chunk_id,
                        chunk_index=chunk_counter,
                        content=child_text,
                        parent_content=parent_text,
                        section_path=section.section_path,
                        title=doc.title,
                        source=doc.source,
                        source_url=doc.source_url,
                        author=doc.author,
                        created_at=doc.created_at,
                        updated_at=doc.updated_at,
                        version=doc.version,
                        doc_status=doc.doc_status,
                        authority_score=doc.authority_score,
                        language=doc.language,
                        owner_group=doc.owner_group,
                        acl=doc.acl,
                        pii_flags=[],
                        tenant_id=doc.metadata.get("tenant_id", "tenant-nimbus-default"),
                    )
                )

        return document_chunks
