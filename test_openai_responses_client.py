import io
import json
import unittest
from http.client import HTTPMessage
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from authoritylab.memory_gate import (
    GateRequest,
    InvocationOutcomeUnknown,
)
from authoritylab.openai_responses_client import (
    OpenAIAPIError,
    OpenAIResponsesClient,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


class FakeOpener:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def response_payload(text="answer", status="completed"):
    return {
        "object": "response", "status": status,
        "output": [{
            "type": "message",
            "content": [{"type": "output_text", "text": text}],
        }],
    }


class OpenAIResponsesClientTests(unittest.TestCase):
    def client(self, opener):
        return OpenAIResponsesClient(
            "secret-openai-key", "configured-model", opener=opener,
            token_verifier=lambda token, request: token == "valid-token",
        )

    def invoke(self, client, payload, token="valid-token"):
        request = GateRequest(
            "request-1", "subject-1", GateRequest.digest_payload(payload)
        )
        return client.invoke(
            payload, request=request, gate_token=token
        )

    def test_payload_binds_memory_and_disables_response_storage(self):
        client = self.client(FakeOpener(FakeResponse(response_payload())))
        payload = client.build_payload("question", "retrieved memory")
        self.assertEqual(payload["model"], "configured-model")
        self.assertEqual(payload["input"][0]["content"], "question")
        self.assertFalse(payload["store"])
        self.assertIn("retrieved memory", payload["input"][1]["content"])
        self.assertIn("untrusted evidence", payload["instructions"])

    def test_output_limit_is_bounded_by_server_policy(self):
        client = self.client(FakeOpener(FakeResponse(response_payload())))
        with self.assertRaises(ValueError):
            client.build_payload("question", "memory", max_output_tokens=2048)
        with self.assertRaises(ValueError):
            client.build_payload("question", "memory", max_output_tokens=8)

    def test_invoke_sends_authorized_responses_request(self):
        opener = FakeOpener(FakeResponse(response_payload("ok")))
        client = self.client(opener)
        payload = client.build_payload("question", "memory")
        result = self.invoke(client, payload)
        request = opener.requests[0]
        self.assertEqual(
            request.full_url, "https://api.openai.com/v1/responses"
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.get_header("Authorization"), "Bearer secret-openai-key"
        )
        sent = json.loads(request.data)
        self.assertFalse(sent["store"])
        self.assertEqual(result["status"], "completed")

    def test_payload_rejects_tools_or_other_unapproved_fields(self):
        opener = FakeOpener(FakeResponse(response_payload()))
        client = self.client(opener)
        payload = client.build_payload("question", "memory")
        payload["tools"] = [{"type": "web_search"}]
        with self.assertRaises(ValueError):
            self.invoke(client, payload)
        self.assertEqual(opener.requests, [])

    def test_payload_without_memory_context_is_rejected(self):
        opener = FakeOpener(FakeResponse(response_payload()))
        client = self.client(opener)
        payload = client.build_payload("question", "memory")
        payload["input"] = [
            {"role": "user", "content": "question"},
            {"role": "user", "content": "plain text"},
        ]
        with self.assertRaises(ValueError):
            self.invoke(client, payload)
        self.assertEqual(opener.requests, [])

    def test_invalid_gate_token_blocks_before_network(self):
        opener = FakeOpener(FakeResponse(response_payload()))
        client = self.client(opener)
        payload = client.build_payload("question", "memory")
        request = GateRequest(
            "request-1", "subject-1", GateRequest.digest_payload(payload)
        )
        with self.assertRaises(PermissionError):
            client.invoke(payload, request=request, gate_token="invalid")
        self.assertEqual(opener.requests, [])

    def test_payload_change_after_authorization_is_blocked(self):
        opener = FakeOpener(FakeResponse(response_payload()))
        client = self.client(opener)
        payload = client.build_payload("question", "memory")
        request = GateRequest(
            "request-1", "subject-1", GateRequest.digest_payload(payload)
        )
        payload["input"][0]["content"] = "tampered"
        with self.assertRaises(PermissionError):
            client.invoke(
                payload, request=request, gate_token="valid-token"
            )
        self.assertEqual(opener.requests, [])

    def test_unauthorized_is_known_failure_and_key_is_redacted(self):
        headers = HTTPMessage()
        error = HTTPError(
            "https://api.openai.com", 401, "Unauthorized", headers,
            io.BytesIO(b'{"error":{"code":"invalid_api_key"}}'),
        )
        opener = FakeOpener(error)
        client = self.client(opener)
        payload = client.build_payload("question", "memory")
        with self.assertRaises(OpenAIAPIError) as raised:
            self.invoke(client, payload)
        self.assertEqual(raised.exception.status, 401)
        self.assertEqual(raised.exception.code, "invalid_api_key")
        self.assertNotIn("secret-openai-key", str(raised.exception))
        self.assertEqual(len(opener.requests), 1)

    def test_rate_limit_is_known_failure_without_retry(self):
        headers = HTTPMessage()
        error = HTTPError(
            "https://api.openai.com", 429, "Rate limited", headers,
            io.BytesIO(b'{"error":{"code":"rate_limit_exceeded"}}'),
        )
        opener = FakeOpener(error)
        client = self.client(opener)
        payload = client.build_payload("question", "memory")
        with self.assertRaises(OpenAIAPIError) as raised:
            self.invoke(client, payload)
        self.assertEqual(raised.exception.status, 429)
        self.assertEqual(len(opener.requests), 1)

    def test_server_error_is_unknown_and_never_retried(self):
        headers = HTTPMessage()
        error = HTTPError(
            "https://api.openai.com", 500, "Server error", headers,
            io.BytesIO(b'{"error":{"code":"server_error"}}'),
        )
        opener = FakeOpener(error)
        client = self.client(opener)
        payload = client.build_payload("question", "memory")
        with self.assertRaises(InvocationOutcomeUnknown):
            self.invoke(client, payload)
        self.assertEqual(len(opener.requests), 1)

    def test_network_failure_is_unknown_and_never_retried(self):
        opener = FakeOpener(URLError("connection reset"))
        client = self.client(opener)
        payload = client.build_payload("question", "memory")
        with self.assertRaises(InvocationOutcomeUnknown):
            self.invoke(client, payload)
        self.assertEqual(len(opener.requests), 1)

    def test_unreadable_success_response_is_unknown(self):
        opener = FakeOpener(FakeResponse({"not": "a response"}))
        client = self.client(opener)
        payload = client.build_payload("question", "memory")
        with self.assertRaises(InvocationOutcomeUnknown):
            self.invoke(client, payload)

    def test_failed_response_is_known_failure(self):
        opener = FakeOpener(FakeResponse({
            "object": "response", "status": "failed",
            "error": {"code": "model_error"},
        }))
        client = self.client(opener)
        payload = client.build_payload("question", "memory")
        with self.assertRaises(OpenAIAPIError) as raised:
            self.invoke(client, payload)
        self.assertEqual(raised.exception.code, "model_error")

    def test_extract_output_text(self):
        result = OpenAIResponsesClient.extract_output_text(
            response_payload("expected output")
        )
        self.assertEqual(result, "expected output")

    def test_from_env_requires_api_key_and_model(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                OpenAIResponsesClient.from_env(
                    token_verifier=lambda token, request: False
                )


if __name__ == "__main__":
    unittest.main()
