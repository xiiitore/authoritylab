"""Append-only audit storage with a hash chain and optional HMAC signatures.

The hash chain detects accidental edits/reordering. Optional HMAC signatures
also detect whole-file rewrites by actors who do not possess the external key.
Neither mode prevents deletion or denial of service; protect the key and store.
"""
from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import stat
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

_ZERO_HASH = "0" * 64
_BASE_FIELDS = {"event_id", "recorded_at", "previous_hash", "event", "hash"}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _digest(record_without_hash: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(record_without_hash)).hexdigest()


class DurableAuditLog:
    def __init__(
        self,
        path: str,
        *,
        integrity_key: bytes | None = None,
        max_record_bytes: int = 1_048_576,
    ) -> None:
        if not isinstance(path, str) or not path.strip():
            raise ValueError("audit path must be a non-empty string")
        if integrity_key is not None and (
            not isinstance(integrity_key, bytes) or len(integrity_key) < 32
        ):
            raise ValueError("integrity_key must be at least 32 bytes")
        if type(max_record_bytes) is not int or max_record_bytes < 128:
            raise ValueError("max_record_bytes must be an integer of at least 128")
        self.path = os.path.abspath(path)
        self.integrity_key = integrity_key
        self.max_record_bytes = max_record_bytes

    def append(self, event: Mapping[str, Any]) -> dict[str, str]:
        if not isinstance(event, Mapping):
            raise TypeError("audit event must be a mapping")
        directory = os.path.dirname(self.path)
        os.makedirs(directory, exist_ok=True)
        flags = os.O_CREAT | os.O_RDWR | os.O_APPEND
        flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.path, flags, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("audit path must refer to a regular file")
            os.fchmod(descriptor, 0o600)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            previous_hash = self._read_and_validate(descriptor)
            record: dict[str, Any] = {
                "event_id": uuid.uuid4().hex,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "previous_hash": previous_hash,
                "event": dict(event),
            }
            record["hash"] = _digest(record)
            if self.integrity_key is not None:
                record["signature"] = self._signature(record)
            payload = _canonical(record) + b"\n"
            if len(payload) - 1 > self.max_record_bytes:
                raise ValueError("audit record exceeds max_record_bytes")
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("audit append made no progress")
                view = view[written:]
            os.fsync(descriptor)
            return {"event_id": record["event_id"], "event_hash": record["hash"]}
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    def verify(self) -> bool:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(self.path, flags)
        except FileNotFoundError:
            return True
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("audit path must refer to a regular file")
            fcntl.flock(descriptor, fcntl.LOCK_SH)
            self._read_and_validate(descriptor)
            return True
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    def _signature(self, record_with_hash: Mapping[str, Any]) -> str:
        assert self.integrity_key is not None
        return hmac.new(
            self.integrity_key, _canonical(record_with_hash), hashlib.sha256
        ).hexdigest()

    def _read_and_validate(self, descriptor: int) -> str:
        """Stream-validate the chain; return the last hash without loading all records."""
        os.lseek(descriptor, 0, os.SEEK_SET)
        expected_previous = _ZERO_HASH
        with os.fdopen(os.dup(descriptor), "rb") as stream:
            while True:
                line = stream.readline(self.max_record_bytes + 2)
                if not line:
                    break
                if len(line) > self.max_record_bytes + 1 or not line.endswith(b"\n"):
                    raise ValueError("audit chain invalid")
                def reject_constant(value: str) -> None:
                    raise ValueError(f"non-standard JSON constant: {value}")

                def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                    result: dict[str, Any] = {}
                    for key, value in pairs:
                        if key in result:
                            raise ValueError("duplicate JSON object key")
                        result[key] = value
                    return result

                try:
                    record = json.loads(
                        line,
                        parse_constant=reject_constant,
                        object_pairs_hook=reject_duplicate_keys,
                    )
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                    raise ValueError("audit chain invalid") from None
                if not isinstance(record, dict):
                    raise ValueError("audit chain invalid")
                signed = "signature" in record
                expected_fields = _BASE_FIELDS | ({"signature"} if signed else set())
                if set(record) != expected_fields:
                    raise ValueError("audit chain invalid")
                stored_hash = record.get("hash")
                if not isinstance(stored_hash, str):
                    raise ValueError("audit chain invalid")
                unhashed = {key: value for key, value in record.items() if key not in {"hash", "signature"}}
                if record.get("previous_hash") != expected_previous or _digest(unhashed) != stored_hash:
                    raise ValueError("audit chain invalid")
                if (
                    not isinstance(record.get("event_id"), str)
                    or not isinstance(record.get("recorded_at"), str)
                    or not isinstance(record.get("event"), dict)
                ):
                    raise ValueError("audit chain invalid")
                if signed:
                    if self.integrity_key is None:
                        raise ValueError("audit signature key required")
                    signature = record.get("signature")
                    signed_record = {key: value for key, value in record.items() if key != "signature"}
                    if not isinstance(signature, str) or not hmac.compare_digest(
                        signature, self._signature(signed_record)
                    ):
                        raise ValueError("audit signature invalid")
                elif self.integrity_key is not None:
                    raise ValueError("audit signature missing")
                expected_previous = stored_hash
        return expected_previous
