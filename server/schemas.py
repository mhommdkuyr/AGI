from pydantic import BaseModel, Field

from .domain import HandoffReason, TaskStatus


class TaskCreate(BaseModel):
    prompt: str = Field(min_length=3, max_length=10000)
    budget_usd: float | None = Field(default=None, gt=0, le=100)
    complexity: str = Field(default="normal", pattern="^(normal|hard|extreme)$")


class ResumeRequest(BaseModel):
    confirmed: bool = False


class TaskResponse(BaseModel):
    id: str
    status: TaskStatus
    model: str | None
    spent_usd: float
    metering_state: str
    reserved_usd: float
    steps: int
    failure_count: int
    result: str | None
    error: str | None
    handoff_reason: HandoffReason | None


class HealthResponse(BaseModel):
    status: str
    version: str


class HumanInput(BaseModel):
    type: str = Field(pattern="^(click|double_click|type|key|scroll|back|forward)$")
    x: int | None = Field(default=None, ge=0, le=1000)
    y: int | None = Field(default=None, ge=0, le=1000)
    text: str | None = Field(default=None, max_length=2000)
    key: str | None = Field(default=None, max_length=50)
    delta: int | None = Field(default=None, ge=-5000, le=5000)
