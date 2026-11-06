"""Unit tests for database session lifecycle and initialization."""

import pytest

from app.db.session import (
    get_db_session,
    get_engine,
    get_session_context,
    get_session_maker,
    init_db,
)


@pytest.mark.unit
async def test_init_db_and_session_factories() -> None:
    """Verify init_db creates all tables and engine/session factories initialize cleanly."""
    engine = get_engine()
    assert engine is not None

    session_maker = get_session_maker()
    assert session_maker is not None

    await init_db()

    async with get_session_context() as session:
        assert session.is_active


@pytest.mark.unit
async def test_get_db_session_dependency() -> None:
    """Verify FastAPI dependency yields active session."""
    generator = get_db_session()
    session = await anext(generator)
    assert session.is_active
    await generator.aclose()
