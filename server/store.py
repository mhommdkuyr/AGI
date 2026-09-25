from __future__ import annotations

from threading import RLock
from uuid import UUID

from .domain import TaskRecord


class TaskStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._tasks: dict[UUID, TaskRecord] = {}

    def create(self, task: TaskRecord) -> TaskRecord:
        with self._lock:
            self._tasks[task.id] = task
        return task

    def get(self, task_id: UUID) -> TaskRecord | None:
        with self._lock:
            return self._tasks.get(task_id)


store = TaskStore()
