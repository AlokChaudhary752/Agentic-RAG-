"""LLM token cost calculation, budget enforcement, and model routing."""

from typing import Literal

from app.core.config import Settings, get_settings
from app.core.errors import BudgetExceededError
from app.core.logging import get_logger
from app.core.telemetry import ESTIMATED_COST_COUNTER, TOKEN_USAGE_COUNTER

logger = get_logger(__name__)

# Model pricing table per 1,000,000 tokens (USD)
# (prompt_price_per_1m, completion_price_per_1m)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gemini/gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini/gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-pro": (1.25, 5.00),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4o": (2.50, 10.00),
    "gpt-4o": (2.50, 10.00),
    "ollama/llama3": (0.00, 0.00),
    "local": (0.00, 0.00),
}

DEFAULT_PRICING = (0.50, 1.50)


class CostTracker:
    """Manages token accounting, cost estimation, and query budget enforcement."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def calculate_cost_usd(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """Compute estimated USD cost for a given LLM completion call."""
        pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
        prompt_cost = (prompt_tokens / 1_000_000.0) * pricing[0]
        completion_cost = (completion_tokens / 1_000_000.0) * pricing[1]
        return round(prompt_cost + completion_cost, 6)

    def track_usage(
        self,
        tenant_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """Record token telemetry into Prometheus metrics and return financial cost in USD."""
        cost_usd = self.calculate_cost_usd(model, prompt_tokens, completion_tokens)

        # Update Prometheus metrics
        TOKEN_USAGE_COUNTER.labels(
            tenant_id=tenant_id, model=model, token_type="prompt"
        ).inc(prompt_tokens)
        TOKEN_USAGE_COUNTER.labels(
            tenant_id=tenant_id, model=model, token_type="completion"
        ).inc(completion_tokens)
        ESTIMATED_COST_COUNTER.labels(
            tenant_id=tenant_id, model=model
        ).inc(cost_usd)

        logger.debug(
            "Tracked LLM token usage",
            tenant_id=tenant_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
        )

        return cost_usd

    def enforce_budget(self, total_query_cost_usd: float) -> None:
        """Verify cumulative query cost does not exceed configured per-query budget."""
        max_budget = self.settings.agent_budget_usd_per_query
        if total_query_cost_usd > max_budget:
            logger.error(
                "Query financial budget exceeded",
                cost_usd=total_query_cost_usd,
                max_budget=max_budget,
            )
            raise BudgetExceededError(
                details={
                    "actual_cost_usd": total_query_cost_usd,
                    "budget_limit_usd": max_budget,
                }
            )

    def route_model(
        self,
        task: Literal["classification", "grading", "synthesis", "verification"],
    ) -> str:
        """Route to cost-effective fast model or strong synthesis model based on cognitive load."""
        if task in ("classification", "grading"):
            return self.settings.llm_fast_model
        return self.settings.llm_strong_model


_cost_tracker: CostTracker | None = None


def get_cost_tracker() -> CostTracker:
    """Retrieve singleton CostTracker instance."""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker
