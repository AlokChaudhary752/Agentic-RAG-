"""Unit tests for JWT security utilities and token verification."""

from datetime import timedelta

import pytest

from app.core.errors import UnauthorizedError
from app.core.security import create_access_token, decode_access_token


@pytest.mark.unit
def test_create_and_decode_access_token() -> None:
    """Verify create_access_token produces a valid token decodable by decode_access_token."""
    payload = {"sub": "user-alice-123", "tenant_id": "tenant-test", "roles": ["engineer"]}
    token = create_access_token(payload)
    assert isinstance(token, str)

    decoded = decode_access_token(token)
    assert decoded["sub"] == "user-alice-123"
    assert decoded["tenant_id"] == "tenant-test"
    assert decoded["roles"] == ["engineer"]
    assert "exp" in decoded
    assert "iat" in decoded


@pytest.mark.unit
def test_expired_token_raises_unauthorized() -> None:
    """Verify expired token raises UnauthorizedError."""
    payload = {"sub": "user-bob"}
    token = create_access_token(payload, expires_delta=timedelta(seconds=-10))

    with pytest.raises(UnauthorizedError, match="Token has expired"):
        decode_access_token(token)


@pytest.mark.unit
def test_invalid_signature_raises_unauthorized() -> None:
    """Verify tampered token raises UnauthorizedError."""
    payload = {"sub": "user-charlie"}
    token = create_access_token(payload)
    tampered_token = token[:-5] + "ABCDE"

    with pytest.raises(UnauthorizedError, match="Invalid token signature"):
        decode_access_token(tampered_token)
