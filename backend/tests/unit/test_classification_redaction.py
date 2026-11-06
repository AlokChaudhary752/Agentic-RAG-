"""Unit tests for classification-aware redaction engine."""

import pytest

from app.domain.models import ClassificationLevel, DocumentACL, DocumentChunk, UserPrincipal
from app.governance.redaction import ClassificationRedactor


@pytest.fixture
def redactor() -> ClassificationRedactor:
    return ClassificationRedactor()


@pytest.fixture
def employee_alice() -> UserPrincipal:
    return UserPrincipal(
        user_id="emp_alice",
        email="alice@nimbus.com",
        full_name="Alice Smith",
        roles=["employee"],
        groups=["group_engineering"],
        clearance=ClassificationLevel.INTERNAL,
    )


@pytest.fixture
def hr_carol() -> UserPrincipal:
    return UserPrincipal(
        user_id="hr_carol",
        email="carol@nimbus.com",
        full_name="Carol White",
        roles=["hr_admin"],
        groups=["group_hr"],
        clearance=ClassificationLevel.CONFIDENTIAL,
    )


@pytest.mark.unit
def test_insufficient_clearance_redacts_entire_chunk(
    redactor: ClassificationRedactor,
    employee_alice: UserPrincipal,
) -> None:
    """Verify chunk is completely redacted when user clearance is lower than chunk level."""
    confidential_chunk = DocumentChunk(
        id="c_conf",
        doc_id="fin-audit-2026",
        chunk_index=1,
        title="Internal Audit Report",
        content="Q4 operating loss was $2.4M due to acquisition expenses.",
        acl=DocumentACL(
            allowed_groups=["group_engineering", "group_finance"],
            classification_level=ClassificationLevel.CONFIDENTIAL,
        ),
    )

    # Alice has INTERNAL clearance, chunk requires CONFIDENTIAL
    redacted = redactor.redact_chunk(confidential_chunk, employee_alice)
    assert "[REDACTED: CLEARANCE INSUFFICIENT" in redacted.content
    assert "Requires CONFIDENTIAL, current: INTERNAL" in redacted.content
    assert "operating loss" not in redacted.content


@pytest.mark.unit
def test_pii_masked_for_regular_employee(
    redactor: ClassificationRedactor,
    employee_alice: UserPrincipal,
) -> None:
    """Verify regular employee receives masked PII when chunk contains PII flags."""
    chunk_with_pii = DocumentChunk(
        id="c_pii",
        doc_id="employee-contact-sheet",
        chunk_index=1,
        title="Team Directory",
        content="Contact John Doe at john.doe@personalmail.com or call 415-555-0199 for help.",
        acl=DocumentACL(
            allowed_groups=["group_engineering"],
            classification_level=ClassificationLevel.INTERNAL,
        ),
        pii_flags=["EMAIL", "PHONE"],
    )

    redacted = redactor.redact_chunk(chunk_with_pii, employee_alice)
    assert "john.doe@personalmail.com" not in redacted.content
    assert "415-555-0199" not in redacted.content
    assert "REDACTED" in redacted.content


@pytest.mark.unit
def test_pii_preserved_for_hr_admin(
    redactor: ClassificationRedactor,
    hr_carol: UserPrincipal,
) -> None:
    """Verify HR administrator retains full visibility over employee PII."""
    chunk_with_pii = DocumentChunk(
        id="c_pii",
        doc_id="employee-contact-sheet",
        chunk_index=1,
        title="Team Directory",
        content="Contact John Doe at john.doe@personalmail.com or call 415-555-0199 for help.",
        acl=DocumentACL(
            allowed_groups=["group_hr"],
            classification_level=ClassificationLevel.CONFIDENTIAL,
        ),
        pii_flags=["EMAIL", "PHONE"],
    )

    redacted = redactor.redact_chunk(chunk_with_pii, hr_carol)
    # Carol has group_hr and CONFIDENTIAL clearance, so PII is not masked
    assert "john.doe@personalmail.com" in redacted.content
    assert "415-555-0199" in redacted.content
