from __future__ import annotations

import base64
import io
import json
import os
import time
import urllib.request
from PIL import Image, ImageDraw


BASE = os.getenv("UCOA_BASE_URL", "https://ucoa-agent-brain-69bo.onrender.com").rstrip("/")
TOKEN = os.getenv("UCOA_API_TOKEN", "").strip()


def request(method: str, path: str, payload: dict | None = None) -> dict:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=45) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not isinstance(body, dict):
        raise RuntimeError("UCOA returned a non-object JSON response")
    return body


def screenshot() -> str:
    image = Image.new("RGB", (360, 640), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((60, 270, 300, 360), radius=12, outline="black", width=4)
    draw.text((125, 300), "CONTINUE", fill="black")
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=85)
    return base64.b64encode(out.getvalue()).decode("ascii")


health = request("GET", "/health")
assert health.get("ok") is True, health

probe = request("GET", "/v1/providers/probe")
assert probe.get("ok") is True, probe
provider_rows = [p for p in probe.get("providers", []) if p.get("ok")]
runtime_provider = str((probe.get("runtime") or {}).get("provider") or "")
assert provider_rows or runtime_provider, probe

payload = {
    "task": "Press the visible CONTINUE button and verify the UI moved forward.",
    "step": 0,
    "max_steps": 4,
    "history": [],
    "ui_tree": json.dumps([
        {
            "class_name": "android.widget.Button",
            "text": "CONTINUE",
            "content_description": "",
            "clickable": True,
            "editable": False,
            "enabled": True,
            "bounds": {"left": 60, "top": 270, "right": 300, "bottom": 360},
        }
    ], ensure_ascii=False),
    "screenshot_base64": screenshot(),
    "installed_apps": ["Settings", "Chrome"],
    "capabilities": ["click_any_text", "tap", "observe", "done"],
    "session_id": "agi-ucoa-live-probe",
    "foreground_package": "com.android.settings",
}
body = request("POST", "/v1/agent/step", payload)
if body.get("status") == "completed" and isinstance(body.get("result"), dict):
    result = body["result"]
else:
    job_id = str(body.get("job_id") or "")
    assert job_id, body
    deadline = time.time() + 60
    result = {}
    while time.time() < deadline:
        state = request("GET", f"/v1/agent/jobs/{job_id}")
        if state.get("status") == "completed":
            result = state.get("result") or {}
            break
        if state.get("status") == "failed":
            raise RuntimeError(str(state.get("error") or "UCOA job failed"))
        time.sleep(1)
    assert result, body

provider = str(result.get("provider") or "")
vision_provider = str(result.get("vision_provider") or "")
assert provider and provider not in {"repair", "compatibility", "ucoa-resilient-fallback"}, result
assert result.get("action") in {"click_any_text", "tap", "observe", "done"}, result
print(json.dumps({
    "health": health,
    "probe_runtime": runtime_provider,
    "working_provider_count": len(provider_rows),
    "provider": provider,
    "vision_provider": vision_provider,
    "action": result.get("action"),
    "confidence": result.get("confidence"),
}, ensure_ascii=False))
print("UCOA_LIVE_PROVIDER_SMOKE_PASS")
