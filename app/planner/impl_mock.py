from typing import Dict, List, Optional

from app.orchestrator.models import Message, MessageField, MessageType, Plan, PlanStep
from app.planner.interface import Planner, PlannerInput, PlannerOutput


class MockPlanner(Planner):
    """Deterministic mock planner for tests and demos."""

    def _build_intake_form(self, intent: str) -> Message:
        return Message(
            role="assistant",
            type=MessageType.FORM,
            text=f"To plan for '{intent}', please share a few details.",
            fields=[
                MessageField(
                    key="team_size",
                    label="Team size",
                    type="number",
                    required=True,
                    placeholder="e.g. 5",
                ),
                MessageField(
                    key="priority",
                    label="Overall priority",
                    type="select",
                    required=True,
                    options=[
                        {"id": "low", "label": "Low"},
                        {"id": "medium", "label": "Medium"},
                        {"id": "high", "label": "High"},
                    ],
                ),
                MessageField(
                    key="notes",
                    label="Additional context (optional)",
                    type="textarea",
                    required=False,
                    placeholder="Any other details that would help planning...",
                ),
            ],
        )

    def _build_plan(self, input: PlannerInput) -> Plan:
        return Plan(
            plan_id="mock-plan",
            tool_key=input.tool_key,
            objective=input.intent,
            steps=[
                PlanStep(
                    step_id="S1",
                    op_id="clickup.space.create",
                    params={"name": "Main Space"},
                    depends_on=[],
                ),
                PlanStep(
                    step_id="S2",
                    op_id="clickup.folder.create",
                    params={"name": "Primary Folder"},
                    depends_on=["S1"],
                ),
                PlanStep(
                    step_id="S3",
                    op_id="clickup.list.create",
                    params={"name": "Initial List"},
                    depends_on=["S2"],
                ),
            ],
        )

    def next(self, input: PlannerInput) -> PlannerOutput:
        # If no user input yet, return form
        if not any(msg.role == "user" for msg in input.conversation):
            intake_form = self._build_intake_form(input.intent)
            return {
                "role": "assistant",
                "type": "form",
                "text": "I need a bit more information to set this up correctly.",
                "fields": intake_form.fields,
            }

        # Else, return plan
        return {
            "role": "assistant",
            "type": "plan",
            "plan": self._build_plan(input),
        }


