import asyncio
from typing import Any, AsyncGenerator, Dict, Optional

from app.executor.interface import Executor
from app.orchestrator.models import ErrorEnvelope, ErrorSeverity, ErrorSource, ExecEvent, ExecutionEventType, Plan


class MockExecutor(Executor):
    """Mock executor that simulates plan execution with async events."""

    def fetch_state(self, tool_key: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "spaces": [],
            "folders": [],
            "lists": []
        }

    async def execute_plan(
        self,
        tool_key: str,
        plan: Plan,
        user_context: Optional[Dict[str, Any]] = None,
        fail_on_step_id: Optional[str] = None,
    ) -> AsyncGenerator[ExecEvent, None]:
        for step in plan.steps:
            yield ExecEvent(
                type=ExecutionEventType.STEP_STARTED,
                step_id=step.step_id,
                ts=asyncio.get_event_loop().time()
            )
            
            yield ExecEvent(
                type=ExecutionEventType.STEP_LOG,
                step_id=step.step_id,
                message=f"Executing {step.op_id}",
                ts=asyncio.get_event_loop().time()
            )
            
            await asyncio.sleep(0.5)
            
            if fail_on_step_id == step.step_id:
                yield ExecEvent(
                    type=ExecutionEventType.STEP_FAILED,
                    step_id=step.step_id,
                    error=ErrorEnvelope(
                        code="MOCK_FAILURE",
                        message="Mock failure for testing",
                        source=ErrorSource.EXECUTOR,
                        step_id=step.step_id,
                        retryable=True,
                        severity=ErrorSeverity.STEP
                    ),
                    ts=asyncio.get_event_loop().time()
                )
                return
            else:
                yield ExecEvent(
                    type=ExecutionEventType.STEP_DONE,
                    step_id=step.step_id,
                    output={"ok": True, "step_id": step.step_id},
                    ts=asyncio.get_event_loop().time()
                )
        
        yield ExecEvent(
            type=ExecutionEventType.RUN_SUMMARY,
            ts=asyncio.get_event_loop().time()
        )

