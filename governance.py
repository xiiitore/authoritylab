"""Acceptance policy: required checks are explicit and deterministic."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GovernancePolicy:
    required_checks: tuple[str, ...] = ("result_present", "tool_succeeded")

    def __post_init__(self) -> None:
        if not isinstance(self.required_checks, tuple):
            raise TypeError("required_checks must be a tuple")
        if not self.required_checks:
            raise ValueError("required_checks must not be empty")
        if any(
            not isinstance(name, str) or not name.strip()
            for name in self.required_checks
        ):
            raise ValueError("required check names must be non-empty strings")
        if len(set(self.required_checks)) != len(self.required_checks):
            raise ValueError("required_checks must not contain duplicates")
        supported = {"result_present", "tool_succeeded"}
        unknown = set(self.required_checks) - supported
        if unknown:
            raise ValueError(f"unsupported required checks: {', '.join(sorted(unknown))}")
