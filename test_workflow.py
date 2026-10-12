import unittest

from authoritylab import (
    EvidenceSchema,
    GovernancePolicy,
    Task,
    ToolResult,
    WorkflowCore,
    WorkflowStatus,
)
from authoritylab.tools import ToolRegistry
from authoritylab.verification import ResultVerifier
from authoritylab.loop_guardrails import LoopDetector, ToolObservation


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        self.policy = GovernancePolicy(
            evidence_schemas=(EvidenceSchema("echo", ("x",)),)
        )
        self.core = WorkflowCore(self.registry, policy=self.policy)

    def test_success_requires_present_output_success_flag_and_schema(self):
        self.registry.register("echo", lambda task: ToolResult(ok=True, output={"x": 1}), trusted=True)
        report = self.core.run(Task("t-1", "echo", {"x": 1}))
        self.assertEqual(report.status, WorkflowStatus.PASS)
        self.assertEqual([c.status.value for c in report.checks], ["PASS", "PASS", "PASS", "PASS"])
        self.assertEqual(report.audit["status"], "PASS")
        self.assertEqual(
            [item["name"] for item in report.audit["checks"]],
            ["result_present", "tool_succeeded", "task_evidence_valid", "loop_guard"],
        )
        self.assertNotIn("output", report.audit)

    def test_success_without_task_schema_is_unknown_not_pass(self):
        registry = ToolRegistry()
        registry.register("unconfigured", lambda task: ToolResult(ok=True, output={"truth": True}), trusted=True)
        report = WorkflowCore(registry).run(Task("t-schema-unknown", "unconfigured"))
        self.assertEqual(report.status, WorkflowStatus.UNKNOWN)
        evidence_check = next(c for c in report.checks if c.name == "task_evidence_valid")
        self.assertEqual(evidence_check.status.value, "UNKNOWN")

    def test_schema_missing_required_field_is_unknown(self):
        self.registry.register("echo", lambda task: ToolResult(ok=True, output={"other": 1}), trusted=True)
        report = self.core.run(Task("t-missing-evidence", "echo"))
        self.assertEqual(report.status, WorkflowStatus.UNKNOWN)

    def test_untrusted_handler_is_never_executed(self):
        calls = []
        self.registry.register("untrusted", lambda task: calls.append("ran") or ToolResult(ok=True, output={"x": 1}))
        report = self.core.run(Task("t-untrusted", "untrusted"))
        self.assertEqual(report.status, WorkflowStatus.BLOCKED)
        self.assertEqual(calls, [])
        self.assertIn("not allow-listed as trusted", report.audit["outcome"])

    def test_missing_handler_is_blocked(self):
        report = self.core.run(Task("t-2", "missing"))
        self.assertEqual(report.status, WorkflowStatus.BLOCKED)
        self.assertIsNone(report.route)
        self.assertEqual(report.audit["status"], "BLOCKED")

    def test_missing_output_fails(self):
        self.registry.register("empty", lambda task: ToolResult(ok=True, output=None), trusted=True)
        report = self.core.run(Task("t-3", "empty"))
        self.assertEqual(report.status, WorkflowStatus.FAIL)
        self.assertEqual(report.checks[0].status.value, "FAIL")

    def test_tool_failure_cannot_pass(self):
        self.registry.register("bad", lambda task: ToolResult(ok=False, output={"partial": True}, error="denied"), trusted=True)
        report = self.core.run(Task("t-4", "bad"))
        self.assertEqual(report.status, WorkflowStatus.FAIL)
        self.assertEqual(report.checks[1].detail, "denied")

    def test_handler_exception_is_recorded_without_exception_message(self):
        def explode(task):
            raise RuntimeError("secret-value-must-not-leak")
        self.registry.register("explode", explode, trusted=True)
        report = self.core.run(Task("t-5", "explode"))
        self.assertEqual(report.status, WorkflowStatus.FAIL)
        self.assertIn("RuntimeError", report.tool_result.error)
        self.assertNotIn("secret-value", report.tool_result.error)
        self.assertEqual(report.audit["error_type"], "handler raised RuntimeError")

    def test_malformed_handler_return_is_failure(self):
        self.registry.register("malformed", lambda task: {"ok": True}, trusted=True)
        report = self.core.run(Task("t-6", "malformed"))
        self.assertEqual(report.status, WorkflowStatus.FAIL)

    def test_duplicate_handler_rejected(self):
        self.registry.register("echo", lambda task: ToolResult(ok=True, output={"x": 1}), trusted=True)
        with self.assertRaises(ValueError):
            self.registry.register("echo", lambda task: ToolResult(ok=True, output={"x": 2}), trusted=True)

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
        self.assertIn("mandatory_policy_checks", [check.name for check in checks])

    def test_verifier_blocks_policy_missing_mandatory_check_if_validation_is_bypassed(self):
        policy = object.__new__(GovernancePolicy)
        object.__setattr__(policy, "required_checks", ("tool_succeeded",))
        checks, status = ResultVerifier().verify(
            ToolResult(ok=True, output=None), policy
        )
        self.assertEqual(status, WorkflowStatus.BLOCKED)
        self.assertIn("mandatory_policy_checks", [check.name for check in checks])
        self.assertIn("result_present", [check.name for check in checks])

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
        self.registry.register(" echo ", lambda task: ToolResult(ok=True, output={"x": 1}), trusted=True)
        with self.assertRaises(ValueError):
            self.registry.register("echo", lambda task: ToolResult(ok=True, output={"x": 2}), trusted=True)
        report = self.core.run(Task("t-8", "echo"))
        self.assertEqual(report.status, WorkflowStatus.PASS)

    def test_task_rejects_invalid_field_types(self):
        with self.assertRaises(TypeError):
            Task(None, "echo")
        with self.assertRaises(TypeError):
            Task("t-9", 123)
        with self.assertRaises(TypeError):
            Task("t-10", "echo", payload=None)

    def test_policy_cannot_disable_mandatory_baseline_checks(self):
        with self.assertRaisesRegex(ValueError, "mandatory checks cannot be disabled"):
            GovernancePolicy(required_checks=("tool_succeeded",))

    def test_duplicate_evidence_schemas_rejected(self):
        with self.assertRaises(ValueError):
            GovernancePolicy(evidence_schemas=(
                EvidenceSchema("echo", ("x",)),
                EvidenceSchema("echo", ("y",)),
            ))

    def test_empty_evidence_schema_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceSchema("echo", ())


    def test_loop_guard_blocks_after_repeated_identical_execution(self):
        calls = []
        registry = ToolRegistry()
        registry.register(
            "echo",
            lambda task: calls.append(dict(task.payload)) or ToolResult(ok=True, output={"x": "same"}),
            trusted=True,
        )
        core = WorkflowCore(
            registry,
            policy=GovernancePolicy(evidence_schemas=(EvidenceSchema("echo", ("x",)),)),
            loop_detector=LoopDetector(repeat_threshold=3),
        )

        first = core.run(Task("loop-1", "echo", {"input": "same"}))
        second = core.run(Task("loop-2", "echo", {"input": "same"}))
        third = core.run(Task("loop-3", "echo", {"input": "same"}))
        fourth = core.run(Task("loop-4", "echo", {"input": "same"}))

        self.assertEqual(first.status, WorkflowStatus.PASS)
        self.assertEqual(second.status, WorkflowStatus.PASS)
        self.assertEqual(third.status, WorkflowStatus.BLOCKED)
        self.assertEqual(fourth.status, WorkflowStatus.BLOCKED)
        self.assertEqual(len(calls), 3, "the latched guard must block the fourth handler call")
        self.assertIn("EXACT_REPEAT_NO_PROGRESS", third.audit["checks"][-1]["name"] + third.checks[-1].detail)
        self.assertIn("EXACT_REPEAT_NO_PROGRESS", third.audit["checks"][-1]["detail"])

    def test_loop_guard_requires_observed_progress_to_clear_latch(self):
        calls = []
        registry = ToolRegistry()
        registry.register(
            "echo",
            lambda task: calls.append(task.task_id) or ToolResult(ok=True, output={"x": "same"}),
            trusted=True,
        )
        core = WorkflowCore(
            registry,
            policy=GovernancePolicy(evidence_schemas=(EvidenceSchema("echo", ("x",)),)),
            loop_detector=LoopDetector(repeat_threshold=3),
        )
        for i in range(3):
            report = core.run(Task(f"before-{i}", "echo", {"input": "same"}))
        self.assertEqual(report.status, WorkflowStatus.BLOCKED)
        with self.assertRaises(ValueError):
            core.reset_loop_guard(ToolObservation("harness.progress", {}, {}, event_id="missing-progress-flag"))
        core.reset_loop_guard(ToolObservation(
            "harness.progress", {"milestone": "verified-change"}, {"verified": True},
            progress=True, event_id="progress-verified-1",
        ))
        after_reset = core.run(Task("after-reset-1", "echo", {"input": "same"}))
        self.assertEqual(after_reset.status, WorkflowStatus.PASS)
        self.assertEqual(len(calls), 4)

    def test_non_json_result_makes_loop_check_unknown_not_pass(self):
        registry = ToolRegistry()
        registry.register("odd", lambda task: ToolResult(ok=True, output=object()), trusted=True)
        core = WorkflowCore(registry)
        report = core.run(Task("non-json", "odd"))
        loop_check = next(check for check in report.checks if check.name == "loop_guard")
        self.assertEqual(loop_check.status.value, "UNKNOWN")
        self.assertEqual(report.status, WorkflowStatus.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
