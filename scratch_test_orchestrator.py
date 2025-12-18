import asyncio
from app.orchestrator.service import OrchestratorService
from app.planner.impl_mock import MockPlanner
from app.executor.impl_mock import MockExecutor
from app.archivist.impl_jsonl import JsonlArchivist
from app.orchestrator.models import Message, MessageType


async def main():
    planner = MockPlanner()
    executor = MockExecutor()
    archivist = JsonlArchivist()

    orch = OrchestratorService(planner=planner, executor=executor, archivist=archivist)

    # ---- fake UI: send events to console ----
    async def send_event(payload: dict):
        print("\nEVENT:", payload)

    # ---- fake UI: provide planner answers ----
    async def wait_for_user_message(run_id: str):
        return Message(
            role="user",
            type=MessageType.TEXT,
            text="team_size=8; workstreams=Product, Ops, Sales",
        )

    # ---- fake UI: decide what to do on step failure (interactive) ----
    async def wait_for_step_decision(run_id: str, step_id: str):
        def ask():
            print("\n--- STEP FAILED ---")
            print(f"run_id={run_id} step_id={step_id}")
            print("Choose: RETRY_STEP | SKIP_STEP | SKIP_DEPENDENTS | ABORT_RUN | REPLAN")
            return input("> ").strip().upper()

        choice = await asyncio.to_thread(ask)
        if choice not in {"RETRY_STEP", "SKIP_STEP", "SKIP_DEPENDENTS", "ABORT_RUN", "REPLAN"}:
            choice = "RETRY_STEP"

        return {
            "type": "STEP_DECISION",
            "run_id": run_id,
            "step_id": step_id,
            "decision": choice,
            "notes": "manual decision from terminal",
        }

    result = await orch.start_run(
        tool_key="clickup",
        intent="Set up ClickUp for my startup",
        user_context={"demo_user": True, "fail_on_step_id": "S2"},
        send_event=send_event,
        wait_for_user_message=wait_for_user_message,
        wait_for_step_decision=wait_for_step_decision,
    )

    print("\nFINAL RESULT:\n", result)


if __name__ == "__main__":
    asyncio.run(main())
