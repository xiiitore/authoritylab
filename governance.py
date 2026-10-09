"""Acceptance policy and structural evidence schemas."""

from __future__ import annotations

from dataclasses import dataclass


MANDATORY_CHECKS = ("result_present", "tool_succeeded")


@dataclass(frozen=True, slots=True)
class EvidenceSchema:
    """Minimal structural contract for one task kind's output.

    This validates shape/completeness only; it cannot prove factual truth.
    """
    task_kind: str
    required_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.task_kind, str) or not self.task_kind.strip():
            raise ValueError("task_kind must be a non-empty string")
        if not isinstance(self.required_fields, tuple) or not self.required_fields:
            raise ValueError("required_fields must be a non-empty tuple")
        if any(not isinstance(field, str) or not field.strip() for field in self.required_fields):
            raise ValueError("required field names must be non-empty strings")
        if len(set(self.required_fields)) != len(self.required_fields):
            raise ValueError("required field names must be unique")


@dataclass(frozen=True, slots=True)
class GovernancePolicy:
    # The baseline checks cannot be removed or reordered into an unsafe subset.
    required_checks: tuple[str, ...] = MANDATORY_CHECKS
    evidence_schemas: tuple[EvidenceSchema, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.required_checks, tuple):
            raise TypeError("required_checks must be a tuple")
        if any(
            not isinstance(name, str) or not name.strip()
            for name in self.required_checks
        ):
            raise ValueError("required check names must be non-empty strings")
        if len(set(self.required_checks)) != len(self.required_checks):
            raise ValueError("required_checks must not contain duplicates")
        supported = set(MANDATORY_CHECKS)
        unknown = set(self.required_checks) - supported
        if unknown:
            raise ValueError(f"unsupported required checks: {', '.join(sorted(unknown))}")
        missing = set(MANDATORY_CHECKS) - set(self.required_checks)
        if missing:
            raise ValueError(
                "mandatory checks cannot be disabled: " + ", ".join(sorted(missing))
            )
        if self.required_checks != MANDATORY_CHECKS:
            raise ValueError(
                "required_checks must include both mandatory checks in canonical order"
            )
        if not isinstance(self.evidence_schemas, tuple):
            raise TypeError("evidence_schemas must be a tuple")
        if any(not isinstance(schema, EvidenceSchema) for schema in self.evidence_schemas):
            raise TypeError("evidence_schemas must contain EvidenceSchema values")
        kinds = [schema.task_kind for schema in self.evidence_schemas]
        if len(set(kinds)) != len(kinds):
            raise ValueError("only one evidence schema may be registered per task kind")

    def schema_for(self, task_kind: str | None) -> EvidenceSchema | None:
        if not isinstance(task_kind, str):
            return None
        return next(
            (schema for schema in self.evidence_schemas if schema.task_kind == task_kind),
            None,
        )
