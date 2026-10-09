"""Domain-specific semantic evidence validation hooks."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .models import CheckStatus


@dataclass(frozen=True, slots=True)
class SemanticValidationResult:
    status: CheckStatus
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, CheckStatus):
            raise TypeError("status must be a CheckStatus")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError("detail must be a non-empty string")


SemanticValidator = Callable[[Mapping[str, Any]], SemanticValidationResult]


class SemanticValidatorRegistry:
    """Explicit task-kind registry; duplicate registrations are rejected."""

    def __init__(self) -> None:
        self._validators: dict[str, SemanticValidator] = {}

    def register(self, task_kind: str, validator: SemanticValidator) -> None:
        if not isinstance(task_kind, str) or not task_kind.strip():
            raise ValueError("task_kind must be a non-empty string")
        task_kind = task_kind.strip()
        if not callable(validator):
            raise TypeError("validator must be callable")
        if task_kind in self._validators:
            raise ValueError(f"validator already registered for task kind: {task_kind}")
        self._validators[task_kind] = validator

    def resolve(self, task_kind: str | None) -> SemanticValidator | None:
        if not isinstance(task_kind, str) or not task_kind.strip():
            return None
        return self._validators.get(task_kind.strip())

    def validate(self, task_kind: str, evidence: Mapping[str, Any]) -> SemanticValidationResult:
        if not isinstance(evidence, Mapping):
            return SemanticValidationResult(
                CheckStatus.UNKNOWN, "semantic evidence must be a mapping"
            )
        validator = self.resolve(task_kind)
        if validator is None:
            return SemanticValidationResult(CheckStatus.UNKNOWN, "no semantic validator is registered")
        try:
            result = validator(evidence)
        except Exception as exc:
            return SemanticValidationResult(CheckStatus.UNKNOWN, f"semantic validator raised {type(exc).__name__}")
        if not isinstance(result, SemanticValidationResult):
            return SemanticValidationResult(CheckStatus.UNKNOWN, "semantic validator returned an invalid result type")
        return result
