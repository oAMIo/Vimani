from abc import ABC, abstractmethod
from typing import Any, Dict


class Archivist(ABC):
    """Archivist interface for persisting runs."""

    @abstractmethod
    def store_run(self, payload: Dict[str, Any]) -> Dict[str, str]:
        raise NotImplementedError


