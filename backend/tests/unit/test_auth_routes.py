"""Unit tests for authentication API routes and JWT security principal resolution."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.db.repositories.user_repo import UserRepository
from app.db.session import get_db_session
from app.domain.models import ClassificationLevel
from app.main import app


@pytest.fixture
async def setup_auth_users(async_session: AsyncSession) -> AsyncGenerator[None, None]:
    repo = UserRepository(async_session)
    await repo.upsert_group("group_engineering", "Engineering", "Software Team")
    await repo.upsert_group("group_managers", "Management", "People Managers")

    hashed_pw = get_password_hash("SecretPass123!")
    await repo.upsert_user(
        user_id="emp_alice",
        email="alice@nimbus.com",
        full_name="Alice Smith",
        hashed_password=hashed_pw,
        role="employee",
        clearance="INTERNAL",
        group_ids=["group_engineering"],
    )

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield async_session

    app.dependency_overrides[get_db_session] = override_get_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.unit
async def test_auth_login_successful(setup_auth_users: None) -> None:
    """Verify login returns valid JWT token and resolved UserPrincipal."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": "alice@nimbus.com", "password": "SecretPass123!"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["user_id"] == "emp_alice"
        assert data["user"]["email"] == "alice@nimbus.com"
        assert data["user"]["clearance"] == "INTERNAL"
        assert "group_engineering" in data["user"]["groups"]


@pytest.mark.unit
async def test_auth_login_invalid_password(setup_auth_users: None) -> None:
    """Verify login fails with 401 when given invalid credentials."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": "alice@nimbus.com", "password": "WrongPassword!"},
        )
        assert res.status_code == 401
        assert "Invalid corporate email or password" in res.json()["error"]["message"]


@pytest.mark.unit
async def test_auth_me_endpoint() -> None:
    """Verify protected /auth/me route extracts UserPrincipal correctly from Bearer token."""
    token = create_access_token(
        {
            "sub": "mgr_bob",
            "user_id": "mgr_bob",
            "email": "bob@nimbus.com",
            "full_name": "Bob Jones",
            "roles": ["manager"],
            "groups": ["group_engineering", "group_managers"],
            "clearance": ClassificationLevel.CONFIDENTIAL.value,
            "tenant_id": "tenant-nimbus-default",
        }
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == "mgr_bob"
        assert data["email"] == "bob@nimbus.com"
        assert data["clearance"] == "CONFIDENTIAL"
        assert "group_managers" in data["groups"]


@pytest.mark.unit
async def test_auth_me_unauthorized_without_header() -> None:
    """Verify missing authorization header returns 401 Unauthorized."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/auth/me")
        assert res.status_code == 401
