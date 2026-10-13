"""Test-only reference gateway; not production cryptography or a real executor."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol


class Status(str, Enum):
    VALIDATION_PASS = "VALIDATION_PASS"
    EXECUTION_COMMITTED = "EXECUTION_COMMITTED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Claims:
    issuer: str
    subject: str
    audience: str
    token_id: str
    key_id: str
    issued_at: datetime
    not_before: datetime
    expires_at: datetime
    nonce: str
    request_id: str
    target_entity: str
    target_operation: str


@dataclass(frozen=True)
class VerifiedToken:
    claims: Claims
    signature_verified: bool


@dataclass(frozen=True)
class Result:
    status: Status
    transaction_id: str | None = None
    idempotent_replay: bool = False
    reason: str | None = None


class Verifier(Protocol):
    def verify_and_extract(self, raw_token: str) -> VerifiedToken: ...


class RevocationChecker(Protocol):
    def is_revoked(self, issuer: str, token_id: str, key_id: str) -> bool: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class Critic(Protocol):
    def audit(self, **kwargs: Any) -> Status: ...


class Gateway:
    def __init__(self, verifier: Verifier, revocations: RevocationChecker, clock: Clock,
                 *, issuer: str, audience: str, allowed_operations: set[str],
                 permissions: dict[str, set[str]], max_age_seconds: int = 300,
                 clock_skew_seconds: int = 5):
        if max_age_seconds <= 0 or clock_skew_seconds < 0:
            raise ValueError("invalid time policy")
        self.verifier, self.revocations, self.clock = verifier, revocations, clock
        self.issuer, self.audience = issuer, audience
        self.allowed_operations = frozenset(allowed_operations)
        self.permissions = {k: frozenset(v) for k, v in permissions.items()}
        self.max_age_seconds, self.clock_skew_seconds = max_age_seconds, clock_skew_seconds

    def authorize(self, raw_token: str, operation: str, entity: str) -> tuple[Claims | None, str | None]:
        try:
            verified = self.verifier.verify_and_extract(raw_token)
        except Exception:
            return None, "TOKEN_VERIFICATION_FAILED"
        if not isinstance(verified, VerifiedToken) or not verified.signature_verified:
            return None, "SIGNATURE_NOT_VERIFIED"
        c = verified.claims
        times = (c.issued_at, c.not_before, c.expires_at)
        if any(t.tzinfo is None or t.utcoffset() is None for t in times):
            return None, "TIMEZONE_REQUIRED"
        now = self.clock.now()
        if now.tzinfo is None or now.utcoffset() is None:
            return None, "TRUSTED_TIME_INVALID"
        now = now.astimezone(timezone.utc)
        issued, nbf, exp = (t.astimezone(timezone.utc) for t in times)
        skew = self.clock_skew_seconds
        if (issued - now).total_seconds() > skew:
            return None, "ISSUED_IN_FUTURE"
        if (nbf - now).total_seconds() > skew:
            return None, "NOT_YET_VALID"
        if now >= exp:
            return None, "TOKEN_EXPIRED"
        if exp <= issued:
            return None, "INVALID_TOKEN_LIFETIME"
        if (now - issued).total_seconds() > self.max_age_seconds:
            return None, "TOKEN_TOO_OLD"
        if c.issuer != self.issuer:
            return None, "ISSUER_MISMATCH"
        if c.audience != self.audience:
            return None, "AUDIENCE_MISMATCH"
        if operation not in self.allowed_operations:
            return None, "OPERATION_NOT_ALLOWED_BY_POLICY"
        if operation not in self.permissions.get(c.subject, frozenset()):
            return None, "SUBJECT_NOT_AUTHORIZED"
        if c.target_operation != operation or c.target_entity != entity:
            return None, "SCOPE_MISMATCH"
        try:
            if self.revocations.is_revoked(c.issuer, c.token_id, c.key_id):
                return None, "TOKEN_OR_KEY_REVOKED"
        except Exception:
            return None, "REVOCATION_STATUS_UNKNOWN"
        return c, None


class SQLiteStore:
    """Local test store. Real business effects must share its transaction boundary."""
    def __init__(self, path: str = ":memory:"):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS nonces(issuer TEXT NOT NULL, nonce TEXT NOT NULL, PRIMARY KEY(issuer,nonce));
        CREATE TABLE IF NOT EXISTS requests(request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
          issuer TEXT NOT NULL, nonce TEXT NOT NULL, state TEXT NOT NULL,
          transaction_id TEXT, reason TEXT);
        CREATE TABLE IF NOT EXISTS effects(transaction_id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE
          REFERENCES requests(request_id), entity TEXT NOT NULL, operation TEXT NOT NULL);
        """)

    @staticmethod
    def fingerprint(c: Claims, operation: str, entity: str) -> str:
        payload = {"issuer": c.issuer, "subject": c.subject, "audience": c.audience,
                   "request_id": c.request_id, "operation": operation, "entity": entity,
                   "token_id": c.token_id, "key_id": c.key_id, "nonce": c.nonce,
                   "issued_at": c.issued_at.astimezone(timezone.utc).isoformat(),
                   "not_before": c.not_before.astimezone(timezone.utc).isoformat(),
                   "expires_at": c.expires_at.astimezone(timezone.utc).isoformat(),
                   "target_entity": c.target_entity, "target_operation": c.target_operation}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def reserve(self, c: Claims, fingerprint: str) -> Result | None:
        with self.lock:
            cur = self.db.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                row = cur.execute("SELECT * FROM requests WHERE request_id=?", (c.request_id,)).fetchone()
                if row:
                    self.db.commit()
                    if row["fingerprint"] != fingerprint:
                        return Result(Status.BLOCKED, reason="REQUEST_ID_PAYLOAD_CONFLICT")
                    if row["state"] == "COMMITTED":
                        return Result(Status.EXECUTION_COMMITTED, row["transaction_id"], True, "IDEMPOTENT_REPLAY")
                    if row["state"] == "BLOCKED":
                        return Result(Status.BLOCKED, reason=row["reason"] or "PREVIOUSLY_BLOCKED")
                    return Result(Status.UNKNOWN, reason="PENDING_RECONCILIATION_REQUIRED")
                try:
                    cur.execute("INSERT INTO nonces VALUES (?,?)", (c.issuer, c.nonce))
                except sqlite3.IntegrityError:
                    self.db.rollback()
                    return Result(Status.BLOCKED, reason="NONCE_REPLAY")
                cur.execute("INSERT INTO requests(request_id,fingerprint,issuer,nonce,state) VALUES (?,?,?,?, 'PENDING')",
                            (c.request_id, fingerprint, c.issuer, c.nonce))
                self.db.commit()
                return None
            except Exception:
                self.db.rollback()
                raise

    def block(self, request_id: str, reason: str) -> None:
        with self.lock, self.db:
            self.db.execute("UPDATE requests SET state='BLOCKED',reason=? WHERE request_id=? AND state='PENDING'",
                            (reason, request_id))

    def commit(self, request_id: str, entity: str, operation: str) -> str:
        with self.lock:
            cur = self.db.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                row = cur.execute("SELECT state FROM requests WHERE request_id=?", (request_id,)).fetchone()
                if row is None or row["state"] != "PENDING":
                    raise RuntimeError("request is not pending")
                tx_id = "tx_" + hashlib.sha256(request_id.encode()).hexdigest()[:24]
                cur.execute("INSERT INTO effects VALUES (?,?,?,?)", (tx_id, request_id, entity, operation))
                cur.execute("UPDATE requests SET state='COMMITTED',transaction_id=? WHERE request_id=? AND state='PENDING'",
                            (tx_id, request_id))
                if cur.rowcount != 1:
                    raise RuntimeError("request state changed")
                self.db.commit()
                return tx_id
            except Exception:
                self.db.rollback()
                raise

    def effect_count(self, request_id: str | None = None) -> int:
        with self.lock:
            q = "SELECT COUNT(*) AS n FROM effects" if request_id is None else "SELECT COUNT(*) AS n FROM effects WHERE request_id=?"
            row = self.db.execute(q, () if request_id is None else (request_id,)).fetchone()
            return int(row["n"])

    def close(self) -> None:
        with self.lock:
            self.db.close()


class ExecutionCore:
    def __init__(self, gateway: Gateway, critic: Critic, store: SQLiteStore):
        self.gateway, self.critic, self.store = gateway, critic, store

    def execute(self, raw_token: str, operation: str, entity: str,
                contract: dict[str, Any] | None = None,
                tool_outputs: list[dict[str, Any]] | None = None) -> Result:
        claims, reason = self.gateway.authorize(raw_token, operation, entity)
        if claims is None:
            return Result(Status.BLOCKED, reason=reason or "AUTHORIZATION_FAILED")
        fingerprint = self.store.fingerprint(claims, operation, entity)
        try:
            prior = self.store.reserve(claims, fingerprint)
        except Exception:
            return Result(Status.UNKNOWN, reason="RESERVATION_OUTCOME_UNKNOWN")
        if prior is not None:
            return prior
        try:
            critic_status = self.critic.audit(request_id=claims.request_id, operation=operation,
                entity=entity, contract=contract or {}, untrusted_tool_outputs=tool_outputs or [])
        except Exception:
            self.store.block(claims.request_id, "CRITIC_FAILURE")
            return Result(Status.BLOCKED, reason="CRITIC_FAILURE")
        if critic_status != Status.VALIDATION_PASS:
            self.store.block(claims.request_id, "CRITIC_REJECTED")
            return Result(Status.BLOCKED, reason="CRITIC_REJECTED")
        try:
            tx_id = self.store.commit(claims.request_id, entity, operation)
            return Result(Status.EXECUTION_COMMITTED, tx_id)
        except Exception:
            return Result(Status.UNKNOWN, reason="COMMIT_OUTCOME_REQUIRES_RECONCILIATION")


# Explicit test doubles only. These are not production cryptography or revocation.
class StaticVerifier:
    def __init__(self, tokens: dict[str, VerifiedToken]): self.tokens = tokens
    def verify_and_extract(self, raw_token: str) -> VerifiedToken:
        if raw_token not in self.tokens: raise ValueError("unknown test token")
        return self.tokens[raw_token]


class StaticRevocations:
    def __init__(self): self.revoked: set[tuple[str, str, str]] = set(); self.unavailable = False
    def is_revoked(self, issuer: str, token_id: str, key_id: str) -> bool:
        if self.unavailable: raise ConnectionError("test service unavailable")
        return (issuer, token_id, key_id) in self.revoked


class FixedClock:
    def __init__(self, current: datetime): self.current = current
    def now(self) -> datetime: return self.current


class PassCritic:
    def audit(self, **kwargs: Any) -> Status: return Status.VALIDATION_PASS
