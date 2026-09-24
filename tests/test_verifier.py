from types import SimpleNamespace

from server.verifier import verify_terminal


def test_verifier_requires_terminal_success_and_evidence():
    history = SimpleNamespace(is_done=lambda: True, is_successful=lambda: True, final_result=lambda: "confirmed")
    assert verify_terminal(history=history, task_text="Complete the task").passed


def test_verifier_rejects_non_terminal_history():
    history = SimpleNamespace(is_done=lambda: False, is_successful=lambda: True, final_result=lambda: "confirmed")
    assert not verify_terminal(history=history, task_text="Complete the task").passed
