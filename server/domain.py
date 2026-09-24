from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_HUMAN = "waiting_human"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HandoffReason(StrEnum):
    AUTHENTICATION = "authentication"
    HUMAN_VERIFICATION = "human_verification"
    SENSITIVE_ACTION = "sensitive_action"
    UNKNOWN_BLOCK = "unknown_block"


@dataclass(slots=True)
class TaskRecord:
    id: UUID
    user_id: str
    prompt: str
    status: TaskStatus
    budget_usd: float
    reserved_usd: float = 0.0
    spent_usd: float = 0.0
    model: str | None = None
    steps: int = 0
    failure_count: int = 0
    result: str | None = None
    error: str | None = None
    handoff_reason: HandoffReason | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        now = utc_now()
        self.created_at = self.created_at or now
        self.updated_at = self.updated_at or now

    @classmethod
    def new(cls, user_id: str, prompt: str, budget_usd: float) -> "TaskRecord":
        return cls(uuid4(), user_id, prompt, TaskStatus.QUEUED, budget_usd)

    def touch(self) -> None:
        self.updated_at = utc_now()
