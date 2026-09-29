from __future__ import annotations

from dataclasses import dataclass

from .config import Settings


@dataclass(frozen=True, slots=True)
class ModelChoice:
    executor_model: str
    planner_model: str | None
    reason: str


class ModelRouter:
    """Route planning work only when task complexity justifies the extra spend."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def choose(
        self,
        *,
        budget_usd: float,
        complexity: str = "normal",
        force_planner: str | None = None,
    ) -> ModelChoice:
        if force_planner:
            planner = force_planner
        elif complexity == "extreme":
            planner = (
                self.settings.planner_model
                if budget_usd >= 0.50
                else self.settings.primary_model
            )
        elif complexity == "hard":
            planner = (
                self.settings.planner_model
                if budget_usd >= 0.25
                else self.settings.primary_model
            )
        else:
            planner = None

        reason = (
            f"executor={self.settings.primary_model}; "
            f"planner={planner or 'none'}; complexity={complexity}"
        )
        return ModelChoice(
            executor_model=self.settings.primary_model,
            planner_model=planner,
            reason=reason,
        )
