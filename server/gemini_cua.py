from __future__ import annotations

import base64
import json
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .costs import Usage, estimate_token_cost
from .domain import HandoffReason


AUTH_TEXT = re.compile(
    r"(captcha|verify you are human|security check|two-factor|two factor|"
    r"multi-factor|one-time password|verification code|sign in|log in|password|passkey)",
    re.IGNORECASE,
)

SAFE_REASONS = {"authentication", "human_verification", "unknown_block"}


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
    pending_confirmation: dict[str, Any] | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)


class GeminiComputerUse:
    """Gemini Computer Use executor backed by an isolated persistent Playwright session."""

    MODEL = "gemini-3.8-flash"
    WIDTH = 1440
    HEIGHT = 900

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

    def _session_dir(self, task_id: str) -> Path:
        folder = self.root_dir / task_id
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _new_session(self, task_id: str) -> GeminiBrowserSession:
        from playwright.sync_api import sync_playwright

        folder = self._session_dir(task_id)
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        storage = folder / "storage.json"
        context = browser.new_context(
            viewport={"width": self.WIDTH, "height": self.HEIGHT},
            storage_state=str(storage) if storage.exists() else None,
        )
        page = context.new_page()
        metadata = folder / "session.json"
        interaction_id = None
        pending_confirmation = None
        if metadata.exists():
            try:
                saved = json.loads(metadata.read_text(encoding="utf-8"))
                interaction_id = saved.get("interaction_id")
                pending_confirmation = saved.get("pending_confirmation")
            except (OSError, json.JSONDecodeError):
                pass
        return GeminiBrowserSession(
            task_id,
            pw,
            browser,
            context,
            page,
            interaction_id=interaction_id,
            pending_confirmation=pending_confirmation,
            lock=threading.RLock(),
        )

    def _get_or_create(self, task_id: str) -> GeminiBrowserSession:
        with self._lock:
            session = self._sessions.get(task_id)
            if session is not None:
                return session
            session = self._new_session(task_id)
            self._sessions[task_id] = session
            return session

    def _save_state(self, session: GeminiBrowserSession) -> None:
        folder = self._session_dir(session.task_id)
        session.context.storage_state(path=str(folder / "storage.json"))
        metadata = {
            "interaction_id": session.interaction_id,
            "status": session.status,
            "pending_confirmation": session.pending_confirmation,
            "url": session.page.url,
            "title": session.page.title(),
        }
        (folder / "session.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def has_session(self, task_id: str) -> bool:
        with self._lock:
            return task_id in self._sessions

    def screenshot(self, task_id: str) -> bytes:
        session = self._get_or_create(task_id)
        with session.lock:
            return session.page.screenshot(type="png")

    def page_state(self, task_id: str) -> dict[str, Any]:
        session = self._get_or_create(task_id)
        with session.lock:
            return {
                "url": session.page.url,
                "title": session.page.title(),
                "status": session.status,
                "handoff_reason": session.handoff_reason.value if session.handoff_reason else None,
            }

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
        if any(
            token in lowered
            for token in (
                "two-factor",
                "two factor",
                "multi-factor",
                "verification code",
                "one-time password",
                "passkey",
            )
        ):
            return HandoffReason.AUTHENTICATION
        if re.search(r"\b(sign in|log in|password)\b", lowered):
            # Only classify as an auth gate if the page also resembles an auth surface.
            auth_markers = ("email", "username", "continue", "forgot", "passkey")
            if sum(marker in lowered for marker in auth_markers) >= 1:
                return HandoffReason.AUTHENTICATION
        return None

    @staticmethod
    def _step_type(step: Any) -> str:
        return str(getattr(step, "type", "") or "")

    @staticmethod
    def _step_text(step: Any) -> str:
        parts: list[str] = []
        for block in getattr(step, "content", None) or []:
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", "") or "")
        return " ".join(parts)

    def _extract_text(self, interaction: Any) -> str:
        if getattr(interaction, "output_text", None):
            return str(interaction.output_text).strip()
        texts = [
            self._step_text(step)
            for step in (getattr(interaction, "steps", None) or [])
            if self._step_type(step) == "model_output"
        ]
        return " ".join(text for text in texts if text).strip()

    def _calls(self, interaction: Any) -> list[Any]:
        return [
            step
            for step in (getattr(interaction, "steps", None) or [])
            if self._step_type(step) == "function_call"
        ]

    @staticmethod
    def _usage(interaction: Any) -> tuple[Usage, bool]:
        raw = getattr(interaction, "usage", None)
        if raw is None:
            return Usage(), False

        def value(name: str) -> int:
            if isinstance(raw, dict):
                return int(raw.get(name, 0) or 0)
            return int(getattr(raw, name, 0) or 0)

        input_tokens = value("total_input_tokens") or value("input_tokens")
        output_tokens = value("total_output_tokens") or value("output_tokens")
        return Usage(input_tokens, output_tokens), True

    def _execute_one(
        self,
        session: GeminiBrowserSession,
        name: str,
        args: dict[str, Any],
        *,
        safety_acknowledgement: bool = False,
    ) -> dict[str, Any]:
        page = session.page
        width, height = self.WIDTH, self.HEIGHT
        result: dict[str, Any] = {}

        decision = args.get("safety_decision")
        if isinstance(decision, dict) and decision.get("decision") == "require_confirmation" and not safety_acknowledgement:
            session.pending_confirmation = {
                "name": name,
                "arguments": {k: v for k, v in args.items() if k != "safety_decision"},
            }
            session.handoff_reason = HandoffReason.SENSITIVE_ACTION
            session.status = "waiting_human"
            self._save_state(session)
            return {
                "status": "waiting_human",
                "reason": HandoffReason.SENSITIVE_ACTION.value,
                "safety_decision": decision,
            }

        try:
            x = self._xy(int(args.get("x", 0)), width)
            y = self._xy(int(args.get("y", 0)), height)
            if name in {"click", "click_at"}:
                page.mouse.click(x, y)
            elif name == "double_click":
                page.mouse.dblclick(x, y)
            elif name == "triple_click":
                page.mouse.click(x, y, click_count=3)
            elif name == "right_click":
                page.mouse.click(x, y, button="right")
            elif name == "middle_click":
                page.mouse.click(x, y, button="middle")
            elif name == "move":
                page.mouse.move(x, y)
            elif name == "mouse_down":
                page.mouse.move(x, y)
                page.mouse.down()
            elif name == "mouse_up":
                page.mouse.move(x, y)
                page.mouse.up()
            elif name == "long_press":
                page.mouse.move(x, y)
                page.mouse.down()
                page.wait_for_timeout(max(200, int(float(args.get("seconds", 2)) * 1000)))
                page.mouse.up()
            elif name in {"type", "type_text_at"}:
                if "x" in args and "y" in args:
                    page.mouse.click(x, y)
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type(str(args.get("text", "")))
                if args.get("press_enter"):
                    page.keyboard.press("Enter")
            elif name == "drag_and_drop":
                sx = self._xy(int(args.get("start_x", args.get("x", 0))), width)
                sy = self._xy(int(args.get("start_y", args.get("y", 0))), height)
                ex = self._xy(int(args.get("end_x", args.get("destination_x", 0))), width)
                ey = self._xy(int(args.get("end_y", args.get("destination_y", 0))), height)
                page.mouse.move(sx, sy)
                page.mouse.down()
                page.mouse.move(ex, ey, steps=8)
                page.mouse.up()
            elif name == "press_key":
                page.keyboard.press(str(args["key"]))
            elif name == "key_down":
                page.keyboard.down(str(args["key"]))
            elif name == "key_up":
                page.keyboard.up(str(args["key"]))
            elif name in {"hotkey", "key_combination"}:
                keys = args.get("keys", [])
                if isinstance(keys, str):
                    keys = [part.strip() for part in keys.replace("+", " ").split()]
                page.keyboard.press("+".join(str(key) for key in keys))
            elif name == "take_screenshot":
                pass
            elif name == "scroll":
                direction = str(args.get("direction", "down")).lower()
                magnitude = int(args.get("magnitude_in_pixels", args.get("magnitude", 300)) or 300)
                dx = magnitude if direction == "right" else -magnitude if direction == "left" else 0
                dy = magnitude if direction == "down" else -magnitude if direction == "up" else 0
                page.mouse.move(x, y)
                page.mouse.wheel(dx, dy)
            elif name in {"navigate"}:
                page.goto(str(args["url"]), wait_until="domcontentloaded", timeout=30000)
            elif name == "go_back":
                page.go_back(wait_until="domcontentloaded", timeout=30000)
            elif name == "go_forward":
                page.go_forward(wait_until="domcontentloaded", timeout=30000)
            elif name == "wait":
                page.wait_for_timeout(max(100, int(float(args.get("seconds", 1)) * 1000)))
            elif name in {"open_web_browser", "open_app"}:
                pass
            else:
                result["error"] = f"Unsupported computer-use action: {name}"

            try:
                page.wait_for_load_state(timeout=5000)
            except Exception:
                pass
            time.sleep(0.2)
            result.update(
                {
                    "url": page.url,
                    "title": page.title(),
                    "safety_acknowledgement": safety_acknowledgement or None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            result.update({"error": str(exc), "url": page.url, "title": page.title()})
        return result

    def _execute_calls(
        self,
        session: GeminiBrowserSession,
        calls: list[Any],
        *,
        confirm_pending: bool = False,
    ) -> tuple[list[dict[str, Any]], bool]:
        results: list[dict[str, Any]] = []
        waiting = False

        if confirm_pending and session.pending_confirmation:
            pending = session.pending_confirmation
            result = self._execute_one(
                session,
                str(pending["name"]),
                dict(pending["arguments"]),
                safety_acknowledgement=True,
            )
            session.pending_confirmation = None
            if result.get("status") == "waiting_human":
                waiting = True
            results.append(
                {
                    "type": "function_result",
                    "name": str(pending["name"]),
                    "call_id": str(pending["arguments"].get("_call_id", "")),
                    "result": [
                        {"type": "text", "text": json.dumps(result, ensure_ascii=False)},
                        {
                            "type": "image",
                            "data": base64.b64encode(session.page.screenshot(type="png")).decode("utf-8"),
                            "mime_type": "image/png",
                        },
                    ],
                }
            )
            if waiting:
                return results, True
            return results, False

        for call in calls:
            name = str(getattr(call, "name", "") or "")
            raw_args = getattr(call, "arguments", {}) or {}
            args = dict(raw_args) if not isinstance(raw_args, dict) else raw_args
            result = self._execute_one(session, name, args)
            if result.get("status") == "waiting_human":
                args = dict(args)
                args["_call_id"] = getattr(call, "id", "")
                session.pending_confirmation = {
                    "name": name,
                    "arguments": args,
                }
                waiting = True
                break

            results.append(
                {
                    "type": "function_result",
                    "name": name,
                    "call_id": getattr(call, "id", ""),
                    "result": [
                        {"type": "text", "text": json.dumps(result, ensure_ascii=False)},
                        {
                            "type": "image",
                            "data": base64.b64encode(session.page.screenshot(type="png")).decode("utf-8"),
                            "mime_type": "image/png",
                        },
                    ],
                }
            )
        return results, waiting

    def _create_initial_interaction(self, client: Any, prompt: str, session: GeminiBrowserSession) -> Any:
        first = session.page.screenshot(type="png")
        return client.interactions.create(
            model=self.MODEL,
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

    def run(
        self,
        task_id: str,
        prompt: str,
        max_turns: int = 40,
        budget_usd: float | None = None,
        *,
        resume: bool = False,
        user_confirmed: bool = False,
    ) -> tuple[str, dict[str, Any]]:
        session = self._get_or_create(task_id)
        with session.lock:
            client = self._get_client()
            session.status = "running"
            session.handoff_reason = None

            if resume and session.interaction_id:
                if user_confirmed and session.pending_confirmation:
                    # We must send the acknowledged action result back to the same interaction.
                    empty_calls: list[Any] = []
                    function_responses, waiting = self._execute_calls(
                        session, empty_calls, confirm_pending=True
                    )
                    if waiting:
                        return "", {
                            "status": "waiting_human",
                            "reason": session.handoff_reason.value if session.handoff_reason else HandoffReason.UNKNOWN_BLOCK.value,
                            "turns": 0,
                            "usage_known": False,
                        }
                    interaction = client.interactions.create(
                        model=self.MODEL,
                        previous_interaction_id=session.interaction_id,
                        input=function_responses,
                        tools=[self._tool()],
                    )
                else:
                    interaction = client.interactions.create(
                        model=self.MODEL,
                        previous_interaction_id=session.interaction_id,
                        input=[
                            {
                                "type": "text",
                                "text": "The user has completed the required human step. Re-observe the current browser state and continue the original task.",
                            }
                        ],
                        tools=[self._tool()],
                    )
            else:
                interaction = self._create_initial_interaction(client, prompt, session)

            session.interaction_id = getattr(interaction, "id", session.interaction_id)
            total_usage = Usage()
            first_usage, known = self._usage(interaction)
            usage_known = known
            total_usage = Usage(
                total_usage.input_tokens + first_usage.input_tokens,
                total_usage.output_tokens + first_usage.output_tokens,
            )

            for turn in range(max_turns):
                interaction_status = str(getattr(interaction, "status", "") or "")
                if interaction_status in {"failed", "cancelled", "incomplete"}:
                    self._save_state(session)
                    return "", {
                        "status": "failed",
                        "error": f"Gemini interaction status: {interaction_status}",
                        "turns": turn + 1,
                        "input_tokens": total_usage.input_tokens,
                        "output_tokens": total_usage.output_tokens,
                        "provider_cost_usd": estimate_token_cost(self.MODEL, total_usage),
                        "usage_known": usage_known,
                        "final_url": session.page.url,
                        "final_title": session.page.title(),
                    }

                gate = self._human_gate(session)
                if gate and session.pending_confirmation is None:
                    session.status = "waiting_human"
                    session.handoff_reason = gate
                    self._save_state(session)
                    cost = estimate_token_cost(self.MODEL, total_usage)
                    return "", {
                        "status": "waiting_human",
                        "reason": gate.value,
                        "turns": turn,
                        "input_tokens": total_usage.input_tokens,
                        "output_tokens": total_usage.output_tokens,
                        "provider_cost_usd": cost,
                        "usage_known": usage_known,
                        "final_url": session.page.url,
                        "final_title": session.page.title(),
                    }

                calls = self._calls(interaction)
                if not calls:
                    text = self._extract_text(interaction)
                    session.status = "finished"
                    self._save_state(session)
                    cost = estimate_token_cost(self.MODEL, total_usage)
                    return text, {
                        "status": "finished",
                        "turns": turn + 1,
                        "input_tokens": total_usage.input_tokens,
                        "output_tokens": total_usage.output_tokens,
                        "provider_cost_usd": cost,
                        "usage_known": usage_known,
                        "final_url": session.page.url,
                        "final_title": session.page.title(),
                        "evidence": {
                            "url": session.page.url,
                            "title": session.page.title(),
                            "text": text,
                        },
                    }

                function_responses, waiting = self._execute_calls(session, calls)
                self._save_state(session)
                if waiting:
                    cost = estimate_token_cost(self.MODEL, total_usage)
                    return "", {
                        "status": "waiting_human",
                        "reason": session.handoff_reason.value if session.handoff_reason else HandoffReason.UNKNOWN_BLOCK.value,
                        "turns": turn + 1,
                        "input_tokens": total_usage.input_tokens,
                        "output_tokens": total_usage.output_tokens,
                        "provider_cost_usd": cost,
                        "usage_known": usage_known,
                        "final_url": session.page.url,
                        "final_title": session.page.title(),
                    }

                interaction = client.interactions.create(
                    model=self.MODEL,
                    previous_interaction_id=session.interaction_id,
                    input=function_responses,
                    tools=[self._tool()],
                )
                session.interaction_id = getattr(interaction, "id", session.interaction_id)
                usage, known = self._usage(interaction)
                usage_known = usage_known and known
                total_usage = Usage(
                    total_usage.input_tokens + usage.input_tokens,
                    total_usage.output_tokens + usage.output_tokens,
                )
                if budget_usd is not None:
                    cost = estimate_token_cost(self.MODEL, total_usage)
                    if cost >= budget_usd:
                        session.status = "failed"
                        self._save_state(session)
                        return "", {
                            "status": "failed",
                            "error": "computer-use budget exhausted",
                            "turns": turn + 1,
                            "input_tokens": total_usage.input_tokens,
                            "output_tokens": total_usage.output_tokens,
                            "provider_cost_usd": cost,
                            "usage_known": usage_known,
                            "final_url": session.page.url,
                            "final_title": session.page.title(),
                        }

            session.status = "failed"
            self._save_state(session)
            return "", {
                "status": "failed",
                "error": "maximum computer-use turns reached",
                "turns": max_turns,
                "input_tokens": total_usage.input_tokens,
                "output_tokens": total_usage.output_tokens,
                "provider_cost_usd": estimate_token_cost(self.MODEL, total_usage),
                "usage_known": usage_known,
                "final_url": session.page.url,
                "final_title": session.page.title(),
            }

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
