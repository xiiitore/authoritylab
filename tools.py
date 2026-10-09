"""Explicit registry of workflow handlers."""

from __future__ import annotations

from collections.abc import Callable

from .models import Task, ToolResult

Handler = Callable[[Task], ToolResult]


class ToolRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, kind: str, handler: Handler) -> None:
        if not kind.strip():
            raise ValueError("tool kind must not be empty")
        if kind in self._handlers:
            raise ValueError(f"handler already registered for kind: {kind}")
        self._handlers[kind] = handler

    def resolve(self, kind: str) -> Handler | None:
        return self._handlers.get(kind)

    def registered_kinds(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))
