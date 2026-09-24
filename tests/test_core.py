from server.config import Settings
from server.costs import Usage, estimate_token_cost
from server.domain import HandoffReason
from server.guardrails import classify_handoff, looks_like_loop
from server.model_router import ModelRouter


def test_gemini_cost_estimate():
    cost = estimate_token_cost("gemini-3.8-flash", Usage(1_000_000, 1_000_000))
    assert cost == 4.5


def test_default_browser_router():
    choice = ModelRouter(Settings()).choose(budget_usd=0.75)
    assert choice.model == "gemini-3.8-flash"
    assert choice.provider == "google"


def test_hard_router_escalates():
    choice = ModelRouter(Settings()).choose(budget_usd=0.75, complexity="hard")
    assert choice.model == "claude-sonnet-5"


def test_auth_detection():
    assert classify_handoff("Enter the verification code") == HandoffReason.AUTHENTICATION


def test_human_verification_detection():
    assert classify_handoff("Verify you are human with CAPTCHA") == HandoffReason.HUMAN_VERIFICATION


def test_loop_detection():
    assert looks_like_loop("same state, no change")
