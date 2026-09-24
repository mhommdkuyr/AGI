from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VerificationResult:
    passed: bool
    reason: str


def verify_terminal(*, history, task_text: str) -> VerificationResult:
    """MVP verifier: require a completed history and non-empty evidence.

    It deliberately does not infer success from a model's prose alone.
    Stronger task-specific verifiers will be added for artifacts, downloads,
    forms, messages, and other observable state transitions.
    """
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
