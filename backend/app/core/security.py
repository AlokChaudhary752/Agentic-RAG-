"""Security module providing JWT token handling, hashing, and signature verification."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import get_settings
from app.core.errors import UnauthorizedError

ALGORITHM = "HS256"


def get_password_hash(password: str) -> str:
    """Generate a secure PBKDF2-HMAC-SHA256 salted password hash."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"pbkdf2:sha256:{salt}:{key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain text password against PBKDF2 hash or development seed mock hash."""
    if not hashed_password or not plain_password:
        return False

    parts = hashed_password.split(":")
    if len(parts) == 4 and parts[0] == "pbkdf2" and parts[1] == "sha256":
        salt = parts[2]
        expected_hex = parts[3]
        calculated_key = hashlib.pbkdf2_hmac(
            "sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100_000
        )
        return hmac.compare_digest(calculated_key.hex(), expected_hex)

    # Support seed/demo credentials (e.g. "pbkdf2:sha256:fakehash_alice")
    if hashed_password.startswith("pbkdf2:sha256:fakehash_"):
        user_suffix = hashed_password.split("fakehash_")[-1]
        return plain_password in (user_suffix, f"{user_suffix}123", "password")

    return hmac.compare_digest(plain_password, hashed_password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Encode user claims into a signed JSON Web Token (JWT)."""
    settings = get_settings()
    to_encode = data.copy()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt: str = jwt.encode(
        to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed JWT token."""
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError as err:
        raise UnauthorizedError("Token has expired") from err
    except jwt.InvalidTokenError as err:
        raise UnauthorizedError("Invalid token signature or payload") from err
