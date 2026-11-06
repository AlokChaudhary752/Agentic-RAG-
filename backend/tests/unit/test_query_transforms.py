"""Unit tests for query transformations, rewriting, expansion, and step-back queries."""

import pytest

from app.retrieval.query_transforms import QueryTransformer


@pytest.mark.unit
def test_query_rewriting() -> None:
    """Verify ambiguous pronouns trigger company context injection."""
    transformer = QueryTransformer()
    rewritten = transformer.rewrite_query("What is its leave policy?")
    assert "Nimbus Technologies" in rewritten


@pytest.mark.unit
def test_query_expansion() -> None:
    """Verify domain-specific queries expand into multiple complementary search terms."""
    transformer = QueryTransformer()
    expanded = transformer.expand_query("What is the engineering salary bands?")
    assert len(expanded) >= 2
    assert any("L3 L4 L5 L6" in q for q in expanded)


@pytest.mark.unit
def test_step_back_and_hyde() -> None:
    """Verify step-back query generation abstracts specific details."""
    transformer = QueryTransformer()
    step_back = transformer.generate_step_back_query("What is our P0 outage resolution time?")
    assert "IT operations, support tiers, and incident SLAs" in step_back

    bundle = transformer.transform("How to book flights in Navan?", enable_hyde=True)
    assert bundle.hypothetical_document is not None
    assert "Nimbus Technologies corporate guidelines" in bundle.hypothetical_document
