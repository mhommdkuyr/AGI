from __future__ import annotations

import base64
import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .domain import HandoffReason


AUTH_TEXT = re.compile(
    r"(captcha|verify you are human|security check|two-factor|two factor|"
    r"multi-factor|one-time password|verification code|sign in|log in|password)",
    re.IGNORECASE,
)


@dataclass
class GeminiBrowserSession:
    task_id: str
    playwright: Any
    browser: Any
    context: Any
    page: Any
    interaction_id: str | None = None
    status: str = "running"
    handoff_reason: HandoffReason | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)


class GeminiComputerUse:
    def __init__(self, api_key: str, root_dir: str = ".sessions") -> None:
        self.api_key = api_key
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, GeminiBrowserSession] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _xy(value: int, maximum: int) -> int:
        return max(0, min(maximum - 1, int(value / 1000 * maximum)))

    def _get_client(self):
        from google import genai
        return genai.Client(api_key=self.api_key)

    def _tool(self) -> dict[str, Any]:
        return {
            "type": "computer_use",
            "environment": "browser",
            "enable_prompt_injection_detection": True,
        }

    def _new_session(self, task_id: str) -> GeminiBrowserSession:
        from playwright.sync_api import sync_playwright

        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            storage_state=str(self.root_dir / task_id / "storage.json")
            if (self.root_dir / task_id / "storage.json").exists()
            else None,
        )
        page = context.new_page()
        return GeminiBrowserSession(task_id, pw, browser, context, page, lock=threading.RLock())

    def _get_or_create(self, task_id: str) -> GeminiBrowserSession:
        with self._lock:
            session = self._sessions.get(task_id)
            if session is not None:
                return session
            session = self._new_session(task_id)
            self._sessions[task_id] = session
            return session

    def _save_state(self, session: GeminiBrowserSession) -> None:
        folder = self.root_dir / session.task_id
        folder.mkdir(parents=True, exist_ok=True)
        session.context.storage_state(path=str(folder / "storage.json"))

    def _visible_text(self, page: Any) -> str:
        try:
            return page.locator("body").inner_text(timeout=1500)[:20000]
        except Exception:
            return ""

    def _human_gate(self, session: GeminiBrowserSession) -> HandoffReason | None:
        text = self._visible_text(session.page)
        if not text:
            return None
        lowered = text.lower()
        if "captcha" in lowered or "verify you are human" in lowered:
            return HandoffReason.HUMAN_VERIFICATION
        if AUTH_TEXT.search(text):
            # Avoid treating ordinary words in page content as a gate unless
            # they occur around authentication/security UI.
            auth_terms = ("sign in", "log in", "password", "verification code",
                          "two-factor", "two factor", "multi-factor", "passkey")
            if any(term in lowered for term in auth_terms):
                return HandoffReason.AUTHENTICATION
        return None

    @staticmethod
    def _step_type(step: Any) -> str:
        value = getattr(step, "type", None)
        return str(value or "")

    @staticmethod
    def _step_text(step: Any) -> str:
        try:
            parts = []
            for block in getattr(step, "content", None) or []:
                if getattr(block, "type", None) == "text":
                    parts.append(getattr(block, "text", "") or "")
            return " ".join(parts)
        except Exception:
            return ""

    def _extract_text(self, interaction: Any) -> str:
        texts = []
        for step in getattr(interaction, "steps", None) or []:
            if self._step_type(step) == "model_output":
                texts.append(self._step_text(step))
        return " ".join(x for x in texts if x).strip()

    def _calls(self, interaction: Any) -> list[Any]:
        return [s for s in (getattr(interaction, "steps", None) or [])
                if self._step_type(s) == "function_call"]

    def _execute(self, session: GeminiBrowserSession, calls: list[Any]) -> list[dict[str, Any]]:
        results = []
        page = session.page
        width, height = 1440, 900
        for call in calls:
            name = str(getattr(call, "name", "") or "")
            args = getattr(call, "arguments", {}) or {}
            if not isinstance(args, dict):
                args = dict(args)

            result: dict[str, Any] = {}
            try:
                x = self._xy(int(args.get("x", 0)), width)
                y = self._xy(int(args.get("y", 0)), height)

                if name in {"open_web_browser", "open_app"}:
                    pass
                elif name in {"click", "click_at"}:
                    page.mouse.click(x, y)
                elif name == "double_click":
                    page.mouse.dblclick(x, y)
                elif name == "right_click":
                    page.mouse.click(x, y, button="right")
                elif name == "middle_click":
                    page.mouse.click(x, y, button="middle")
                elif name == "move":
                    page.mouse.move(x, y)
                elif name == "long_press":
                    page.mouse.move(x, y)
                    page.mouse.down()
                    page.wait_for_timeout(700)
                    page.mouse.up()
                elif name in {"type", "type_text_at"}:
                    if "x" in args and "y" in args:
                        page.mouse.click(x, y)
                    page.keyboard.press("Control+A")
                    page.keyboard.type(str(args.get("text", "")))
                    if args.get("press_enter"):
                        page.keyboard.press("Enter")
                elif name == "navigate":
                    page.goto(str(args["url"]), wait_until="domcontentloaded", timeout=30000)
                elif name == "go_back":
                    page.go_back(wait_until="domcontentloaded", timeout=30000)
                elif name == "go_forward":
                    page.go_forward(wait_until="domcontentloaded", timeout=30000)
                elif name == "wait":
                    page.wait_for_timeout(max(100, int(float(args.get("seconds", 1)) * 1000)))
                else:
                    result["error"] = f"Unsupported computer-use action: {name}"

                result["url"] = page.url
                result["title"] = page.title()
            except Exception as exc:
                result["error"] = str(exc)
                result["url"] = page.url

            results.append({
                "type": "function_result",
                "name": name,
                "call_id": getattr(call, "id", ""),
                "result": [
                    {"type": "text", "text": json.dumps(result, ensure_ascii=False)},
                    {
                        "type": "image",
                        "data": base64.b64encode(page.screenshot(type="png")).decode("utf-8"),
                        "mime_type": "image/png",
                    },
                ],
            })
        return results

    def run(self, task_id: str, prompt: str, max_turns: int = 40) -> tuple[str, dict[str, Any]]:
        from google import genai  # noqa: F401

        session = self._get_or_create(task_id)
        with session.lock:
            session.status = "running"
            client = self._get_client()
            first = session.page.screenshot(type="png")
            interaction = client.interactions.create(
                model="gemini-3.8-flash",
                input=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "data": base64.b64encode(first).decode("utf-8"),
                        "mime_type": "image/png",
                    },
                ],
                tools=[self._tool()],
            )
            session.interaction_id = getattr(interaction, "id", None)

            for turn in range(max_turns):
                gate = self._human_gate(session)
                if gate:
                    session.status = "waiting_human"
                    session.handoff_reason = gate
                    self._save_state(session)
                    return "", {"status": "waiting_human", "reason": gate.value, "turns": turn}

                calls = self._calls(interaction)
                if not calls:
                    text = self._extract_text(interaction)
                    session.status = "finished"
                    self._save_state(session)
                    return text, {"status": "finished", "turns": turn + 1}

                responses = self._execute(session, calls)
                self._save_state(session)
                interaction = client.interactions.create(
                    model="gemini-3.8-flash",
                    previous_interaction_id=session.interaction_id,
                    input=responses,
                    tools=[self._tool()],
                )
                session.interaction_id = getattr(interaction, "id", session.interaction_id)

            session.status = "failed"
            return "", {"status": "failed", "error": "maximum computer-use turns reached"}

    def close(self, task_id: str) -> None:
        with self._lock:
            session = self._sessions.pop(task_id, None)
        if not session:
            return
        with session.lock:
            try:
                self._save_state(session)
            finally:
                session.context.close()
                session.browser.close()
                session.playwright.stop()

    def resume(self, task_id: str, prompt: str, max_turns: int = 40) -> tuple[str, dict[str, Any]]:
        # The browser session and authentication state remain associated with task_id.
        return self.run(task_id, prompt, max_turns=max_turns)
