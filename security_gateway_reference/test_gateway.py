from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
import tempfile
import unittest

if __package__:
    from .gateway import (
        Claims, VerifiedToken, Status, Gateway, SQLiteStore, ExecutionCore,
        StaticVerifier, StaticRevocations, FixedClock, PassCritic,
    )
else:
    from security_gateway_reference.gateway import (
        Claims, VerifiedToken, Status, Gateway, SQLiteStore, ExecutionCore,
        StaticVerifier, StaticRevocations, FixedClock, PassCritic,
    )

NOW = datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc)


def claims(**changes):
    data = dict(issuer="issuer-A", subject="subject-1", audience="backend-service",
        token_id="token-1", key_id="key-1", issued_at=NOW-timedelta(seconds=10),
        not_before=NOW-timedelta(seconds=10), expires_at=NOW+timedelta(minutes=2),
        nonce="nonce-unique-001", request_id="request-001", target_entity="DATA_REF_100",
        target_operation="read")
    data.update(changes)
    return Claims(**data)


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.c = claims()
        self.verifier = StaticVerifier({"token-1": VerifiedToken(self.c, True)})
        self.revocations = StaticRevocations()
        self.store = SQLiteStore()
        self.gateway = Gateway(self.verifier, self.revocations, FixedClock(NOW), issuer="issuer-A",
            audience="backend-service", allowed_operations={"read", "delete"},
            permissions={"subject-1": {"read", "delete"}})
        self.core = ExecutionCore(self.gateway, PassCritic(), self.store)

    def tearDown(self):
        self.store.close()

    def test_wrong_audience_blocked(self):
        self.verifier.tokens["bad-aud"] = VerifiedToken(claims(audience="wrong"), True)
        r = self.core.execute("bad-aud", "read", "DATA_REF_100")
        self.assertEqual((r.status, r.reason), (Status.BLOCKED, "AUDIENCE_MISMATCH"))
        self.assertEqual(self.store.effect_count(), 0)

    def test_wrong_issuer_blocked(self):
        self.verifier.tokens["bad-iss"] = VerifiedToken(claims(issuer="wrong"), True)
        self.assertEqual(self.core.execute("bad-iss", "read", "DATA_REF_100").reason, "ISSUER_MISMATCH")

    def test_wrong_scope_blocked(self):
        r = self.core.execute("token-1", "delete", "DATA_REF_100")
        self.assertEqual((r.status, r.reason), (Status.BLOCKED, "SCOPE_MISMATCH"))
        self.assertEqual(self.store.effect_count(), 0)

    def test_revocation_outage_fails_closed(self):
        self.revocations.unavailable = True
        r = self.core.execute("token-1", "read", "DATA_REF_100")
        self.assertEqual(r.reason, "REVOCATION_STATUS_UNKNOWN")
        self.assertEqual(self.store.effect_count(), 0)

    def test_revoked_token_blocked(self):
        self.revocations.revoked.add(("issuer-A", "token-1", "key-1"))
        self.assertEqual(self.core.execute("token-1", "read", "DATA_REF_100").reason, "TOKEN_OR_KEY_REVOKED")

    def test_expired_and_future_tokens_blocked(self):
        self.verifier.tokens["expired"] = VerifiedToken(claims(expires_at=NOW-timedelta(seconds=1)), True)
        self.verifier.tokens["future"] = VerifiedToken(
            Claims(**{**self.c.__dict__, "issued_at": NOW+timedelta(minutes=1)}), True)
        self.assertEqual(self.core.execute("expired", "read", "DATA_REF_100").reason, "TOKEN_EXPIRED")
        self.assertEqual(self.core.execute("future", "read", "DATA_REF_100").reason, "ISSUED_IN_FUTURE")

    def test_blank_target_and_malformed_time_claims_blocked(self):
        self.verifier.tokens["blank-target"] = VerifiedToken(claims(target_entity=" "), True)
        self.verifier.tokens["naive-time"] = VerifiedToken(
            Claims(**{**self.c.__dict__, "issued_at": datetime(2026, 10, 13, 9, 59)}), True)
        self.assertEqual(self.core.execute("blank-target", "read", "DATA_REF_100").reason,
                         "CLAIMS_OR_TARGET_MISSING")
        self.assertEqual(self.core.execute("naive-time", "read", "DATA_REF_100").reason,
                         "TIMEZONE_REQUIRED")
        self.assertEqual(self.store.effect_count(), 0)

    def test_trusted_clock_failure_fails_closed(self):
        class BrokenClock:
            def now(self): raise RuntimeError("clock unavailable")
        gateway = Gateway(self.verifier, self.revocations, BrokenClock(), issuer="issuer-A",
            audience="backend-service", allowed_operations={"read"}, permissions={"subject-1": {"read"}})
        core = ExecutionCore(gateway, PassCritic(), self.store)
        self.assertEqual(core.execute("token-1", "read", "DATA_REF_100").reason,
                         "TRUSTED_TIME_UNKNOWN")
        self.assertEqual(self.store.effect_count(), 0)

    def test_unverified_signature_blocked(self):
        self.verifier.tokens["bad-signature"] = VerifiedToken(self.c, False)
        self.assertEqual(self.core.execute("bad-signature", "read", "DATA_REF_100").reason, "SIGNATURE_NOT_VERIFIED")

    def test_critic_cannot_authorize_and_rejection_has_no_effect(self):
        class OverreachingCritic:
            def audit(self, **kwargs): return Status.EXECUTION_COMMITTED
        core = ExecutionCore(self.gateway, OverreachingCritic(), self.store)
        r = core.execute("token-1", "read", "DATA_REF_100")
        self.assertEqual((r.status, r.reason), (Status.BLOCKED, "CRITIC_REJECTED"))
        self.assertEqual(self.store.effect_count(), 0)

    def test_same_request_retry_returns_same_transaction(self):
        a = self.core.execute("token-1", "read", "DATA_REF_100")
        b = self.core.execute("token-1", "read", "DATA_REF_100")
        self.assertEqual(a.status, Status.EXECUTION_COMMITTED)
        self.assertEqual(b.status, Status.EXECUTION_COMMITTED)
        self.assertTrue(b.idempotent_replay)
        self.assertEqual(a.transaction_id, b.transaction_id)
        self.assertEqual(self.store.effect_count(), 1)

    def test_nonce_replay_under_different_request_blocked(self):
        self.assertEqual(self.core.execute("token-1", "read", "DATA_REF_100").status, Status.EXECUTION_COMMITTED)
        c = claims(token_id="token-2", request_id="request-002")
        self.verifier.tokens["token-2"] = VerifiedToken(c, True)
        r = self.core.execute("token-2", "read", "DATA_REF_100")
        self.assertEqual((r.status, r.reason), (Status.BLOCKED, "NONCE_REPLAY"))
        self.assertEqual(self.store.effect_count(), 1)

    def test_request_id_cannot_be_reused_with_changed_security_context(self):
        self.core.execute("token-1", "read", "DATA_REF_100")
        c = claims(key_id="rotated-key", token_id="token-rotated", nonce="nonce-rotated")
        self.verifier.tokens["changed"] = VerifiedToken(c, True)
        r = self.core.execute("changed", "read", "DATA_REF_100")
        self.assertEqual((r.status, r.reason), (Status.BLOCKED, "REQUEST_ID_PAYLOAD_CONFLICT"))
        self.assertEqual(self.store.effect_count(), 1)

    def test_pending_request_returns_unknown(self):
        fp = self.store.fingerprint(self.c, "read", "DATA_REF_100")
        self.assertIsNone(self.store.reserve(self.c, fp))
        r = self.core.execute("token-1", "read", "DATA_REF_100")
        self.assertEqual(r.status, Status.UNKNOWN)
        self.assertEqual(r.reason, "PENDING_RECONCILIATION_REQUIRED")
        self.assertEqual(self.store.effect_count(), 0)

    def test_two_store_connections_commit_at_most_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "gateway.db")
            a, b = SQLiteStore(path), SQLiteStore(path)
            try:
                ca, cb = ExecutionCore(self.gateway, PassCritic(), a), ExecutionCore(self.gateway, PassCritic(), b)
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda core: core.execute("token-1", "read", "DATA_REF_100"), [ca, cb]))
                self.assertEqual(a.effect_count(), 1)
                committed = [r for r in results if r.status == Status.EXECUTION_COMMITTED]
                self.assertTrue(committed)
                self.assertTrue(all(r.transaction_id == committed[0].transaction_id for r in committed))
            finally:
                a.close()
                b.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
