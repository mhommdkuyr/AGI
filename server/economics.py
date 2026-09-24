from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EconomicsInputs:
    direct_cost_usd: float
    payment_fee_rate: float = 0.0
    fixed_payment_fee_usd: float = 0.0
    tax_rate: float = 0.0
    target_margin_rate: float = 0.35
    risk_reserve_rate: float = 0.05


def quote_price(inputs: EconomicsInputs) -> float:
    if not 0 <= inputs.payment_fee_rate < 1:
        raise ValueError("payment_fee_rate must be between 0 and 1")
    if not 0 <= inputs.tax_rate < 1:
        raise ValueError("tax_rate must be between 0 and 1")
    if not 0 <= inputs.target_margin_rate < 1:
        raise ValueError("target_margin_rate must be between 0 and 1")
    if not 0 <= inputs.risk_reserve_rate < 1:
        raise ValueError("risk_reserve_rate must be between 0 and 1")
    denominator = 1 - inputs.payment_fee_rate - inputs.tax_rate - inputs.risk_reserve_rate - inputs.target_margin_rate
    if denominator <= 0:
        raise ValueError("Configured rates leave no room for cost and margin")
    base = inputs.direct_cost_usd + inputs.fixed_payment_fee_usd
    return base / denominator
