"""Acceptance policy: mandatory baseline checks are never optional."""

from __future__ import annotations

from dataclasses import dataclass


MANDATORY_CHECKS = ("result_present", "tool_succeeded")


@dataclass(frozen=True, slots=True)
class GovernancePolicy:
    # Kept explicit in configuration for auditability, but the baseline checks
    # cannot be removed or reordered into an unsafe partial acceptance policy.
    required_checks: tuple[str, ...] = MANDATORY_CHECKS

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
