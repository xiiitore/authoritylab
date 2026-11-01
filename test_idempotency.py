import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from authoritylab.idempotency import (
    IdempotencyConflict,
    SQLiteIdempotencyStore,
)


class IdempotencyStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(
            self.temp.name, "state", "requests.sqlite3"
        )
        self.now = 1_800_000_000.0
        self.store = SQLiteIdempotencyStore(
            self.path, lease_seconds=30, clock=lambda: self.now
        )
        self.key = "client-request-key-0001"
        self.digest = "a" * 64

    def tearDown(self):
        self.temp.cleanup()

    def test_new_key_is_claimed_once(self):
        self.assertEqual(self.store.claim(self.key, self.digest), "CLAIMED")
        self.assertEqual(
            self.store.claim(self.key, self.digest), "IN_PROGRESS"
        )

    def test_terminal_state_survives_store_reopen(self):
        self.store.claim(self.key, self.digest)
        self.store.finish(self.key, self.digest, "COMPLETED")
        reopened = SQLiteIdempotencyStore(
            self.path, lease_seconds=30, clock=lambda: self.now
        )
        self.assertEqual(reopened.claim(self.key, self.digest), "COMPLETED")

    def test_same_key_with_different_payload_conflicts(self):
        self.store.claim(self.key, self.digest)
        with self.assertRaises(IdempotencyConflict):
            self.store.claim(self.key, "b" * 64)

    def test_expired_in_progress_claim_becomes_unknown_not_reclaimed(self):
        self.store.claim(self.key, self.digest)
        self.now += 31
        self.assertEqual(self.store.claim(self.key, self.digest), "UNKNOWN")
        self.assertEqual(self.store.claim(self.key, self.digest), "UNKNOWN")

    def test_finish_requires_matching_in_progress_claim(self):
        with self.assertRaises(IdempotencyConflict):
            self.store.finish(self.key, self.digest, "COMPLETED")

    def test_only_terminal_states_can_finish(self):
        self.store.claim(self.key, self.digest)
        with self.assertRaises(ValueError):
            self.store.finish(self.key, self.digest, "IN_PROGRESS")

    def test_invalid_idempotency_key_rejected(self):
        with self.assertRaises(ValueError):
            self.store.claim("short", self.digest)

    def test_invalid_request_digest_rejected(self):
        with self.assertRaises(ValueError):
            self.store.claim(self.key, "not-a-digest")

    def test_raw_idempotency_key_is_not_stored(self):
        self.store.claim(self.key, self.digest)
        with open(self.path, "rb") as handle:
            database_bytes = handle.read()
        self.assertNotIn(self.key.encode(), database_bytes)
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)

    def test_concurrent_claims_only_have_one_winner(self):
        other_key = "parallel-request-key-0002"
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(
                lambda _: self.store.claim(other_key, self.digest), range(8)
            ))
        self.assertEqual(results.count("CLAIMED"), 1)
        self.assertEqual(results.count("IN_PROGRESS"), 7)

    def test_get_reports_missing_and_terminal_states(self):
        self.assertIsNone(self.store.get(self.key, self.digest))
        self.store.claim(self.key, self.digest)
        self.store.finish(self.key, self.digest, "FAILED")
        self.assertEqual(self.store.get(self.key, self.digest), "FAILED")


if __name__ == "__main__":
    unittest.main()
