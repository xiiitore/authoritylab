"""Fail-closed pre-inference memory gate primitives.

This is a policy component, not a network gateway. Host enforcement requires
all model calls to use its executor and provider credentials to remain private.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import secrets
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

_TOKEN_VERSION = 1


def _canonical(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            dict(value), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise ValueError("value must be finite JSON data") from None


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str) and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    allowed = (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    )
    if (
        not isinstance(value, str) or not value
        or any(c not in allowed for c in value)
    ):
        raise ValueError("invalid token encoding")
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass(frozen=True, slots=True)
class GateRequest:
    request_id: str
    subject_id: str
    request_digest: str

    def __post_init__(self) -> None:
        for name in ("request_id", "subject_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if not _is_digest(self.request_digest):
            raise ValueError("request_digest must be lowercase SHA-256 hex")

    @staticmethod
    def digest_payload(payload: Mapping[str, Any]) -> str:
        """Hash the exact JSON request payload sent by the trusted host."""
        if not isinstance(payload, Mapping):
            raise TypeError("payload must be a mapping")
        return _hash(_canonical(payload).decode("utf-8"))


@dataclass(frozen=True, slots=True)
class MemorySnapshot:
    subject_id: str
    source_ids: tuple[str, ...]
    content: str
    retrieved_at: float
    version: str

    def __post_init__(self) -> None:
        if not isinstance(self.subject_id, str) or not self.subject_id.strip():
            raise ValueError("subject_id must be non-empty")
        if not isinstance(self.source_ids, tuple) or not self.source_ids:
            raise ValueError("source_ids must be a non-empty tuple")
        if any(
            not isinstance(x, str) or not x.strip() for x in self.source_ids
        ):
            raise ValueError("source_ids must contain non-empty strings")
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("source_ids must be unique")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("content must be non-empty")
        try:
            self.content.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("content must be valid UTF-8") from None
        if type(self.retrieved_at) not in (int, float):
            raise ValueError("retrieved_at must be a finite timestamp")
        if not math.isfinite(self.retrieved_at):
            raise ValueError("retrieved_at must be a finite timestamp")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version must be non-empty")

    @property
    def digest(self) -> str:
        return _hash(_canonical({
            "subject_id": self.subject_id,
            "source_ids": list(self.source_ids),
            "content": self.content,
            "retrieved_at": float(self.retrieved_at),
            "version": self.version,
        }).decode("utf-8"))


@dataclass(frozen=True, slots=True)
class GateDecision:
    status: str
    reason: str
    token: str | None = None
    snapshot_digest: str | None = None
    expires_at: float | None = None


class InvocationOutcomeUnknown(RuntimeError):
    """The provider request may have executed without a reliable response."""


@dataclass(frozen=True, slots=True)
class GateExecution:
    status: str
    result: Any
    decision: GateDecision


class MemoryGate:
    """Issue short-lived request-bound tokens only after memory and audit pass.

    Production audit sinks must be durable. This component controls only calls
    made through `execute`; host isolation must prevent direct provider bypass.
    """

    def __init__(
        self,
        signing_key: bytes,
        *,
        policy_version: str,
        audit_sink: Callable[[Mapping[str, Any]], Any],
        max_age_seconds: float = 86_400,
        token_ttl_seconds: float = 120,
        max_context_bytes: int = 32_768,
        future_skew_seconds: float = 30,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not isinstance(signing_key, bytes) or len(signing_key) < 32:
            raise ValueError("signing_key must be at least 32 bytes")
        if not isinstance(policy_version, str) or not policy_version.strip():
            raise ValueError("policy_version must be non-empty")
        if not callable(audit_sink) or not callable(clock):
            raise ValueError("audit_sink and clock must be callable")
        for name, value in (
            ("max_age_seconds", max_age_seconds),
            ("token_ttl_seconds", token_ttl_seconds),
            ("future_skew_seconds", future_skew_seconds),
        ):
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be positive and finite")
        if type(max_context_bytes) is not int or max_context_bytes < 1:
            raise ValueError("max_context_bytes must be positive")
        self._key = signing_key
        self.policy_version = policy_version
        self.audit_sink = audit_sink
        self.max_age_seconds = float(max_age_seconds)
        self.token_ttl_seconds = float(token_ttl_seconds)
        self.max_context_bytes = max_context_bytes
        self.future_skew_seconds = float(future_skew_seconds)
        self.clock = clock

    def authorize(
        self, request: GateRequest, snapshot: MemorySnapshot | None
    ) -> GateDecision:
        try:
            now = self.clock()
            if type(now) not in (int, float) or not math.isfinite(now):
                raise ValueError("invalid clock")
        except Exception:
            return self._blocked(request, snapshot, "clock_unavailable")
        reason = self._validate(request, snapshot, float(now))
        if reason:
            return self._blocked(request, snapshot, reason)
        assert isinstance(request, GateRequest)
        assert isinstance(snapshot, MemorySnapshot)
        expires = float(now) + self.token_ttl_seconds
        payload = {
            "v": _TOKEN_VERSION,
            "policy_version": self.policy_version,
            "request_id_sha256": _hash(request.request_id),
            "subject_id_sha256": _hash(request.subject_id),
            "request_digest": request.request_digest,
            "snapshot_digest": snapshot.digest,
            "source_id_hashes": [_hash(x) for x in snapshot.source_ids],
            "memory_version": snapshot.version,
            "issued_at": float(now),
            "expires_at": expires,
            "nonce": secrets.token_urlsafe(18),
        }
        body = _canonical(payload)
        signature = hmac.new(self._key, body, hashlib.sha256).digest()
        token = f"{_encode(body)}.{_encode(signature)}"
        if not self._record(
            request, snapshot, "PASS", "memory_context_admitted"
        ):
            return GateDecision("BLOCKED", "audit_unavailable")
        return GateDecision(
            "PASS", "memory_context_admitted", token,
            snapshot.digest, expires,
        )

    def block(
        self,
        request: GateRequest,
        snapshot: MemorySnapshot | None,
        reason: str,
    ) -> GateDecision:
        """Record a pre-inference block with a bounded reason code."""
        allowed = "abcdefghijklmnopqrstuvwxyz0123456789_"
        if (
            not isinstance(reason, str) or not 1 <= len(reason) <= 64
            or any(char not in allowed for char in reason)
        ):
            raise ValueError("block reason must be a lowercase reason code")
        return self._blocked(request, snapshot, reason)

    def verify_token(self, token: str, request: GateRequest) -> bool:
        """Verify signature, expiry, policy version, and request binding."""
        if not isinstance(request, GateRequest) or not isinstance(token, str):
            return False
        try:
            body_part, signature_part = token.split(".", 1)
            body = _decode(body_part)
            signature = _decode(signature_part)
            expected = hmac.new(self._key, body, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected):
                return False
            payload = json.loads(body.decode("utf-8"))
            now = self.clock()
            return (
                isinstance(payload, dict)
                and payload.get("v") == _TOKEN_VERSION
                and payload.get("policy_version") == self.policy_version
                and payload.get("request_id_sha256") == _hash(
                    request.request_id
                )
                and payload.get("subject_id_sha256") == _hash(
                    request.subject_id
                )
                and payload.get("request_digest") == request.request_digest
                and _is_digest(payload.get("snapshot_digest"))
                and isinstance(payload.get("source_id_hashes"), list)
                and bool(payload["source_id_hashes"])
                and all(_is_digest(x) for x in payload["source_id_hashes"])
                and type(payload.get("issued_at")) in (int, float)
                and type(payload.get("expires_at")) in (int, float)
                and math.isfinite(payload["issued_at"])
                and math.isfinite(payload["expires_at"])
                and payload["issued_at"]
                <= float(now) + self.future_skew_seconds
                and payload["expires_at"] > float(now)
                and payload["expires_at"] > payload["issued_at"]
                and isinstance(payload.get("nonce"), str)
                and bool(payload["nonce"])
            )
        except Exception:
            return False

    def execute(
        self,
        request: GateRequest,
        snapshot: MemorySnapshot | None,
        invoke_model: Callable[[GateRequest, str, str], Any],
    ) -> GateExecution:
        """Invoke the model callback only after memory and audit admission."""
        if not callable(invoke_model):
            decision = GateDecision("BLOCKED", "model_invoker_unavailable")
            return GateExecution("BLOCKED", None, decision)
        decision = self.authorize(request, snapshot)
        if decision.status != "PASS" or not decision.token:
            return GateExecution("BLOCKED", None, decision)
        if not self.verify_token(decision.token, request):
            self._record(request, snapshot, "BLOCKED", "issued_token_invalid")
            blocked = GateDecision("BLOCKED", "issued_token_invalid")
            return GateExecution("BLOCKED", None, blocked)
        assert isinstance(snapshot, MemorySnapshot)
        try:
            result = invoke_model(request, snapshot.content, decision.token)
        except InvocationOutcomeUnknown:
            self._record(
                request, snapshot, "UNKNOWN",
                "model_invocation_outcome_unknown",
            )
            return GateExecution("UNKNOWN", None, decision)
        except Exception:
            if not self._record(
                request, snapshot, "FAIL", "model_invocation_failed"
            ):
                return GateExecution("UNKNOWN", None, decision)
            return GateExecution("FAIL", None, decision)
        if not self._record(
            request, snapshot, "PASS", "model_invocation_completed"
        ):
            return GateExecution("UNKNOWN", result, decision)
        return GateExecution("PASS", result, decision)

    def _validate(
        self, request: GateRequest, snapshot: MemorySnapshot | None, now: float
    ) -> str | None:
        if not isinstance(request, GateRequest):
            return "invalid_request"
        if snapshot is None:
            return "memory_unavailable"
        if not isinstance(snapshot, MemorySnapshot):
            return "invalid_memory_snapshot"
        if request.subject_id != snapshot.subject_id:
            return "memory_scope_mismatch"
        age = now - float(snapshot.retrieved_at)
        if age < -self.future_skew_seconds:
            return "memory_timestamp_in_future"
        if age > self.max_age_seconds:
            return "memory_stale"
        if len(snapshot.content.encode("utf-8")) > self.max_context_bytes:
            return "memory_context_too_large"
        return None

    def _blocked(
        self,
        request: GateRequest | Any,
        snapshot: MemorySnapshot | None,
        reason: str,
    ) -> GateDecision:
        if not self._record(request, snapshot, "BLOCKED", reason):
            return GateDecision("BLOCKED", "audit_unavailable")
        return GateDecision("BLOCKED", reason)

    def _record(
        self,
        request: GateRequest | Any,
        snapshot: MemorySnapshot | None,
        status: str,
        reason: str,
    ) -> bool:
        event = {
            "event_type": "memory_gate",
            "status": status,
            "reason": reason,
            "request_id_sha256": (
                _hash(request.request_id)
                if isinstance(request, GateRequest) else None
            ),
            "subject_id_sha256": (
                _hash(request.subject_id)
                if isinstance(request, GateRequest) else None
            ),
            "request_digest": (
                request.request_digest
                if isinstance(request, GateRequest) else None
            ),
            "snapshot_digest": (
                snapshot.digest
                if isinstance(snapshot, MemorySnapshot) else None
            ),
            "source_id_hashes": (
                [_hash(x) for x in snapshot.source_ids]
                if isinstance(snapshot, MemorySnapshot) else []
            ),
            "policy_version": self.policy_version,
        }
        try:
            return self.audit_sink(event) is not False
        except Exception:
            return False
