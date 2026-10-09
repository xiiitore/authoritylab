"""Evaluate tool evidence against mandatory baseline checks and policy."""

from __future__ import annotations

from .governance import MANDATORY_CHECKS, GovernancePolicy
from .models import CheckResult, CheckStatus, ToolResult, WorkflowStatus


class ResultVerifier:
    def verify(self, result: ToolResult, policy: GovernancePolicy) -> tuple[tuple[CheckResult, ...], WorkflowStatus]:
        checks: list[CheckResult] = []
        configured = getattr(policy, "required_checks", ())
        if not isinstance(configured, tuple) or not set(MANDATORY_CHECKS).issubset(configured):
            checks.append(CheckResult(
                "mandatory_policy_checks",
                CheckStatus.BLOCKED,
                "mandatory acceptance checks are missing or malformed",
            ))
        if not configured:
            checks.append(CheckResult(
                "policy_nonempty",
                CheckStatus.BLOCKED,
                "no required checks are configured",
            ))
        # Evaluate each supported check only once, in canonical order. The policy
        # validator prevents unsafe subsets; this verifier repeats the invariant
        # so bypassing dataclass validation cannot turn an incomplete result into PASS.
        for name in MANDATORY_CHECKS:
            if name == "result_present":
                present = result.output is not None
                checks.append(CheckResult(name, CheckStatus.PASS if present else CheckStatus.FAIL,
                                          "output is present" if present else "output is missing"))
            elif name == "tool_succeeded":
                checks.append(CheckResult(name, CheckStatus.PASS if result.ok else CheckStatus.FAIL,
                                          "tool reported success" if result.ok else (result.error or "tool reported failure")))

        if any(check.status == CheckStatus.BLOCKED for check in checks):
            status = WorkflowStatus.BLOCKED
        elif any(check.status == CheckStatus.FAIL for check in checks):
            status = WorkflowStatus.FAIL
        elif any(check.status == CheckStatus.UNKNOWN for check in checks):
            status = WorkflowStatus.UNKNOWN
        else:
            status = WorkflowStatus.PASS
        return tuple(checks), status
