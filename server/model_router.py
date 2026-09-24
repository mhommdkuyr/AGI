from __future__ import annotations

from dataclasses import dataclass

from .config import Settings


@dataclass(frozen=True, slots=True)
class ModelChoice:
    model: str
    provider: str
    reason: str


class ModelRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def choose(self, *, budget_usd: float, complexity: str = "normal", force: str | None = None) -> ModelChoice:
        if force:
            return self._choice(force, "explicit selection")
        if complexity == "extreme" and budget_usd >= 0.50:
            return self._choice(self.settings.escalation_model, "highest configured escalation tier")
        if complexity == "hard" and budget_usd >= 0.20:
            return self._choice(self.settings.secondary_model, "hard agentic workload")
        return self._choice(self.settings.primary_model, "default browser tier")

    @staticmethod
    def _choice(model: str, reason: str) -> ModelChoice:
        if model.startswith("gemini-"):
            provider = "google"
        elif model.startswith("claude-"):
            provider = "anthropic"
        elif model.startswith("gpt-"):
            provider = "openai"
        else:
            provider = "custom"
        return ModelChoice(model, provider, reason)
