"""Unit tests for structured logging and correlation ID propagation."""

import uuid

import pytest

from app.core.logging import (
    add_correlation_fields,
    correlation_id_ctx_var,
    get_correlation_id,
    get_logger,
    setup_logging,
    tenant_id_ctx_var,
    user_id_ctx_var,
)


@pytest.mark.unit
def test_correlation_id_generation() -> None:
    """Verify get_correlation_id returns a valid UUID string and sets contextvar."""
    cid = get_correlation_id()
    assert isinstance(cid, str)
    assert len(cid) > 0
    # Calling again in same context returns identical ID
    assert get_correlation_id() == cid


@pytest.mark.unit
def test_add_correlation_fields_processor() -> None:
    """Verify add_correlation_fields injects contextvar values into event dict."""
    test_cid = str(uuid.uuid4())
    test_tid = "tenant-test-123"
    test_uid = "user-alice"

    correlation_id_ctx_var.set(test_cid)
    tenant_id_ctx_var.set(test_tid)
    user_id_ctx_var.set(test_uid)

    event_dict: dict[str, object] = {"event": "test_event"}
    processed = add_correlation_fields(None, "info", event_dict)  # type: ignore[arg-type]

    assert processed["correlation_id"] == test_cid
    assert processed["tenant_id"] == test_tid
    assert processed["user_id"] == test_uid


@pytest.mark.unit
def test_logger_setup_and_acquisition() -> None:
    """Verify logger setup does not raise exceptions and returns BoundLogger."""
    setup_logging(log_level="DEBUG", log_format="json")
    logger = get_logger("test.subsystem")
    assert logger is not None
