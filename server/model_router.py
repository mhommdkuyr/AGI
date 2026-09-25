from __future__ import annotations

from dataclasses import dataclass

from .config import Settings


@dataclass(frozen=True, slots=True)
class ModelChoice:
    executor_model: str
    planner_model: str
    reason: str


class ModelRouter:
    """Cost-aware routing for a browser-first stack.

    The computer-use executor stays on Gemini 3.8 Flash. Harder jobs can
    spend extra reasoning budget on a planning pass with Gemini 3.1 Pro,
    then return to the cheaper computer-use executor.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def choose(self, *, budget_usd: float, complexity: str = "normal", force_planner: str | None = None) -> ModelChoice:
        planner = force_planner or self.settings.planner_model
        if complexity == "extreme" and budget_usd < 0.25:
            planner = self.settings.primary_model
        elif complexity == "hard" and budget_usd < 0.10:
            planner = self.settings.primary_model
        return ModelChoice(
            executor_model=self.settings.primary_model,
            planner_model=planner,
            reason=f"executor={self.settings.primary_model}; planner={planner}; complexity={complexity}",
        )
