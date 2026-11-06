"""Unit tests for PII detection and classification-based masking."""

import pytest

from app.domain.models import ClassificationLevel
from app.ingestion.pii.masker import PIIMasker


@pytest.mark.unit
def test_detect_all_pii_categories() -> None:
    """Verify PIIMasker detects email, phone, SSN, card, and salary."""
    masker = PIIMasker()
    sample = """
    Contact John at john.smith@example.com or call (555) 234-5678.
    His SSN is 000-12-3456 and corporate card is 4111-2222-3333-4444.
    Base salary: $150,000.
    """
    flags = masker.detect_pii(sample)
    assert "EMAIL" in flags
    assert "PHONE" in flags
    assert "SSN" in flags
    assert "CREDIT_CARD" in flags
    assert "SALARY" in flags


@pytest.mark.unit
def test_mask_public_document_redaction() -> None:
    """Verify PUBLIC documents strictly redact personal email, phone, and salary."""
    masker = PIIMasker()
    text = "Email me at user@gmail.com, phone 555-123-4567, SSN 123-45-6789. Base salary: $120,000."
    masked, flags = masker.mask(text, ClassificationLevel.PUBLIC)

    assert "[EMAIL_REDACTED]" in masked
    assert "[PHONE_REDACTED]" in masked
    assert "[SSN_REDACTED]" in masked
    assert "[REDACTED_PUBLIC_VIEW]" in masked
    assert "123-45-6789" not in masked


@pytest.mark.unit
def test_mask_internal_preserves_corporate_email() -> None:
    """Verify INTERNAL documents retain corporate @nimbus.com emails while masking external and SSNs."""
    masker = PIIMasker()
    text = "Work: alice@nimbus.com, Personal: alice@yahoo.com, SSN: 999-88-7777."
    masked, flags = masker.mask(text, ClassificationLevel.INTERNAL)

    assert "alice@nimbus.com" in masked
    assert "[EXTERNAL_EMAIL_REDACTED]" in masked
    assert "[SSN_REDACTED]" in masked
