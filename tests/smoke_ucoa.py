from __future__ import annotations

import base64
import json
import os
import urllib.request


BASE = os.getenv("UCOA_BASE_URL", "https://ucoa-agent-brain-agi-control.onrender.com").rstrip("/")
TOKEN = os.getenv("UCOA_API_TOKEN", "").strip()


def request(method: str, path: str, payload: dict | None = None) -> dict:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=45) as response:
        body = json.loads(response.read().decode())
    assert isinstance(body, dict)
    return body


health = request("GET", "/health")
assert health.get("ok") is True, health

models = request("GET", "/v1/providers/models")
assert models.get("object") == "list", models
assert isinstance(models.get("data"), list), models

# This verifies the live UCOA Android control API without consuming AGI Gemini.
payload = {
    "task": "افتح تطبيق الإعدادات",
    "step": 0,
    "max_steps": 4,
    "history": [],
    "ui_tree": "[]",
    "screenshot_base64": base64.b64encode(
        b"synthetic-no-model-image"
    ).decode("ascii"),
    "installed_apps": ["Settings", "Chrome"],
    "capabilities": ["open_app_by_name", "click_any_text", "tap", "observe", "done"],
    "session_id": "agi-ucoa-control-smoke",
    "foreground_package": "com.android.launcher",
}
body = request("POST", "/v1/agent/step", payload)
assert body.get("action") == "open_app_by_name", body
assert (body.get("params") or {}).get("app_name") == "settings", body
assert body.get("provider") in {"deterministic-target-gate", "ucoa-resilient-fallback", "repair"} or str(body.get("provider","")).startswith("deterministic"), body

print(
    json.dumps(
        {
            "ucoa_health": health.get("ok"),
            "provider_models_count": len(models.get("data", [])),
            "action": body.get("action"),
            "app_name": (body.get("params") or {}).get("app_name"),
            "provider": body.get("provider"),
            "output_mode": body.get("output_mode"),
        },
        ensure_ascii=False,
    )
)
print("UCOA_LIVE_CONTROL_API_PASS")
