"""Reproducible authority-boundary matrix; illustrative baseline, not a competitor benchmark.

Run after installing the project:
    python -m authoritylab.authority_boundary_matrix

The execution-only baseline is intentionally minimal: it accepts a non-null output
when a handler reports success. It is included to demonstrate which configured
governance checks that naive rule ignores; it is not a measurement of another
product or a claim of comparative superiority.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Callable

from authoritylab import (
    CheckStatus,
    DurableAuditLog,
    EvidenceSchema,
    GovernancePolicy,
    SemanticValidationResult,
    SemanticValidatorRegistry,
    Task,
    ToolResult,
    WorkflowCore,
    WorkflowStatus,
)
from authoritylab.tools import ToolRegistry


class FailingAuditLog(DurableAuditLog):
    """Deterministic fault injection for the audit-persistence boundary."""

    def append(self, event: Any) -> dict[str, str]:
        raise OSError("injected audit persistence failure")


def execute_case(case: dict[str, Any]) -> dict[str, Any]:
    calls = {"handler": 0}
    result = case.get("result", ToolResult(ok=True, output={"source_id": "source-1", "claim": "supported"}))
    registry = ToolRegistry()

    def handler(task: Task) -> ToolResult:
        calls["handler"] += 1
        return result

    registry.register("lookup", handler, trusted=case.get("trusted", True))

    schemas = ()
    if case.get("schema", True):
        fields = case.get("fields", ("source_id", "claim"))
        schemas = (EvidenceSchema("lookup", tuple(fields)),)
    policy = GovernancePolicy(evidence_schemas=schemas)

    validators = None
    if case.get("semantic_mode", False):
        validators = SemanticValidatorRegistry()
        validator_status = case.get("validator_status")
        if validator_status is not None:
            if validator_status == "RAISE":
                def validator(evidence: Any) -> SemanticValidationResult:
                    raise RuntimeError("injected validator failure")
            else:
                status = CheckStatus(validator_status)
                def validator(evidence: Any) -> SemanticValidationResult:
                    return SemanticValidationResult(status, "deterministic benchmark validator result")
            validators.register("lookup", validator)

    verifier = None
    if validators is not None:
        from authoritylab.verification import ResultVerifier
        verifier = ResultVerifier(semantic_validators=validators)

    with tempfile.TemporaryDirectory() as directory:
        audit_log = None
        if case.get("audit_failure", False):
            audit_log = FailingAuditLog(str(Path(directory) / "audit.jsonl"))
        core = WorkflowCore(
            registry,
            policy=policy,
            verifier=verifier,
            audit_log=audit_log,
        )
        report = core.run(Task(case["name"], "lookup"))

    naive_accept = bool(
        calls["handler"] > 0
        and result.ok
        and result.output is not None
    )
    expected = WorkflowStatus(case["expected"])
    observed = report.status
    false_accept = naive_accept and observed != WorkflowStatus.PASS

    return {
        "case": case["name"],
        "expected": expected.value,
        "observed": observed.value,
        "case_pass": observed == expected,
        "handler_calls": calls["handler"],
        "execution_only_baseline_accepts": naive_accept,
        "baseline_false_accept": false_accept,
        "check_results": {check.name: check.status.value for check in report.checks},
    }


def cases() -> list[dict[str, Any]]:
    good = ToolResult(ok=True, output={"source_id": "source-1", "claim": "supported"})
    return [
        {"name": "complete_structural_evidence", "expected": "PASS", "result": good},
        {"name": "schema_missing", "expected": "UNKNOWN", "schema": False, "result": good},
        {"name": "required_field_missing", "expected": "UNKNOWN",
         "result": ToolResult(ok=True, output={"source_id": "source-1"})},
        {"name": "handler_reports_failure", "expected": "FAIL",
         "result": ToolResult(ok=False, output={"source_id": "source-1", "claim": "supported"},
                              error="injected failure")},
        {"name": "semantic_validator_missing", "expected": "UNKNOWN",
         "semantic_mode": True, "result": good},
        {"name": "semantic_validator_rejects", "expected": "FAIL",
         "semantic_mode": True, "validator_status": "FAIL", "result": good},
        {"name": "semantic_validator_raises", "expected": "UNKNOWN",
         "semantic_mode": True, "validator_status": "RAISE", "result": good},
        {"name": "handler_not_trusted", "expected": "BLOCKED", "trusted": False, "result": good},
        {"name": "audit_persistence_fails", "expected": "BLOCKED",
         "audit_failure": True, "result": good},
    ]


def main() -> int:
    rows = [execute_case(case) for case in cases()]
    failures = [row for row in rows if not row["case_pass"]]
    false_accepts = [row["case"] for row in rows if row["baseline_false_accept"]]
    summary = {
        "benchmark": "authority-boundary-matrix-v1",
        "scope": "local deterministic regression matrix; not production certification",
        "baseline": "illustrative execution-only rule; not an external product comparison",
        "case_count": len(rows),
        "case_pass_count": len(rows) - len(failures),
        "case_fail_count": len(failures),
        "execution_only_baseline_false_accept_count": len(false_accepts),
        "execution_only_baseline_false_accept_cases": false_accepts,
        "cases": rows,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
