import json
import uuid
from typing import Any, Dict, List

from openai import OpenAI
from pydantic import ValidationError

from app.config import settings
from app.errors import VimaniError
from app.orchestrator.models import (
    ErrorEnvelope,
    ErrorSeverity,
    ErrorSource,
    Message,
    MessageField,
    MessageType,
    Plan,
)
from app.planner.interface import Planner, PlannerInput, PlannerOutput


SYSTEM_PROMPT = (
    "You are a planner. Return JSON only. Output must be either:\n"
    "1) {'role':'assistant','type':'form','text':..., 'fields':[{'key':'<string>','label':'<string>','type':'text|number|select|textarea','required':true|false,'placeholder':null|'<string>','options':[]}...]}\n"
    "2) {'role':'assistant','type':'plan','plan': {'plan_id':'<string>','tool_key':'<string>','objective':'<string>','steps':[{'step_id':'S1','op_id':'<string>','params':{},'depends_on':[]}]}}\n"
    "For plans: params must always be present (use {} if none). step_id like 'S1','S2', depends_on as list of step_ids."
)


PLANNER_OUTPUT_SCHEMA: Dict[str, Any] = {
    "name": "planner_output",
    "schema": {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["form", "plan"]},
            "text": {"type": "string"},
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["key", "label", "type", "required", "placeholder", "options"],
                    "properties": {
                        "key": {"type": "string"},
                        "label": {"type": "string"},
                        "type": {"type": "string", "enum": ["text", "number", "select", "textarea"]},
                        "required": {"type": "boolean"},
                        "placeholder": {"type": ["string", "null"]},
                        "options": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["id", "label"],
                                "properties": {
                                    "id": {"type": "string"},
                                    "label": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
            "plan": {
                "type": "object",
                "properties": {
                    "plan_id": {"type": "string"},
                    "tool_key": {"type": "string"},
                    "objective": {"type": "string"},
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "step_id": {"type": "string"},
                                "op_id": {"type": "string"},
                                "params": {"type": "object"},
                                "depends_on": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "default": [],
                                },
                                "on_fail": {"type": "string"},
                            },
                            "required": ["step_id", "op_id", "params"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["plan_id", "tool_key", "objective", "steps"],
                "additionalProperties": False,
            },
        },
        "required": ["type"],
        "additionalProperties": False,
    },
}


class LLMPlanner(Planner):
    """Planner implementation backed by the OpenAI Responses API."""

    def __init__(self) -> None:
        # This will raise a structured ErrorEnvelope if the API key is missing.
        api_key = settings.openai_api_key
        self._client = OpenAI(api_key=api_key)

    def _raise_output_error(self, message: str) -> None:
        raise VimaniError(
            ErrorEnvelope(
                code="PLANNER_INVALID_OUTPUT",
                message=message,
                source=ErrorSource.PLANNER,
                severity=ErrorSeverity.RUN,
                retryable=True,
            )
        )

    def _call_openai(self, payload: Dict[str, Any], corrective_message: str | None = None) -> Dict[str, Any]:
        # Minimal runtime log to confirm which model is being used.
        print("LLMPlanner calling model=", settings.planner_model)
        print("LLM sanity test: calling OpenAI")
        
        system_content = SYSTEM_PROMPT
        if corrective_message:
            system_content = f"{SYSTEM_PROMPT}\n\nCORRECTIVE INSTRUCTION: {corrective_message}"
        
        try:
            response = self._client.responses.create(
                model=settings.planner_model,
                input=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": json.dumps(payload)},
                ],
                text={
                    "format": {"type": "json_object"}
                },
            )
        except Exception as exc:  # pragma: no cover - integration edge
            raise VimaniError(
                ErrorEnvelope(
                    code="PLANNER_LLM_CALL_FAILED",
                    message=f"Planner LLM call failed: {exc}",
                    source=ErrorSource.PLANNER,
                    severity=ErrorSeverity.RUN,
                    retryable=True,
                )
            )

        try:
            # Parse JSON from text response (not parsed)
            text_content = response.output[0].content[0].text  # type: ignore[attr-defined]
            if hasattr(text_content, 'value'):
                json_str = text_content.value
            else:
                json_str = str(text_content)
            content = json.loads(json_str)
        except (json.JSONDecodeError, Exception) as exc:  # pragma: no cover - defensive
            self._raise_output_error(
                f"Planner LLM returned invalid JSON: {exc}"
            )

        if not isinstance(content, dict):
            self._raise_output_error("Planner LLM output must be a JSON object.")

        return content

    def _build_payload(self, input: PlannerInput) -> Dict[str, Any]:
        conversation_payload: List[Dict[str, Any]] = [
            msg.model_dump() if hasattr(msg, "model_dump") else msg  # type: ignore[arg-type]
            for msg in input.conversation
        ]

        return {
            "tool_key": input.tool_key,
            "intent": input.intent,
            "conversation": conversation_payload,
            "operation_registry": input.operation_registry,
            "pre_state": input.pre_state,
            "validation_errors": [
                err.model_dump() if hasattr(err, "model_dump") else err  # type: ignore[arg-type]
                for err in (input.validation_errors or [])
            ],
        }

    def _validate_form_fields(self, fields_raw: Any) -> List[MessageField]:
        """Manually validate form fields shape."""
        if not isinstance(fields_raw, list):
            self._raise_output_error("Planner form output must include 'fields' as a list.")
        
        if not fields_raw:
            self._raise_output_error("Planner form output must include at least one field in 'fields'.")
        
        fields: List[MessageField] = []
        for idx, field in enumerate(fields_raw):
            if not isinstance(field, dict):
                self._raise_output_error(
                    f"Planner form field at index {idx} must be an object."
                )
            
            # --- v0 canonical: require only label + type. key/required can be defaulted/mapped ---
            required_keys = {"label", "type"}
            missing_keys = required_keys - set(field.keys())
            if missing_keys:
                self._raise_output_error(
                    f"Planner form field at index {idx} missing required keys: {missing_keys}"
                )

            # Accept 'id' as an alias for 'key'
            if "key" not in field and "id" in field:
                field["key"] = field["id"]

            # Default required if missing
            if "required" not in field:
                field["required"] = False

            # Default placeholder/options if missing
            if "placeholder" not in field:
                field["placeholder"] = None
            if "options" not in field:
                field["options"] = []

            # Validate key types (key can come from id mapping above)
            if "key" not in field:
                self._raise_output_error(f"Planner form field at index {idx}: must have 'key' or 'id'.")
            if not isinstance(field.get("key"), str):
                self._raise_output_error(f"Planner form field at index {idx}: 'key' must be a string.")
            if not isinstance(field.get("label"), str):
                self._raise_output_error(f"Planner form field at index {idx}: 'label' must be a string.")
            if not isinstance(field.get("type"), str):
                self._raise_output_error(f"Planner form field at index {idx}: 'type' must be a string.")
            if field.get("type") not in ("text", "number", "select", "textarea"):
                self._raise_output_error(
                    f"Planner form field at index {idx}: 'type' must be one of: text, number, select, textarea"
                )
            if not isinstance(field.get("required"), bool):
                self._raise_output_error(f"Planner form field at index {idx}: 'required' must be a boolean.")
            if field.get("placeholder") is not None and not isinstance(field.get("placeholder"), str):
                self._raise_output_error(f"Planner form field at index {idx}: 'placeholder' must be a string or null.")
            if not isinstance(field.get("options"), list):
                self._raise_output_error(f"Planner form field at index {idx}: 'options' must be an array.")
            
            # Validate options if present
            options = field.get("options", [])
            for opt_idx, option in enumerate(options):
                if not isinstance(option, dict):
                    self._raise_output_error(
                        f"Planner form field at index {idx}, option at index {opt_idx}: must be an object."
                    )
                if "id" not in option or "label" not in option:
                    self._raise_output_error(
                        f"Planner form field at index {idx}, option at index {opt_idx}: must have 'id' and 'label'."
                    )
                if not isinstance(option.get("id"), str) or not isinstance(option.get("label"), str):
                    self._raise_output_error(
                        f"Planner form field at index {idx}, option at index {opt_idx}: 'id' and 'label' must be strings."
                    )
            
            try:
                fields.append(MessageField.model_validate(field))
            except ValidationError as exc:
                self._raise_output_error(
                    f"Planner form field at index {idx} validation failed: {exc}"
                )
        
        if not fields:
            self._raise_output_error("Planner form output must include at least one valid field in 'fields'.")
        
        return fields

    def next(self, input: PlannerInput) -> PlannerOutput:
        payload = self._build_payload(input)
        
        # Try once, then retry with corrective message if validation fails
        try:
            data = self._call_openai(payload)
        except VimaniError:
            # If LLM call itself fails, don't retry
            raise
        
        # Validate and process, with retry on validation failure
        try:
            return self._process_llm_output(data, input.tool_key, input.intent)
        except VimaniError as ve:
            # Retry once with corrective message
            corrective_msg = f"Previous output was invalid: {ve.envelope.message if hasattr(ve, 'envelope') else str(ve)}. Please ensure the output matches the required format exactly."
            try:
                data = self._call_openai(payload, corrective_message=corrective_msg)
                return self._process_llm_output(data, input.tool_key, input.intent)
            except VimaniError:
                # If retry also fails, raise the original error
                raise ve

    def _process_llm_output(self, data: Dict[str, Any], tool_key: str, intent: str) -> PlannerOutput:
        """Process and validate LLM output."""
        output_type = data.get("type")
        if output_type not in ("form", "plan"):
            self._raise_output_error(
                f"Planner LLM output must have type 'form' or 'plan', got: {output_type}"
            )

        if output_type == "form":
            text = data.get("text")
            if not isinstance(text, str):
                self._raise_output_error("Planner form output must include 'text' as a string.")
            
            # Ensure text is non-empty, use default if empty
            if not text or not text.strip():
                text = "Please provide the following details."

            # Validate fields manually
            fields = self._validate_form_fields(data.get("fields"))

            # Normalize to consistent structure
            fields_dict = [field.model_dump() if hasattr(field, "model_dump") else field for field in fields]
            result = {
                "role": "assistant",
                "type": "form",
                "text": text,
                "fields": fields_dict,
            }
            print("LLMPlanner output:", result)
            return result

        # type == "plan"
        plan_obj = data.get("plan")
        
        # Check if output contains only {"steps": ...} at top level (no "plan" key)
        if not isinstance(plan_obj, dict) and "steps" in data:
            plan_obj = {"steps": data["steps"]}
        
        if not isinstance(plan_obj, dict):
            self._raise_output_error("Planner plan output must include 'plan' as an object or 'steps' array.")
        
        # Ensure required Plan fields are present with defaults
        if "plan_id" not in plan_obj:
            plan_obj["plan_id"] = str(uuid.uuid4())
        if "tool_key" not in plan_obj:
            plan_obj["tool_key"] = "clickup"
        if "objective" not in plan_obj:
            plan_obj["objective"] = ""
        
        # Ensure all steps have params
        steps = plan_obj.get("steps", [])
        if isinstance(steps, list):
            for step in steps:
                if isinstance(step, dict) and "params" not in step:
                    step["params"] = {}
        
        try:
            plan = Plan.model_validate(plan_obj)
        except ValidationError as exc:
            self._raise_output_error(
                f"Planner LLM returned an invalid plan object: {exc}"
            )

        # Normalize to consistent structure
        result = {
            "role": "assistant",
            "type": "plan",
            "plan": plan,
        }
        print("LLMPlanner output:", result)
        return result

