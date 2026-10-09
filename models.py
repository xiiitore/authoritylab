"""Typed data structures shared by the workflow components."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class WorkflowStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class Task:
    task_id: str
    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str):
            raise TypeError("task_id must be a string")
        if not isinstance(self.kind, str):
            raise TypeError("kind must be a string")
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a mapping")
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        if not self.kind.strip():
            raise ValueError("kind must not be empty")


@dataclass(frozen=True, slots=True)
class ToolResult:
    ok: bool
    output: Any = None
    error: str | None = None

    def __post_init__(self) -> None:
        if type(self.ok) is not bool:
            raise TypeError("ok must be a bool")
        if self.error is not None and not isinstance(self.error, str):
            raise TypeError("error must be a string or None")


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    status: CheckStatus
    detail: str


@dataclass(frozen=True, slots=True)
class WorkflowReport:
    task_id: str
    route: str | None
    status: WorkflowStatus
    tool_result: ToolResult | None
    checks: tuple[CheckResult, ...]
    audit: Mapping[str, Any]
