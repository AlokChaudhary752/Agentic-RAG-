"""Layout-aware document parser preserving tables, markdown headings, and OCR fallbacks."""

import re

from pydantic import BaseModel, Field


class ParsedSection(BaseModel):
    """Extracted layout section with heading hierarchy and content."""

    heading_level: int = Field(default=0, description="0 for body, 1 for H1, 2 for H2, etc.")
    heading_title: str = Field(default="", description="Section title")
    section_path: str = Field(
        default="", description="Full breadcrumb path (e.g. Policies > Leaves)"
    )
    content: str = Field(..., description="Section content including markdown tables")
    is_table: bool = Field(default=False, description="True if section is a structured data table")


class LayoutParser:
    """Parses heterogeneous documents into structured sections while preserving tables and formatting."""

    def __init__(self) -> None:
        self.table_pattern = re.compile(
            r"(\|[^\n]+\|\r?\n\|[-:\s|]+\|\r?\n(?:\|[^\n]+\|\r?\n?)+)", re.MULTILINE
        )
        self.heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def extract_tables(self, text: str) -> list[str]:
        """Detect and extract all GitHub-flavored Markdown tables."""
        return [match.group(1).strip() for match in self.table_pattern.finditer(text)]

    def clean_ocr_text(self, raw_text: str) -> str:
        """Heuristic cleaner correcting common OCR artifacts and broken hyphenation."""
        # Fix hyphenated line breaks (e.g. "connec-\ntion" -> "connection")
        cleaned = re.sub(r"(\w+)-\n(\w+)", r"\1\2", raw_text)
        # Normalize excessive whitespace but preserve newlines
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def parse_into_sections(self, content: str, doc_title: str = "") -> list[ParsedSection]:
        """Break document into semantic hierarchical sections based on Markdown headings."""
        lines = content.splitlines()
        sections: list[ParsedSection] = []
        current_heading_level = 0
        current_heading_title = doc_title or "Overview"
        heading_stack: list[str] = [current_heading_title] if current_heading_title else []
        current_content_lines: list[str] = []

        for line in lines:
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
            if heading_match:
                # Flush previous section
                if current_content_lines:
                    text_block = "\n".join(current_content_lines).strip()
                    if text_block:
                        path_str = " > ".join(heading_stack)
                        is_tbl = bool(self.table_pattern.search(text_block))
                        sections.append(
                            ParsedSection(
                                heading_level=current_heading_level,
                                heading_title=current_heading_title,
                                section_path=path_str,
                                content=text_block,
                                is_table=is_tbl,
                            )
                        )
                    current_content_lines = []

                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                current_heading_level = level
                current_heading_title = title

                # Update heading breadcrumb stack
                while len(heading_stack) >= level:
                    heading_stack.pop()
                heading_stack.append(title)
            else:
                current_content_lines.append(line)

        # Flush final section
        if current_content_lines:
            text_block = "\n".join(current_content_lines).strip()
            if text_block:
                path_str = " > ".join(heading_stack)
                is_tbl = bool(self.table_pattern.search(text_block))
                sections.append(
                    ParsedSection(
                        heading_level=current_heading_level,
                        heading_title=current_heading_title,
                        section_path=path_str,
                        content=text_block,
                        is_table=is_tbl,
                    )
                )

        if not sections and content.strip():
            # Fallback for plain text without markdown headings
            sections.append(
                ParsedSection(
                    heading_level=0,
                    heading_title=doc_title or "Document",
                    section_path=doc_title or "Document",
                    content=content.strip(),
                    is_table=bool(self.table_pattern.search(content)),
                )
            )

        return sections
