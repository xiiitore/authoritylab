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
from urllib.parse import quote

_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{16,128}$")
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TERMINAL_STATES = {"COMPLETED", "BLOCKED", "FAILED", "UNKNOWN"}


class IdempotencyError(RuntimeError):
    pass


class IdempotencyConflict(IdempotencyError):
    pass


class SQLiteIdempotencyStore:
    """SQLite claims rooted at a pinned, private directory descriptor.

    SQLite opens the database through /proc/self/fd/<dirfd>/<name>, so later
    path replacement cannot redirect connections to a different directory.
    The containing directory must be owned by this process and mode 0700.
    """

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
        if os.name != "posix" or not os.path.isdir("/proc/self/fd"):
            raise OSError("safe SQLite path requires POSIX procfs")
        self.path = os.path.abspath(path)
        self.name = os.path.basename(self.path)
        if self.name in ("", ".", ".."):
            raise ValueError("idempotency filename is invalid")
        self.lease_seconds = float(lease_seconds)
        self.clock = clock
        self._parent_fd: int | None = self._open_parent_directory()
        try:
            self._prepare_file()
            self._initialize()
        except BaseException:
            self.close()
            raise

    def _open_parent_directory(self) -> int:
        """Walk from / using dirfd + O_NOFOLLOW; never follow path symlinks."""
        nofollow = getattr(os, "O_NOFOLLOW", None)
        directory = getattr(os, "O_DIRECTORY", None)
        if (
            nofollow is None or directory is None
            or os.open not in os.supports_dir_fd
            or os.mkdir not in os.supports_dir_fd
        ):
            raise OSError("platform lacks safe descriptor-relative directory APIs")
        flags = os.O_RDONLY | directory | os.O_CLOEXEC | nofollow
        descriptor = os.open(os.sep, flags)
        try:
            parent = os.path.dirname(self.path)
            components = [part for part in parent.split(os.sep) if part]
            for component in components:
                try:
                    child = os.open(component, flags, dir_fd=descriptor)
                except FileNotFoundError:
                    try:
                        os.mkdir(component, 0o700, dir_fd=descriptor)
                    except FileExistsError:
                        pass
                    child = os.open(component, flags, dir_fd=descriptor)
                    os.fchmod(child, 0o700)
                metadata = os.fstat(child)
                if not stat.S_ISDIR(metadata.st_mode):
                    os.close(child)
                    raise ValueError(
                        "idempotency parent path must contain only directories"
                    )
                os.close(descriptor)
                descriptor = child
            metadata = os.fstat(descriptor)
            if metadata.st_uid != os.geteuid():
                raise PermissionError(
                    "idempotency parent directory must be owned by this process"
                )
            if stat.S_IMODE(metadata.st_mode) & 0o077:
                raise PermissionError(
                    "idempotency parent directory must have private 0700 permissions"
                )
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def _prepare_file(self) -> None:
        assert self._parent_fd is not None
        flags = (
            os.O_CREAT | os.O_RDWR | os.O_CLOEXEC
            | os.O_NOFOLLOW | os.O_NONBLOCK
        )
        descriptor = os.open(
            self.name, flags, 0o600, dir_fd=self._parent_fd
        )
        try:
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
                or metadata.st_uid != os.geteuid()
            ):
                raise ValueError(
                    "idempotency path must be an owned, single-link regular file"
                )
            os.fchmod(descriptor, 0o600)
        finally:
            os.close(descriptor)

    def _connect(self) -> sqlite3.Connection:
        if self._parent_fd is None:
            raise IdempotencyError("idempotency store is closed")
        pinned_path = (
            f"/proc/self/fd/{self._parent_fd}/{quote(self.name, safe='')}"
        )
        connection = sqlite3.connect(
            f"file:{pinned_path}?mode=rw",
            uri=True, timeout=5, isolation_level=None,
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

    def close(self) -> None:
        """Close the pinned directory descriptor."""
        if self._parent_fd is not None:
            os.close(self._parent_fd)
            self._parent_fd = None

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
