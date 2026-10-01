"""User-facing errors raised by ListenSignal."""

from __future__ import annotations


class DataProblem(ValueError):
    """Raised when a configuration or analysis request cannot be honored."""


def friendly_message(exc: Exception) -> str:
    """Return a useful message without exposing an internal traceback by default."""
    if isinstance(exc, DataProblem):
        return str(exc)
    if isinstance(exc, ValueError):
        return f"ListenSignal could not complete that step: {exc}"
    return (
        "ListenSignal could not complete that step. Check brands.yaml and sources.yaml and try again. "
        "Set LISTENSIGNAL_DEBUG=1 before launch if you need technical details."
    )
