"""Unit tests for conversation memory manager and right-to-be-forgotten support."""

import pytest

from app.agent.memory import ConversationMemoryManager


@pytest.mark.unit
def test_sliding_window_trimming() -> None:
    """Verify memory manager keeps message history within sliding window bounds."""
    manager = ConversationMemoryManager(window_size=3)

    messages = [
        {"role": "user", "content": "msg 1"},
        {"role": "assistant", "content": "msg 2"},
        {"role": "user", "content": "msg 3"},
        {"role": "assistant", "content": "msg 4"},
        {"role": "user", "content": "msg 5"},
    ]

    trimmed = manager.trim_history(messages)
    assert len(trimmed) == 3
    assert trimmed[0]["content"] == "msg 3"
    assert trimmed[2]["content"] == "msg 5"


@pytest.mark.unit
def test_long_term_user_memory_lifecycle() -> None:
    """Verify saving, retrieving, and GDPR-compliant purging of long-term user context."""
    manager = ConversationMemoryManager()

    tenant_id = "tenant-nimbus-default"
    user_id = "emp_alice"

    # 1. Save facts
    manager.save_user_memory(
        tenant_id=tenant_id,
        user_id=user_id,
        facts={"preferred_language": "hi", "favorite_tools": ["jira", "slack"]},
    )

    # 2. Retrieve facts
    mem = manager.get_user_memory(tenant_id, user_id)
    assert mem["preferred_language"] == "hi"
    assert "jira" in mem["favorite_tools"]
    assert "updated_at" in mem

    # 3. Forget / purge user memory
    purged = manager.forget_user_memory(tenant_id, user_id)
    assert purged is True

    # 4. Verify context is deleted
    assert manager.get_user_memory(tenant_id, user_id) == {}

