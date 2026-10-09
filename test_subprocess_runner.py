import time
import unittest

from authoritylab import (
    CheckStatus,
    EvidenceSchema,
    GovernancePolicy,
    Task,
    ToolResult,
    WorkflowCore,
    WorkflowStatus,
)
from authoritylab.execution import ExecutionBlockedError, SubprocessHandlerRunner
from authoritylab.tools import ToolRegistry


def echo_handler(task):
    return ToolResult(ok=True, output={"task_id": task.task_id, "kind": task.kind})


def raising_handler(task):
    raise RuntimeError("private secret must not be exposed")


def sleeping_handler(task):
    time.sleep(3)
    return ToolResult(ok=True, output={"done": True})


def non_json_handler(task):
    return ToolResult(ok=True, output={"not_json": object()})


def huge_output_handler(task):
    return ToolResult(ok=True, output={"large": "x" * 100_000})


class SubprocessHandlerRunnerTests(unittest.TestCase):
    def test_importable_handler_runs_in_child_process(self):
        runner = SubprocessHandlerRunner(timeout_seconds=4)
        result = runner.run(echo_handler, Task("sub-1", "echo", {"x": 1}))
        self.assertTrue(result.ok)
        self.assertEqual(result.output, {"task_id": "sub-1", "kind": "echo"})

    def test_handler_exception_is_sanitized(self):
        result = SubprocessHandlerRunner(timeout_seconds=4).run(
            raising_handler, Task("sub-2", "raises")
        )
        self.assertFalse(result.ok)
        self.assertIn("RuntimeError", result.error)
        self.assertNotIn("private secret", result.error)

    def test_timeout_terminates_child_process_group(self):
        result = SubprocessHandlerRunner(timeout_seconds=0.25).run(
            sleeping_handler, Task("sub-3", "sleep")
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "handler execution timed out")

    def test_non_json_output_fails_closed(self):
        result = SubprocessHandlerRunner(timeout_seconds=4).run(
            non_json_handler, Task("sub-4", "non-json")
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "handler raised TypeError")

    def test_oversized_output_fails_closed(self):
        result = SubprocessHandlerRunner(timeout_seconds=4, max_output_bytes=1024).run(
            huge_output_handler, Task("sub-large", "large")
        )
        self.assertFalse(result.ok)

    def test_lambda_is_rejected_before_execution(self):
        runner = SubprocessHandlerRunner()
        with self.assertRaises(ExecutionBlockedError):
            runner.run(lambda task: ToolResult(ok=True, output={"x": 1}), Task("sub-5", "lambda"))

    def test_non_json_input_is_blocked(self):
        runner = SubprocessHandlerRunner()
        with self.assertRaises(ExecutionBlockedError):
            runner.run(echo_handler, Task("sub-6", "echo", {"object": object()}))

    def test_invalid_resource_limits_are_rejected(self):
        with self.assertRaises(ValueError):
            SubprocessHandlerRunner(timeout_seconds=0)
        with self.assertRaises(ValueError):
            SubprocessHandlerRunner(memory_limit_bytes=True)
        with self.assertRaises(ValueError):
            SubprocessHandlerRunner(max_output_bytes=0)

    def test_workflow_core_marks_unsupported_handler_as_blocked(self):
        registry = ToolRegistry()
        registry.register("lambda", lambda task: ToolResult(ok=True, output={"x": 1}), trusted=True)
        policy = GovernancePolicy(evidence_schemas=(EvidenceSchema("lambda", ("x",)),))
        report = WorkflowCore(
            registry, policy=policy, execution_runner=SubprocessHandlerRunner()
        ).run(Task("sub-7", "lambda"))
        self.assertEqual(report.status, WorkflowStatus.BLOCKED)
        self.assertEqual(report.checks[0].status, CheckStatus.BLOCKED)

    def test_workflow_core_can_use_subprocess_runner(self):
        registry = ToolRegistry()
        registry.register("echo", echo_handler, trusted=True)
        policy = GovernancePolicy(evidence_schemas=(EvidenceSchema("echo", ("task_id", "kind")),))
        report = WorkflowCore(
            registry, policy=policy, execution_runner=SubprocessHandlerRunner(timeout_seconds=4)
        ).run(Task("sub-8", "echo"))
        self.assertEqual(report.status, WorkflowStatus.PASS)
        self.assertEqual(report.tool_result.output["task_id"], "sub-8")


if __name__ == "__main__":
    unittest.main()
