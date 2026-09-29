from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from typing import Any


class UcoaMobileComputerUse:
    """Cloud brain adapter for UCOA; Android execution remains owned by this app."""

    def __init__(self, base_url: str, api_token: str | None = None, timeout_s: float = 35.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_token = (api_token or "").strip()
        self.timeout_s = timeout_s

    def _request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="ignore")[:500]
            except Exception:
                pass
            raise RuntimeError(f"UCOA HTTP {exc.code}: {detail or exc.reason}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"UCOA network error: {type(exc).__name__}") from exc
        if not isinstance(body, dict):
            raise RuntimeError("UCOA returned a non-object response.")
        return body

    @staticmethod
    def _unwrap(body: dict[str, Any]) -> dict[str, Any]:
        if body.get("status") == "failed":
            raise RuntimeError(str(body.get("error") or "UCOA request failed"))
        result = body.get("result")
        if isinstance(result, dict):
            return result
        if isinstance(body, dict) and "action" in body:
            return body
        job_id = str(body.get("job_id") or "")
        if not job_id:
            raise RuntimeError("UCOA response has no result or job_id.")
        return {"_job_id": job_id}

    def _step(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._unwrap(self._request("/v1/agent/step", payload))
        job_id = str(result.get("_job_id") or "")
        if not job_id:
            return result
        headers = {"Accept": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        request = urllib.request.Request(
            f"{self.base_url}/v1/agent/jobs/{job_id}",
            headers=headers,
            method="GET",
        )
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                    body = json.loads(response.read().decode("utf-8"))
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
                raise RuntimeError(f"UCOA job polling failed: {type(exc).__name__}") from exc
            if not isinstance(body, dict):
                raise RuntimeError("UCOA job returned invalid JSON.")
            status = str(body.get("status") or "")
            if status == "completed":
                result = body.get("result")
                if not isinstance(result, dict):
                    raise RuntimeError("UCOA completed job has no object result.")
                return result
            if status == "failed":
                raise RuntimeError(str(body.get("error") or "UCOA job failed"))
            time.sleep(0.4)
        raise TimeoutError("UCOA job timed out.")

    @staticmethod
    def _node_text(node: dict[str, Any]) -> str:
        return " ".join(
            str(node.get(key) or "").strip()
            for key in ("text", "content_description", "view_id")
            if str(node.get(key) or "").strip()
        ).strip()

    @staticmethod
    def _find_text_center(observation: dict[str, Any], texts: list[str]) -> tuple[int, int] | None:
        wanted = [str(text).strip().casefold() for text in texts if str(text).strip()]
        if not wanted:
            return None
        width = int(observation.get("screen_width") or 1080)
        height = int(observation.get("screen_height") or 2400)
        for node in observation.get("nodes") or []:
            hay = UcoaMobileComputerUse._node_text(node).casefold()
            if not hay:
                continue
            if not any(w in hay for w in wanted):
                continue
            bounds = node.get("bounds") or {}
            try:
                x = (int(bounds["left"]) + int(bounds["right"])) // 2
                y = (int(bounds["top"]) + int(bounds["bottom"])) // 2
            except (KeyError, TypeError, ValueError):
                continue
            return round(max(0, min(1000, x / max(width, 1) * 1000))), round(
                max(0, min(1000, y / max(height, 1) * 1000))
            )
        return None

    @staticmethod
    def _pixel_to_normalized(value: Any, size: int) -> int:
        try:
            return round(max(0, min(1000, float(value) / max(size, 1) * 1000)))
        except (TypeError, ValueError):
            raise ValueError("UCOA returned a non-numeric coordinate.")

    @classmethod
    def _to_command(
        cls,
        action: str,
        params: dict[str, Any],
        observation: dict[str, Any],
        screenshot_size: tuple[int, int],
    ) -> dict[str, Any] | None:
        action = str(action or "observe").strip()
        width, height = screenshot_size

        if action == "open_app_by_name":
            return {"type": "open_app", "app_name": str(params.get("app_name") or "").strip()}
        if action == "click_any_text":
            center = cls._find_text_center(
                observation,
                list(params.get("texts") or []) + ([params.get("text")] if params.get("text") else []),
            )
            if center is None:
                return {"type": "take_screenshot"}
            return {"type": "click", "x": center[0], "y": center[1]}
        if action == "type_into_any":
            return {
                "type": "type",
                "text": str(params.get("text") or params.get("value") or ""),
                "press_enter": bool(params.get("press_enter", False)),
            }
        if action in {"tap", "long_press"}:
            if "x" not in params or "y" not in params:
                return {"type": "take_screenshot"}
            x = cls._pixel_to_normalized(params["x"], width)
            y = cls._pixel_to_normalized(params["y"], height)
            command: dict[str, Any] = {"type": "click" if action == "tap" else "long_press", "x": x, "y": y}
            if action == "long_press":
                command["seconds"] = int(params.get("seconds", 2) or 2)
            return command
        if action == "swipe":
            if not all(key in params for key in ("x1", "y1", "x2", "y2")):
                return {"type": "scroll", "direction": "down"}
            return {
                "type": "drag_and_drop",
                "start_x": cls._pixel_to_normalized(params["x1"], width),
                "start_y": cls._pixel_to_normalized(params["y1"], height),
                "end_x": cls._pixel_to_normalized(params["x2"], width),
                "end_y": cls._pixel_to_normalized(params["y2"], height),
            }
        if action == "back":
            return {"type": "go_back"}
        if action == "home":
            return {"type": "press_key", "key": "HOME"}
        if action == "wait":
            ms = int(params.get("duration_ms") or params.get("wait_after_ms") or 700)
            return {"type": "wait", "seconds": max(1, round(ms / 1000))}
        if action == "observe":
            return {"type": "take_screenshot"}
        return None

    def run(
        self,
        task_id: str,
        prompt: str,
        max_turns: int,
        budget_usd: float | None,
        *,
        mobile_session_id: str,
        resume: bool = False,
        user_confirmed: bool = False,
    ) -> tuple[str, dict[str, Any]]:
        from PIL import Image
        from io import BytesIO
        from .mobile_bridge import mobile_bridge

        session = mobile_bridge.get(mobile_session_id)
        if session is None:
            raise RuntimeError("Mobile session not found.")
        if not self.base_url:
            raise RuntimeError("UCOA_BASE_URL is not configured.")

        session.wait_for_observation(timeout_s=30.0)
        history: list[dict[str, Any]] = []
        total_turns = 0
        last_result: dict[str, Any] = {}

        for step in range(max(1, max_turns)):
            observation = dict(session.observation or {})
            screenshot_b64 = str(session.screenshot_b64 or "")
            if not screenshot_b64:
                raise RuntimeError("Android device has not supplied a screenshot.")
            try:
                width, height = Image.open(BytesIO(base64.b64decode(screenshot_b64))).size
            except Exception:
                width = int(observation.get("screen_width") or 1080)
                height = int(observation.get("screen_height") or 2400)

            apps: list[str] = []
            for node in observation.get("installed_apps") or []:
                if isinstance(node, dict):
                    name = str(node.get("name") or node.get("package_name") or "").strip()
                    if name:
                        apps.append(name)
                elif str(node).strip():
                    apps.append(str(node).strip())
            payload = {
                "task": prompt,
                "step": step,
                "max_steps": max_turns,
                "history": history[-10:],
                "ui_tree": json.dumps(observation, ensure_ascii=False)[:18000],
                "screenshot_base64": screenshot_b64,
                "installed_apps": apps[:250],
                "capabilities": [
                    "open_app_by_name",
                    "click_any_text",
                    "type_into_any",
                    "tap",
                    "long_press",
                    "swipe",
                    "back",
                    "home",
                    "wait",
                    "observe",
                    "done",
                ],
                "session_id": f"agi-mobile-{task_id}",
                "foreground_package": str(observation.get("package_name") or ""),
            }
            if resume and step == 0:
                payload["history"].append({"type": "resume", "message": "User confirmed the pending action."})

            result = self._step(payload)
            last_result = result
            total_turns += 1
            action = str(result.get("action") or "observe")
            params = result.get("params") if isinstance(result.get("params"), dict) else {}
            result["provider"] = str(result.get("provider") or "ucoa")
            result["vision_provider"] = str(result.get("vision_provider") or "ucoa")
            result["reasoning_provider"] = str(
                result.get("reasoning_provider") or result.get("provider") or "ucoa"
            )
            result["provider_cost_usd"] = 0.0
            result["usage_known"] = True
            result["turns"] = total_turns

            if action == "done" or bool(result.get("done")):
                text = str(result.get("message") or result.get("verification_goal") or "").strip()
                if not text:
                    text = (
                        f"UCOA verified the requested state in package "
                        f"{observation.get('package_name') or 'unknown'}."
                    )
                return text, {
                    "status": "finished",
                    "turns": total_turns,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "provider_cost_usd": 0.0,
                    "usage_known": True,
                    "package_name": observation.get("package_name"),
                    "activity_name": observation.get("activity_name"),
                    "provider": result.get("provider"),
                    "vision_provider": result.get("vision_provider"),
                }

            command = self._to_command(action, params, observation, (width, height))
            if command is None:
                raise RuntimeError(f"UCOA returned unsupported action: {action}")
            command_id = session.enqueue(command)
            execution = dict(session.wait_for_result(command_id, timeout_s=45.0))
            if str(execution.get("status") or "") not in {"ok", "success"}:
                raise RuntimeError(
                    f"Android command failed: {execution.get('error') or execution.get('status') or 'unknown'}"
                )
            history.append(
                {
                    "step": step,
                    "action": action,
                    "params": params,
                    "execution": {k: v for k, v in execution.items() if k != "screenshot_b64"},
                    "foreground_package": observation.get("package_name"),
                }
            )
            wait_after_ms = int(result.get("wait_after_ms") or 500)
            if wait_after_ms > 0:
                time.sleep(min(wait_after_ms, 1500) / 1000.0)

        return "", {
            "status": "failed",
            "turns": total_turns,
            "input_tokens": 0,
            "output_tokens": 0,
            "provider_cost_usd": 0.0,
            "usage_known": True,
            "package_name": (session.observation or {}).get("package_name"),
            "activity_name": (session.observation or {}).get("activity_name"),
            "error": "maximum external-agent turns reached",
        }
