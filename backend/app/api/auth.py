"""Authentication API routes and principal extraction dependencies."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import UnauthorizedError
from app.core.security import create_access_token, decode_access_token, verify_password
from app.db.repositories.user_repo import UserRepository
from app.db.session import get_db_session
from app.domain.models import ClassificationLevel, UserPrincipal

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    """User login request payload."""

    email: EmailStr = Field(..., description="Corporate email address")
    password: str = Field(..., description="User password")


class TokenResponse(BaseModel):
    """JWT access token response."""

    access_token: str = Field(..., description="Signed JWT access token")
    token_type: str = Field(default="bearer", description="Token schema type")
    expires_in_minutes: int = Field(..., description="Validity period in minutes")
    user: UserPrincipal = Field(..., description="Authenticated user principal")


async def get_current_principal(
    authorization: Annotated[str | None, Header()] = None,
) -> UserPrincipal:
    """FastAPI dependency to extract and validate UserPrincipal from Authorization Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header. Expected 'Bearer <token>'")

    token = authorization.split("Bearer ", 1)[1].strip()
    payload = decode_access_token(token)

    try:
        user_id = payload.get("user_id") or payload.get("sub")
        email = payload.get("email")
        full_name = payload.get("full_name", "Employee")
        roles = payload.get("roles", ["employee"])
        groups = payload.get("groups", [])
        clearance_str = payload.get("clearance", "INTERNAL")
        tenant_id = payload.get("tenant_id", "tenant-nimbus-default")

        if not user_id or not email:
            raise UnauthorizedError("Malformed token payload: missing identity claims")

        clearance = ClassificationLevel(clearance_str)

        return UserPrincipal(
            user_id=str(user_id),
            email=str(email),
            full_name=str(full_name),
            roles=roles,
            groups=groups,
            clearance=clearance,
            tenant_id=str(tenant_id),
        )
    except Exception as exc:
        raise UnauthorizedError(f"Failed to resolve principal from token: {exc}") from exc


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    """Authenticate corporate credentials and issue a signed permission-bearing JWT access token."""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_email(req.email)

    if not user or not verify_password(req.password, user.hashed_password):
        raise UnauthorizedError("Invalid corporate email or password")

    settings = get_settings()
    principal = await user_repo.resolve_principal(user.id)
    if not principal:
        raise UnauthorizedError("User account is inactive or disabled")

    token_data = {
        "sub": principal.user_id,
        "user_id": principal.user_id,
        "email": principal.email,
        "full_name": principal.full_name,
        "roles": principal.roles,
        "groups": principal.groups,
        "clearance": principal.clearance.value,
        "tenant_id": principal.tenant_id,
    }

    access_token = create_access_token(token_data)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_minutes=settings.access_token_expire_minutes,
        user=principal,
    )


@router.get("/me", response_model=UserPrincipal)
async def get_current_user_profile(
    principal: Annotated[UserPrincipal, Depends(get_current_principal)],
) -> UserPrincipal:
    """Return the currently authenticated user's profile, roles, groups, and clearance."""
    return principal
