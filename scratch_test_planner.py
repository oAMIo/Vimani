from app.planner.impl_mock import MockPlanner
from app.planner.interface import PlannerInput
from app.orchestrator.models import Message

planner = MockPlanner()
inp = PlannerInput(
    tool_key="clickup",
    intent="Set up ClickUp for my startup",
    operation_registry={"tool_key":"clickup","version":"v1","operations":[]},
    pre_state={},
    conversation=[],
    validation_errors=None,
)
print(planner.next(inp))
