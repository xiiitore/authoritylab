"""Workflow Core: route tasks, execute one handler, and verify evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .governance import GovernancePolicy
from .models import Task, ToolResult, WorkflowReport, WorkflowStatus
from .tools import ToolRegistry
from .verification import ResultVerifier


class WorkflowCore:
    def __init__(
        self,
        registry: ToolRegistry,
        policy: GovernancePolicy | None = None,
        verifier: ResultVerifier | None = None,
    ) -> None:
        self.registry = registry
        self.policy = policy or GovernancePolicy()
        self.verifier = verifier or ResultVerifier()

    def run(self, task: Task) -> WorkflowReport:
        handler = self.registry.resolve(task.kind)
        if handler is None:
            outcome = "no handler registered for task kind"
            return WorkflowReport(
                task_id=task.task_id,
                route=None,
                status=WorkflowStatus.BLOCKED,
                tool_result=None,
                checks=(),
                audit=self._audit(task, None, outcome, None, (), WorkflowStatus.BLOCKED),
            )

        try:
            result = handler(task)
            if not isinstance(result, ToolResult):
                result = ToolResult(
                    ok=False,
                    error="handler returned a non-ToolResult value",
                )
        except Exception as exc:
            # Do not turn a handler exception into a successful workflow.
            result = ToolResult(
                ok=False,
                error=f"handler raised {type(exc).__name__}",
            )

        checks, status = self.verifier.verify(result, self.policy, task.kind)
        outcome = "completed" if status == WorkflowStatus.PASS else "completed with non-pass status"
        return WorkflowReport(
            task_id=task.task_id,
            route=task.kind,
            status=status,
            tool_result=result,
            checks=checks,
            audit=self._audit(task, task.kind, outcome, result, checks, status),
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
