from __future__ import annotations

from server.ucoa_mobile import UcoaMobileComputerUse


def test_ucoa_maps_click_any_text_to_visible_node_center():
    obs = {
        "screen_width": 1000,
        "screen_height": 2000,
        "nodes": [
            {
                "text": "Network & internet",
                "content_description": "",
                "view_id": "settings:network",
                "bounds": {"left": 100, "top": 400, "right": 900, "bottom": 600},
            }
        ],
    }
    command = UcoaMobileComputerUse._to_command(
        "click_any_text",
        {"texts": ["network & internet"]},
        obs,
        (1000, 2000),
    )
    assert command == {"type": "click", "x": 500, "y": 250}


def test_ucoa_maps_pixel_tap_back_to_normalized_coordinates():
    command = UcoaMobileComputerUse._to_command(
        "tap",
        {"x": 540, "y": 1200},
        {},
        (1080, 2400),
    )
    assert command == {"type": "click", "x": 500, "y": 500}


def test_ucoa_done_requires_no_android_command():
    command = UcoaMobileComputerUse._to_command("done", {}, {}, (1080, 2400))
    assert command is None
