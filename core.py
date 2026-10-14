"""Workflow Core: route tasks, execute one trusted handler, and verify evidence."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .audit_log import DurableAuditLog
from .authorization import AuthorizationDecision, AuthorizationRequest, Authorizer
from .execution import ExecutionBlockedError, HandlerRunner, InProcessRunner
from .governance import GovernancePolicy
from .models import CheckResult, CheckStatus, Task, ToolResult, WorkflowReport, WorkflowStatus
from .loop_guardrails import LoopDetector, ToolObservation
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
        loop_detector: LoopDetector | None = None,
        authorizer: Authorizer | None = None,
        legacy_mode: bool = False,
    ) -> None:
        if audit_log is not None and not isinstance(audit_log, DurableAuditLog):
            raise TypeError("audit_log must be a DurableAuditLog or None")
        if execution_runner is not None and not callable(getattr(execution_runner, "run", None)):
            raise TypeError("execution_runner must provide a callable run method")
        if loop_detector is not None and not isinstance(loop_detector, LoopDetector):
            raise TypeError("loop_detector must be a LoopDetector or None")
        if authorizer is not None and not callable(getattr(authorizer, "authorize", None)):
            raise TypeError("authorizer must provide a callable authorize method")
        if type(legacy_mode) is not bool:
            raise TypeError("legacy_mode must be a bool")
        self.registry = registry
        self.policy = policy or GovernancePolicy()
        self.verifier = verifier or ResultVerifier()
        self.audit_log = audit_log
        self.execution_runner = execution_runner if execution_runner is not None else InProcessRunner()
        self.loop_detector = loop_detector if loop_detector is not None else LoopDetector()
        self.authorizer = authorizer
        self.legacy_mode = legacy_mode
        self._loop_guard_blocked = False
        self._loop_guard_reason: str | None = None
        self._loop_event_counter = 0

    def reset_loop_guard(self, progress_observation: ToolObservation) -> None:
        """Clear a loop block only with a harness-sourced, observable progress event.

        The caller is responsible for grounding this event in an external milestone;
        a model-authored assertion alone is not sufficient evidence of progress.
        """
        if not isinstance(progress_observation, ToolObservation):
            raise TypeError("progress_observation must be a ToolObservation")
        if not progress_observation.progress or not progress_observation.event_id:
            raise ValueError("reset requires a progress=True observation with an event_id")
        self.loop_detector.observe(progress_observation)
        self._loop_guard_blocked = False
        self._loop_guard_reason = None

    def run(
        self, task: Task, *, authorization: AuthorizationRequest | None = None
    ) -> WorkflowReport:
        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        if not self.legacy_mode:
            try:
                task = Task(task.task_id, task.kind, deepcopy(dict(task.payload)))
            except Exception:
                raise ValueError("task payload could not be safely snapshotted") from None
        if self._loop_guard_blocked:
            result = ToolResult(ok=False, error="loop guard blocked execution pending observed progress")
            checks = (CheckResult(
                "loop_guard", CheckStatus.BLOCKED,
                self._loop_guard_reason or "execution remains blocked until observed progress is recorded",
            ),)
            audit = self._audit(task, None, "loop guard blocked execution before handler invocation", result, checks, WorkflowStatus.BLOCKED)
            return self._finish(task, None, WorkflowStatus.BLOCKED, result, checks, audit)
        handler = self.registry.resolve(task.kind)
        if handler is None:
            outcome = (
                "handler is registered but not allow-listed as trusted"
                if self.registry.is_registered(task.kind)
                else "no handler registered for task kind"
            )
            loop_check = self._observe_loop_guard(task, None, fallback_error=outcome, fallback_status="blocked")
            checks = (loop_check,)
            audit = self._audit(task, None, outcome, None, checks, WorkflowStatus.BLOCKED)
            return self._finish(task, None, WorkflowStatus.BLOCKED, None, checks, audit)

        authorization_check: CheckResult | None = None
        authorization_audit: dict[str, str] | None = None
        if not self.legacy_mode:
            authorization_check, authorization_audit = self._authorize_task(task, authorization)
            if authorization_check.status != CheckStatus.PASS:
                loop_check = self._observe_loop_guard(
                    task, None,
                    fallback_error=authorization_check.detail,
                    fallback_status="blocked",
                )
                checks = (authorization_check, loop_check)
                audit = self._audit(
                    task, None, "authorization denied or unavailable", None,
                    checks, WorkflowStatus.BLOCKED,
                )
                audit["authorization"] = authorization_audit or {
                    "status": "BLOCKED", "reason": "authorization unavailable"
                }
                return self._finish(
                    task, None, WorkflowStatus.BLOCKED, None, checks, audit
                )

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
            loop_check = self._observe_loop_guard(task, result)
            checks = ((authorization_check,) if authorization_check is not None else ()) + checks + (loop_check,)
            audit = self._audit(task, task.kind, "execution backend blocked", result, checks, WorkflowStatus.BLOCKED)
            if authorization_audit is not None:
                audit["authorization"] = authorization_audit
            return self._finish(task, task.kind, WorkflowStatus.BLOCKED, result, checks, audit)
        except Exception as exc:
            result = ToolResult(
                ok=False,
                error=f"handler raised {type(exc).__name__}",
            )

        checks, status = self.verifier.verify(result, self.policy, task.kind)
        loop_check = self._observe_loop_guard(task, result)
        checks = ((authorization_check,) if authorization_check is not None else ()) + checks + (loop_check,)
        if loop_check.status == CheckStatus.BLOCKED:
            status = WorkflowStatus.BLOCKED
        elif loop_check.status == CheckStatus.UNKNOWN and status == WorkflowStatus.PASS:
            status = WorkflowStatus.UNKNOWN
        outcome = "completed" if status == WorkflowStatus.PASS else "completed with non-pass status"
        audit = self._audit(task, task.kind, outcome, result, checks, status)
        if authorization_audit is not None:
            audit["authorization"] = authorization_audit
        return self._finish(task, task.kind, status, result, checks, audit)

    def _authorize_task(
        self, task: Task, request: AuthorizationRequest | None
    ) -> tuple[CheckResult, dict[str, str]]:
        def blocked(reason: str, decision_id: str | None = None) -> tuple[CheckResult, dict[str, str]]:
            detail = {"status": "BLOCKED", "reason": reason}
            if decision_id:
                detail["decision_id"] = decision_id
            return CheckResult("authorization", CheckStatus.BLOCKED, reason), detail

        if self.authorizer is None:
            return blocked("no authorizer configured; execution denied")
        if not isinstance(request, AuthorizationRequest):
            return blocked("a valid authorization request is required")
        if request.action != task.kind:
            return blocked("authorization action does not match task kind")
        if request.target_field not in task.payload or task.payload.get(request.target_field) != request.resource_id:
            return blocked("authorized resource does not match the task target")
        try:
            authorization_task = Task(task.task_id, task.kind, deepcopy(dict(task.payload)))
            decision = self.authorizer.authorize(authorization_task, request)
        except Exception as exc:
            return blocked(f"authorizer failed ({type(exc).__name__})")
        if not isinstance(decision, AuthorizationDecision):
            return blocked("authorizer returned an invalid decision")
        # Do not expose arbitrary policy-engine text: it may contain secrets or
        # personal data. Keep the public report reason controlled and predictable.
        safe_reason = (
            "explicit grant matched"
            if decision.allowed
            else "authorization denied by policy"
        )
        detail = {
            "status": "PASS" if decision.allowed else "BLOCKED",
            "decision_id": decision.decision_id,
            "reason": safe_reason,
        }
        if not decision.allowed:
            return CheckResult("authorization", CheckStatus.BLOCKED, safe_reason), detail
        if request.action != task.kind or task.payload.get(request.target_field) != request.resource_id:
            return blocked("authorized scope changed before execution", decision.decision_id)
        return CheckResult(
            "authorization", CheckStatus.PASS,
            "explicit authorization granted for the exact action and resource",
        ), detail

    def _observe_loop_guard(
        self,
        task: Task,
        result: ToolResult | None,
        *,
        fallback_error: str | None = None,
        fallback_status: str = "failed",
    ) -> CheckResult:
        """Record one task attempt, including blocked routing/backend outcomes."""
        self._loop_event_counter += 1
        try:
            observation = ToolObservation(
                tool_name=task.kind,
                arguments=dict(task.payload),
                result={
                    "ok": result.ok if result is not None else False,
                    "output": result.output if result is not None else None,
                    "error": result.error if result is not None else fallback_error,
                },
                status=(
                    ("success" if result.ok else "failed")
                    if result is not None
                    else fallback_status
                ),
                event_id=f"{task.task_id}:{self._loop_event_counter}",
            )
        except (TypeError, ValueError, OverflowError):
            return CheckResult(
                "loop_guard", CheckStatus.UNKNOWN,
                "task observation could not be fingerprinted as JSON-compatible data; loop detection is inconclusive",
            )
        findings = self.loop_detector.observe(observation)
        if findings:
            codes = ", ".join(finding.code for finding in findings)
            details = "; ".join(finding.message for finding in findings)
            self._loop_guard_blocked = True
            self._loop_guard_reason = f"{codes}: {details}"
            return CheckResult("loop_guard", CheckStatus.BLOCKED, self._loop_guard_reason)
        return CheckResult(
            "loop_guard", CheckStatus.PASS,
            "no configured loop pattern detected in the observed trace window",
        )

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
                {
                    "name": check.name,
                    "status": check.status.value,
                    **({"detail": check.detail} if check.name == "loop_guard" else {}),
                }
                for check in checks
            ],
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
