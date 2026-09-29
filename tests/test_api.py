from fastapi.testclient import TestClient

from server.main import app
from server.mobile_bridge import mobile_bridge


client = TestClient(app)


def test_health_endpoint_is_ready_without_gemini():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_mobile_session_lifecycle_without_gemini():
    response = client.post("/v1/mobile/sessions", json={"device_name": "CI Pixel"})
    assert response.status_code == 200
    session_id = response.json()["id"]

    response = client.get("/v1/mobile/sessions/" + session_id)
    assert response.status_code == 200
    assert response.json()["device_name"] == "CI Pixel"
    assert response.json()["has_screenshot"] is False

    response = client.post(
        "/v1/mobile/sessions/" + session_id + "/observation",
        json={
            "observation": {
                "package_name": "com.example",
                "screen_width": 1080,
                "screen_height": 2400,
                "nodes": [{"password": True, "text": "secret"}],
            }
        },
    )
    assert response.status_code == 200

    session = mobile_bridge.get(session_id)
    assert session is not None
    assert session.observation["nodes"][0]["text"] is None