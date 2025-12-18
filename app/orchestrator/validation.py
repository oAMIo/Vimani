import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonschema

from app.orchestrator.models import ValidationError


PLAN_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "plan.schema.json"
MAX_STEPS = 5


def _load_plan_schema() -> Dict[str, Any]:
    with PLAN_SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


PLAN_SCHEMA = _load_plan_schema()


def _make_error(code: str, message: str, step_id: Optional[str] = None, path: Optional[str] = None, op_id: Optional[str] = None) -> ValidationError:
    return ValidationError(code=code, message=message, step_id=step_id, path=path, op_id=op_id)


def validate_plan(plan_dict: Dict[str, Any], registry: Dict[str, Any]) -> List[ValidationError]:
    """Validate a plan against schema, registry, params, dependencies, and limits."""
    errors: List[ValidationError] = []

    # 1. JSON schema validation
    try:
        jsonschema.validate(instance=plan_dict, schema=PLAN_SCHEMA)
    except jsonschema.ValidationError as exc:
        path_str = "/".join(str(p) for p in exc.path) if exc.path else ""
        errors.append(_make_error("SCHEMA_INVALID", exc.message, path=path_str))

    steps: List[Dict[str, Any]] = plan_dict.get("steps", []) or []

    # 2. Limits
    if len(steps) > MAX_STEPS:
        errors.append(_make_error("LIMIT_EXCEEDED", f"Plan has {len(steps)} steps; max is {MAX_STEPS}", path="steps"))

    # 3. Registry lookup
    ops = {op["op_id"]: op for op in registry.get("operations", [])}

    for step in steps:
        step_id = step.get("step_id")
        op_id = step.get("op_id")

        if op_id not in ops:
            errors.append(_make_error("UNKNOWN_OPERATION", f"Operation '{op_id}' not found in registry", step_id=step_id, op_id=op_id))
            continue

        op_schema = ops[op_id].get("input_schema", {})
        try:
            jsonschema.validate(instance=step.get("params", {}), schema=op_schema)
        except jsonschema.ValidationError as exc:
            path_str = "/".join(str(p) for p in exc.path) if exc.path else ""
            errors.append(_make_error("INVALID_PARAMS", exc.message, step_id=step_id, path=path_str, op_id=op_id))

    # 4. Dependency validation
    step_ids = {s.get("step_id") for s in steps}
    adjacency = {s.get("step_id"): s.get("depends_on", []) or [] for s in steps}

    for step in steps:
        step_id = step.get("step_id")
        for dep in step.get("depends_on", []) or []:
            if dep not in step_ids:
                errors.append(_make_error("INVALID_DEPENDENCY", f"Dependency '{dep}' not found", step_id=step_id, path="depends_on"))
            if dep == step_id:
                errors.append(_make_error("INVALID_DEPENDENCY", "Step cannot depend on itself", step_id=step_id, path="depends_on"))

    # cycle detection using DFS
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: Optional[str]) -> bool:
        if node is None:
            return False
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in adjacency.get(node, []):
            if dfs(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    for node in list(adjacency.keys()):
        if dfs(node):
            errors.append(_make_error("INVALID_DEPENDENCY", "Cycle detected in dependencies", step_id=node, path="depends_on"))
            break

    return errors


if __name__ == "__main__":
    # Tiny self-test
    registry_path = Path(__file__).resolve().parent.parent / "registries" / "clickup.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))

    valid_plan = {
        "plan_id": "p1",
        "tool_key": "clickup",
        "objective": "Set up workspace",
        "steps": [
          {
            "step_id": "S1",
            "op_id": "clickup.space.create",
            "params": { "name": "Space A" },
            "depends_on": []
          },
          {
            "step_id": "S2",
            "op_id": "clickup.folder.create",
            "params": { "name": "Folder A" },
            "depends_on": ["S1"]
          }
        ]
    }

    invalid_plan = {
        "plan_id": "p2",
        "tool_key": "clickup",
        "objective": "Bad plan",
        "steps": [
          {
            "step_id": "S1",
            "op_id": "clickup.unknown",
            "params": {},
            "depends_on": ["S2"]
          },
          {
            "step_id": "S2",
            "op_id": "clickup.space.create",
            "params": {},
            "depends_on": ["S1"]
          }
        ]
    }

    print("Valid plan errors:", validate_plan(valid_plan, registry))
    print("Invalid plan errors:", validate_plan(invalid_plan, registry))


