from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .agent_runtime import runtime
from .config import settings
from .domain import TaskRecord, TaskStatus
from .schemas import HealthResponse, ResumeRequest, TaskCreate, TaskResponse
from .store import store
from .usage import ledger

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
app = FastAPI(title=settings.app_name, version="0.1.0")
app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")


def to_response(task: TaskRecord) -> TaskResponse:
    return TaskResponse(
        id=str(task.id), status=task.status, model=task.model,
        spent_usd=round(task.spent_usd, 6), metering_state=task.metering_state, reserved_usd=round(task.reserved_usd, 6),
        steps=task.steps, failure_count=task.failure_count, result=task.result,
        error=task.error, handoff_reason=task.handoff_reason,
    )


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", version="0.1.0")


@app.post("/v1/tasks", response_model=TaskResponse)
async def create_task(payload: TaskCreate, background_tasks: BackgroundTasks):
    budget = payload.budget_usd or settings.default_task_budget_usd
    task = TaskRecord.new(user_id="local-dev-user", prompt=payload.prompt, budget_usd=budget)
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
    if runtime.gemini_cua is None:
        raise HTTPException(status_code=503, detail="Computer-use runtime is not configured")
    if not runtime.gemini_cua.has_session(str(task.id)):
        raise HTTPException(status_code=409, detail="Browser session is not ready")
    try:
        image = await __import__("asyncio").to_thread(runtime.gemini_cua.screenshot, str(task.id))
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(content=image, media_type="image/png", headers={"Cache-Control":"no-store"})

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
        state = await __import__("asyncio").to_thread(runtime.gemini_cua.human_input, str(task.id), action)
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
    task.touch()
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
