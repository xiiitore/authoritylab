"""Workflow Core: route tasks, execute one handler, and verify the evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .governance import GovernancePolicy
from .models import Task, ToolResult, WorkflowReport, WorkflowStatus
from .tools import ToolRegistry
from .verification import ResultVerifier


class WorkflowCore:
    def __init__(self, registry: ToolRegistry, policy: GovernancePolicy | None = None,
                 verifier: ResultVerifier | None = None) -> None:
        self.registry = registry
        self.policy = policy or GovernancePolicy()
        self.verifier = verifier or ResultVerifier()

    def run(self, task: Task) -> WorkflowReport:
        handler = self.registry.resolve(task.kind)
        if handler is None:
            return WorkflowReport(
                task_id=task.task_id, route=None, status=WorkflowStatus.BLOCKED,
                tool_result=None, checks=(),
                audit=self._audit(task, None, "no handler registered for task kind"),
            )

        try:
            result = handler(task)
            if not isinstance(result, ToolResult):
                result = ToolResult(ok=False, error="handler returned a non-ToolResult value")
        except Exception as exc:  # Convert handler exceptions into explicit failure evidence.
            result = ToolResult(ok=False, error=f"handler raised {type(exc).__name__}: {exc}")

        checks, status = self.verifier.verify(result, self.policy)
        return WorkflowReport(
            task_id=task.task_id, route=task.kind, status=status,
            tool_result=result, checks=checks,
            audit=self._audit(task, task.kind, "completed" if status == WorkflowStatus.PASS else "completed with non-pass status"),
        )

    @staticmethod
    def _audit(task: Task, route: str | None, outcome: str) -> dict[str, Any]:
        return {
            "task_id": task.task_id,
            "kind": task.kind,
            "route": route,
            "outcome": outcome,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
