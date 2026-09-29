from __future__ import annotations

import base64
import threading
import time

from server.mobile_bridge import MobileBridge


def test_mobile_session_round_trip_command_result():
    bridge = MobileBridge()
    session = bridge.create_session("Pixel")
    session.update_observation(
        {
            "package_name": "com.example",
            "screen_width": 1080,
            "screen_height": 2400,
            "nodes": [],
        },
        base64.b64encode(b"png").decode(),
    )

    command_id = session.enqueue({"type": "click", "x": 500, "y": 500})
    command = session.next_command()
    assert command is not None
    assert command["id"] == command_id

    session.set_result(command_id, {"command_id": command_id, "status": "ok"})
    result = session.wait_for_result(command_id, timeout_s=0.5)
    assert result["status"] == "ok"


def test_mobile_session_waits_for_observation():
    bridge = MobileBridge()
    session = bridge.create_session("Pixel")

    def publish():
        time.sleep(0.05)
        session.update_observation({"package_name": "com.example", "nodes": []}, None)

    thread = threading.Thread(target=publish)
    thread.start()
    observation, screenshot = session.wait_for_observation(timeout_s=1.0)
    thread.join()
    assert observation["package_name"] == "com.example"
    assert screenshot is None


def test_mobile_observation_sanitizes_password_text():
    bridge = MobileBridge()
    session = bridge.create_session("Pixel")
    raw = {
        "package_name": "com.example",
        "nodes": [
            {"password": True, "text": "secret", "content_description": "secret"},
            {"password": False, "text": "visible"},
        ],
    }
    sanitized = bridge.sanitize_observation(raw)
    assert sanitized["nodes"][0]["text"] is None
    assert sanitized["nodes"][0]["content_description"] is None
    assert sanitized["nodes"][1]["text"] == "visible"
