"""Acceptance policy: required checks are explicit and deterministic."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GovernancePolicy:
    required_checks: tuple[str, ...] = ("result_present", "tool_succeeded")

    def __post_init__(self) -> None:
        if len(set(self.required_checks)) != len(self.required_checks):
            raise ValueError("required_checks must not contain duplicates")
        supported = {"result_present", "tool_succeeded"}
        unknown = set(self.required_checks) - supported
        if unknown:
            raise ValueError(f"unsupported required checks: {', '.join(sorted(unknown))}")
