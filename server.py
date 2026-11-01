"""HTTP entry point for the single-user Memory Gate service."""
from __future__ import annotations

import base64
import binascii
import hmac
import json
import math
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from .audit_log import DurableAuditLog
from .idempotency import SQLiteIdempotencyStore
from .memory_gate import MemoryGate
from .memory_gate_service import MemoryGateService
from .notion_memory_provider import NotionMemoryProvider
from .openai_responses_client import OpenAIResponsesClient


_BASE64_PATTERN = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"required environment variable is missing: {name}")
    return value.strip()


def _decode_key(name: str) -> bytes:
    value = _required_env(name)
    if not _BASE64_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be URL-safe base64")
    try:
        decoded = base64.urlsafe_b64decode(
            value + "=" * (-len(value) % 4)
        )
    except (ValueError, binascii.Error):
        raise ValueError(f"{name} is invalid base64") from None
    if len(decoded) < 32:
        raise ValueError(f"{name} must decode to at least 32 bytes")
    return decoded


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer") from None
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _env_float(name: str, default: float, minimum: float = 0.001) -> float:
    raw = os.environ.get(name, str(default))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be numeric") from None
    if not math.isfinite(value) or value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def build_service_from_env() -> tuple[MemoryGateService, int]:
    signing_key = _decode_key("MEMORY_GATE_SIGNING_KEY_B64")
    audit_key = _decode_key("MEMORY_GATE_AUDIT_HMAC_KEY_B64")
    if hmac.compare_digest(signing_key, audit_key):
        raise ValueError("gate signing and audit integrity keys must differ")
    client_token = _required_env("MEMORY_GATE_CLIENT_TOKEN")
    if len(client_token) < 32:
        raise ValueError(
            "MEMORY_GATE_CLIENT_TOKEN must be at least 32 characters"
        )
    subject_id = _required_env("MEMORY_GATE_SUBJECT_ID")
    audit_path = _required_env("MEMORY_GATE_AUDIT_PATH")
    idempotency_path = _required_env("MEMORY_GATE_IDEMPOTENCY_PATH")
    if not os.path.isabs(audit_path) or not os.path.isabs(idempotency_path):
        raise ValueError("audit and idempotency paths must be absolute")
    if os.path.abspath(audit_path) == os.path.abspath(idempotency_path):
        raise ValueError("audit and idempotency paths must be different")
    max_context_bytes = _env_int(
        "MEMORY_GATE_MAX_CONTEXT_BYTES", 32_768
    )

    audit_log = DurableAuditLog(audit_path, integrity_key=audit_key)
    if not audit_log.verify():
        raise RuntimeError("durable audit log verification failed")
    gate = MemoryGate(
        signing_key,
        policy_version=os.environ.get("MEMORY_GATE_POLICY_VERSION", "v1"),
        audit_sink=audit_log.append,
        max_age_seconds=_env_float(
            "MEMORY_GATE_MAX_AGE_SECONDS", 86_400
        ),
        token_ttl_seconds=_env_float(
            "MEMORY_GATE_TOKEN_TTL_SECONDS", 120
        ),
        max_context_bytes=max_context_bytes,
    )
    provider = NotionMemoryProvider.from_env(
        max_context_bytes=max_context_bytes
    )
    model_client = OpenAIResponsesClient.from_env(
        token_verifier=gate.verify_token
    )
    idempotency_store = SQLiteIdempotencyStore(
        idempotency_path,
        lease_seconds=_env_float(
            "MEMORY_GATE_IDEMPOTENCY_LEASE_SECONDS", 300
        ),
    )
    service = MemoryGateService(
        gate, provider, model_client, idempotency_store,
        subject_id=subject_id,
        client_token=client_token,
        max_input_bytes=_env_int("MEMORY_GATE_MAX_INPUT_BYTES", 32_768),
    )
    return service, _env_int("MEMORY_GATE_MAX_REQUEST_BYTES", 65_536)


def make_handler(
    service: MemoryGateService, *, max_request_bytes: int = 65_536
) -> type[BaseHTTPRequestHandler]:
    if type(max_request_bytes) is not int or max_request_bytes < 1:
        raise ValueError("max_request_bytes must be positive")

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "MemoryGate"
        sys_version = ""

        def log_message(self, format: str, *args: Any) -> None:
            # Do not log paths, client addresses, or payload metadata.
            return

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(
                payload, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
            self.send_response(status)
            self.send_header(
                "Content-Type", "application/json; charset=utf-8"
            )
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            self.wfile.write(body)

        def do_GET(self) -> None:
            if urlsplit(self.path).path == "/health":
                self._send(200, {"status": "alive"})
                return
            self._send(
                404, {"status": "FAIL", "reason": "not_found"}
            )

        def do_POST(self) -> None:
            if urlsplit(self.path).path != "/v1/chat":
                self._send(
                    404, {"status": "FAIL", "reason": "not_found"}
                )
                return
            content_type = self.headers.get("Content-Type", "")
            media_type = content_type.split(";", 1)[0].strip().lower()
            if media_type != "application/json":
                self._send(
                    415, {"status": "FAIL", "reason": "json_required"}
                )
                return
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                self._send(
                    411,
                    {"status": "FAIL", "reason": "content_length_required"},
                )
                return
            try:
                length = int(raw_length)
            except ValueError:
                self._send(
                    400, {"status": "FAIL", "reason": "invalid_content_length"}
                )
                return
            if length < 1:
                self._send(400, {"status": "FAIL", "reason": "empty_body"})
                return
            if length > max_request_bytes:
                self._send(
                    413, {"status": "FAIL", "reason": "request_too_large"}
                )
                return
            raw = self.rfile.read(length)
            if len(raw) != length:
                self._send(
                    400, {"status": "FAIL", "reason": "incomplete_body"}
                )
                return
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                self._send(400, {"status": "FAIL", "reason": "invalid_json"})
                return
            authorization = self.headers.get("Authorization", "")
            bearer = (
                authorization[7:]
                if authorization.startswith("Bearer ") else None
            )
            idempotency_key = self.headers.get("Idempotency-Key")
            status, result = service.handle_chat(
                bearer, idempotency_key, payload
            )
            self._send(status, result)

    return Handler


def main() -> None:
    service, max_request_bytes = build_service_from_env()
    host = os.environ.get("MEMORY_GATE_HOST", "0.0.0.0")
    port = _env_int("PORT", 8000)
    handler = make_handler(
        service, max_request_bytes=max_request_bytes
    )
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = False
    server.block_on_close = True
    server.allow_reuse_address = True
    try:
        server.serve_forever()
    finally:
        server.server_close()
        service.idempotency_store.close()


if __name__ == "__main__":
    main()
