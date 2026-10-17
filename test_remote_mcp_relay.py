"""Focused tests for the read-only remote MCP relay prototype."""
from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from remote_mcp_relay import (
    RequestBroker, RelayError, make_handler, _json_bytes, _valid_token,
)


CLIENT_TOKEN = "c" * 40
AGENT_TOKEN = "a" * 40


class BrokerTests(unittest.TestCase):
    def test_tool_allowlist_and_argument_validation(self):
        broker = RequestBroker()
        with self.assertRaisesRegex(RelayError, "tool_not_allowed"):
            broker.submit("shell", {"command": "id"}, timeout=0.1)
        with self.assertRaisesRegex(RelayError, "invalid_arguments"):
            broker.submit("read_file", {"path": "../secret"}, timeout=0.1)

    def test_expired_request_cannot_be_completed(self):
        broker = RequestBroker()
        with self.assertRaisesRegex(RelayError, "device_timeout"):
            broker.submit("status", {}, timeout=0.1)
        self.assertFalse(broker.complete("not-a-live-request", result={"ok": True}))

    def test_single_completion_only(self):
        broker = RequestBroker()
        got = {}

        def submitter():
            try:
                got["result"] = broker.submit("status", {}, timeout=2.0)
            except Exception as exc:  # captured for assertion in test thread
                got["error"] = exc

        thread = threading.Thread(target=submitter)
        thread.start()
        task = broker.next_request(wait=1.0)
        self.assertIsNotNone(task)
        self.assertTrue(broker.complete(task["id"], result={"status": "ready"}))
        self.assertFalse(broker.complete(task["id"], result={"status": "changed"}))
        thread.join(2.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(got.get("result"), {"status": "ready"})

    def test_response_size_limit(self):
        with self.assertRaisesRegex(RelayError, "response_too_large"):
            _json_bytes("x" * (256 * 1024))
        self.assertTrue(_valid_token("x" * 32))
        self.assertFalse(_valid_token("short"))


class HttpIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.broker = RequestBroker()
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(cls.broker, CLIENT_TOKEN, AGENT_TOKEN)
        )
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(2.0)

    def call(self, path, token, payload=None, method=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base + path, data=data,
            headers={"Authorization": "Bearer " + token,
                     "Content-Type": "application/json"},
            method=method or ("POST" if payload is not None else "GET"),
        )
        with urllib.request.urlopen(req, timeout=3.0) as response:
            body = response.read()
            return response.status, json.loads(body) if body else None

    def test_auth_required(self):
        req = urllib.request.Request(
            self.base + "/agent/next", headers={"Authorization": "Bearer wrong"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=2.0)
        self.assertEqual(ctx.exception.code, 401)

    def test_tools_list_is_read_only(self):
        status, body = self.call("/mcp", CLIENT_TOKEN, {
            "jsonrpc": "2.0", "id": 1, "method": "tools/list"
        })
        self.assertEqual(status, 200)
        names = {item["name"] for item in body["result"]["tools"]}
        self.assertEqual(names, {"status", "list_files", "read_file"})

    def test_mcp_call_round_trip_to_agent(self):
        result_box = {}

        def fake_agent():
            status, body = self.call("/agent/next", AGENT_TOKEN)
            task = body["request"]
            result_box["id"] = task["id"]
            self.call("/agent/result", AGENT_TOKEN, {
                "id": task["id"], "result": {"status": "ready"}
            })

        agent_thread = threading.Thread(target=fake_agent)
        agent_thread.start()
        status, body = self.call("/mcp", CLIENT_TOKEN, {
            "jsonrpc": "2.0", "id": 9, "method": "tools/call",
            "params": {"name": "status", "arguments": {}},
        })
        agent_thread.join(2.0)
        self.assertEqual(status, 200)
        self.assertFalse(body["result"]["isError"])
        self.assertIn('"status": "ready"', body["result"]["content"][0]["text"])
        self.assertTrue(result_box.get("id"))

    def test_unknown_tool_is_not_dispatched(self):
        status, body = self.call("/mcp", CLIENT_TOKEN, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "run_shell", "arguments": {"command": "id"}},
        })
        self.assertEqual(status, 200)
        self.assertTrue(body["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
