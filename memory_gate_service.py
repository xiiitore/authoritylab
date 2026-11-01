"""Single-user request coordinator for the enforced memory-gated model path."""
from __future__ import annotations

import hashlib
import hmac
from typing import Any

from .idempotency import (
    IdempotencyConflict,
    SQLiteIdempotencyStore,
)
from .memory_gate import GateRequest, MemoryGate
from .notion_memory_provider import NotionMemoryProvider
from .openai_responses_client import OpenAIResponsesClient


class MemoryGateService:
    """Only public chat path; every accepted request is idempotency-claimed."""

    def __init__(
        self,
        gate: MemoryGate,
        memory_provider: NotionMemoryProvider,
        model_client: OpenAIResponsesClient,
        idempotency_store: SQLiteIdempotencyStore,
        *,
        subject_id: str,
        client_token: str,
        max_input_bytes: int = 32_768,
    ) -> None:
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise ValueError("subject_id is required")
        if not isinstance(client_token, str) or len(client_token) < 32:
            raise ValueError("client_token must be at least 32 characters")
        if type(max_input_bytes) is not int or max_input_bytes < 1:
            raise ValueError("max_input_bytes must be positive")
        self.gate = gate
        self.memory_provider = memory_provider
        self.model_client = model_client
        self.idempotency_store = idempotency_store
        self.subject_id = subject_id
        self._client_token = client_token
        self.max_input_bytes = max_input_bytes

    def handle_chat(
        self,
        bearer_token: str | None,
        idempotency_key: str | None,
        payload: Any,
    ) -> tuple[int, dict[str, Any]]:
        if (
            not isinstance(bearer_token, str)
            or not hmac.compare_digest(bearer_token, self._client_token)
        ):
            return 401, {"status": "BLOCKED", "reason": "unauthorized"}
        if not isinstance(payload, dict):
            return 400, {"status": "FAIL", "reason": "invalid_json_object"}
        if set(payload) - {"input", "max_output_tokens"}:
            return 400, {"status": "FAIL", "reason": "unsupported_fields"}
        user_input = payload.get("input")
        if not isinstance(user_input, str) or not user_input.strip():
            return 400, {"status": "FAIL", "reason": "input_required"}
        if len(user_input.encode("utf-8")) > self.max_input_bytes:
            return 413, {"status": "FAIL", "reason": "input_too_large"}
        max_output_tokens = payload.get("max_output_tokens")
        if max_output_tokens is not None and (
            type(max_output_tokens) is not int
            or not (
                16 <= max_output_tokens
                <= self.model_client.max_output_tokens
            )
        ):
            return 400, {"status": "FAIL", "reason": "invalid_output_limit"}

        client_digest = GateRequest.digest_payload({
            "input": user_input,
            "max_output_tokens": max_output_tokens,
        })
        try:
            claim = self.idempotency_store.claim(
                idempotency_key, client_digest
            )
        except IdempotencyConflict:
            return 409, {"status": "BLOCKED", "reason": "idempotency_conflict"}
        except (TypeError, ValueError):
            return 400, {"status": "FAIL", "reason": "invalid_idempotency_key"}
        except Exception:
            return 503, {
                "status": "BLOCKED",
                "reason": "idempotency_store_unavailable",
            }

        request_id = hashlib.sha256(
            idempotency_key.encode("utf-8")
        ).hexdigest()
        audit_ref = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
        if claim != "CLAIMED":
            return self._existing_result(claim, request_id, audit_ref)

        try:
            snapshot = self.memory_provider.retrieve(self.subject_id)
        except Exception:
            gate_request = GateRequest(
                request_id, self.subject_id, client_digest
            )
            decision = self.gate.block(
                gate_request, None, "memory_unavailable"
            )
            if not self._finish(idempotency_key, client_digest, "BLOCKED"):
                return self._unknown(request_id, audit_ref)
            return 503, {
                "status": "BLOCKED", "reason": decision.reason,
                "request_id": request_id, "audit_ref": audit_ref,
            }

        try:
            outbound_payload = self.model_client.build_payload(
                user_input, snapshot.content,
                max_output_tokens=max_output_tokens,
            )
            gate_request = GateRequest(
                request_id, self.subject_id,
                GateRequest.digest_payload(outbound_payload),
            )
        except Exception:
            gate_request = GateRequest(
                request_id, self.subject_id,
                GateRequest.digest_payload({
                    "input": user_input,
                    "memory_snapshot_digest": snapshot.digest,
                }),
            )
            decision = self.gate.block(
                gate_request, snapshot, "payload_build_failed"
            )
            if not self._finish(idempotency_key, client_digest, "BLOCKED"):
                return self._unknown(request_id, audit_ref)
            return 503, {
                "status": "BLOCKED", "reason": decision.reason,
                "request_id": request_id, "audit_ref": audit_ref,
            }

        def invoke(request: GateRequest, context: str, token: str) -> str:
            response = self.model_client.invoke(
                outbound_payload, request=request, gate_token=token
            )
            return self.model_client.extract_output_text(response)

        try:
            execution = self.gate.execute(
                gate_request, snapshot, invoke
            )
        except Exception:
            self._finish(idempotency_key, client_digest, "UNKNOWN")
            return self._unknown(request_id, audit_ref)

        if execution.status == "PASS":
            if not self._finish(idempotency_key, client_digest, "COMPLETED"):
                return self._unknown(request_id, audit_ref)
            return 200, {
                "status": "PASS", "output_text": execution.result,
                "request_id": request_id, "audit_ref": audit_ref,
            }
        if execution.status == "BLOCKED":
            if not self._finish(idempotency_key, client_digest, "BLOCKED"):
                return self._unknown(request_id, audit_ref)
            return 503, {
                "status": "BLOCKED", "reason": execution.decision.reason,
                "request_id": request_id, "audit_ref": audit_ref,
            }
        if execution.status == "FAIL":
            if not self._finish(idempotency_key, client_digest, "FAILED"):
                return self._unknown(request_id, audit_ref)
            return 502, {
                "status": "FAIL", "reason": execution.decision.reason,
                "request_id": request_id, "audit_ref": audit_ref,
            }
        if not self._finish(idempotency_key, client_digest, "UNKNOWN"):
            return self._unknown(request_id, audit_ref)
        return self._unknown(request_id, audit_ref)

    def _finish(self, key: str, digest: str, status: str) -> bool:
        try:
            self.idempotency_store.finish(key, digest, status)
            return True
        except Exception:
            return False

    @staticmethod
    def _unknown(
        request_id: str, audit_ref: str
    ) -> tuple[int, dict[str, Any]]:
        return 202, {
            "status": "UNKNOWN",
            "reason": "outcome_unknown_do_not_retry",
            "request_id": request_id,
            "audit_ref": audit_ref,
        }

    @staticmethod
    def _existing_result(
        status: str, request_id: str, audit_ref: str
    ) -> tuple[int, dict[str, Any]]:
        responses = {
            "IN_PROGRESS": (
                202, "request_in_progress_do_not_resubmit"
            ),
            "COMPLETED": (
                409, "already_completed_result_not_retained"
            ),
            "BLOCKED": (503, "previous_attempt_blocked"),
            "FAILED": (502, "previous_attempt_failed"),
            "UNKNOWN": (202, "outcome_unknown_do_not_retry"),
        }
        code, reason = responses.get(
            status, (503, "idempotency_state_unknown")
        )
        return code, {
            "status": status if status in responses else "UNKNOWN",
            "reason": reason,
            "request_id": request_id,
            "audit_ref": audit_ref,
        }
