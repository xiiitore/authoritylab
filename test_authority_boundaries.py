"""Regression tests for execution authority and durable audit integrity."""

import tempfile
import unittest
from pathlib import Path

from authoritylab import (
    DurableAuditLog,
    ExecutionBlockedError,
    Task,
    ToolResult,
    WorkflowCore,
    WorkflowStatus,
)
from authoritylab.tools import ToolRegistry


class BlockingRunner:
    """Test backend that refuses execution before calling a handler."""

    def run(self, handler, task):
        raise ExecutionBlockedError("backend policy rejected task")


class AuthorityBoundaryTests(unittest.TestCase):
    def test_backend_block_is_not_reported_as_success_and_handler_does_not_run(self):
        calls = []
        registry = ToolRegistry()
        registry.register(
            "sensitive",
            lambda task: calls.append(task.task_id) or ToolResult(ok=True, output={"done": True}),
            trusted=True,
        )

        report = WorkflowCore(registry, execution_runner=BlockingRunner()).run(
            Task("blocked-1", "sensitive")
        )

        self.assertEqual(report.status, WorkflowStatus.BLOCKED)
        self.assertEqual(calls, [])
        self.assertEqual(report.audit["status"], "BLOCKED")
        self.assertIn("execution_backend", [check.name for check in report.checks])

    def test_audit_hash_chain_detects_record_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            log = DurableAuditLog(str(path))
            log.append({"outcome": "PASS", "task_id": "task-1"})
            self.assertTrue(log.verify())

            original = path.read_text(encoding="utf-8")
            self.assertIn('"outcome":"PASS"', original)
            path.write_text(original.replace('"outcome":"PASS"', '"outcome":"FAIL"'), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "audit chain invalid"):
                log.verify()

    def test_signed_audit_requires_the_correct_integrity_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "signed-audit.jsonl"
            writer = DurableAuditLog(str(path), integrity_key=b"a" * 32)
            writer.append({"outcome": "PASS"})
            self.assertTrue(writer.verify())

            wrong_key_reader = DurableAuditLog(str(path), integrity_key=b"b" * 32)
            with self.assertRaisesRegex(ValueError, "audit signature invalid"):
                wrong_key_reader.verify()


if __name__ == "__main__":
    unittest.main()
