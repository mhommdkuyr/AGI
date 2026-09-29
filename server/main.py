from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import UUID

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .agent_runtime import runtime
from .config import settings
from .domain import TaskRecord, TaskStatus, TaskTarget
from .mobile_bridge import mobile_bridge
from .schemas import (
    HealthResponse,
    HumanInput,
    MobileCommandResult,
    MobileObservation,
    MobileSessionCreate,
    ResumeRequest,
    TaskCreate,
    TaskResponse,
)
from .store import store
from .usage import ledger

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
app = FastAPI(title=settings.app_name, version="0.1.0")
app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")


async def _startup_smoke_test() -> None:
    if runtime.gemini_cua is None:
        print("STARTUP_SMOKE: skipped; GOOGLE_API_KEY/GEMINI_API_KEY is not configured", flush=True)
        return
    task_id = "startup-smoke"
    try:
        result, meta = await asyncio.to_thread(
            runtime.gemini_cua.run,
            task_id,
            (
                "Open https://example.com. Read the current page and return one concise "
                "sentence containing the exact page title and the final URL. Do not visit any other site."
            ),
            8,
            0.10,
        )
        print(
            "STARTUP_SMOKE: "
            f"status={meta.get('status')} usage_known={meta.get('usage_known')} "
            f"turns={meta.get('turns')} cost_usd={meta.get('provider_cost_usd')} "
            f"final_url={meta.get('final_url')} result={result!r}", flush=True
        )
    except Exception as exc:
        print(f"STARTUP_SMOKE: failed: {exc}", flush=True)
    finally:
        runtime.gemini_cua.close(task_id)


@app.on_event("startup")
async def startup() -> None:
    if os.getenv("STARTUP_SMOKE_TEST", "").lower() == "true":
        asyncio.create_task(_startup_smoke_test())


def to_response(task: TaskRecord) -> TaskResponse:
    return TaskResponse(
        id=str(task.id),
        target=task.target,
        status=task.status,
        model=task.model,
        spent_usd=round(task.spent_usd, 6),
        metering_state=task.metering_state,
        reserved_usd=round(task.reserved_usd, 6),
        steps=task.steps,
        failure_count=task.failure_count,
        result=task.result,
        error=task.error,
        handoff_reason=task.handoff_reason,
    )


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(WEB_DIR / "index.html")

@app.head("/", include_in_schema=False)
async def index_head():
    return Response(status_code=200)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", version="0.1.0")


@app.post("/v1/mobile/sessions")
async def create_mobile_session(payload: MobileSessionCreate):
    session = mobile_bridge.create_session(payload.device_name)
    return {"id": session.id, "device_name": session.device_name, "status": session.status}


@app.get("/v1/mobile/sessions/{session_id}")
async def get_mobile_session(session_id: str):
    session = mobile_bridge.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Mobile session not found.")
    observation = session.observation or {}
    return {
        "id": session.id,
        "device_name": session.device_name,
        "status": session.status,
        "interaction_id": session.interaction_id,
        "handoff_reason": session.handoff_reason.value if session.handoff_reason else None,
        "package_name": observation.get("package_name"),
        "activity_name": observation.get("activity_name"),
        "updated_at": session.updated_at,
        "has_screenshot": bool(session.screenshot_b64),
        "pending_confirmation": session.pending_confirmation is not None,
    }


@app.post("/v1/mobile/sessions/{session_id}/observation")
async def update_mobile_observation(session_id: str, payload: MobileObservation):
    session = mobile_bridge.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Mobile session not found.")
    observation = mobile_bridge.sanitize_observation(payload.observation)
    session.update_observation(observation, payload.screenshot_b64)
    return {"ok": True, "status": session.status}


@app.get("/v1/mobile/sessions/{session_id}/command")
async def get_mobile_command(session_id: str):
    session = mobile_bridge.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Mobile session not found.")
    command = session.next_command()
    if command is None:
        return Response(status_code=204)
    return command


@app.post("/v1/mobile/sessions/{session_id}/command-result", response_model=MobileCommandResult)
async def post_mobile_command_result(session_id: str, payload: MobileCommandResult):
    session = mobile_bridge.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Mobile session not found.")
    command_id = str(payload.result.get("command_id") or "")
    if not command_id:
        raise HTTPException(status_code=400, detail="command_id is required in result.")
    session.set_result(command_id, dict(payload.result))
    if payload.screenshot_b64 is not None:
        session.screenshot_b64 = payload.screenshot_b64
        session.updated_at = __import__("time").time()
    return {"result": payload.result, "screenshot_b64": payload.screenshot_b64}


@app.post("/v1/tasks", response_model=TaskResponse)
async def create_task(payload: TaskCreate, background_tasks: BackgroundTasks):
    if runtime.gemini_cua is None:
        raise HTTPException(status_code=503, detail="Computer-use runtime is not configured. Add GOOGLE_API_KEY or GEMINI_API_KEY to the deployed service.")
    budget = payload.budget_usd or settings.default_task_budget_usd
    if payload.target == TaskTarget.MOBILE:
        if runtime.gemini_mobile is None:
            raise HTTPException(status_code=503, detail="Mobile computer-use runtime is not configured.")
        if not payload.mobile_session_id:
            raise HTTPException(status_code=400, detail="mobile_session_id is required for mobile tasks.")
        if mobile_bridge.get(payload.mobile_session_id) is None:
            raise HTTPException(status_code=404, detail="Mobile session not found.")
    task = TaskRecord.new(
        user_id="local-dev-user",
        prompt=payload.prompt,
        budget_usd=budget,
        target=payload.target,
        mobile_session_id=payload.mobile_session_id,
    )
    ledger.reserve(task.id, budget)
    task.reserved_usd = budget
    store.create(task)
    background_tasks.add_task(runtime.run, task, payload.complexity)
    return to_response(task)


@app.get("/v1/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: UUID):
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return to_response(task)


@app.get("/v1/tasks/{task_id}/screen")
async def task_screen(task_id: UUID):
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.target == TaskTarget.MOBILE:
        if not task.mobile_session_id:
            raise HTTPException(status_code=409, detail="Task has no mobile session.")
        mobile_session = mobile_bridge.get(task.mobile_session_id)
        if mobile_session is None:
            raise HTTPException(status_code=404, detail="Mobile session not found.")
        image = mobile_bridge.screenshot_bytes(mobile_session)
        if image is None:
            raise HTTPException(status_code=409, detail="Mobile screenshot is not ready")
    else:
        if runtime.gemini_cua is None:
            raise HTTPException(status_code=503, detail="Computer-use runtime is not configured")
        if not runtime.gemini_cua.has_session(str(task.id)):
            raise HTTPException(status_code=409, detail="Browser session is not ready")
        try:
            image = await asyncio.to_thread(runtime.gemini_cua.screenshot, str(task.id))
        except Exception as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(content=image, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.post("/v1/tasks/{task_id}/human-input")
async def human_input(task_id: UUID, payload: HumanInput):
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.WAITING_HUMAN:
        raise HTTPException(status_code=409, detail="Task is not waiting for human interaction")
    if runtime.gemini_cua is None:
        raise HTTPException(status_code=503, detail="Computer-use runtime is not configured")
    action = payload.model_dump(exclude_none=True)
    try:
        state = await asyncio.to_thread(
            runtime.gemini_cua.human_input, str(task.id), action
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "state": state}


@app.post("/v1/tasks/{task_id}/resume", response_model=TaskResponse)
async def resume_task(task_id: UUID, payload: ResumeRequest, background_tasks: BackgroundTasks):
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.WAITING_HUMAN:
        raise HTTPException(status_code=409, detail="Task is not waiting for human input")
    background_tasks.add_task(runtime.run, task, "auto", None, payload.confirmed)
    return to_response(task)


@app.post("/v1/tasks/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: UUID):
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = TaskStatus.CANCELLED
    task.touch()
    return to_response(task)
