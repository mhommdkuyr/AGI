from pydantic import BaseModel, Field

from .domain import HandoffReason, TaskStatus, TaskTarget


class TaskCreate(BaseModel):
    prompt: str = Field(min_length=3, max_length=10000)
    budget_usd: float | None = Field(default=None, gt=0, le=100)
    complexity: str = Field(default="normal", pattern="^(normal|hard|extreme)$")
    target: TaskTarget = TaskTarget.BROWSER
    mobile_session_id: str | None = Field(default=None, max_length=128)


class ResumeRequest(BaseModel):
    confirmed: bool = True


class TaskResponse(BaseModel):
    id: str
    target: TaskTarget
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


class MobileSessionCreate(BaseModel):
    device_name: str = Field(default="Android device", min_length=1, max_length=120)


class MobileObservation(BaseModel):
    observation: dict
    screenshot_b64: str | None = None


class MobileCommandResult(BaseModel):
    result: dict
    screenshot_b64: str | None = None
