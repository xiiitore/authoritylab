import unittest

from authoritylab.loop_guardrails import LoopDetector, ToolObservation, audit_execution_claim


class LoopDetectorTests(unittest.TestCase):
    def test_exact_repeat_requires_same_call_and_same_outcome(self):
        detector = LoopDetector()
        findings = ()
        for i in range(3):
            findings = detector.observe(ToolObservation("search", {"q": "x"}, {"hits": []}, event_id=str(i)))
        self.assertIn("EXACT_REPEAT_NO_PROGRESS", {f.code for f in findings})

    def test_changed_result_does_not_trigger_exact_repeat(self):
        detector = LoopDetector()
        for i in range(3):
            findings = detector.observe(ToolObservation("poll", {"job": 1}, {"state": i}, event_id=str(i)))
        self.assertNotIn("EXACT_REPEAT_NO_PROGRESS", {f.code for f in findings})

    def test_observed_progress_resets_streak(self):
        detector = LoopDetector()
        detector.observe(ToolObservation("search", {"q": "x"}, {"hits": []}))
        detector.observe(ToolObservation("search", {"q": "x"}, {"hits": []}))
        findings = detector.observe(ToolObservation("search", {"q": "x"}, {"hits": []}, progress=True))
        self.assertNotIn("EXACT_REPEAT_NO_PROGRESS", {f.code for f in findings})

    def test_two_tool_oscillation_is_detected(self):
        detector = LoopDetector()
        findings = ()
        for i, name in enumerate(["search", "read"] * 3):
            findings = detector.observe(ToolObservation(name, {}, {"ok": True}, event_id=str(i)))
        self.assertIn("OSCILLATION_NO_PROGRESS", {f.code for f in findings})

    def test_failure_cascade_detected_across_different_tools(self):
        detector = LoopDetector()
        findings = ()
        for i, name in enumerate(["search", "read", "parse", "verify"]):
            findings = detector.observe(ToolObservation(name, {}, {"error": "x"}, status="failed", event_id=str(i)))
        self.assertIn("CONSECUTIVE_FAILURE_CASCADE", {f.code for f in findings})

    def test_loop_finding_is_emitted_once_per_streak(self):
        detector = LoopDetector()
        for _ in range(3):
            findings = detector.observe(ToolObservation("search", {"q": "x"}, {"hits": []}))
        self.assertIn("EXACT_REPEAT_NO_PROGRESS", {f.code for f in findings})
        findings = detector.observe(ToolObservation("search", {"q": "x"}, {"hits": []}))
        self.assertNotIn("EXACT_REPEAT_NO_PROGRESS", {f.code for f in findings})

    def test_progress_marker_does_not_count_as_a_stalled_call(self):
        detector = LoopDetector()
        for _ in range(2):
            detector.observe(ToolObservation("search", {"q": "x"}, {"hits": []}))
        detector.observe(ToolObservation("search", {"q": "x"}, {"hits": []}, progress=True))
        for _ in range(2):
            findings = detector.observe(ToolObservation("search", {"q": "x"}, {"hits": []}))
        self.assertNotIn("EXACT_REPEAT_NO_PROGRESS", {f.code for f in findings})
        findings = detector.observe(ToolObservation("search", {"q": "x"}, {"hits": []}))
        self.assertIn("EXACT_REPEAT_NO_PROGRESS", {f.code for f in findings})

    def test_non_json_arguments_are_rejected_at_ingestion(self):
        with self.assertRaises(TypeError):
            ToolObservation("tool", object())

    def test_execution_claim_requires_observed_success(self):
        result = audit_execution_claim(
            tool_name="pytest",
            claimed_success=True,
            observations=[ToolObservation("pytest", {}, {"exit_code": 1}, status="failed", event_id="t1")],
            trace_complete=True,
        )
        self.assertEqual(result.status, "CONTRADICTED")

    def test_missing_claim_evidence_is_unknown_when_trace_incomplete(self):
        result = audit_execution_claim(
            tool_name="pytest", claimed_success=True, observations=[], trace_complete=False
        )
        self.assertEqual(result.status, "UNKNOWN")

    def test_success_observation_does_not_claim_semantic_correctness(self):
        result = audit_execution_claim(
            tool_name="pytest",
            claimed_success=True,
            observations=[ToolObservation("pytest", {}, {"exit_code": 0}, status="success", event_id="t1")],
            trace_complete=True,
        )
        self.assertEqual(result.status, "SUPPORTED")
        self.assertIn("semantic correctness remains unverified", result.reason)


if __name__ == "__main__":
    unittest.main()
