"""Conversation memory, sliding window management, and long-term user profile store."""

from datetime import UTC, datetime
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from app.core.logging import get_logger

logger = get_logger(__name__)


class ConversationMemoryManager:
    """Manages short-term conversation sliding window and long-term user context with forget support."""

    def __init__(self, window_size: int = 10) -> None:
        self.window_size = window_size
        self.checkpointer = MemorySaver()
        self._long_term_store: dict[str, dict[str, Any]] = {}

    def get_checkpointer(self) -> MemorySaver:
        """Provide LangGraph checkpointer for state checkpointing and interrupt/resume."""
        return self.checkpointer

    def trim_history(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Maintain recent sliding window of messages to stay within token budgets."""
        if len(messages) <= self.window_size:
            return messages
        return messages[-self.window_size :]

    def save_user_memory(
        self,
        tenant_id: str,
        user_id: str,
        facts: dict[str, Any],
    ) -> None:
        """Store summarized long-term preferences or context for a specific employee."""
        key = f"{tenant_id}:{user_id}"
        existing = self._long_term_store.setdefault(key, {})
        existing.update(facts)
        existing["updated_at"] = datetime.now(UTC).isoformat()
        logger.info("Updated long-term user memory", user_id=user_id, tenant_id=tenant_id)

    def get_user_memory(self, tenant_id: str, user_id: str) -> dict[str, Any]:
        """Fetch long-term memory for a specific employee."""
        key = f"{tenant_id}:{user_id}"
        return self._long_term_store.get(key, {})

    def forget_user_memory(self, tenant_id: str, user_id: str) -> bool:
        """Delete/forget all stored long-term memory for a user (GDPR / right-to-be-forgotten)."""
        key = f"{tenant_id}:{user_id}"
        removed = self._long_term_store.pop(key, None) is not None
        logger.info("Purged long-term user memory", user_id=user_id, success=removed)
        return removed
