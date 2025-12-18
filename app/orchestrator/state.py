import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.orchestrator.models import RunPhase, RunStatus


class RunState(BaseModel):
    """State for a single orchestrator run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    tool_key: str
    intent: str
    phase: RunPhase = RunPhase.CREATED
    status: RunStatus = RunStatus.SUCCESS
    conversation: List[Dict[str, Any]] = Field(default_factory=list)
    pre_state: Dict[str, Any] = Field(default_factory=dict)
    post_state: Dict[str, Any] = Field(default_factory=dict)
    plan: Optional[Dict[str, Any]] = None
    validation_errors: List[Dict[str, Any]] = Field(default_factory=list)
    exec_trace: List[Dict[str, Any]] = Field(default_factory=list)
    step_status: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def touch(self) -> None:
        self.updated_at = datetime.utcnow()


class InMemoryRunStore:
    """Lightweight in-memory store for run states."""

    def __init__(self) -> None:
        self._runs: Dict[str, RunState] = {}

    def create_run(self, tool_key: str, intent: str) -> RunState:
        run_id = str(uuid.uuid4())
        state = RunState(run_id=run_id, tool_key=tool_key, intent=intent, status=RunStatus.SUCCESS)
        self._runs[run_id] = state
        return state

    def get_run(self, run_id: str) -> Optional[RunState]:
        return self._runs.get(run_id)

    def update_run(self, run_id: str, **updates: Any) -> RunState:
        state = self._runs.get(run_id)
        if state is None:
            raise KeyError(f"Run {run_id} not found")
        updated = state.model_copy(update=updates)
        updated.touch()
        self._runs[run_id] = updated
        return updated

    def delete_run(self, run_id: str) -> None:
        self._runs.pop(run_id, None)


