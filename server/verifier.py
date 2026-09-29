from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class VerificationResult:
    passed: bool
    reason: str


def verify_terminal(*, history, task_text: str) -> VerificationResult:
    """Legacy history verifier kept for callers with a structured execution history."""
    try:
        done = bool(history.is_done())
    except Exception:  # noqa: BLE001
        done = False
    try:
        successful = bool(history.is_successful())
    except Exception:  # noqa: BLE001
        successful = False
    try:
        result = str(history.final_result() or "").strip()
    except Exception:  # noqa: BLE001
        result = ""

    if not done:
        return VerificationResult(False, "Execution history is not terminal.")
    if not successful:
        return VerificationResult(False, "Execution history does not report success.")
    if not result:
        return VerificationResult(False, "No final evidence was produced.")
    if len(task_text.strip()) < 3:
        return VerificationResult(False, "Task objective is too short to verify.")
    return VerificationResult(True, "Terminal execution state has observable evidence.")


def verify_browser_evidence(*, prompt: str, final_text: str, final_url: str, final_title: str) -> VerificationResult:
    """Verify observable browser state without treating model prose as sufficient evidence."""
    prompt = prompt.strip()
    final_text = final_text.strip()
    final_url = final_url.strip()
    final_title = final_title.strip()

    if not prompt or len(prompt) < 3:
        return VerificationResult(False, "Task objective is too short to verify.")
    if not final_text:
        return VerificationResult(False, "No final evidence was produced.")
    parsed = urlparse(final_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return VerificationResult(False, "Final browser URL is not a valid HTTP(S) page.")
    if final_url.lower() == "about:blank":
        return VerificationResult(False, "Browser remained on a blank page.")
    if not final_title:
        return VerificationResult(False, "Final browser title is empty.")

    explicit_urls = re.findall(r"https?://[^\s)]+", prompt)
    if explicit_urls:
        expected = urlparse(explicit_urls[0])
        if expected.netloc and parsed.netloc.lower() != expected.netloc.lower():
            return VerificationResult(
                False,
                f"Final host {parsed.netloc!r} does not match requested host {expected.netloc!r}.",
            )

    lowered = prompt.lower()
    if any(token in lowered for token in ("title", "page title", "عنوان الصفحة", "العنوان")):
        if final_title.casefold() not in final_text.casefold():
            return VerificationResult(False, "Requested page title is not present in final evidence.")

    if any(token in lowered for token in ("url", "link", "الرابط", "الرابط النهائي")):
        if final_url not in final_text and parsed.netloc not in final_text:
            return VerificationResult(False, "Requested URL is not present in final evidence.")

    return VerificationResult(True, "Browser reached a valid terminal page and evidence matches requested constraints.")
