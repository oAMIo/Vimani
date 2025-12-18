from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, Optional

from app.orchestrator.models import ExecEvent, Plan


class Executor(ABC):
    """Executor interface for running plan steps."""

    @abstractmethod
    def fetch_state(self, tool_key: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def execute_plan(
        self,
        tool_key: str,
        plan: Plan,
        user_context: Optional[Dict[str, Any]] = None,
        fail_on_step_id: Optional[str] = None,
    ) -> AsyncGenerator[ExecEvent, None]:
        raise NotImplementedError


