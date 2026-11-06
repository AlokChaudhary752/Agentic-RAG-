"""Unit tests for layout-aware parsing and table extraction."""

import pytest

from app.ingestion.parsers.layout_parser import LayoutParser


@pytest.mark.unit
def test_extract_markdown_tables() -> None:
    """Verify table extractor finds and preserves markdown tables."""
    parser = LayoutParser()
    sample_md = """
# Heading

Here is some introductory text.

| Name | Role | Level |
|---|---|---|
| Alice | Engineer | L5 |
| Bob | Manager | M1 |

Concluding paragraph.
"""
    tables = parser.extract_tables(sample_md)
    assert len(tables) == 1
    assert "| Alice | Engineer | L5 |" in tables[0]
    assert "| Bob | Manager | M1 |" in tables[0]


@pytest.mark.unit
def test_parse_into_hierarchical_sections() -> None:
    """Verify parser breaks markdown into sections with proper breadcrumb paths."""
    parser = LayoutParser()
    sample_md = """# Corporate Policies
Overview text.

## Paid Leave
Leave guidelines.

### Sick Days
Sick leave details.
"""
    sections = parser.parse_into_sections(sample_md, doc_title="Employee Handbook")
    assert len(sections) == 3

    assert sections[0].heading_title == "Corporate Policies"
    assert sections[1].heading_title == "Paid Leave"
    assert sections[1].section_path == "Corporate Policies > Paid Leave"
    assert sections[2].heading_title == "Sick Days"
    assert sections[2].section_path == "Corporate Policies > Paid Leave > Sick Days"


@pytest.mark.unit
def test_clean_ocr_text() -> None:
    """Verify OCR cleaner fixes broken hyphenated words and excessive spacing."""
    parser = LayoutParser()
    raw_ocr = "This is a demon-\nstration of broken text  with   excessive    spacing."
    cleaned = parser.clean_ocr_text(raw_ocr)
    assert "demonstration" in cleaned
    assert "  " not in cleaned
