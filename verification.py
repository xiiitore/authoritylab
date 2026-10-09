"""Evaluate tool evidence against an explicit acceptance policy."""

from __future__ import annotations

from .governance import GovernancePolicy
from .models import CheckResult, CheckStatus, ToolResult, WorkflowStatus


class ResultVerifier:
    def verify(self, result: ToolResult, policy: GovernancePolicy) -> tuple[tuple[CheckResult, ...], WorkflowStatus]:
        checks: list[CheckResult] = []
        for name in policy.required_checks:
            if name == "result_present":
                present = result.output is not None
                checks.append(CheckResult(name, CheckStatus.PASS if present else CheckStatus.FAIL,
                                          "output is present" if present else "output is missing"))
            elif name == "tool_succeeded":
                checks.append(CheckResult(name, CheckStatus.PASS if result.ok else CheckStatus.FAIL,
                                          "tool reported success" if result.ok else (result.error or "tool reported failure")))
            else:  # Guard against a policy implementation bypassing validation.
                checks.append(CheckResult(name, CheckStatus.BLOCKED, "check is not implemented"))

        if any(check.status == CheckStatus.BLOCKED for check in checks):
            status = WorkflowStatus.BLOCKED
        elif any(check.status == CheckStatus.FAIL for check in checks):
            status = WorkflowStatus.FAIL
        elif any(check.status == CheckStatus.UNKNOWN for check in checks):
            status = WorkflowStatus.UNKNOWN
        else:
            status = WorkflowStatus.PASS
        return tuple(checks), status
