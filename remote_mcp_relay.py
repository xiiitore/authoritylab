"""Prototype remote MCP relay for a single Termux agent.

Security boundary: read-only tools only. This module is a staging prototype,
not a production deployment. Bind the gateway to loopback behind an authenticated
TLS reverse proxy. Never expose its HTTP listener directly to the Internet.
"""
from __future__ import annotations

import hmac
import json
import os
import secrets
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 256 * 1024
MAX_FILE_BYTES = 200_000
MAX_PENDING = 4
REQUEST_TIMEOUT = 15.0
AGENT_POLL_TIMEOUT = 10.0
PROTOCOL_VERSION = "2025-03-26"

TOOLS = [
    {"name": "status", "description": "Return bounded Termux workspace status.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "list_files", "description": "List direct file names in the configured workspace root.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "read_file", "description": "Read a UTF-8 file by relative path (maximum 200 KB).",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string", "minLength": 1, "maxLength": 1024}},
                     "required": ["path"], "additionalProperties": False}},
]
ALLOWED_TOOLS = frozenset(tool["name"] for tool in TOOLS)


class RelayError(Exception):
    """A bounded, safe-to-return relay error."""


class RequestBroker:
    """In-memory single-agent broker. Restart/disconnect fails closed."""

    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._queue: deque[str] = deque()
        self._pending: dict[str, dict[str, Any]] = {}

    def submit(self, tool: str, arguments: dict[str, Any], timeout: float = REQUEST_TIMEOUT) -> Any:
        if tool not in ALLOWED_TOOLS:
            raise RelayError("tool_not_allowed")
        if not isinstance(arguments, dict):
            raise RelayError("invalid_arguments")
        if tool != "read_file" and arguments:
            raise RelayError("unexpected_arguments")
        if tool == "read_file":
            if set(arguments) != {"path"} or not isinstance(arguments.get("path"), str):
                raise RelayError("invalid_arguments")
            path = arguments["path"]
            normalized = path.replace(chr(92), "/")
            if (not path or len(path) > 1024 or chr(0) in path
                    or path.startswith("/") or any(part == ".." for part in normalized.split("/"))):
                raise RelayError("invalid_arguments")
        request_id = secrets.token_urlsafe(24)
        deadline = time.monotonic() + min(max(timeout, 0.1), REQUEST_TIMEOUT)
        with self._cv:
            if len(self._pending) >= MAX_PENDING:
                raise RelayError("queue_full")
            self._pending[request_id] = {
                "id": request_id, "tool": tool, "arguments": arguments,
                "deadline": deadline, "state": "queued",
            }
            self._queue.append(request_id)
            self._cv.notify_all()
            while True:
                item = self._pending.get(request_id)
                if item is None:
                    raise RelayError("request_expired")
                if item["state"] == "done":
                    self._pending.pop(request_id, None)
                    if item.get("error"):
                        raise RelayError("device_tool_failed")
                    return item.get("result")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._pending.pop(request_id, None)
                    try:
                        self._queue.remove(request_id)
                    except ValueError:
                        pass
                    self._cv.notify_all()
                    raise RelayError("device_timeout")
                self._cv.wait(min(remaining, 0.5))

    def next_request(self, wait: float = AGENT_POLL_TIMEOUT) -> dict[str, Any] | None:
        end = time.monotonic() + min(max(wait, 0.0), AGENT_POLL_TIMEOUT)
        with self._cv:
            while True:
                while self._queue:
                    request_id = self._queue.popleft()
                    item = self._pending.get(request_id)
                    if item is None or item["deadline"] <= time.monotonic():
                        self._pending.pop(request_id, None)
                        continue
                    if item["state"] != "queued":
                        continue
                    item["state"] = "claimed"
                    return {"id": item["id"], "tool": item["tool"], "arguments": item["arguments"]}
                remaining = end - time.monotonic()
                if remaining <= 0:
                    return None
                self._cv.wait(remaining)

    def complete(self, request_id: str, *, result: Any = None, error: bool = False) -> bool:
        if not isinstance(request_id, str) or len(request_id) > 128:
            return False
        with self._cv:
            item = self._pending.get(request_id)
            if item is None or item["state"] != "claimed" or item["deadline"] <= time.monotonic():
                return False
            item["state"] = "done"
            item["result"] = result
            item["error"] = bool(error)
            self._cv.notify_all()
            return True


def _json_bytes(value: Any, maximum: int = MAX_RESPONSE_BYTES) -> bytes:
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise RelayError("invalid_json_result") from None
    if len(encoded) > maximum:
        raise RelayError("response_too_large")
    return encoded


def _valid_token(value: str | None) -> bool:
    return isinstance(value, str) and len(value) >= 32


def make_handler(broker: RequestBroker, client_token: str, agent_token: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AuthorityLabRelay/0.1"
        sys_version = ""

        def log_message(self, fmt: str, *args: Any) -> None:
            # Do not log headers, request bodies, paths or credentials.
            print("relay_http: request handled")

        def _reply(self, status: int, payload: Any = None) -> None:
            body = b"" if payload is None else _json_bytes(payload)
            self.send_response(status)
            if payload is not None:
                self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _authorized(self, expected: str) -> bool:
            header = self.headers.get("Authorization", "")
            supplied = header[7:] if header.startswith("Bearer ") else ""
            return hmac.compare_digest(supplied, expected)

        def _body(self) -> Any:
            length = self.headers.get("Content-Length")
            if length is None or not length.isdigit():
                raise RelayError("content_length_required")
            size = int(length)
            if size < 1 or size > MAX_REQUEST_BYTES:
                raise RelayError("request_size_rejected")
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise RelayError("incomplete_request")
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise RelayError("invalid_json") from None

        def do_GET(self) -> None:
            route = urlsplit(self.path).path
            if route != "/agent/next":
                self._reply(404, {"error": "not_found"})
                return
            if not self._authorized(agent_token):
                self._reply(401, {"error": "unauthorized"})
                return
            task = broker.next_request()
            self._reply(200, {"request": task})

        def do_POST(self) -> None:
            route = urlsplit(self.path).path
            if route == "/mcp":
                if not self._authorized(client_token):
                    self._reply(401, {"error": "unauthorized"})
                    return
                self._mcp()
                return
            if route == "/agent/result":
                if not self._authorized(agent_token):
                    self._reply(401, {"error": "unauthorized"})
                    return
                try:
                    body = self._body()
                    if not isinstance(body, dict) or set(body) - {"id", "result", "error"}:
                        raise RelayError("invalid_result_payload")
                    if not isinstance(body.get("id"), str):
                        raise RelayError("invalid_result_payload")
                    error = body.get("error", False)
                    if not isinstance(error, bool):
                        raise RelayError("invalid_result_payload")
                    if "result" in body and len(_json_bytes(body["result"])) > MAX_RESPONSE_BYTES:
                        raise RelayError("response_too_large")
                    accepted = broker.complete(body["id"], result=body.get("result"), error=error)
                    self._reply(200 if accepted else 409, {"accepted": accepted})
                except RelayError as exc:
                    self._reply(400, {"error": str(exc)})
                return
            self._reply(404, {"error": "not_found"})

        def _mcp(self) -> None:
            try:
                message = self._body()
                if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                    raise RelayError("invalid_json_rpc")
                method = message.get("method")
                request_id = message.get("id")
                if method == "notifications/initialized" and "id" not in message:
                    self._reply(202)
                    return
                if method == "initialize":
                    result = {"protocolVersion": PROTOCOL_VERSION,
                              "capabilities": {"tools": {}},
                              "serverInfo": {"name": "authoritylab-termux-relay", "version": "0.1.0"}}
                elif method == "ping":
                    result = {}
                elif method == "tools/list":
                    result = {"tools": TOOLS}
                elif method == "tools/call":
                    params = message.get("params")
                    if not isinstance(params, dict) or not isinstance(params.get("name"), str):
                        raise RelayError("invalid_tool_call")
                    name = params["name"]
                    arguments = params.get("arguments", {})
                    if name not in ALLOWED_TOOLS or not isinstance(arguments, dict):
                        result = {"content": [{"type": "text", "text": "tool_not_allowed"}], "isError": True}
                    else:
                        try:
                            output = broker.submit(name, arguments)
                            result = {"content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False)}],
                                      "isError": False}
                        except RelayError as exc:
                            result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
                else:
                    if "id" not in message:
                        self._reply(202)
                        return
                    self._reply(200, {"jsonrpc": "2.0", "id": request_id,
                                      "error": {"code": -32601, "message": "Method not found"}})
                    return
                if "id" not in message:
                    self._reply(202)
                else:
                    response = {"jsonrpc": "2.0", "id": request_id, "result": result}
                    try:
                        _json_bytes(response)
                    except RelayError:
                        response = {"jsonrpc": "2.0", "id": request_id, "result": {
                            "content": [{"type": "text", "text": "response_too_large"}], "isError": True}}
                    self._reply(200, response)
            except RelayError as exc:
                self._reply(400, {"error": str(exc)})

        def do_PUT(self) -> None:
            self._reply(405, {"error": "method_not_allowed"})

        def do_DELETE(self) -> None:
            self._reply(405, {"error": "method_not_allowed"})

    return Handler


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    """Threaded HTTP server with a hard cap on active request threads."""

    max_concurrent_connections = 16

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._connection_slots = threading.BoundedSemaphore(self.max_concurrent_connections)
        super().__init__(*args, **kwargs)

    def process_request(self, request: Any, client_address: Any) -> None:
        if not self._connection_slots.acquire(blocking=False):
            try:
                request.sendall(
                    b"HTTP/1.1 503 Service Unavailable\\r\\n"
                    b"Connection: close\\r\\n"
                    b"Content-Length: 0\\r\\n\\r\\n"
                )
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._connection_slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._connection_slots.release()


def main() -> None:
    client_token = os.environ.get("AUTHORITYLAB_CLIENT_TOKEN")
    agent_token = os.environ.get("AUTHORITYLAB_AGENT_TOKEN")
    if (not _valid_token(client_token) or not _valid_token(agent_token)
            or hmac.compare_digest(client_token or "", agent_token or "")):
        raise SystemExit("Set two distinct 32+ character AUTHORITYLAB_CLIENT_TOKEN and AUTHORITYLAB_AGENT_TOKEN secrets.")
    host = os.environ.get("AUTHORITYLAB_RELAY_HOST", "127.0.0.1")
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("Gateway must bind to loopback; put an authenticated TLS reverse proxy in front.")
    port = int(os.environ.get("AUTHORITYLAB_RELAY_PORT", "8765"))
    server = BoundedThreadingHTTPServer((host, port), make_handler(RequestBroker(), client_token, agent_token))
    print(f"AuthorityLab relay listening on {host}:{port}; loopback only. Ctrl-C to stop.")
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
