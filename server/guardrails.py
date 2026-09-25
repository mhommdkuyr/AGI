from __future__ import annotations

import re

from .domain import HandoffReason


AUTH_PATTERNS = (
    r"\blog[ -]?in\b", r"\bsign[ -]?in\b", r"\bpassword\b", r"\bverification code\b",
    r"\bone[- ]time password\b", r"\bmulti[- ]factor\b", r"\bmfa\b", r"\bpasskey\b",
    r"\bcaptcha\b", r"\bsecurity check\b", r"\bverify you are human\b",
)


def classify_handoff(text: str | None) -> HandoffReason | None:
    if not text:
        return None
    lowered = text.lower()
    if "captcha" in lowered or "verify you are human" in lowered:
        return HandoffReason.HUMAN_VERIFICATION
    if any(re.search(pattern, lowered) for pattern in AUTH_PATTERNS):
        return HandoffReason.AUTHENTICATION
    return None


def looks_like_loop(text: str | None) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(token in lowered for token in ("same state", "no change", "repeating", "loop detected"))
