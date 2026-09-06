"""
Token Budgeting and Cost Accounting.
Maintains model pricing registry, computes per-request costs, and enforces budget caps.
"""
import time
from typing import Dict, Tuple
from backend.app.core.config import settings
from backend.app.core.exceptions import CostBudgetExceededException

# Pricing in USD per 1 Million Tokens (Input, Output)
MODEL_PRICING_PER_MILLION: Dict[str, Tuple[float, float]] = {
    # Groq Cloud (Primary Engine)
    "openai/gpt-oss-20b": (0.05, 0.08),
    "openai/gpt-oss-120b": (0.15, 0.25),
    "groq/compound-mini": (0.05, 0.08),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-70b-versatile": (0.59, 0.79),
    "llama-3.2-1b-preview": (0.04, 0.04),
    "llama-3.2-3b-preview": (0.06, 0.06),
    "llama-guard-3-8b": (0.20, 0.20),
    "mixtral-8x7b-32768": (0.24, 0.24),
    "gemma2-9b-it": (0.20, 0.20),
    # Local & Mock
    "mock-model": (0.00, 0.00),
    "local-deterministic": (0.00, 0.00),
    # Fallback / Secondary
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "claude-3-5-sonnet": (3.00, 15.00),
}


class CostTracker:
    def __init__(self):
        self._daily_spend = 0.0
        self._last_reset_day = time.strftime("%Y-%m-%d")

    def _check_day_rollover(self):
        current_day = time.strftime("%Y-%m-%d")
        if current_day != self._last_reset_day:
            self._daily_spend = 0.0
            self._last_reset_day = current_day

    def estimate_tokens(self, text: str) -> int:
        """
        Conservative token estimator (approx 4 chars per token for English text).
        """
        if not text:
            return 0
        return max(1, int(len(text) / 3.8))

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculates cost in USD for the given token consumption."""
        rates = MODEL_PRICING_PER_MILLION.get(model, (1.0, 2.0))
        input_cost = (input_tokens / 1_000_000.0) * rates[0]
        output_cost = (output_tokens / 1_000_000.0) * rates[1]
        return round(input_cost + output_cost, 6)

    def verify_request_budget(self, model: str, estimated_input_tokens: int, max_output_tokens: int):
        """Verifies if the estimated request will breach per-request or daily budget."""
        self._check_day_rollover()

        projected_cost = self.calculate_cost(model, estimated_input_tokens, max_output_tokens)
        if projected_cost > settings.PER_REQUEST_MAX_COST_USD:
            raise CostBudgetExceededException(
                f"Projected request cost ${projected_cost:.4f} exceeds per-request limit of ${settings.PER_REQUEST_MAX_COST_USD:.2f}"
            )

        if self._daily_spend + projected_cost > settings.DAILY_COST_BUDGET_USD:
            raise CostBudgetExceededException(
                f"Daily AI budget of ${settings.DAILY_COST_BUDGET_USD:.2f} reached. Current spend: ${self._daily_spend:.2f}"
            )

    def record_actual_spend(self, cost_usd: float):
        """Records actual incurred cost."""
        self._check_day_rollover()
        self._daily_spend += cost_usd

    def get_current_daily_spend(self) -> float:
        self._check_day_rollover()
        return round(self._daily_spend, 4)


cost_tracker = CostTracker()
