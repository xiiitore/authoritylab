import unittest

from authoritylab import GovernancePolicy, Task, ToolResult, WorkflowCore, WorkflowStatus
from authoritylab.tools import ToolRegistry
from authoritylab.verification import ResultVerifier


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        self.core = WorkflowCore(self.registry)

    def test_success_requires_present_output_and_success_flag(self):
        self.registry.register("echo", lambda task: ToolResult(ok=True, output={"x": 1}))
        report = self.core.run(Task("t-1", "echo", {"x": 1}))
        self.assertEqual(report.status, WorkflowStatus.PASS)
        self.assertEqual([c.status.value for c in report.checks], ["PASS", "PASS"])
        self.assertEqual(report.audit["status"], "PASS")
        self.assertEqual([item["name"] for item in report.audit["checks"]],
                         ["result_present", "tool_succeeded"])
        self.assertNotIn("output", report.audit)

    def test_missing_handler_is_blocked(self):
        report = self.core.run(Task("t-2", "missing"))
        self.assertEqual(report.status, WorkflowStatus.BLOCKED)
        self.assertIsNone(report.route)
        self.assertEqual(report.audit["status"], "BLOCKED")

    def test_missing_output_fails(self):
        self.registry.register("empty", lambda task: ToolResult(ok=True, output=None))
        report = self.core.run(Task("t-3", "empty"))
        self.assertEqual(report.status, WorkflowStatus.FAIL)
        self.assertEqual(report.checks[0].status.value, "FAIL")

    def test_tool_failure_cannot_pass(self):
        self.registry.register("bad", lambda task: ToolResult(ok=False, output={"partial": True}, error="denied"))
        report = self.core.run(Task("t-4", "bad"))
        self.assertEqual(report.status, WorkflowStatus.FAIL)
        self.assertEqual(report.checks[1].detail, "denied")

    def test_handler_exception_is_recorded_without_exception_message(self):
        def explode(task):
            raise RuntimeError("secret-value-must-not-leak")
        self.registry.register("explode", explode)
        report = self.core.run(Task("t-5", "explode"))
        self.assertEqual(report.status, WorkflowStatus.FAIL)
        self.assertIn("RuntimeError", report.tool_result.error)
        self.assertNotIn("secret-value", report.tool_result.error)
        self.assertEqual(report.audit["error_type"], "handler raised RuntimeError")

    def test_malformed_handler_return_is_failure(self):
        self.registry.register("malformed", lambda task: {"ok": True})
        report = self.core.run(Task("t-6", "malformed"))
        self.assertEqual(report.status, WorkflowStatus.FAIL)

    def test_duplicate_handler_rejected(self):
        self.registry.register("echo", lambda task: ToolResult(ok=True, output="x"))
        with self.assertRaises(ValueError):
            self.registry.register("echo", lambda task: ToolResult(ok=True, output="y"))

    def test_invalid_task_rejected(self):
        with self.assertRaises(ValueError):
            Task(" ", "echo")

    def test_unknown_policy_check_rejected(self):
        with self.assertRaises(ValueError):
            GovernancePolicy(required_checks=("imaginary_check",))

    def test_verifier_blocks_empty_policy_if_validation_is_bypassed(self):
        policy = object.__new__(GovernancePolicy)
        object.__setattr__(policy, "required_checks", ())
        checks, status = ResultVerifier().verify(
            ToolResult(ok=True, output={"x": 1}), policy
        )
        self.assertEqual(status, WorkflowStatus.BLOCKED)
        self.assertEqual(len(checks), 1)

    def test_empty_policy_rejected(self):
        with self.assertRaises(ValueError):
            GovernancePolicy(required_checks=())

    def test_non_tuple_policy_rejected(self):
        with self.assertRaises(TypeError):
            GovernancePolicy(required_checks=["tool_succeeded"])

    def test_tool_result_requires_actual_boolean(self):
        with self.assertRaises(TypeError):
            ToolResult(ok="yes", output={"x": 1})

    def test_tool_result_error_must_be_string_or_none(self):
        with self.assertRaises(TypeError):
            ToolResult(ok=False, error=123)

    def test_non_callable_handler_rejected_at_registration(self):
        with self.assertRaises(TypeError):
            self.registry.register("bad-handler", None)

    def test_handler_names_are_normalized(self):
        self.registry.register(" echo ", lambda task: ToolResult(ok=True, output="x"))
        with self.assertRaises(ValueError):
            self.registry.register("echo", lambda task: ToolResult(ok=True, output="y"))
        report = self.core.run(Task("t-8", "echo"))
        self.assertEqual(report.status, WorkflowStatus.PASS)

    def test_task_rejects_invalid_field_types(self):
        with self.assertRaises(TypeError):
            Task(None, "echo")
        with self.assertRaises(TypeError):
            Task("t-9", 123)
        with self.assertRaises(TypeError):
            Task("t-10", "echo", payload=None)

    def test_policy_can_require_only_selected_checks(self):
        registry = ToolRegistry()
        registry.register("custom", lambda task: ToolResult(ok=True, output=None))
        core = WorkflowCore(registry, GovernancePolicy(required_checks=("tool_succeeded",)))
        report = core.run(Task("t-7", "custom"))
        self.assertEqual(report.status, WorkflowStatus.PASS)


if __name__ == "__main__":
    unittest.main()
