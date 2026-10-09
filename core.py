"""Workflow Core: route tasks, execute one trusted handler, and verify evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .audit_log import DurableAuditLog
from .execution import ExecutionBlockedError, HandlerRunner, InProcessRunner
from .governance import GovernancePolicy
from .models import CheckResult, CheckStatus, Task, ToolResult, WorkflowReport, WorkflowStatus
from .tools import ToolRegistry
from .verification import ResultVerifier


class WorkflowCore:
    def __init__(
        self,
        registry: ToolRegistry,
        policy: GovernancePolicy | None = None,
        verifier: ResultVerifier | None = None,
        audit_log: DurableAuditLog | None = None,
        execution_runner: HandlerRunner | None = None,
    ) -> None:
        if audit_log is not None and not isinstance(audit_log, DurableAuditLog):
            raise TypeError("audit_log must be a DurableAuditLog or None")
        if execution_runner is not None and not callable(getattr(execution_runner, "run", None)):
            raise TypeError("execution_runner must provide a callable run method")
        self.registry = registry
        self.policy = policy or GovernancePolicy()
        self.verifier = verifier or ResultVerifier()
        self.audit_log = audit_log
        self.execution_runner = execution_runner if execution_runner is not None else InProcessRunner()

    def run(self, task: Task) -> WorkflowReport:
        handler = self.registry.resolve(task.kind)
        if handler is None:
            outcome = (
                "handler is registered but not allow-listed as trusted"
                if self.registry.is_registered(task.kind)
                else "no handler registered for task kind"
            )
            audit = self._audit(task, None, outcome, None, (), WorkflowStatus.BLOCKED)
            return self._finish(task, None, WorkflowStatus.BLOCKED, None, (), audit)

        try:
            result = self.execution_runner.run(handler, task)
            if not isinstance(result, ToolResult):
                result = ToolResult(
                    ok=False,
                    error="execution backend returned a non-ToolResult value",
                )
        except ExecutionBlockedError:
            result = ToolResult(ok=False, error="execution backend blocked")
            checks = (CheckResult(
                "execution_backend",
                CheckStatus.BLOCKED,
                "configured execution backend could not safely accept the task",
            ),)
            audit = self._audit(task, task.kind, "execution backend blocked", result, checks, WorkflowStatus.BLOCKED)
            return self._finish(task, task.kind, WorkflowStatus.BLOCKED, result, checks, audit)
        except Exception as exc:
            result = ToolResult(
                ok=False,
                error=f"handler raised {type(exc).__name__}",
            )

        checks, status = self.verifier.verify(result, self.policy, task.kind)
        outcome = "completed" if status == WorkflowStatus.PASS else "completed with non-pass status"
        audit = self._audit(task, task.kind, outcome, result, checks, status)
        return self._finish(task, task.kind, status, result, checks, audit)

    def _finish(
        self,
        task: Task,
        route: str | None,
        status: WorkflowStatus,
        result: ToolResult | None,
        checks: tuple[CheckResult, ...],
        audit: dict[str, Any],
    ) -> WorkflowReport:
        if self.audit_log is not None:
            try:
                metadata = self.audit_log.append(audit)
            except Exception:
                checks = checks + (CheckResult(
                    "audit_persisted",
                    CheckStatus.FAIL,
                    "durable audit append failed",
                ),)
                status = WorkflowStatus.BLOCKED
                audit["status"] = status.value
                audit["outcome"] = "audit persistence failed"
                audit["checks"] = [
                    {"name": check.name, "status": check.status.value}
                    for check in checks
                ]
                audit["audit_persistence"] = "failed"
            else:
                audit["audit_event_id"] = metadata["event_id"]
                audit["audit_event_hash"] = metadata["event_hash"]
                audit["audit_persistence"] = "persisted"
        return WorkflowReport(
            task_id=task.task_id,
            route=route,
            status=status,
            tool_result=result,
            checks=checks,
            audit=audit,
        )

    @staticmethod
    def _audit(
        task: Task,
        route: str | None,
        outcome: str,
        result: ToolResult | None,
        checks: tuple,
        status: WorkflowStatus,
    ) -> dict[str, Any]:
        """Return a useful audit summary without copying arbitrary payloads or secrets."""
        return {
            "task_id": task.task_id,
            "kind": task.kind,
            "route": route,
            "outcome": outcome,
            "status": status.value,
            "tool_ok": result.ok if result is not None else None,
            "error_type": (
                result.error.split(":", 1)[0]
                if result is not None and result.error
                else None
            ),
            "checks": [
                {"name": check.name, "status": check.status.value}
                for check in checks
            ],
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
