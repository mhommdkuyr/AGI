import pytest

from server.economics import EconomicsInputs, quote_price


def test_quote_price_includes_costs_fees_reserve_and_margin():
    result = quote_price(
        EconomicsInputs(
            direct_cost_usd=10.0,
            payment_fee_rate=0.10,
            tax_rate=0.05,
            target_margin_rate=0.20,
            risk_reserve_rate=0.05,
        )
    )
    assert result == pytest.approx(16.6666667, rel=1e-6)


def test_invalid_rate_rejected():
    with pytest.raises(ValueError):
        quote_price(EconomicsInputs(direct_cost_usd=1.0, target_margin_rate=1.0))
