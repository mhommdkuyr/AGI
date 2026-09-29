from types import SimpleNamespace

from server.verifier import verify_browser_evidence, verify_terminal


def test_verifier_requires_terminal_success_and_evidence():
    history = SimpleNamespace(is_done=lambda: True, is_successful=lambda: True, final_result=lambda: "confirmed")
    assert verify_terminal(history=history, task_text="Complete the task").passed


def test_verifier_rejects_non_terminal_history():
    history = SimpleNamespace(is_done=lambda: False, is_successful=lambda: True, final_result=lambda: "confirmed")
    assert not verify_terminal(history=history, task_text="Complete the task").passed


def test_browser_evidence_matches_explicit_url_title_and_url():
    result = verify_browser_evidence(
        prompt="Open https://example.com and return the page title and URL.",
        final_text="The title is Example Domain and the URL is https://example.com/.",
        final_url="https://example.com/",
        final_title="Example Domain",
    )
    assert result.passed


def test_browser_evidence_rejects_wrong_requested_host():
    result = verify_browser_evidence(
        prompt="Open https://example.com and return the page title.",
        final_text="The title is Example Domain.",
        final_url="https://example.org/",
        final_title="Example Domain",
    )
    assert not result.passed


def test_browser_evidence_rejects_missing_title_evidence():
    result = verify_browser_evidence(
        prompt="Open https://example.com and return the page title.",
        final_text="Done.",
        final_url="https://example.com/",
        final_title="Example Domain",
    )
    assert not result.passed
