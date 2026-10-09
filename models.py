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
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        if not self.kind.strip():
            raise ValueError("kind must not be empty")


@dataclass(frozen=True, slots=True)
class ToolResult:
    ok: bool
    output: Any = None
    error: str | None = None


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
