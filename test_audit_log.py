import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from authoritylab.audit_log import DurableAuditLog


class DurableAuditLogTests(unittest.TestCase):
    KEY = b"test-integrity-key-that-is-at-least-32-bytes-long"

    def test_append_generates_stable_ids_and_verifiable_hash_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "audit.jsonl")
            log = DurableAuditLog(path)
            first = log.append({"task_id": "task-1", "status": "PASS"})
            second = log.append({"task_id": "task-2", "status": "UNKNOWN"})
            self.assertNotEqual(first["event_id"], second["event_id"])
            self.assertTrue(log.verify())
            records = [json.loads(line) for line in Path(path).read_text().splitlines()]
            self.assertEqual(records[1]["previous_hash"], records[0]["hash"])
            self.assertEqual(records[0]["event"]["task_id"], "task-1")

    def test_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            log = DurableAuditLog(str(path))
            log.append({"task_id": "task-1", "status": "PASS"})
            record = json.loads(path.read_text())
            record["event"]["status"] = "FAIL"
            path.write_text(json.dumps(record) + "\n")
            with self.assertRaisesRegex(ValueError, "audit chain invalid"):
                log.verify()

    def test_signed_chain_verifies_only_with_the_correct_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "signed.jsonl")
            signed = DurableAuditLog(path, integrity_key=self.KEY)
            signed.append({"task_id": "signed-1", "status": "PASS"})
            self.assertTrue(signed.verify())
            with self.assertRaisesRegex(ValueError, "signature key required"):
                DurableAuditLog(path).verify()
            with self.assertRaisesRegex(ValueError, "signature invalid"):
                DurableAuditLog(path, integrity_key=b"x" * 32).verify()

    def test_hmac_detects_a_rewritten_hash_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "signed.jsonl"
            log = DurableAuditLog(str(path), integrity_key=self.KEY)
            log.append({"task_id": "signed-1", "status": "PASS"})
            record = json.loads(path.read_text())
            record["event"]["status"] = "FAIL"
            unhashed = {key: value for key, value in record.items() if key not in {"hash", "signature"}}
            canonical = json.dumps(unhashed, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
            record["hash"] = hashlib.sha256(canonical).hexdigest()
            path.write_text(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            with self.assertRaisesRegex(ValueError, "signature invalid"):
                log.verify()

    def test_signed_log_cannot_be_mixed_with_unsigned_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "mixed.jsonl")
            DurableAuditLog(path).append({"task_id": "unsigned", "status": "PASS"})
            signed = DurableAuditLog(path, integrity_key=self.KEY)
            with self.assertRaisesRegex(ValueError, "signature missing"):
                signed.append({"task_id": "signed", "status": "PASS"})

    def test_record_size_limit_rejects_append_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "bounded.jsonl")
            log = DurableAuditLog(path, max_record_bytes=256)
            with self.assertRaisesRegex(ValueError, "exceeds max_record_bytes"):
                log.append({"payload": "x" * 500})
            self.assertTrue(log.verify())
            self.assertEqual(Path(path).read_bytes(), b"")

    def test_symlink_audit_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target.jsonl"
            link = Path(directory) / "link.jsonl"
            target.write_text("")
            os.symlink(target, link)
            with self.assertRaises(OSError):
                DurableAuditLog(str(link)).append({"task_id": "x"})

    @unittest.skipUnless(callable(getattr(os, "link", None)), "os.link is unavailable on this Python build")
    def test_append_rejects_hard_link_without_mutating_target(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "ordinary.txt"
            audit_alias = Path(directory) / "audit.jsonl"
            target.write_text("preserve this file\\n", encoding="utf-8")
            os.link(target, audit_alias)
            before = target.read_bytes()
            with self.assertRaisesRegex(ValueError, "hard-linked audit files"):
                DurableAuditLog(str(audit_alias)).append({"task_id": "x"})
            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(audit_alias.read_bytes(), before)

    @unittest.skipUnless(callable(getattr(os, "link", None)), "os.link is unavailable on this Python build")
    def test_verify_rejects_hard_linked_audit_path(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "ordinary.txt"
            audit_alias = Path(directory) / "audit.jsonl"
            target.write_text("not an audit log\\n", encoding="utf-8")
            os.link(target, audit_alias)
            with self.assertRaisesRegex(ValueError, "hard-linked audit files"):
                DurableAuditLog(str(audit_alias)).verify()

    def test_constructor_rejects_weak_keys_and_invalid_record_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "audit.jsonl")
            with self.assertRaises(ValueError):
                DurableAuditLog(path, integrity_key=b"short")
            with self.assertRaises(ValueError):
                DurableAuditLog(path, max_record_bytes=0)
            with self.assertRaises(ValueError):
                DurableAuditLog(path, max_record_bytes=True)

    def test_missing_file_is_a_valid_empty_log(self):
        with tempfile.TemporaryDirectory() as directory:
            log = DurableAuditLog(str(Path(directory) / "not-created.jsonl"))
            self.assertTrue(log.verify())

    def test_non_mapping_event_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            log = DurableAuditLog(str(Path(directory) / "audit.jsonl"))
            with self.assertRaises(TypeError):
                log.append("not-a-mapping")


    def test_concurrent_appends_preserve_a_single_valid_chain(self):
        from concurrent.futures import ThreadPoolExecutor

        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "concurrent.jsonl")
            log = DurableAuditLog(path, integrity_key=self.KEY)
            count = 32
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(
                    lambda index: log.append({"task_id": f"task-{index}", "status": "PASS"}),
                    range(count),
                ))
            self.assertEqual(len({result["event_id"] for result in results}), count)
            self.assertTrue(log.verify())
            records = [json.loads(line) for line in Path(path).read_text().splitlines()]
            self.assertEqual(len(records), count)
            self.assertEqual(len({record["event"]["task_id"] for record in records}), count)
            self.assertEqual(records[0]["previous_hash"], "0" * 64)
            for previous, current in zip(records, records[1:]):
                self.assertEqual(current["previous_hash"], previous["hash"])

    def test_truncated_final_record_is_rejected_and_not_silently_repaired(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "truncated.jsonl"
            log = DurableAuditLog(str(path))
            log.append({"task_id": "task-1", "status": "PASS"})
            with path.open("ab") as stream:
                stream.write(b'{"event_id":"partial"')
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "audit chain invalid"):
                log.verify()
            with self.assertRaisesRegex(ValueError, "audit chain invalid"):
                log.append({"task_id": "task-2", "status": "PASS"})
            self.assertEqual(path.read_bytes(), before)


    def test_non_finite_json_constants_are_rejected_as_invalid_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "non-finite.jsonl"
            path.write_text(
                '{"event_id":"x","recorded_at":"now","previous_hash":"'
                + ("0" * 64)
                + '","event":{"value":NaN},"hash":"'
                + ("0" * 64)
                + '"}\\n'
            )
            with self.assertRaisesRegex(ValueError, "audit chain invalid"):
                DurableAuditLog(str(path)).verify()

    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.jsonl"
            path.write_text(
                '{"event_id":"first","event_id":"second","recorded_at":"now",'
                '"previous_hash":"' + ("0" * 64) + '","event":{},"hash":"' + ("0" * 64) + '"}\\n'
            )
            with self.assertRaisesRegex(ValueError, "audit chain invalid"):
                DurableAuditLog(str(path)).verify()

    def test_invalid_utf8_is_rejected_as_invalid_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid-utf8.jsonl"
            path.write_bytes(b'{"event_id":"x","event":\\xff}\\n')
            with self.assertRaisesRegex(ValueError, "audit chain invalid"):
                DurableAuditLog(str(path)).verify()


if __name__ == "__main__":
    unittest.main()
