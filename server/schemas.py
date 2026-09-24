from pydantic import BaseModel, Field

from .domain import HandoffReason, TaskStatus


class TaskCreate(BaseModel):
    prompt: str = Field(min_length=3, max_length=10000)
    budget_usd: float | None = Field(default=None, gt=0, le=100)
    complexity: str = Field(default="normal", pattern="^(normal|hard|extreme)$")


class TaskResponse(BaseModel):
    id: str
    status: TaskStatus
    model: str | None
    spent_usd: float
    reserved_usd: float
    steps: int
    failure_count: int
    result: str | None
    error: str | None
    handoff_reason: HandoffReason | None


class HealthResponse(BaseModel):
    status: str
    version: str
