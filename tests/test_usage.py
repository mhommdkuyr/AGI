from uuid import uuid4

import pytest

from server.usage import BudgetLedger


def test_reserve_then_settle_releases_unused_budget():
    ledger = BudgetLedger()
    task_id = uuid4()
    ledger.reserve(task_id, 1.0)
    assert ledger.remaining(task_id) == 1.0
    assert ledger.settle(task_id, 0.4) == 0.6
    assert ledger.remaining(task_id) == 0.6


def test_duplicate_reservation_is_rejected():
    ledger = BudgetLedger()
    task_id = uuid4()
    ledger.reserve(task_id, 1.0)
    with pytest.raises(ValueError):
        ledger.reserve(task_id, 1.0)
