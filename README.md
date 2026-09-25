# Universal Web Agent

A mobile-first general-purpose web agent runtime.

## Architecture

The system separates intelligence from execution:

- Gemini 3.8 Flash is the default browser/computer-use model.
- Claude Sonnet 5 and GPT-6 Sol are configurable escalation providers.
- Playwright provides the browser execution layer; Gemini Computer Use provides the visual action policy.
- The runtime adds task state, budgets, model routing, loop protection, human handoff, and verification hooks.
- A mobile-first progressive web interface is included as the first client surface.

## Safety boundary

The runtime is designed to detect authentication, CAPTCHA, MFA, and other human-verification barriers and hand control to the user. It does not implement bypasses for access controls or security challenges.

## Development

Copy .env.example to .env, install dependencies with uv sync, install Chromium with uv run playwright install chromium, then run:

uv run uvicorn server.main:app --reload

Open http://localhost:8000/.

The current milestone is a real single-user execution core with a live mobile execution view. Multi-tenant persistence, billing, tax configuration, durable queues, isolated browser workers, human browser control, push notifications, and native Android packaging remain production layers.
