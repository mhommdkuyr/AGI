from __future__ import annotations

import base64
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class MobileSession:
    id: str
    device_name: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    observation: dict[str, Any] | None = None
    screenshot_b64: str | None = None
    commands: list[dict[str, Any]] = field(default_factory=list)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)
    changed: threading.Condition = field(init=False)

    def __post_init__(self) -> None:
        self.changed = threading.Condition(self.lock)

    def update_observation(
        self,
        observation: dict[str, Any],
        screenshot_b64: str | None = None,
    ) -> None:
        with self.changed:
            self.observation = observation
            self.screenshot_b64 = screenshot_b64
            self.updated_at = time.time()
            self.changed.notify_all()

    def wait_for_observation(self, timeout_s: float = 30.0) -> tuple[dict[str, Any], str | None]:
        deadline = time.time() + timeout_s
        with self.changed:
            while self.observation is None:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise TimeoutError("Timed out waiting for a mobile observation.")
                self.changed.wait(timeout=remaining)
            return dict(self.observation), self.screenshot_b64

    def enqueue(self, action: dict[str, Any]) -> str:
        command_id = str(uuid4())
        with self.changed:
            self.commands.append({"id": command_id, **action})
            self.changed.notify_all()
        return command_id

    def next_command(self) -> dict[str, Any] | None:
        with self.lock:
            return self.commands.pop(0) if self.commands else None

    def set_result(self, command_id: str, result: dict[str, Any]) -> None:
        with self.changed:
            self.results[command_id] = result
            self.changed.notify_all()

    def wait_for_result(self, command_id: str, timeout_s: float = 30.0) -> dict[str, Any]:
        deadline = time.time() + timeout_s
        with self.changed:
            while command_id not in self.results:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise TimeoutError("Timed out waiting for the mobile command result.")
                self.changed.wait(timeout=remaining)
            return self.results.pop(command_id)


class MobileBridge:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, MobileSession] = {}

    def create_session(self, device_name: str) -> MobileSession:
        session = MobileSession(str(uuid4()), device_name.strip() or "Android device")
        with self._lock:
            self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> MobileSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    @staticmethod
    def screenshot_bytes(session: MobileSession) -> bytes | None:
        if not session.screenshot_b64:
            return None
        try:
            return base64.b64decode(session.screenshot_b64, validate=True)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def sanitize_observation(raw: dict[str, Any]) -> dict[str, Any]:
        # Keep the wire format small and do not retain raw password text.
        value = json.loads(json.dumps(raw))
        for node in value.get("nodes", []):
            if bool(node.get("password")):
                node["text"] = None
                node["content_description"] = None
        return value


mobile_bridge = MobileBridge()
