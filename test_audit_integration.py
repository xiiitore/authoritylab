import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from authoritylab import DurableAuditLog, EvidenceSchema, GovernancePolicy, Task, ToolResult, WorkflowStatus
from authoritylab.core import WorkflowCore as _WorkflowCore
from authoritylab.tools import ToolRegistry


def WorkflowCore(*args, **kwargs):
    """Legacy-behavior adapter for regression tests; security tests use _WorkflowCore."""
    kwargs.setdefault("legacy_mode", True)
    return _WorkflowCore(*args, **kwargs)


class AuditIntegrationTests(unittest.TestCase):
    def test_workflow_persists_audit_event_and_returns_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            log = DurableAuditLog(str(Path(directory) / "audit.jsonl"))
            registry = ToolRegistry()
            registry.register("lookup", lambda task: ToolResult(ok=True, output={"source": "unit-test"}), trusted=True)
            policy = GovernancePolicy(evidence_schemas=(EvidenceSchema("lookup", ("source",)),))
            report = WorkflowCore(registry, policy=policy, audit_log=log).run(Task("audit-1", "lookup"))
            self.assertEqual(report.status, WorkflowStatus.PASS)
            self.assertEqual(report.audit["audit_persistence"], "persisted")
            self.assertTrue(report.audit["audit_event_id"])
            self.assertTrue(log.verify())

    def test_audit_write_failure_blocks_workflow_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            log = DurableAuditLog(str(Path(directory) / "audit.jsonl"))
            registry = ToolRegistry()
            registry.register("lookup", lambda task: ToolResult(ok=True, output={"source": "unit-test"}), trusted=True)
            policy = GovernancePolicy(evidence_schemas=(EvidenceSchema("lookup", ("source",)),))
            with patch.object(log, "append", side_effect=OSError("private path should not leak")):
                report = WorkflowCore(registry, policy=policy, audit_log=log).run(Task("audit-2", "lookup"))
            self.assertEqual(report.status, WorkflowStatus.BLOCKED)
            self.assertEqual(report.audit["audit_persistence"], "failed")
            self.assertIn("audit_persisted", [check.name for check in report.checks])
            self.assertNotIn("private path", str(report.audit))


if __name__ == "__main__":
    unittest.main()
