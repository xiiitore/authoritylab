"""Explicit registry of handlers; untrusted callables are never executed."""

from __future__ import annotations

from collections.abc import Callable

from .models import Task, ToolResult

Handler = Callable[[Task], ToolResult]


class ToolRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, tuple[Handler, bool]] = {}

    def register(self, kind: str, handler: Handler, *, trusted: bool = False) -> None:
        if not isinstance(kind, str):
            raise TypeError("tool kind must be a string")
        kind = kind.strip()
        if not kind:
            raise ValueError("tool kind must not be empty")
        if not callable(handler):
            raise TypeError("handler must be callable")
        if type(trusted) is not bool:
            raise TypeError("trusted must be a bool")
        if kind in self._handlers:
            raise ValueError(f"handler already registered for kind: {kind}")
        # This is an execution allow-list, not a sandbox. Callers must only set
        # trusted=True for code they control and have reviewed.
        self._handlers[kind] = (handler, trusted)

    def resolve(self, kind: str) -> Handler | None:
        if not isinstance(kind, str):
            return None
        entry = self._handlers.get(kind.strip())
        if entry is None or not entry[1]:
            return None
        return entry[0]

    def is_registered(self, kind: str) -> bool:
        return isinstance(kind, str) and kind.strip() in self._handlers

    def registered_kinds(self) -> tuple[str, ...]:
        """Return only handlers explicitly allow-listed as trusted."""
        return tuple(sorted(kind for kind, (_, trusted) in self._handlers.items() if trusted))
