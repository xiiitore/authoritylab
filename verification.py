"""Evaluate execution results, structural evidence, and configured semantics."""

from __future__ import annotations

from collections.abc import Mapping

from .governance import MANDATORY_CHECKS, GovernancePolicy
from .models import CheckResult, CheckStatus, ToolResult, WorkflowStatus
from .semantic_validation import SemanticValidatorRegistry


class ResultVerifier:
    def __init__(
        self, semantic_validators: SemanticValidatorRegistry | None = None
    ) -> None:
        if semantic_validators is not None and not isinstance(
            semantic_validators, SemanticValidatorRegistry
        ):
            raise TypeError("semantic_validators must be a SemanticValidatorRegistry or None")
        self.semantic_validators = semantic_validators

    def verify(
        self,
        result: ToolResult,
        policy: GovernancePolicy,
        task_kind: str | None = None,
    ) -> tuple[tuple[CheckResult, ...], WorkflowStatus]:
        checks: list[CheckResult] = []
        configured = getattr(policy, "required_checks", ())
        if not isinstance(configured, tuple) or configured != MANDATORY_CHECKS:
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

        for name in MANDATORY_CHECKS:
            if name == "result_present":
                present = result.output is not None
                checks.append(CheckResult(
                    name,
                    CheckStatus.PASS if present else CheckStatus.FAIL,
                    "output is present" if present else "output is missing",
                ))
            elif name == "tool_succeeded":
                checks.append(CheckResult(
                    name,
                    CheckStatus.PASS if result.ok else CheckStatus.FAIL,
                    "tool reported success" if result.ok else (result.error or "tool reported failure"),
                ))

        schema_for = getattr(policy, "schema_for", None)
        schema = schema_for(task_kind) if callable(schema_for) else None
        structurally_valid = False
        if schema is None:
            checks.append(CheckResult(
                "task_evidence_valid",
                CheckStatus.UNKNOWN,
                "no task-specific evidence schema is configured",
            ))
        elif not isinstance(result.output, Mapping):
            checks.append(CheckResult(
                "task_evidence_valid",
                CheckStatus.UNKNOWN,
                "task output is not a mapping matching the required evidence contract",
            ))
        else:
            missing = [
                field for field in schema.required_fields
                if field not in result.output or result.output[field] is None
            ]
            if missing:
                checks.append(CheckResult(
                    "task_evidence_valid",
                    CheckStatus.UNKNOWN,
                    "required evidence fields are missing or empty",
                ))
            else:
                structurally_valid = True
                checks.append(CheckResult(
                    "task_evidence_valid",
                    CheckStatus.PASS,
                    "required evidence fields are present; factual truth is not established",
                ))

        # Supplying a registry enables semantic mode: every task must have an
        # explicit validator, and no validator runs before structural validation.
        if self.semantic_validators is not None:
            validator = self.semantic_validators.resolve(task_kind)
            if validator is None:
                checks.append(CheckResult(
                    "semantic_evidence_valid",
                    CheckStatus.UNKNOWN,
                    "no semantic validator is registered for this task kind",
                ))
            elif structurally_valid and isinstance(result.output, Mapping) and isinstance(task_kind, str):
                semantic = self.semantic_validators.validate(task_kind, result.output)
                checks.append(CheckResult(
                    "semantic_evidence_valid", semantic.status, semantic.detail
                ))
            else:
                checks.append(CheckResult(
                    "semantic_evidence_valid",
                    CheckStatus.UNKNOWN,
                    "semantic validation skipped because structural evidence is incomplete",
                ))

        if any(check.status == CheckStatus.BLOCKED for check in checks):
            status = WorkflowStatus.BLOCKED
        elif any(check.status == CheckStatus.FAIL for check in checks):
            status = WorkflowStatus.FAIL
        elif any(check.status == CheckStatus.UNKNOWN for check in checks):
            status = WorkflowStatus.UNKNOWN
        else:
            status = WorkflowStatus.PASS
        return tuple(checks), status
