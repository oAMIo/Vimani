import asyncio
import inspect
import json
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from app.archivist.interface import Archivist
from app.executor.interface import Executor
from app.orchestrator.models import ErrorEnvelope, ErrorSeverity, ErrorSource, ExecutionEventType, ExecEvent, Message, MessageType, Plan, PlanStep, RunResult, RunStatus, StepDecision, ValidationError
from app.orchestrator.validation import validate_plan
from app.planner.interface import Planner, PlannerInput


def load_registry(tool_key: str) -> Dict[str, Any]:
    """Load the operation registry for a given tool."""
    registries_dir = Path(__file__).resolve().parent.parent / "registries"
    registry_path = registries_dir / f"{tool_key}.json"
    if not registry_path.exists():
        raise FileNotFoundError(f"Registry not found for tool_key '{tool_key}' at {registry_path}")
    with registry_path.open("r", encoding="utf-8") as f:
        return json.load(f)


class OrchestratorService:
    """Coordinates planner, executor, and archivist interactions."""

    def __init__(self, planner: Planner, executor: Executor, archivist: Archivist) -> None:
        self.planner = planner
        self.executor = executor
        self.archivist = archivist

    def _to_serializable(self, value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if isinstance(value, dict):
            return {k: self._to_serializable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._to_serializable(v) for v in value]
        return value

    async def _emit(self, send_event: Callable[[Dict[str, Any]], Any], payload: Dict[str, Any]) -> None:
        """Emit an event, handling both sync and async send_event functions."""
        serializable_payload = self._to_serializable(payload)
        result = send_event(serializable_payload)
        if inspect.iscoroutine(result):
            await result

    async def start_run(
        self,
        tool_key: str,
        intent: str,
        user_context: Optional[Dict[str, Any]],
        send_event: Callable[[Dict[str, Any]], None],
        wait_for_user_message: Callable[[], Any],
        wait_for_step_decision: Callable[[], Any],
    ) -> RunResult:
        run_id = str(uuid.uuid4())
        
        registry = load_registry(tool_key)
        
        pre_state = self.executor.fetch_state(tool_key, user_context)
        
        await self._emit(send_event, {"type": ExecutionEventType.RUN_CREATED, "run_id": run_id})
        await self._emit(send_event, {"type": ExecutionEventType.DEBUG, "run_id": run_id, "message": "orchestrator skeleton ok"})
        
        conversation: list[Message] = []
        plan_dict: Optional[Dict[str, Any]] = None
        last_errors: Optional[list] = None
        
        for turn in range(10):
            planner_input = PlannerInput(
                tool_key=tool_key,
                intent=intent,
                operation_registry=registry,
                pre_state=pre_state,
                conversation=conversation,
                validation_errors=last_errors
            )
            
            output = self.planner.next(planner_input)
            
            if output["type"] == "form":
                # Planner requests user input via form:
                # 1. Emit PLANNER_MESSAGE to send form to user
                # 2. Wait for user response
                # 3. Add user message to conversation
                # 4. Continue loop to call planner again with updated context
                # DO NOT proceed to execution - only proceed when type="plan"
                message_dict = {
                    "role": output.get("role", "assistant"),
                    "type": "form",
                    "text": output["text"],
                    "fields": output["fields"],
                }
                await self._emit(send_event, {"type": ExecutionEventType.PLANNER_MESSAGE, "run_id": run_id, "message": message_dict})
                user_response = await wait_for_user_message()
                if isinstance(user_response, dict):
                    user_message = Message(**user_response)
                else:
                    user_message = user_response
                conversation.append(user_message)
                continue
            
            if output["type"] == "plan":
                # Planner returned a plan - break out of loop to proceed with validation
                # Only after validation passes will we emit PLAN_ACCEPTED and start execution
                plan = output["plan"]
                plan_dict = plan.model_dump() if hasattr(plan, "model_dump") else plan
                break
            
            # Unexpected output type - log and continue (will timeout after 10 turns)
            await self._emit(send_event, {
                "type": ExecutionEventType.DEBUG,
                "run_id": run_id,
                "message": f"Unexpected planner output type: {output.get('type')}"
            })
        
        if plan_dict is None:
            return RunResult(
                run_id=run_id,
                status=RunStatus.FAILED,
                tool_key=tool_key,
                intent=intent,
                pre_state=pre_state,
                errors=[
                    ErrorEnvelope(
                        code="PLANNING_TIMEOUT",
                        message="Planning loop ended without PLAN_FINAL",
                        source=ErrorSource.PLANNER,
                        severity=ErrorSeverity.RUN,
                        retryable=False,
                    )
                ],
            )
        
        validation_errors = validate_plan(plan_dict, registry)
        correction_retries = 0
        max_correction_retries = 3
        
        while validation_errors and correction_retries < max_correction_retries:
            errors_dict = [err.model_dump() for err in validation_errors]
            await self._emit(send_event, {"type": ExecutionEventType.PLAN_INVALID, "run_id": run_id, "errors": errors_dict})
            
            last_errors = validation_errors
            planner_input = PlannerInput(
                tool_key=tool_key,
                intent=intent,
                operation_registry=registry,
                pre_state=pre_state,
                conversation=conversation,
                validation_errors=last_errors
            )
            
            output = self.planner.next(planner_input)
            
            if output["type"] == "form":
                # Normalized form structure: {role, type, text, fields}
                message_dict = {
                    "role": output.get("role", "assistant"),
                    "type": "form",
                    "text": output["text"],
                    "fields": output["fields"],
                }
                await self._emit(send_event, {"type": ExecutionEventType.PLANNER_MESSAGE, "run_id": run_id, "message": message_dict})
                user_response = await wait_for_user_message()
                if isinstance(user_response, dict):
                    user_message = Message(**user_response)
                else:
                    user_message = user_response
                conversation.append(user_message)
                continue
            
            if output["type"] == "plan":
                # Normalized plan structure: {role, type, plan}
                plan = output["plan"]
                plan_dict = plan.model_dump() if hasattr(plan, "model_dump") else plan
                validation_errors = validate_plan(plan_dict, registry)
                correction_retries += 1
            else:
                break
        
        if validation_errors:
            return RunResult(
                run_id=run_id,
                status=RunStatus.FAILED,
                tool_key=tool_key,
                intent=intent,
                pre_state=pre_state,
                errors=[
                    ErrorEnvelope(
                        code=err.code,
                        message=err.message,
                        source=ErrorSource.PLANNER,
                        step_id=err.step_id,
                        severity=ErrorSeverity.STEP if err.step_id else ErrorSeverity.RUN,
                        retryable=False,
                    )
                    for err in validation_errors
                ],
            )
        
        plan_model = Plan(**plan_dict)
        await self._emit(send_event, {"type": ExecutionEventType.PLAN_ACCEPTED, "run_id": run_id, "plan": plan_dict})
        
        skipped_steps: Set[str] = set()
        exec_trace: list[ExecEvent] = []
        aborted = False
        fail_on_step_id = (user_context or {}).get("fail_on_step_id")
        await self._emit(
            send_event,
            {
                "type": ExecutionEventType.DEBUG,
                "run_id": run_id,
                "message": f"fail_on_step_id resolved to {fail_on_step_id!r}",
            },
        )
        
        while True:
            need_replan = False
            step_index = 0
            
            while step_index < len(plan_model.steps):
                if aborted:
                    break
                
                current_step = plan_model.steps[step_index]
                if current_step.step_id in skipped_steps:
                    step_index += 1
                    continue
                
                if any(dep in skipped_steps for dep in current_step.depends_on):
                    skipped_steps.add(current_step.step_id)
                    step_index += 1
                    continue
                
                retry_without_fail = False
                step_completed = False
                
                while True:
                    context_to_use = user_context
                    if retry_without_fail and user_context:
                        context_to_use = dict(user_context)
                        context_to_use.pop("fail_on_step_id", None)
                    
                    single_plan = Plan(
                        plan_id=f"{plan_model.plan_id}_step_{current_step.step_id}",
                        tool_key=tool_key,
                        objective=f"Execute step {current_step.step_id}",
                        steps=[current_step]
                    )
                    
                    fail_target = None if retry_without_fail else (fail_on_step_id if fail_on_step_id == current_step.step_id else None)
                    failure_event: ExecEvent | None = None
                    step_done_event = False
                    
                    async for event in self.executor.execute_plan(
                        tool_key,
                        single_plan,
                        user_context=context_to_use,
                        fail_on_step_id=fail_target,
                    ):
                        if event.type == ExecutionEventType.RUN_SUMMARY:
                            continue
                        event_dict = event.model_dump() if hasattr(event, "model_dump") else event
                        await self._emit(send_event, {"type": ExecutionEventType.EXEC_EVENT, "run_id": run_id, "event": event_dict})
                        exec_trace.append(event)
                        if event.type == ExecutionEventType.STEP_FAILED and event.step_id == current_step.step_id:
                            failure_event = event
                            break
                        if event.type == ExecutionEventType.STEP_DONE and event.step_id == current_step.step_id:
                            step_done_event = True
                    
                    if failure_event is None:
                        step_completed = step_done_event
                        break
                    
                    error_dict = failure_event.error.model_dump() if failure_event.error and hasattr(failure_event.error, "model_dump") else (failure_event.error if failure_event.error else {})
                    await self._emit(send_event, {"type": ExecutionEventType.NEED_STEP_DECISION, "run_id": run_id, "step_id": failure_event.step_id, "error": error_dict})
                    
                    # Wait for step decision and filter by step_id
                    while True:
                        decision_response = await wait_for_step_decision()
                        if isinstance(decision_response, dict):
                            if decision_response.get("run_id") == run_id and decision_response.get("step_id") == failure_event.step_id:
                                decision = decision_response.get("decision")
                                break
                        else:
                            # Fallback if not a dict
                            decision = decision_response
                            break
                    
                    if decision == StepDecision.ABORT_RUN:
                        aborted = True
                        break
                    if decision == StepDecision.RETRY_STEP:
                        retry_without_fail = True
                        continue
                    if decision == StepDecision.SKIP_STEP:
                        skipped_steps.add(failure_event.step_id)
                        if fail_on_step_id == failure_event.step_id:
                            fail_on_step_id = None
                        break
                    if decision == StepDecision.SKIP_DEPENDENTS:
                        skipped_steps.add(failure_event.step_id)
                        for step in plan_model.steps:
                            if failure_event.step_id in step.depends_on:
                                skipped_steps.add(step.step_id)
                        if fail_on_step_id == failure_event.step_id:
                            fail_on_step_id = None
                        break
                    if decision == StepDecision.REPLAN:
                        failure_msg = Message(
                            role="assistant",
                            type=MessageType.TEXT,
                            text=f"Step {failure_event.step_id} failed: {failure_event.error.message if failure_event.error else 'Unknown error'}. Please provide a new plan."
                        )
                        conversation.append(failure_msg)
                        plan_dict = None
                        need_replan = True
                        break
                    break
                
                if aborted or need_replan:
                    break
                
                if current_step.step_id in skipped_steps:
                    step_index += 1
                    continue
                
                if step_completed:
                    if fail_on_step_id == current_step.step_id:
                        fail_on_step_id = None
                    step_index += 1
                else:
                    step_index += 1
            
            if aborted:
                break
            
            if need_replan:
                for turn in range(10):
                    planner_input = PlannerInput(
                        tool_key=tool_key,
                        intent=intent,
                        operation_registry=registry,
                        pre_state=pre_state,
                        conversation=conversation,
                        validation_errors=None
                    )
                    output = self.planner.next(planner_input)
                    if output["type"] == "form":
                        # Normalized form structure: {role, type, text, fields}
                        message_dict = {
                            "role": output.get("role", "assistant"),
                            "type": "form",
                            "text": output["text"],
                            "fields": output["fields"],
                        }
                        await self._emit(send_event, {"type": ExecutionEventType.PLANNER_MESSAGE, "run_id": run_id, "message": message_dict})
                        user_response = await wait_for_user_message()
                        if isinstance(user_response, dict):
                            user_message = Message(**user_response)
                        else:
                            user_message = user_response
                        conversation.append(user_message)
                        continue
                    if output["type"] == "plan":
                        # Normalized plan structure: {role, type, plan}
                        plan = output["plan"]
                        plan_dict = plan.model_dump() if hasattr(plan, "model_dump") else plan
                        break
                if plan_dict:
                    validation_errors = validate_plan(plan_dict, registry)
                    if not validation_errors:
                        plan_model = Plan(**plan_dict)
                        await self._emit(send_event, {"type": ExecutionEventType.PLAN_ACCEPTED, "run_id": run_id, "plan": plan_dict})
                        skipped_steps.clear()
                        exec_trace.clear()
                        continue
                aborted = True
                break
            
            break
        
        post_state = self.executor.fetch_state(tool_key, user_context)
        
        final_status = RunStatus.CANCELLED if aborted else (RunStatus.PARTIAL if skipped_steps or any(evt.type == ExecutionEventType.STEP_FAILED for evt in exec_trace) else RunStatus.SUCCESS)
        
        summary_event = ExecEvent(
            type=ExecutionEventType.RUN_SUMMARY,
            message=f"Run completed with status {final_status.value}",
            output={
                "status": final_status.value,
                "skipped_steps": sorted(list(skipped_steps)),
                "total_steps": len(plan_model.steps),
            },
        )
        await self._emit(
            send_event,
            {
                "type": "EXEC_EVENT",
                "run_id": run_id,
                "event": summary_event.model_dump(),
            },
        )
        exec_trace.append(summary_event)
        
        archive_payload = {
            "run_id": run_id,
            "tool_key": tool_key,
            "intent": intent,
            "registry_version": registry.get("version"),
            "conversation": [msg.model_dump() if hasattr(msg, "model_dump") else msg for msg in conversation],
            "plan": plan_dict,
            "exec_trace": [evt.model_dump() if hasattr(evt, "model_dump") else evt for evt in exec_trace],
            "pre_state": pre_state,
            "post_state": post_state,
            "status": final_status.value
        }
        
        archive_ref = None
        try:
            archive_result = self.archivist.store_run(archive_payload)
            archive_ref = archive_result.get("archive_ref") if archive_result else None
        except Exception as e:
            await self._emit(send_event, {
                "type": ExecutionEventType.DEBUG,
                "run_id": run_id,
                "message": f"Archivist skipped: {e}"
            })
        
        return RunResult(
            run_id=run_id,
            status=final_status,
            tool_key=tool_key,
            intent=intent,
            registry_version=registry.get("version"),
            plan=plan_model,
            execution_trace=exec_trace,
            pre_state=pre_state,
            post_state=post_state,
            archive_ref=archive_ref
        )


if __name__ == "__main__":
    # Simple debug demonstration to verify registry loading works.
    try:
        print("Loaded registry:", load_registry("clickup"))
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
