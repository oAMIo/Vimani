from abc import ABC, abstractmethod
from typing import List, Literal, Optional, TypedDict, Union

from pydantic import BaseModel, ConfigDict

from app.orchestrator.models import Message, MessageField, Plan, ValidationError


class PlannerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_key: str
    intent: str
    operation_registry: dict
    pre_state: dict
    conversation: List[Message]
    validation_errors: Optional[List[ValidationError]] = None


class PlannerFormOutput(TypedDict):
    role: Literal["assistant"]
    type: Literal["form"]
    text: str
    fields: List[MessageField]


class PlannerPlanOutput(TypedDict):
    role: Literal["assistant"]
    type: Literal["plan"]
    plan: Plan


PlannerOutput = Union[PlannerFormOutput, PlannerPlanOutput]


class Planner(ABC):
    """Planner interface for generating messages and plans."""

    @abstractmethod
    def next(self, input: PlannerInput) -> PlannerOutput:
        raise NotImplementedError


