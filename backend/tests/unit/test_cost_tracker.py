"""Unit tests for LLM cost tracking, budget enforcement, and model routing."""

import pytest

from app.core.config import Settings
from app.core.cost_tracker import CostTracker
from app.core.errors import BudgetExceededError


def test_cost_calculation_per_model() -> None:
    """Verify dollar cost estimation per 1M tokens across models."""
    tracker = CostTracker()

    # Gemini 1.5 Flash: $0.075 / 1M prompt, $0.30 / 1M completion
    cost_flash = tracker.calculate_cost_usd(
        model="gemini/gemini-1.5-flash",
        prompt_tokens=10_000,
        completion_tokens=2_000,
    )
    # (10k / 1M * 0.075) + (2k / 1M * 0.30) = 0.00075 + 0.0006 = 0.00135
    assert cost_flash == 0.00135

    # Local Ollama: $0.00
    cost_ollama = tracker.calculate_cost_usd(
        model="ollama/llama3",
        prompt_tokens=50_000,
        completion_tokens=10_000,
    )
    assert cost_ollama == 0.0


def test_track_usage_metrics_and_budget_enforcement() -> None:
    """Verify Prometheus counter integration and budget enforcement threshold."""
    settings = Settings(agent_budget_usd_per_query=0.05)
    tracker = CostTracker(settings=settings)

    # Within budget
    cost = tracker.track_usage(
        tenant_id="tenant-test",
        model="gemini/gemini-1.5-flash",
        prompt_tokens=500,
        completion_tokens=200,
    )
    assert cost < 0.05
    tracker.enforce_budget(cost)

    # Exceeds budget: should raise BudgetExceededError
    with pytest.raises(BudgetExceededError) as exc_info:
        tracker.enforce_budget(0.06)
    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "BUDGET_EXCEEDED"


def test_model_routing_strategy() -> None:
    """Verify fast model selection for classification/grading and strong model for synthesis."""
    settings = Settings(
        llm_fast_model="gemini/gemini-1.5-flash",
        llm_strong_model="gemini/gemini-1.5-pro",
    )
    tracker = CostTracker(settings=settings)

    assert tracker.route_model("classification") == "gemini/gemini-1.5-flash"
    assert tracker.route_model("grading") == "gemini/gemini-1.5-flash"
    assert tracker.route_model("synthesis") == "gemini/gemini-1.5-pro"
    assert tracker.route_model("verification") == "gemini/gemini-1.5-pro"
