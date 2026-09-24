# Architecture

## Goal

Create a browser-first general web agent that can accept a natural-language objective, operate a persistent browser session, verify state transitions, recover from failures, and hand control to the user when authentication or human verification is required.

## Core loop

1. Interpret the objective and define a verifiable success condition.
2. Select a model according to task complexity and budget.
3. Observe the browser state.
4. Ask the model for the next action(s).
5. Execute actions through Playwright/browser-use.
6. Observe the resulting state again.
7. Verify that the intended transition occurred.
8. Continue, recover with a new strategy, or hand off to the user.
9. Stop on verified success, cancellation, hard failure, or budget exhaustion.

## Model policy

The first production candidate is Gemini 3.8 Flash because Google documents it as the recommended model for computer use and currently prices it materially below the flagship alternatives. Claude Sonnet 5 is the configured escalation provider for harder agentic workloads. GPT-6 Sol is a second escalation path. Actual parity with any flagship model must be established by our own benchmark suite; the router does not assume parity.

## Cost control

Every task receives a hard budget. The production ledger will reserve budget before execution, record provider tokens and browser runtime, settle actual spend after execution, and release unused reservation. The task is stopped before its provider budget can be exceeded.

## Human handoff

Authentication, CAPTCHA, MFA, sensitive confirmation, and similar barriers are states, not exceptions to be bypassed. The browser session remains the task resource. The client is notified, the user completes the required step, and the agent resumes from the same state after verification.

## Multi-tenant production layers

- Identity and tenant membership
- Roles and permissions
- Plans and entitlements
- Usage ledger and budget enforcement
- Billing and tax rules
- Durable task queue
- Isolated browser workers
- Object storage for traces
- Push notifications
- Observability and audit logs

## Browser isolation

Each task receives an isolated browser context. Credentials and session material must never be exposed to the model as plain text. Webpage content is untrusted input and must not override the user objective or server-side policy.

## Product packaging

The included progressive web interface is the first mobile client. It can later be replaced or wrapped by a native Android client without changing the agent core API.

## Current milestone

The repository now contains a runnable FastAPI service, browser-use integration, configurable model routing, budget/cost primitives, guardrails, a mobile-first client, Docker packaging, and unit tests. The next production milestone is durable persistence plus a real browser-worker/session manager and authentication handoff channel.
