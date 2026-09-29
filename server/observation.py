from __future__ import annotations

import io
from typing import Any

from PIL import Image, ImageDraw, ImageFont

MAX_BODY_TEXT = 5000


def _visible_interactives(page: Any, max_elements: int = 40) -> list[dict[str, Any]]:
    script = """
    (limit) => {
      const selectors = [
        'button',
        'a',
        'input:not([type="hidden"])',
        'textarea',
        'select',
        '[role="button"]',
        '[role="link"]',
        '[role="textbox"]',
        '[contenteditable="true"]'
      ];
      const seen = new Set();
      const nodes = [];
      for (const selector of selectors) {
        for (const el of document.querySelectorAll(selector)) {
          if (seen.has(el)) continue;
          seen.add(el);
          const r = el.getBoundingClientRect();
          const style = getComputedStyle(el);
          if (r.width < 2 || r.height < 2 || style.visibility === 'hidden' ||
              style.display === 'none' || Number(style.opacity) === 0) continue;
          const tag = el.tagName.toLowerCase();
          const type = (el.getAttribute('type') || '').toLowerCase();
          const name = (
            el.getAttribute('aria-label') ||
            el.getAttribute('title') ||
            el.getAttribute('placeholder') ||
            (tag === 'input' && type === 'password' ? 'password input' : '') ||
            (el.innerText || '')
          ).trim().replace(/\s+/g, ' ').slice(0, 100);
          nodes.push({
            tag,
            role: el.getAttribute('role') || '',
            type,
            name,
            x: Math.max(0, Math.round(r.x)),
            y: Math.max(0, Math.round(r.y)),
            width: Math.max(0, Math.round(r.width)),
            height: Math.max(0, Math.round(r.height))
          });
          if (nodes.length >= limit) return nodes;
        }
      }
      return nodes;
    }
    """
    return page.evaluate(script, max_elements)


def collect_dom_observation(page: Any, max_elements: int = 40) -> dict[str, Any]:
    try:
        body_text = page.locator("body").inner_text(timeout=1500)
    except Exception:
        body_text = ""
    try:
        canvas_count = page.locator("canvas").count()
    except Exception:
        canvas_count = 0
    try:
        iframe_count = page.locator("iframe").count()
    except Exception:
        iframe_count = 0

    elements = _visible_interactives(page, max_elements=max_elements)
    width = int((page.viewport_size or {}).get("width", 1440))
    height = int((page.viewport_size or {}).get("height", 900))

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(elements, start=1):
        normalized.append(
            {
                "id": idx,
                "tag": item.get("tag"),
                "role": item.get("role") or None,
                "type": item.get("type") or None,
                "name": item.get("name") or None,
                "bbox": {
                    "x": round((item.get("x", 0) / max(width, 1)) * 1000),
                    "y": round((item.get("y", 0) / max(height, 1)) * 1000),
                    "width": round((item.get("width", 0) / max(width, 1)) * 1000),
                    "height": round((item.get("height", 0) / max(height, 1)) * 1000),
                },
            }
        )

    clean_text = " ".join(body_text.split())[:MAX_BODY_TEXT]
    needs_vision = (
        not normalized
        or canvas_count > 0
        or iframe_count > 0
        or (len(clean_text) < 80 and len(normalized) < 3)
    )
    return {
        "url": page.url,
        "title": page.title(),
        "viewport": {"width": width, "height": height},
        "body_text": clean_text,
        "interactive_elements": normalized,
        "canvas_count": canvas_count,
        "iframe_count": iframe_count,
        "needs_vision": needs_vision,
    }


def render_set_of_mark(
    screenshot_bytes: bytes,
    observation: dict[str, Any],
) -> bytes:
    image = Image.open(io.BytesIO(screenshot_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    font = ImageFont.load_default()
    width, height = image.size

    for item in observation.get("interactive_elements", []):
        bbox = item.get("bbox", {})
        x = int(float(bbox.get("x", 0)) / 1000 * width)
        y = int(float(bbox.get("y", 0)) / 1000 * height)
        w = int(float(bbox.get("width", 0)) / 1000 * width)
        h = int(float(bbox.get("height", 0)) / 1000 * height)
        if w < 2 or h < 2:
            continue
        idx = int(item.get("id", 0))
        draw.rectangle((x, y, x + w, y + h), outline=(255, 255, 255, 230), width=2)
        label_w, label_h = draw.textbbox((0, 0), str(idx), font=font)[2:4]
        pad = 4
        lx = max(0, x)
        ly = max(0, y - label_h - pad * 2)
        draw.rounded_rectangle(
            (lx, ly, lx + label_w + pad * 2, ly + label_h + pad),
            radius=4,
            fill=(0, 0, 0, 210),
        )
        draw.text((lx + pad, ly + 2), str(idx), fill=(255, 255, 255, 255), font=font)

    output = io.BytesIO()
    image.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()


def observation_text(observation: dict[str, Any]) -> str:
    rows = [
        "DOM observation (preferred over vision when sufficient).",
        f"URL: {observation.get('url', '')}",
        f"Title: {observation.get('title', '')}",
        f"Vision fallback required: {bool(observation.get('needs_vision'))}",
        "Interactive elements:",
    ]
    for item in observation.get("interactive_elements", []):
        rows.append(
            f"[{item.get('id')}] {item.get('tag')} "
            f"role={item.get('role') or '-'} type={item.get('type') or '-'} "
            f"name={item.get('name') or '-'} bbox={item.get('bbox')}"
        )
    body = observation.get("body_text") or ""
    if body:
        rows.append(f"Visible text: {body}")
    return "\n".join(rows)
