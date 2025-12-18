from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RunStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RunPhase(str, Enum):
    CREATED = "CREATED"
    PRE_STATE_FETCHED = "PRE_STATE_FETCHED"
    PLANNING = "PLANNING"
    PLAN_VALIDATING = "PLAN_VALIDATING"
    EXECUTING = "EXECUTING"
    PAUSED_FOR_USER = "PAUSED_FOR_USER"
    POST_STATE_FETCHED = "POST_STATE_FETCHED"
    ARCHIVING = "ARCHIVING"
    DONE = "DONE"


class MessageType(str, Enum):
    TEXT = "text"
    QUESTION = "question"
    CHOICE = "choice"
    FORM = "form"
    STATUS = "status"


class ErrorSource(str, Enum):
    PLANNER = "PLANNER"
    EXECUTOR = "EXECUTOR"
    ORCHESTRATOR = "ORCHESTRATOR"


class ErrorSeverity(str, Enum):
    STEP = "STEP"
    RUN = "RUN"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    PAUSED = "PAUSED"
    SKIPPED = "SKIPPED"


class StepDecision(str, Enum):
    RETRY_STEP = "RETRY_STEP"
    SKIP_STEP = "SKIP_STEP"
    SKIP_DEPENDENTS = "SKIP_DEPENDENTS"
    REPLAN = "REPLAN"
    ABORT_RUN = "ABORT_RUN"


class OnFailAction(str, Enum):
    STOP = "STOP"
    SKIP_DEPENDENTS = "SKIP_DEPENDENTS"
    CONTINUE = "CONTINUE"


class MessageField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    type: str
    required: bool = False
    placeholder: Optional[str] = None
    options: List[Dict[str, Any]] = Field(default_factory=list)


class MessageChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    type: MessageType
    text: str
    fields: List[MessageField] = Field(default_factory=list)
    choices: List[MessageChoice] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    op_id: str
    params: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    on_fail: OnFailAction = OnFailAction.SKIP_DEPENDENTS


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    tool_key: str
    objective: str
    steps: List[PlanStep] = Field(default_factory=list)


class ValidationError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    path: Optional[str] = None
    step_id: Optional[str] = None
    op_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    source: ErrorSource
    step_id: Optional[str] = None
    retryable: bool = False
    severity: ErrorSeverity = ErrorSeverity.STEP


class ExecutionEventType(str, Enum):
    RUN_CREATED = "RUN_CREATED"
    DEBUG = "DEBUG"
    PLANNER_MESSAGE = "PLANNER_MESSAGE"
    PLAN_INVALID = "PLAN_INVALID"
    PLAN_ACCEPTED = "PLAN_ACCEPTED"
    EXEC_EVENT = "EXEC_EVENT"
    NEED_STEP_DECISION = "NEED_STEP_DECISION"
    RUN_DONE = "RUN_DONE"
    RUN_ERROR = "RUN_ERROR"
    STEP_STARTED = "STEP_STARTED"
    STEP_LOG = "STEP_LOG"
    STEP_DONE = "STEP_DONE"
    STEP_FAILED = "STEP_FAILED"
    RUN_SUMMARY = "RUN_SUMMARY"


class ExecEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ExecutionEventType
    step_id: Optional[str] = None
    message: Optional[str] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[ErrorEnvelope] = None
    ts: Optional[float] = None


class RunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: RunStatus
    tool_key: str
    intent: str
    registry_version: Optional[str] = None
    plan: Optional[Plan] = None
    execution_trace: List[ExecEvent] = Field(default_factory=list)
    step_results: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[ErrorEnvelope] = Field(default_factory=list)
    pre_state: Dict[str, Any] = Field(default_factory=dict)
    post_state: Dict[str, Any] = Field(default_factory=dict)
    archive_ref: Optional[str] = None
