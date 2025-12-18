"""Shared error utilities for Vimani backend."""

from __future__ import annotations

from typing import Any, Protocol


class _EnvelopeProtocol(Protocol):
    message: str


class VimaniError(Exception):
    """Base structured error that carries a serialized envelope."""

    def __init__(self, envelope: _EnvelopeProtocol | Any) -> None:
        super().__init__(str(getattr(envelope, "message", envelope)))
        self.envelope = envelope

    def __str__(self) -> str:
        message = getattr(self.envelope, "message", None)
        return message if isinstance(message, str) else repr(self.envelope)
