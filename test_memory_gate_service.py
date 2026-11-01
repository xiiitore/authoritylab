import json
import os
import tempfile
import unittest
from urllib.error import URLError

from authoritylab.idempotency import SQLiteIdempotencyStore
from authoritylab.memory_gate import MemoryGate, MemorySnapshot
from authoritylab.memory_gate_service import MemoryGateService
from authoritylab.openai_responses_client import OpenAIResponsesClient


class FakeResponse:
    status = 200

    def __init__(self, text="gated answer"):
        self._body = json.dumps({
            "object": "response", "status": "completed",
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": text}],
            }],
        }).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


class FakeOpener:
    def __init__(self, result=None):
        self.result = result or FakeResponse()
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeMemoryProvider:
    def __init__(self, snapshot=None, error=None):
        self.snapshot = snapshot
        self.error = error
        self.calls = []

    def retrieve(self, subject_id):
        self.calls.append(subject_id)
        if self.error:
            raise self.error
        return self.snapshot


class MemoryGateServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(
            self.temp.name, "state", "idempotency.sqlite3"
        )
        self.now = 1_800_000_000.0
        self.events = []
        self.gate = MemoryGate(
            b"memory-gate-signing-key-at-least-32-bytes",
            policy_version="test-v1", audit_sink=self.events.append,
            max_age_seconds=300, token_ttl_seconds=60,
            clock=lambda: self.now,
        )
        self.snapshot = MemorySnapshot(
            "subject-1", ("notion-memory-page",), "approved context",
            self.now - 1, "notion-version-1",
        )
        self.provider = FakeMemoryProvider(self.snapshot)
        self.opener = FakeOpener()
        self.model = OpenAIResponsesClient(
            "secret-api-key", "test-model", max_output_tokens=128,
            token_verifier=self.gate.verify_token, opener=self.opener,
        )
        self.store = SQLiteIdempotencyStore(
            self.path, lease_seconds=30, clock=lambda: self.now
        )
        self.client_token = "client-token-for-memory-gate-tests-0001"
        self.service = MemoryGateService(
            self.gate, self.provider, self.model, self.store,
            subject_id="subject-1", client_token=self.client_token,
        )
        self.key = "idempotency-key-for-test-0001"
        self.payload = {"input": "continue the project"}

    def tearDown(self):
        self.temp.cleanup()

    def call(self, key=None, payload=None, token=None):
        return self.service.handle_chat(
            self.client_token if token is None else token,
            self.key if key is None else key,
            self.payload if payload is None else payload,
        )

    def service_digest(self, payload):
        from authoritylab.memory_gate import GateRequest
        return GateRequest.digest_payload({
            "input": payload["input"],
            "max_output_tokens": payload.get("max_output_tokens"),
        })

    def test_success_retrieves_memory_and_invokes_model_once(self):
        status, body = self.call()
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "PASS")
        self.assertEqual(body["output_text"], "gated answer")
        self.assertEqual(self.provider.calls, ["subject-1"])
        self.assertEqual(len(self.opener.requests), 1)
        self.assertEqual(
            self.store.get(self.key, self.service_digest(self.payload)),
            "COMPLETED",
        )

    def test_duplicate_completed_request_is_not_sent_again(self):
        first = self.call()
        second = self.call()
        self.assertEqual(first[0], 200)
        self.assertEqual(second[0], 409)
        self.assertEqual(
            second[1]["reason"], "already_completed_result_not_retained"
        )
        self.assertNotIn("output_text", second[1])
        self.assertEqual(len(self.opener.requests), 1)

    def test_same_key_with_different_payload_conflicts(self):
        self.call()
        status, body = self.call(payload={"input": "different prompt"})
        self.assertEqual(status, 409)
        self.assertEqual(body["reason"], "idempotency_conflict")
        self.assertEqual(len(self.opener.requests), 1)

    def test_provider_failure_blocks_before_model(self):
        provider = FakeMemoryProvider(error=OSError("Notion unavailable"))
        service = MemoryGateService(
            self.gate, provider, self.model, self.store,
            subject_id="subject-1", client_token=self.client_token,
        )
        status, body = service.handle_chat(
            self.client_token, self.key, self.payload
        )
        self.assertEqual(status, 503)
        self.assertEqual(body["status"], "BLOCKED")
        self.assertEqual(body["reason"], "memory_unavailable")
        self.assertEqual(self.opener.requests, [])
        self.assertEqual(self.events[-1]["reason"], "memory_unavailable")

    def test_audit_failure_blocks_before_model(self):
        def broken_audit(event):
            raise OSError("audit storage unavailable")

        gate = MemoryGate(
            b"different-memory-gate-signing-key-32bytes",
            policy_version="test-v1", audit_sink=broken_audit,
            clock=lambda: self.now,
        )
        model = OpenAIResponsesClient(
            "secret-api-key", "test-model", max_output_tokens=128,
            token_verifier=gate.verify_token, opener=self.opener,
        )
        service = MemoryGateService(
            gate, self.provider, model, self.store,
            subject_id="subject-1", client_token=self.client_token,
        )
        status, body = service.handle_chat(
            self.client_token, self.key, self.payload
        )
        self.assertEqual(status, 503)
        self.assertEqual(body["reason"], "audit_unavailable")
        self.assertEqual(self.opener.requests, [])

    def test_unauthorized_request_does_not_retrieve_memory(self):
        status, body = self.call(token="wrong-token")
        self.assertEqual(status, 401)
        self.assertEqual(body["reason"], "unauthorized")
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.opener.requests, [])

    def test_invalid_fields_are_rejected_before_claim(self):
        status, body = self.call(payload={"input": "question", "tools": []})
        self.assertEqual(status, 400)
        self.assertEqual(body["reason"], "unsupported_fields")
        self.assertIsNone(
            self.store.get(self.key, self.service_digest(self.payload))
        )

    def test_invalid_unicode_is_rejected_before_claim(self):
        status, body = self.call(payload={"input": "\ud800"})
        self.assertEqual(status, 400)
        self.assertEqual(body["reason"], "invalid_unicode")
        self.assertEqual(self.opener.requests, [])

    def test_input_size_is_bounded(self):
        service = MemoryGateService(
            self.gate, self.provider, self.model, self.store,
            subject_id="subject-1", client_token=self.client_token,
            max_input_bytes=4,
        )
        status, body = service.handle_chat(
            self.client_token, self.key, {"input": "too long"}
        )
        self.assertEqual(status, 413)
        self.assertEqual(body["reason"], "input_too_large")
        self.assertEqual(self.opener.requests, [])

    def test_invalid_output_limit_is_rejected(self):
        status, body = self.call(
            payload={"input": "question", "max_output_tokens": 999}
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["reason"], "invalid_output_limit")
        self.assertEqual(self.opener.requests, [])

    def test_missing_idempotency_key_is_rejected(self):
        status, body = self.service.handle_chat(
            self.client_token, None, self.payload
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["reason"], "invalid_idempotency_key")

    def test_invalid_idempotency_key_is_rejected(self):
        status, body = self.call(key="short")
        self.assertEqual(status, 400)
        self.assertEqual(body["reason"], "invalid_idempotency_key")
        self.assertEqual(self.opener.requests, [])

    def test_ambiguous_model_outcome_is_persisted_and_not_retried(self):
        self.opener.result = URLError("connection reset")
        status, body = self.call()
        self.assertEqual(status, 202)
        self.assertEqual(body["status"], "UNKNOWN")
        self.assertEqual(body["reason"], "outcome_unknown_do_not_retry")
        second_status, second_body = self.call()
        self.assertEqual(second_status, 202)
        self.assertEqual(second_body["status"], "UNKNOWN")
        self.assertEqual(len(self.opener.requests), 1)

    def test_in_progress_claim_does_not_invoke_model(self):
        digest = self.service_digest(self.payload)
        self.store.claim(self.key, digest)
        status, body = self.call()
        self.assertEqual(status, 202)
        self.assertEqual(body["status"], "IN_PROGRESS")
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.opener.requests, [])


if __name__ == "__main__":
    unittest.main()
