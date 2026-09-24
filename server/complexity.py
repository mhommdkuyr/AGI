from __future__ import annotations

import re


def classify_complexity(prompt: str) -> str:
    text = prompt.lower()
    score = 0
    score += min(len(re.findall(r"\b\S+\b", text)) // 35, 3)
    score += 2 if any(x in text for x in ("multiple sites", "compare", "across", "then", "after", "until")) else 0
    score += 2 if any(x in text for x in ("upload", "download", "form", "account", "dashboard", "checkout")) else 0
    score += 2 if any(x in text for x in ("code", "mfa", "captcha", "verification", "login")) else 0
    if score >= 6:
        return "extreme"
    if score >= 3:
        return "hard"
    return "normal"
