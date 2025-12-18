from typing import Iterable, List


def validate_dependencies(steps: Iterable[dict]) -> None:
    """Ensure no self-dependencies and keep placeholder hook for graph checks."""
    for step in steps:
        step_id = step.get("step_id")
        depends_on: List[str] = step.get("depends_on", []) or []
        if step_id in depends_on:
            raise ValueError(f"Step {step_id} cannot depend on itself")






