from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelRate:
    input_per_million: float
    output_per_million: float


RATES: dict[str, ModelRate] = {
    # Standard paid pricing currently published by Google.
    "gemini-3.8-flash": ModelRate(0.75, 3.75),
    "gemini-3.1-pro-preview": ModelRate(2.00, 12.00),
}


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


def estimate_token_cost(model: str, usage: Usage) -> float:
    rate = RATES.get(model)
    if rate is None:
        raise ValueError(f"No versioned pricing configured for model: {model}")
    return (
        (usage.input_tokens / 1_000_000) * rate.input_per_million
        + (usage.output_tokens / 1_000_000) * rate.output_per_million
    )
