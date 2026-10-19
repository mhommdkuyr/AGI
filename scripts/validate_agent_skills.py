#!/usr/bin/env python3
"""Validate project Agent Skills frontmatter and Arabic alias routing."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / ".agents" / "skills"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REQUIRED_ALIASES = {
    "@تصفح_عميق": ".agents/skills/deep-web-research/SKILL.md",
    "@متصفح_مسجل": ".agents/skills/browser-session-research/SKILL.md",
    "@حصر_المنشآت": ".agents/skills/google-maps-business-research/SKILL.md",
    "@خرائط_جوجل": ".agents/skills/google-maps-platform/SKILL.md",
    "@تحليل_الفيديو": ".agents/skills/video-analysis/SKILL.md",
}

def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)

def main() -> int:
    if not SKILLS_DIR.is_dir():
        fail(f"Skills directory not found: {SKILLS_DIR}")

    skill_files = sorted(SKILLS_DIR.glob("*/SKILL.md"))
    if not skill_files:
        fail("No SKILL.md files found.")

    checked = 0
    for path in skill_files:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            fail(f"{path.relative_to(ROOT)} must start with YAML frontmatter.")
        parts = text.split("---", 2)
        if len(parts) < 3:
            fail(f"Malformed frontmatter in {path.relative_to(ROOT)}.")
        front = parts[1]
        name_match = re.search(r"(?m)^name:\s*([a-z0-9-]+)\s*$", front)
        desc_match = re.search(r'(?m)^description:\s*["\']?(.+?)["\']?\s*$', front)
        if not name_match:
            fail(f"Missing/invalid name in {path.relative_to(ROOT)}.")
        if not desc_match or not desc_match.group(1).strip():
            fail(f"Missing description in {path.relative_to(ROOT)}.")
        name = name_match.group(1)
        if not NAME_RE.fullmatch(name):
            fail(f"Invalid skill name {name!r}.")
        if name != path.parent.name:
            fail(f"Skill name {name!r} must match directory {path.parent.name!r}.")
        if len(desc_match.group(1)) > 1024:
            fail(f"Description too long in {path.relative_to(ROOT)}.")
        checked += 1

    agents_file = ROOT / "AGENTS.md"
    aliases_text = agents_file.read_text(encoding="utf-8") if agents_file.exists() else ""
    index_text = (ROOT / "SKILLS_AR.md").read_text(encoding="utf-8")
    for alias, relative_path in REQUIRED_ALIASES.items():
        if alias not in aliases_text or alias not in index_text:
            fail(f"Alias {alias} is missing from AGENTS.md or SKILLS_AR.md.")
        if not (ROOT / relative_path).is_file():
            fail(f"Alias {alias} points to a missing skill: {relative_path}")

    print(f"PASS: validated {checked} Agent Skills and {len(REQUIRED_ALIASES)} Arabic aliases.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
