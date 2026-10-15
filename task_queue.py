"""SQLite-backed task leases and checkpoints for resumable workers.

This is persistence/coordination infrastructure, not an autonomous planner,
process supervisor, or security sandbox. Use a local filesystem with reliable
SQLite locking semantics; unverified network filesystems are unsupported.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import math
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


class QueueError(RuntimeError):
    """Base error for task queue operations."""


class LeaseLost(QueueError):
    """A worker no longer owns a live lease for the task."""


@dataclass(frozen=True)
class Task:
    task_id: str
    kind: str
    payload: dict[str, Any]
    status: str
    attempt_count: int
    max_attempts: int
    available_at: float
    lease_owner: str | None
    lease_expires_at: float | None
    checkpoint: dict[str, Any] | None
    result: dict[str, Any] | None
    last_error: str | None
    created_at: float
    updated_at: float


def _json_object(value: Any, name: str) -> str:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict")
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain finite JSON-compatible values") from exc


def _positive_finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive finite number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return number


class DurableTaskQueue:
    """Atomic claims, expiring worker leases, retries, and durable checkpoints."""

    def __init__(self, database: str | Path, *, clock=time.time) -> None:
        self.database = str(database)
        self._clock = clock
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN
                        ('pending', 'running', 'succeeded', 'failed')),
                    attempt_count INTEGER NOT NULL CHECK(attempt_count >= 0),
                    max_attempts INTEGER NOT NULL CHECK(max_attempts >= 1),
                    available_at REAL NOT NULL,
                    lease_owner TEXT,
                    lease_expires_at REAL,
                    checkpoint_json TEXT,
                    result_json TEXT,
                    last_error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS tasks_ready
                ON tasks(status, available_at, created_at)
            """)

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        try:
            yield connection
        except BaseException:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _decode(row: sqlite3.Row | None) -> Task | None:
        if row is None:
            return None
        return Task(
            task_id=row["task_id"], kind=row["kind"],
            payload=json.loads(row["payload_json"]), status=row["status"],
            attempt_count=row["attempt_count"], max_attempts=row["max_attempts"],
            available_at=row["available_at"], lease_owner=row["lease_owner"],
            lease_expires_at=row["lease_expires_at"],
            checkpoint=json.loads(row["checkpoint_json"]) if row["checkpoint_json"] else None,
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            last_error=row["last_error"], created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def enqueue(
        self, kind: str, payload: dict[str, Any], *, max_attempts: int = 3,
        task_id: str | None = None, available_at: float | None = None,
    ) -> Task:
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("kind must be a non-empty string")
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        if task_id is not None and (not isinstance(task_id, str) or not task_id.strip()):
            raise ValueError("task_id must be a non-empty string when supplied")
        payload_json = _json_object(payload, "payload")
        now = float(self._clock())
        ready_at = now if available_at is None else float(available_at)
        if not math.isfinite(ready_at):
            raise ValueError("available_at must be finite")
        identifier = task_id or str(uuid.uuid4())
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT INTO tasks
                (task_id, kind, payload_json, status, attempt_count, max_attempts,
                 available_at, created_at, updated_at)
                VALUES (?, ?, ?, 'pending', 0, ?, ?, ?, ?)""",
                (identifier, kind.strip(), payload_json, max_attempts, ready_at, now, now),
            )
            row = connection.execute("SELECT * FROM tasks WHERE task_id=?", (identifier,)).fetchone()
            connection.commit()
        return self._decode(row)

    def claim(self, worker_id: str, *, lease_seconds: float = 60) -> Task | None:
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id must be a non-empty string")
        lease = _positive_finite(lease_seconds, "lease_seconds")
        now = float(self._clock())
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """UPDATE tasks SET status='failed', lease_owner=NULL,
                   lease_expires_at=NULL,
                   last_error=COALESCE(last_error, 'lease expired; attempts exhausted'),
                   updated_at=?
                   WHERE status='running' AND lease_expires_at <= ?
                     AND attempt_count >= max_attempts""", (now, now)
            )
            row = connection.execute(
                """SELECT task_id FROM tasks
                   WHERE attempt_count < max_attempts AND
                     ((status='pending' AND available_at <= ?) OR
                      (status='running' AND lease_expires_at <= ?))
                   ORDER BY available_at, created_at, task_id LIMIT 1""",
                (now, now),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            task_id = row["task_id"]
            connection.execute(
                """UPDATE tasks SET status='running', attempt_count=attempt_count+1,
                   lease_owner=?, lease_expires_at=?, updated_at=?, last_error=NULL
                   WHERE task_id=?""",
                (worker_id.strip(), now + lease, now, task_id),
            )
            claimed = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            connection.commit()
        return self._decode(claimed)

    def _mutate_live_lease(
        self, task_id: str, worker_id: str, assignments: str, values: tuple[Any, ...],
    ) -> Task:
        now = float(self._clock())
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT task_id FROM tasks WHERE task_id=? AND status='running'
                   AND lease_owner=? AND lease_expires_at > ?""",
                (task_id, worker_id, now),
            ).fetchone()
            if row is None:
                raise LeaseLost(f"no live lease for task {task_id!r}")
            connection.execute(
                f"UPDATE tasks SET {assignments}, updated_at=? WHERE task_id=?",
                (*values, now, task_id),
            )
            updated = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            connection.commit()
        return self._decode(updated)

    def heartbeat(self, task_id: str, worker_id: str, *, lease_seconds: float = 60) -> Task:
        lease = _positive_finite(lease_seconds, "lease_seconds")
        return self._mutate_live_lease(
            task_id, worker_id, "lease_expires_at=?",
            (float(self._clock()) + lease,),
        )

    def checkpoint(self, task_id: str, worker_id: str, checkpoint: dict[str, Any]) -> Task:
        return self._mutate_live_lease(
            task_id, worker_id, "checkpoint_json=?",
            (_json_object(checkpoint, "checkpoint"),),
        )

    def complete(self, task_id: str, worker_id: str, result: dict[str, Any]) -> Task:
        return self._mutate_live_lease(
            task_id, worker_id,
            "status='succeeded', result_json=?, lease_owner=NULL, lease_expires_at=NULL",
            (_json_object(result, "result"),),
        )

    def fail(
        self, task_id: str, worker_id: str, error: str, *,
        retryable: bool = True, retry_delay: float = 0,
    ) -> Task:
        if not isinstance(error, str) or not error.strip():
            raise ValueError("error must be a non-empty string")
        if type(retryable) is not bool:
            raise ValueError("retryable must be a bool")
        if isinstance(retry_delay, bool) or not isinstance(retry_delay, (int, float)):
            raise ValueError("retry_delay must be a non-negative finite number")
        delay = float(retry_delay)
        if not math.isfinite(delay) or delay < 0:
            raise ValueError("retry_delay must be a non-negative finite number")
        now = float(self._clock())
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT attempt_count, max_attempts FROM tasks
                   WHERE task_id=? AND status='running' AND lease_owner=?
                     AND lease_expires_at > ?""",
                (task_id, worker_id, now),
            ).fetchone()
            if row is None:
                raise LeaseLost(f"no live lease for task {task_id!r}")
            retry = retryable and row["attempt_count"] < row["max_attempts"]
            connection.execute(
                """UPDATE tasks SET status=?, available_at=?, last_error=?,
                   lease_owner=NULL, lease_expires_at=NULL, updated_at=? WHERE task_id=?""",
                ("pending" if retry else "failed", now + delay if retry else now,
                 error.strip()[:2000], now, task_id),
            )
            updated = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            connection.commit()
        return self._decode(updated)

    def get(self, task_id: str) -> Task | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return self._decode(row)
