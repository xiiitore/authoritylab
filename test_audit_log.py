import json
import tempfile
import unittest
from pathlib import Path

from authoritylab.audit_log import DurableAuditLog


class DurableAuditLogTests(unittest.TestCase):
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

    def test_missing_file_is_a_valid_empty_log(self):
        with tempfile.TemporaryDirectory() as directory:
            log = DurableAuditLog(str(Path(directory) / "not-created.jsonl"))
            self.assertTrue(log.verify())

    def test_non_mapping_event_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            log = DurableAuditLog(str(Path(directory) / "audit.jsonl"))
            with self.assertRaises(TypeError):
                log.append("not-a-mapping")


if __name__ == "__main__":
    unittest.main()
