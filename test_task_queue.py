import tempfile
import unittest
from pathlib import Path

from authoritylab.task_queue import DurableTaskQueue, LeaseLost


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class DurableTaskQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.database = Path(self.temp.name) / "tasks.sqlite3"
        self.queue = DurableTaskQueue(self.database, clock=self.clock)

    def tearDown(self):
        self.temp.cleanup()

    def test_checkpoint_survives_reopen_and_expired_lease_reclaims(self):
        task = self.queue.enqueue("build", {"repo": "authoritylab"}, max_attempts=3)
        claimed = self.queue.claim("worker-a", lease_seconds=5)
        self.assertEqual(claimed.task_id, task.task_id)
        self.queue.checkpoint(task.task_id, "worker-a", {"step": "tests", "completed": 2})
        self.clock.advance(6)
        reopened = DurableTaskQueue(self.database, clock=self.clock)
        recovered = reopened.claim("worker-b", lease_seconds=10)
        self.assertEqual(recovered.task_id, task.task_id)
        self.assertEqual(recovered.attempt_count, 2)
        self.assertEqual(recovered.checkpoint, {"step": "tests", "completed": 2})
        with self.assertRaises(LeaseLost):
            reopened.complete(task.task_id, "worker-a", {"ok": True})
        reopened.complete(task.task_id, "worker-b", {"ok": True})
        self.assertEqual(reopened.get(task.task_id).status, "succeeded")

    def test_same_worker_stale_attempt_cannot_complete_reclaimed_task(self):
        task = self.queue.enqueue("build", {}, max_attempts=3)
        first_attempt = self.queue.claim("worker-a", lease_seconds=5)
        self.assertEqual(first_attempt.attempt_count, 1)

        self.clock.advance(6)
        second_attempt = self.queue.claim("worker-a", lease_seconds=10)
        self.assertEqual(second_attempt.attempt_count, 2)

        # The first attempt must not be able to complete the second attempt's lease.
        with self.assertRaises(LeaseLost):
            self.queue.complete(task.task_id, "worker-a", {"source": "stale attempt"})

        current = self.queue.get(task.task_id)
        self.assertEqual(current.status, "running")
        self.assertEqual(current.attempt_count, 2)

    def test_only_one_worker_can_claim_task(self):
        self.queue.enqueue("test", {})
        self.assertIsNotNone(self.queue.claim("worker-a"))
        self.assertIsNone(self.queue.claim("worker-b"))

    def test_retryable_failure_requeues_until_attempt_limit(self):
        task = self.queue.enqueue("deploy", {}, max_attempts=2)
        self.queue.claim("worker-a")
        retry = self.queue.fail(task.task_id, "worker-a", "transient", retry_delay=4)
        self.assertEqual(retry.status, "pending")
        self.assertIsNone(self.queue.claim("worker-b"))
        self.clock.advance(4)
        second = self.queue.claim("worker-b")
        self.assertEqual(second.attempt_count, 2)
        final = self.queue.fail(task.task_id, "worker-b", "still broken")
        self.assertEqual(final.status, "failed")
        self.assertIsNone(self.queue.claim("worker-c"))

    def test_non_retryable_failure_is_terminal(self):
        task = self.queue.enqueue("test", {})
        self.queue.claim("worker")
        failed = self.queue.fail(task.task_id, "worker", "policy denied", retryable=False)
        self.assertEqual(failed.status, "failed")

    def test_expired_last_attempt_is_marked_failed(self):
        task = self.queue.enqueue("test", {}, max_attempts=1)
        self.queue.claim("worker", lease_seconds=2)
        self.clock.advance(3)
        self.assertIsNone(self.queue.claim("another"))
        self.assertEqual(self.queue.get(task.task_id).status, "failed")

    def test_rejects_invalid_payload_and_limits(self):
        with self.assertRaises(ValueError):
            self.queue.enqueue("test", {"bad": float("nan")})
        with self.assertRaises(ValueError):
            self.queue.enqueue("test", {}, max_attempts=0)
        with self.assertRaises(TypeError):
            self.queue.checkpoint("missing", "worker", ["not", "an", "object"])

    def test_rejects_oversized_json_payload_checkpoint_and_result(self):
        # Queue contract: JSON payloads/checkpoints/results are limited to 1 MB
        # after UTF-8 encoding, before being persisted to SQLite.
        oversized = {"blob": "x" * 1_000_001}
        with self.assertRaisesRegex(ValueError, "size limit"):
            self.queue.enqueue("oversized", oversized)

        task = self.queue.enqueue("bounded", {})
        self.queue.claim("worker")
        with self.assertRaisesRegex(ValueError, "size limit"):
            self.queue.checkpoint(task.task_id, "worker", oversized)
        with self.assertRaisesRegex(ValueError, "size limit"):
            self.queue.complete(task.task_id, "worker", oversized)

        # Rejected data must not have changed the live task state.
        current = self.queue.get(task.task_id)
        self.assertEqual(current.status, "running")
        self.assertIsNone(current.result)

    def test_expired_lease_cannot_be_renewed(self):
        task = self.queue.enqueue("test", {})
        self.queue.claim("worker", lease_seconds=1)
        self.clock.advance(1)
        with self.assertRaises(LeaseLost):
            self.queue.heartbeat(task.task_id, "worker", lease_seconds=10)

    def test_error_text_is_redacted_before_persistence(self):
        task = self.queue.enqueue("test", {})
        self.queue.claim("worker")
        failed = self.queue.fail(
            task.task_id,
            "worker",
            "Authorization: Bearer abcdefghijklmnop",
            retryable=False,
        )
        self.assertNotIn("abcdefghijklmnop", failed.last_error)
        self.assertIn("[REDACTED]", failed.last_error)

    def test_invalid_lease_and_retry_delay_are_rejected(self):
        with self.assertRaises(ValueError):
            self.queue.claim("worker", lease_seconds=float("nan"))
        task = self.queue.enqueue("test", {})
        self.queue.claim("worker")
        with self.assertRaises(ValueError):
            self.queue.fail(task.task_id, "worker", "retry", retry_delay=float("inf"))


if __name__ == "__main__":
    unittest.main()
