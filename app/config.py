import os
from typing import Any, Optional

from app.errors import VimaniError
from app.orchestrator.models import ErrorEnvelope, ErrorSeverity, ErrorSource


class Settings:
    """
    Central configuration for backend services.

    Reads environment variables at runtime when properties are accessed.
    """

    def __init__(self) -> None:
        self._openai_api_key: Optional[str] = None
        self._planner_model: Optional[str] = None

    @property
    def openai_api_key(self) -> str:
        """
        Return the OpenAI API key or raise a structured planner error if missing.
        """
        if self._openai_api_key is None:
            self._openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self._openai_api_key:
            raise VimaniError(
                ErrorEnvelope(
                    code="PLANNER_MISSING_API_KEY",
                    message="OPENAI_API_KEY is not configured in the environment.",
                    source=ErrorSource.PLANNER,
                    severity=ErrorSeverity.RUN,
                    retryable=False,
                )
            )
        return self._openai_api_key

    @property
    def planner_model(self) -> str:
        if self._planner_model is None:
            self._planner_model = os.getenv("VIMANI_PLANNER_MODEL", "gpt-4.1-mini")
        return self._planner_model


_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the singleton Settings instance (lazy initialization)."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


# For backward compatibility, provide a settings object that lazily initializes
class _SettingsProxy:
    """Proxy that lazily initializes Settings on first access."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_settings(), name)


settings = _SettingsProxy()


