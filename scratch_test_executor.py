import asyncio
from app.executor.impl_mock import MockExecutor
from app.orchestrator.models import Plan, PlanStep

async def test():
    executor = MockExecutor()
    plan = Plan(
        plan_id="test",
        tool_key="clickup",
        objective="test",
        steps=[
            PlanStep(step_id="S1", op_id="clickup.space.create", params={}, depends_on=[]),
            PlanStep(step_id="S2", op_id="clickup.folder.create", params={}, depends_on=["S1"]),
        ],
    )

    async for event in executor.execute_plan("clickup", plan, fail_on_step_id="S2"):
        print(event)

asyncio.run(test())
