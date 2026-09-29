from __future__ import annotations

import io
from types import SimpleNamespace

from PIL import Image

from server.observation import collect_dom_observation, observation_text, render_set_of_mark


def test_observation_text_contains_element_ids_without_values():
    observation = {
        "url": "https://example.com",
        "title": "Example",
        "needs_vision": False,
        "interactive_elements": [
            {
                "id": 1,
                "tag": "input",
                "role": "textbox",
                "type": "password",
                "name": "password",
                "bbox": {"x": 100, "y": 200, "width": 300, "height": 80},
            }
        ],
        "body_text": "Login form",
    }
    text = observation_text(observation)
    assert "[1]" in text
    assert "password" in text
    assert "secret" not in text


def test_set_of_mark_renders_numbered_overlay():
    image = Image.new("RGB", (400, 200), "black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    observation = {
        "interactive_elements": [
            {"id": 1, "bbox": {"x": 100, "y": 100, "width": 200, "height": 300}}
        ]
    }
    rendered = render_set_of_mark(buffer.getvalue(), observation)
    assert rendered
    output = Image.open(io.BytesIO(rendered))
    assert output.size == (400, 200)


def test_collect_dom_marks_sparse_pages_for_vision():
    class FakeLocator:
        def __init__(self, value=""):
            self.value = value

        def inner_text(self, timeout=0):
            return self.value

        def count(self):
            return 0

    class FakePage:
        url = "https://example.com"
        viewport_size = {"width": 1440, "height": 900}

        def title(self):
            return "Example"

        def locator(self, selector):
            return FakeLocator("Tiny")

        def evaluate(self, script, limit):
            return []

    observation = collect_dom_observation(FakePage())
    assert observation["needs_vision"] is True
