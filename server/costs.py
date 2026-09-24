from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelRate:
    input_per_million: float
    output_per_million: float


RATES = {
    "gemini-3.8-flash": ModelRate(0.75, 3.75),
    "claude-sonnet-5": ModelRate(2.00, 10.00),
    "gpt-6-sol": ModelRate(2.00, 10.00),
    "gpt-6-luna": ModelRate(0.10, 0.50),
}


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


def estimate_token_cost(model: str, usage: Usage) -> float:
    rate = RATES.get(model)
    if rate is None:
        raise ValueError(f"No pricing configured for model: {model}")
    return (usage.input_tokens / 1_000_000) * rate.input_per_million + (usage.output_tokens / 1_000_000) * rate.output_per_million
