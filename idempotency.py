"""Persistent idempotency claims for one-shot model requests."""
from __future__ import annotations

import hashlib
import math
import os
import re
import sqlite3
import stat
import time
from collections.abc import Callable
from contextlib import closing

_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{16,128}$")
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TERMINAL_STATES = {"COMPLETED", "BLOCKED", "FAILED", "UNKNOWN"}


class IdempotencyError(RuntimeError):
    pass


class IdempotencyConflict(IdempotencyError):
    pass


class SQLiteIdempotencyStore:
    """SQLite-backed claims; raw idempotency keys are never persisted."""

    def __init__(
        self,
        path: str,
        *,
        lease_seconds: float = 300,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not isinstance(path, str) or not path.strip():
            raise ValueError("idempotency path is required")
        if (
            type(lease_seconds) not in (int, float)
            or not math.isfinite(lease_seconds)
            or lease_seconds <= 0
        ):
            raise ValueError("lease_seconds must be positive and finite")
        if not callable(clock):
            raise ValueError("clock must be callable")
        self.path = os.path.abspath(path)
        self.lease_seconds = float(lease_seconds)
        self.clock = clock
        self._prepare_file()
        self._initialize()

    def _prepare_file(self) -> None:
        parent = os.path.dirname(self.path)
        os.makedirs(parent, mode=0o700, exist_ok=True)
        if os.path.realpath(parent) != parent:
            raise ValueError(
                "idempotency parent path may not traverse symlinks"
            )
        parent_stat = os.lstat(parent)
        if not stat.S_ISDIR(parent_stat.st_mode):
            raise ValueError("idempotency parent must be a real directory")
        nofollow = getattr(os, "O_NOFOLLOW", None)
        if nofollow is None:
            raise OSError("platform lacks O_NOFOLLOW support")
        flags = os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | nofollow
        descriptor = os.open(self.path, flags, 0o600)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ValueError(
                    "idempotency path must be a private regular file"
                )
            os.fchmod(descriptor, 0o600)
        finally:
            os.close(descriptor)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path, timeout=5, isolation_level=None
        )
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS idempotency_requests (
                    key_hash TEXT PRIMARY KEY,
                    request_digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )"""
            )
        os.chmod(self.path, 0o600)

    @staticmethod
    def _validate(key: str, request_digest: str) -> str:
        if not isinstance(key, str) or not _KEY_PATTERN.fullmatch(key):
            raise ValueError("Idempotency-Key must be 16-128 safe characters")
        if (
            not isinstance(request_digest, str)
            or not _DIGEST_PATTERN.fullmatch(request_digest)
        ):
            raise ValueError("request_digest must be lowercase SHA-256 hex")
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def claim(self, key: str, request_digest: str) -> str:
        """Claim once; expired in-progress requests become UNKNOWN."""
        key_hash = self._validate(key, request_digest)
        now = self.clock()
        if type(now) not in (int, float) or not math.isfinite(now):
            raise IdempotencyError("clock unavailable")
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT request_digest, status, updated_at "
                "FROM idempotency_requests WHERE key_hash=?",
                (key_hash,),
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO idempotency_requests "
                    "(key_hash, request_digest, status, created_at, "
                    "updated_at) "
                    "VALUES (?, ?, 'IN_PROGRESS', ?, ?)",
                    (key_hash, request_digest, float(now), float(now)),
                )
                connection.commit()
                return "CLAIMED"
            stored_digest, status, updated_at = row
            if status != "IN_PROGRESS" and status not in _TERMINAL_STATES:
                connection.rollback()
                raise IdempotencyError("stored request state is invalid")
            if stored_digest != request_digest:
                connection.rollback()
                raise IdempotencyConflict(
                    "idempotency key was already used for a different request"
                )
            if (
                status == "IN_PROGRESS"
                and float(now) - float(updated_at) > self.lease_seconds
            ):
                connection.execute(
                    "UPDATE idempotency_requests SET status='UNKNOWN', "
                    "updated_at=? WHERE key_hash=? AND status='IN_PROGRESS'",
                    (float(now), key_hash),
                )
                status = "UNKNOWN"
            connection.commit()
            return str(status)

    def finish(
        self, key: str, request_digest: str, status: str
    ) -> None:
        if status not in _TERMINAL_STATES:
            raise ValueError("terminal status is invalid")
        key_hash = self._validate(key, request_digest)
        now = self.clock()
        if type(now) not in (int, float) or not math.isfinite(now):
            raise IdempotencyError("clock unavailable")
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE idempotency_requests SET status=?, updated_at=? "
                "WHERE key_hash=? AND request_digest=? "
                "AND status='IN_PROGRESS'",
                (status, float(now), key_hash, request_digest),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise IdempotencyConflict("no matching in-progress claim")
            connection.commit()

    def get(self, key: str, request_digest: str) -> str | None:
        key_hash = self._validate(key, request_digest)
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT request_digest, status FROM idempotency_requests "
                "WHERE key_hash=?", (key_hash,),
            ).fetchone()
        if row is None:
            return None
        if row[0] != request_digest:
            raise IdempotencyConflict(
                "idempotency key was already used for a different request"
            )
        return str(row[1])
