from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from uuid import UUID


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    reserved_usd: float
    settled_usd: float = 0.0


class BudgetLedger:
    def __init__(self) -> None:
        self._lock = RLock()
        self._entries: dict[UUID, LedgerEntry] = {}

    def reserve(self, task_id: UUID, amount_usd: float) -> None:
        if amount_usd <= 0:
            raise ValueError("Reservation must be positive")
        with self._lock:
            if task_id in self._entries:
                raise ValueError("Budget is already reserved for this task")
            self._entries[task_id] = LedgerEntry(reserved_usd=amount_usd)

    def settle(self, task_id: UUID, actual_usd: float) -> float:
        if actual_usd < 0:
            raise ValueError("Actual spend cannot be negative")
        with self._lock:
            entry = self._entries.get(task_id)
            if entry is None:
                raise KeyError(f"No reservation for task {task_id}")
            self._entries[task_id] = LedgerEntry(entry.reserved_usd, actual_usd)
            return max(entry.reserved_usd - actual_usd, 0.0)

    def remaining(self, task_id: UUID) -> float:
        with self._lock:
            entry = self._entries.get(task_id)
            if entry is None:
                return 0.0
            return max(entry.reserved_usd - entry.settled_usd, 0.0)


ledger = BudgetLedger()
