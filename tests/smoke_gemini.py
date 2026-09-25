from __future__ import annotations

import os

from server.gemini_cua import GeminiComputerUse


def main() -> None:
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("A Gemini API key is required for the live smoke test.")

    agent = GeminiComputerUse(api_key, root_dir=".smoke-sessions")
    task_id = "smoke-public-page"
    try:
        result, meta = agent.run(
            task_id,
            (
                "Open https://example.com. Verify the page title and return a concise "
                "statement containing the title and URL. Do not interact with any other site."
            ),
            max_turns=8,
            budget_usd=0.10,
        )
        if meta.get("status") != "finished":
            raise AssertionError(f"Smoke test did not finish: {meta}")
        if not result or "example" not in result.lower():
            raise AssertionError(f"Unexpected result: {result!r}")
        if "example.com" not in str(meta.get("final_url", "")):
            raise AssertionError(f"Unexpected final URL: {meta.get('final_url')}")
        if not meta.get("usage_known"):
            raise AssertionError("Provider usage was not observable.")
    finally:
        agent.close(task_id)


if __name__ == "__main__":
    main()
