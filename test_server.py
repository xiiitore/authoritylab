import base64
import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from authoritylab.idempotency import SQLiteIdempotencyStore
from authoritylab.memory_gate import MemoryGate, MemorySnapshot
from authoritylab.memory_gate_service import MemoryGateService
from authoritylab.openai_responses_client import OpenAIResponsesClient
from authoritylab.server import build_service_from_env, make_handler


class FakeResponse:
    status = 200

    def __init__(self):
        self.body = json.dumps({
            "object": "response", "status": "completed",
            "output": [{
                "type": "message",
                "content": [{
                    "type": "output_text", "text": "server answer"
                }],
            }],
        }).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class FakeOpener:
    def __init__(self):
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        return FakeResponse()


class FakeProvider:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def retrieve(self, subject_id):
        return self.snapshot


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = 1_800_000_000.0
        self.events = []
        self.gate = MemoryGate(
            b"server-test-memory-gate-signing-key-32bytes",
            policy_version="test-v1", audit_sink=self.events.append,
            clock=lambda: self.now,
        )
        snapshot = MemorySnapshot(
            "subject-server", ("page-1",), "server memory",
            self.now - 1, "v1",
        )
        self.provider = FakeProvider(snapshot)
        self.opener = FakeOpener()
        self.model = OpenAIResponsesClient(
            "api-key", "test-model", max_output_tokens=128,
            token_verifier=self.gate.verify_token, opener=self.opener,
        )
        store = SQLiteIdempotencyStore(
            os.path.join(self.temp.name, "state", "idem.sqlite3"),
            clock=lambda: self.now,
        )
        self.token = "server-client-token-that-is-at-least-32-chars"
        service = MemoryGateService(
            self.gate, self.provider, self.model, store,
            subject_id="subject-server", client_token=self.token,
        )
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(service, max_request_bytes=1024),
        )
        self.server.daemon_threads = True
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.port, timeout=3
        )
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, json.loads(data.decode("utf-8"))

    def test_startup_configuration_builds_without_network_calls(self):
        signing = base64.urlsafe_b64encode(b"s" * 32).decode().rstrip("=")
        audit = base64.urlsafe_b64encode(b"a" * 32).decode().rstrip("=")
        env = {
            "MEMORY_GATE_SIGNING_KEY_B64": signing,
            "MEMORY_GATE_AUDIT_HMAC_KEY_B64": audit,
            "MEMORY_GATE_CLIENT_TOKEN": "client-token-" + "x" * 32,
            "MEMORY_GATE_SUBJECT_ID": "subject-startup",
            "MEMORY_GATE_AUDIT_PATH": os.path.join(
                self.temp.name, "audit", "audit.jsonl"
            ),
            "MEMORY_GATE_IDEMPOTENCY_PATH": os.path.join(
                self.temp.name, "state", "idempotency.sqlite3"
            ),
            "NOTION_API_KEY": "notion-test-token",
            "OPENAI_API_KEY": "openai-test-token",
            "OPENAI_MODEL": "test-model",
        }
        with patch.dict("os.environ", env, clear=True):
            service, max_request_bytes = build_service_from_env()
        self.assertEqual(service.subject_id, "subject-startup")
        self.assertEqual(max_request_bytes, 65_536)
        self.assertTrue(os.path.exists(env["MEMORY_GATE_IDEMPOTENCY_PATH"]))

    def test_startup_rejects_reused_signing_and_audit_keys(self):
        key = base64.urlsafe_b64encode(
            b"same-key-material-32-bytes-long!!"
        ).decode().rstrip("=")
        env = {
            "MEMORY_GATE_SIGNING_KEY_B64": key,
            "MEMORY_GATE_AUDIT_HMAC_KEY_B64": key,
        }
        with patch.dict("os.environ", env, clear=True):
            with self.assertRaises(ValueError):
                build_service_from_env()

    def test_health_endpoint(self):
        status, body = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "alive"})

    def test_chat_endpoint_runs_gated_flow(self):
        body = json.dumps({"input": "question"})
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
            "Idempotency-Key": "server-test-idempotency-key-0001",
        }
        status, result = self.request("POST", "/v1/chat", body, headers)
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["output_text"], "server answer")
        self.assertEqual(len(self.opener.requests), 1)

    def test_wrong_content_type_is_rejected(self):
        status, body = self.request(
            "POST", "/v1/chat", "{}", {"Content-Type": "text/plain"}
        )
        self.assertEqual(status, 415)
        self.assertEqual(body["reason"], "json_required")

    def test_invalid_json_is_rejected(self):
        status, body = self.request(
            "POST", "/v1/chat", "{", {"Content-Type": "application/json"}
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["reason"], "invalid_json")

    def test_request_size_is_bounded(self):
        status, body = self.request(
            "POST", "/v1/chat", "x" * 2048,
            {"Content-Type": "application/json"},
        )
        self.assertEqual(status, 413)
        self.assertEqual(body["reason"], "request_too_large")

    def test_unknown_route_is_not_exposed(self):
        status, body = self.request("GET", "/admin")
        self.assertEqual(status, 404)
        self.assertEqual(body["reason"], "not_found")


if __name__ == "__main__":
    unittest.main()
