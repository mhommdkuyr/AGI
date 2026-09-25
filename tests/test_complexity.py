from server.complexity import classify_complexity


def test_simple_task_is_normal():
    assert classify_complexity("search for a word") == "normal"


def test_workflow_task_is_hard_or_extreme():
    result = classify_complexity("log in, compare three sites, download files, then submit the form")
    assert result in {"hard", "extreme"}
