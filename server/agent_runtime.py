from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from .complexity import classify_complexity
from .config import Settings
from .domain import HandoffReason, TaskRecord, TaskStatus
from .gemini_cua import GeminiComputerUse
from .guardrails import classify_handoff, looks_like_loop
from .model_router import ModelChoice, ModelRouter
from .usage import ledger
from .verifier import verify_terminal


class AgentRuntime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.router = ModelRouter(settings)
        self.gemini_cua = GeminiComputerUse(settings.google_api_key) if settings.google_api_key else None

    async def run(
        self,
        task: TaskRecord,
        complexity: str = "auto",
        on_update: Callable[[TaskRecord], Awaitable[None]] | None = None,
    ) -> TaskRecord:
        was_waiting_human = task.status == TaskStatus.WAITING_HUMAN
        effective_complexity = classify_complexity(task.prompt) if complexity == "auto" else complexity
        choice = self.router.choose(
            budget_usd=task.budget_usd,
            complexity=effective_complexity,
        )
        task.model = choice.executor_model
        task.status = TaskStatus.RUNNING
        task.touch()
        if on_update:
            await on_update(task)

        try:
            if self.gemini_cua is None:
                raise RuntimeError("GOOGLE_API_KEY is required for the computer-use runtime.")

            enriched_prompt = await self._make_agent_prompt(task.prompt, choice)
            final_text, meta = await asyncio.to_thread(
                self.gemini_cua.run,
                str(task.id),
                enriched_prompt,
                self.settings.default_max_steps,
                task.budget_usd,
                resume=was_waiting_human,
            )
            task.steps = int(meta.get("turns", 0))
            task.spent_usd = float(meta.get("provider_cost_usd", 0.0) or 0.0)
            usage_known = bool(meta.get("usage_known"))
            task.metering_state = "measured" if usage_known else "unknown"

            if meta.get("status") == "waiting_human":
                task.status = TaskStatus.WAITING_HUMAN
                task.handoff_reason = HandoffReason(meta["reason"])
                task.error = "Human interaction is required before the task can continue."
            elif meta.get("status") != "finished":
                task.status = TaskStatus.FAILED
                task.error = meta.get("error", "Computer-use execution failed.")
            elif not usage_known:
                task.status = TaskStatus.FAILED
                task.error = "Provider usage was not observable; paid execution is stopped."
            elif not final_text.strip():
                task.status = TaskStatus.FAILED
                task.error = "Execution ended without final evidence."
            else:
                handoff = classify_handoff(final_text)
                if handoff:
                    task.status = TaskStatus.WAITING_HUMAN
                    task.handoff_reason = handoff
                    task.error = "Human interaction is required before the task can continue."
                else:
                    # Native computer-use history is the source of terminal evidence in this MVP.
                    # A domain-specific verifier will replace this generic gate in production.
                    task.status = TaskStatus.SUCCEEDED
                    task.result = final_text
                    if looks_like_loop(final_text):
                        task.status = TaskStatus.FAILED
                        task.error = "Loop-like terminal state detected."

            if task.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
                try:
                    ledger.settle(task.id, task.spent_usd)
                except (KeyError, ValueError):
                    pass
        except Exception as exc:  # noqa: BLE001
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            try:
                ledger.settle(task.id, task.spent_usd)
            except (KeyError, ValueError):
                pass

        task.touch()
        if on_update:
            await on_update(task)
        return task

    async def resume(self, task: TaskRecord) -> TaskRecord:
        if task.status != TaskStatus.WAITING_HUMAN:
            return task
        task.status = TaskStatus.RUNNING
        task.handoff_reason = None
        task.error = None
        task.touch()
        return await self.run(task, "auto")

    async def _make_agent_prompt(self, task_prompt: str, choice: ModelChoice) -> str:
        if choice.planner_model == choice.executor_model:
            return task_prompt

        try:
            from google import genai

            client = genai.Client(api_key=self.settings.google_api_key)
            planning_prompt = (
                "Create a compact execution plan for this browser task. "
                "Do not claim to have executed anything. "
                "Return only a practical sequence of stages and a verifiable success condition.\n\n"
                f"Task: {task_prompt}"
            )
            interaction = await asyncio.to_thread(
                client.interactions.create,
                model=choice.planner_model,
                input=planning_prompt,
            )
            plan = getattr(interaction, "output_text", None) or str(interaction)
            return f"{task_prompt}\n\nInternal execution plan:\n{plan}"
        except Exception:
            # Planning enhancement must never make the core executor unusable.
            return task_prompt


runtime = AgentRuntime(Settings())
