"""Append-only, hash-chained audit storage for POSIX local filesystems.

The hash chain makes edits/reordering detectable; it is not a signature and
cannot prevent a privileged actor from rewriting the entire file.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _digest(record_without_hash: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(record_without_hash)).hexdigest()


class DurableAuditLog:
    def __init__(self, path: str) -> None:
        if not isinstance(path, str) or not path.strip():
            raise ValueError("audit path must be a non-empty string")
        self.path = os.path.abspath(path)

    def append(self, event: Mapping[str, Any]) -> dict[str, str]:
        if not isinstance(event, Mapping):
            raise TypeError("audit event must be a mapping")
        directory = os.path.dirname(self.path)
        os.makedirs(directory, exist_ok=True)
        descriptor = os.open(
            self.path, os.O_CREAT | os.O_RDWR | os.O_APPEND, 0o600
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            records = self._read_and_validate(descriptor)
            previous_hash = records[-1]["hash"] if records else "0" * 64
            record = {
                "event_id": uuid.uuid4().hex,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "previous_hash": previous_hash,
                "event": dict(event),
            }
            record["hash"] = _digest(record)
            payload = _canonical(record) + b"\n"
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("audit append made no progress")
                view = view[written:]
            os.fsync(descriptor)
            return {"event_id": record["event_id"], "event_hash": record["hash"]}
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def verify(self) -> bool:
        try:
            descriptor = os.open(self.path, os.O_RDONLY)
        except FileNotFoundError:
            return True
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH)
            self._read_and_validate(descriptor)
            return True
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    @staticmethod
    def _read_and_validate(descriptor: int) -> list[dict[str, Any]]:
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks = []
        while True:
            chunk = os.read(descriptor, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        raw = b"".join(chunks)
        if raw and not raw.endswith(b"\n"):
            raise ValueError("audit chain invalid")
        records: list[dict[str, Any]] = []
        expected_previous = "0" * 64
        for line in raw.splitlines():
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise ValueError("audit chain invalid") from None
            if not isinstance(record, dict) or not isinstance(record.get("hash"), str):
                raise ValueError("audit chain invalid")
            stored_hash = record["hash"]
            unhashed = {key: value for key, value in record.items() if key != "hash"}
            if record.get("previous_hash") != expected_previous or _digest(unhashed) != stored_hash:
                raise ValueError("audit chain invalid")
            if not isinstance(record.get("event_id"), str) or not isinstance(record.get("event"), dict):
                raise ValueError("audit chain invalid")
            records.append(record)
            expected_previous = stored_hash
        return records
