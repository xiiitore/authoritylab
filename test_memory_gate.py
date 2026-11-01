import base64
import hashlib
import unittest

from authoritylab.memory_gate import (
    GateRequest,
    InvocationOutcomeUnknown,
    MemoryGate,
    MemorySnapshot,
)


class MemoryGateTests(unittest.TestCase):
    KEY = b"memory-gate-test-signing-key-at-least-32-bytes"

    def setUp(self):
        self.now = 1_800_000_000.0
        self.events = []
        self.gate = MemoryGate(
            self.KEY, policy_version="policy-v1",
            audit_sink=self.events.append,
            max_age_seconds=300, token_ttl_seconds=60,
            max_context_bytes=1024, clock=lambda: self.now,
        )
        self.request = GateRequest(
            "req-1", "user-1",
            GateRequest.digest_payload({"input": "hello", "model": "test"}),
        )
        self.snapshot = MemorySnapshot(
            "user-1", ("notion-page-1",), "approved memory context",
            self.now - 5, "notion-version-7",
        )

    def test_valid_context_issues_bound_token(self):
        decision = self.gate.authorize(self.request, self.snapshot)
        self.assertEqual(decision.status, "PASS")
        self.assertTrue(self.gate.verify_token(decision.token, self.request))

    def test_explicit_block_records_machine_reason(self):
        decision = self.gate.block(
            self.request, self.snapshot, "provider_configuration_invalid"
        )
        self.assertEqual(decision.status, "BLOCKED")
        self.assertEqual(
            self.events[-1]["reason"], "provider_configuration_invalid"
        )

    def test_explicit_block_rejects_unbounded_reason(self):
        with self.assertRaises(ValueError):
            self.gate.block(self.request, self.snapshot, "invalid reason")

    def test_missing_memory_blocks(self):
        decision = self.gate.authorize(self.request, None)
        self.assertEqual(decision.reason, "memory_unavailable")

    def test_wrong_subject_blocks(self):
        snapshot = MemorySnapshot(
            "user-2", ("page-1",), "context", self.now, "v1"
        )
        self.assertEqual(
            self.gate.authorize(self.request, snapshot).reason,
            "memory_scope_mismatch",
        )

    def test_stale_memory_blocks(self):
        snapshot = MemorySnapshot(
            "user-1", ("page-1",), "context", self.now - 301, "v1"
        )
        self.assertEqual(
            self.gate.authorize(self.request, snapshot).reason, "memory_stale"
        )

    def test_future_memory_blocks(self):
        snapshot = MemorySnapshot(
            "user-1", ("page-1",), "context", self.now + 31, "v1"
        )
        self.assertEqual(
            self.gate.authorize(self.request, snapshot).reason,
            "memory_timestamp_in_future",
        )

    def test_oversized_memory_blocks(self):
        snapshot = MemorySnapshot(
            "user-1", ("page-1",), "x" * 1025, self.now, "v1"
        )
        self.assertEqual(
            self.gate.authorize(self.request, snapshot).reason,
            "memory_context_too_large",
        )

    def test_request_substitution_invalidates_token(self):
        decision = self.gate.authorize(self.request, self.snapshot)
        other = GateRequest(
            "req-1", "user-1", hashlib.sha256(b"other").hexdigest()
        )
        self.assertFalse(self.gate.verify_token(decision.token, other))

    def test_token_tampering_is_rejected(self):
        decision = self.gate.authorize(self.request, self.snapshot)
        body, signature = decision.token.split(".", 1)
        first = "A" if signature[0] != "A" else "B"
        tampered = body + "." + first + signature[1:]
        self.assertFalse(self.gate.verify_token(tampered, self.request))

    def test_expired_token_is_rejected(self):
        decision = self.gate.authorize(self.request, self.snapshot)
        self.now += 61
        self.assertFalse(self.gate.verify_token(decision.token, self.request))

    def test_policy_change_invalidates_token(self):
        decision = self.gate.authorize(self.request, self.snapshot)
        other = MemoryGate(
            self.KEY, policy_version="policy-v2",
            audit_sink=lambda event: None,
            clock=lambda: self.now,
        )
        self.assertFalse(other.verify_token(decision.token, self.request))

    def test_token_does_not_expose_subject_or_source_ids(self):
        decision = self.gate.authorize(self.request, self.snapshot)
        encoded = decision.token.split(".", 1)[0]
        payload = base64.urlsafe_b64decode(
            encoded + "=" * (-len(encoded) % 4)
        )
        self.assertNotIn(self.request.subject_id.encode(), payload)
        self.assertNotIn(self.snapshot.source_ids[0].encode(), payload)

    def test_audit_failure_blocks_before_model(self):
        calls = []

        def broken_audit(event):
            raise OSError("audit unavailable")

        gate = MemoryGate(
            self.KEY, policy_version="v1", audit_sink=broken_audit,
            clock=lambda: self.now,
        )
        result = gate.execute(
            self.request, self.snapshot, lambda *args: calls.append(args)
        )
        self.assertEqual(result.decision.reason, "audit_unavailable")
        self.assertEqual(calls, [])

    def test_false_audit_result_blocks_before_model(self):
        calls = []
        gate = MemoryGate(
            self.KEY, policy_version="v1", audit_sink=lambda event: False,
            clock=lambda: self.now,
        )
        result = gate.execute(
            self.request, self.snapshot, lambda *args: calls.append(args)
        )
        self.assertEqual(result.decision.reason, "audit_unavailable")
        self.assertEqual(calls, [])

    def test_missing_memory_never_invokes_model(self):
        calls = []
        result = self.gate.execute(
            self.request, None, lambda *args: calls.append(args)
        )
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(calls, [])

    def test_valid_memory_invokes_model_once(self):
        calls = []

        def model(request, context, token):
            calls.append((request, context, token))
            return "result"

        result = self.gate.execute(self.request, self.snapshot, model)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.result, "result")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], self.snapshot.content)

    def test_model_error_is_recorded(self):
        def broken_model(*args):
            raise RuntimeError("provider unavailable")

        result = self.gate.execute(self.request, self.snapshot, broken_model)
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(self.events[-1]["reason"], "model_invocation_failed")

    def test_uncertain_provider_outcome_is_unknown_not_fail(self):
        def unknown_model(*args):
            raise InvocationOutcomeUnknown("response may have been created")

        result = self.gate.execute(self.request, self.snapshot, unknown_model)
        self.assertEqual(result.status, "UNKNOWN")
        self.assertEqual(
            self.events[-1]["reason"], "model_invocation_outcome_unknown"
        )

    def test_post_call_audit_failure_is_unknown_not_pass(self):
        count = {"value": 0}
        calls = []

        def audit(event):
            count["value"] += 1
            if count["value"] == 2:
                raise OSError("audit failure")
            self.events.append(event)

        def model(*args):
            calls.append(args)
            return "result"

        gate = MemoryGate(
            self.KEY, policy_version="v1", audit_sink=audit,
            clock=lambda: self.now,
        )
        result = gate.execute(self.request, self.snapshot, model)
        self.assertEqual(result.status, "UNKNOWN")
        self.assertEqual(len(calls), 1)

    def test_audit_omits_raw_memory_and_subject(self):
        self.gate.authorize(self.request, self.snapshot)
        event = str(self.events[-1])
        self.assertNotIn(self.snapshot.content, event)
        self.assertNotIn(self.request.subject_id, event)

    def test_request_digest_is_deterministic(self):
        left = GateRequest.digest_payload({"a": 1, "b": "x"})
        right = GateRequest.digest_payload({"b": "x", "a": 1})
        self.assertEqual(left, right)

    def test_clock_failure_blocks_and_audits(self):
        def broken_clock():
            raise OSError("clock unavailable")

        gate = MemoryGate(
            self.KEY, policy_version="v1", audit_sink=self.events.append,
            clock=broken_clock,
        )
        decision = gate.authorize(self.request, self.snapshot)
        self.assertEqual(decision.reason, "clock_unavailable")
        self.assertEqual(self.events[-1]["status"], "BLOCKED")

    def test_weak_key_rejected(self):
        with self.assertRaises(ValueError):
            MemoryGate(
                b"short", policy_version="v1",
                audit_sink=self.events.append,
            )


if __name__ == "__main__":
    unittest.main()
