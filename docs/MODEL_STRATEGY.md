# Model strategy

## Primary execution model

Gemini 3.8 Flash is the default browser executor. Google's current Computer Use documentation identifies it as the recommended model for computer use and documents the browser environment, Playwright execution loop, screenshot feedback, safety decisions, and prompt-injection detection.

Current introductory pricing through 2026-12-31:
- Input: $0.75 / 1M tokens
- Output: $3.75 / 1M tokens

From 2027-01-01 the documented standard rates increase to $1.50 / 1M input and $7.50 / 1M output.

## Escalation

Claude Sonnet 5 is the first escalation tier. It supports stable computer use and browser use and is priced at $2 / 1M input and $10 / 1M output.

GPT-6 Sol is a second escalation path for complex agentic work. Current standard pricing is $2 / 1M input and $10 / 1M output.

GPT-6 Luna is reserved for cheap planning, classification, summarization, or verification work where computer control is not required. Its current standard pricing is $0.10 / 1M input and $0.50 / 1M output.

## Why this can compete with a more expensive flagship

We do not claim token-for-token or benchmark parity with GPT-6 Astra. The system targets comparable task outcomes through architecture:

1. Use a model specifically recommended for computer use for the bulk of browser work.
2. Escalate only after complexity, failure, or verifier signals.
3. Use an independent terminal verifier.
4. Retry with a different strategy rather than repeating the same action.
5. Preserve browser state during human handoff.
6. Cache stable context where supported.
7. Use cheaper models for non-action reasoning.

## Benchmark policy

Before commercial claims, evaluate all candidate models on the same internal browser task suite. Record:
- verified task success rate
- intervention rate
- median and p95 task duration
- provider token cost
- browser runtime cost
- total cost per successful task
- recovery count
- loop count
- unsafe-action blocks

A model is promoted only when its verified cost-adjusted score beats the current production route on the target task family.
