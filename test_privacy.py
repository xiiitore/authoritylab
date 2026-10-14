import json
import tempfile
import unittest
from pathlib import Path

from authoritylab.audit_log import DurableAuditLog
from authoritylab.privacy import redact_sensitive_data, redact_text


class PrivacyRedactionTests(unittest.TestCase):
    def test_sensitive_mapping_keys_are_redacted_recursively(self):
        value = {
            "task": {
                "api_key": "example-secret-value",
                "ordinary": "keep this",
                "nested": [{"refresh_token": "refresh-secret"}],
            }
        }
        result = redact_sensitive_data(value)
        self.assertEqual(result["task"]["api_key"], "[REDACTED]")
        self.assertEqual(result["task"]["nested"][0]["refresh_token"], "[REDACTED]")
        self.assertEqual(result["task"]["ordinary"], "keep this")
        self.assertEqual(value["task"]["api_key"], "example-secret-value")

    def test_camel_case_credentials_and_personal_data_fields_are_redacted(self):
        result = redact_sensitive_data({
            "apiKey": "key-value",
            "accessToken": "token-value",
            "emailAddress": "owner@example.invalid",
            "phoneNumber": "+1-555-0100",
            "ordinary_label": "keep",
        })
        self.assertEqual(result["apiKey"], "[REDACTED]")
        self.assertEqual(result["accessToken"], "[REDACTED]")
        self.assertEqual(result["emailAddress"], "[REDACTED]")
        self.assertEqual(result["phoneNumber"], "[REDACTED]")
        self.assertEqual(result["ordinary_label"], "keep")

    def test_common_credential_patterns_are_redacted_in_text(self):
        samples = [
            "Authorization: Bearer abcdefghijklmnop",
            "ghp_" + ("A" * 25),
            "github_pat_" + ("B" * 25),
            "password=hunter2",
            "https://user:password@example.com/path",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                result = redact_text(sample)
                self.assertNotIn("abcdefghijklmnop", result)
                self.assertNotIn("hunter2", result)
                self.assertNotIn("user:password", result)
                self.assertNotIn("ghp_" + ("A" * 25), result)
                self.assertNotIn("github_pat_" + ("B" * 25), result)

    def test_non_json_values_are_not_serialized_with_repr(self):
        class SecretObject:
            def __repr__(self):
                return "password=must-not-leak"

        result = redact_sensitive_data({"value": SecretObject()})
        self.assertEqual(result["value"], "[NON_JSON_VALUE:SecretObject]")
        self.assertNotIn("must-not-leak", json.dumps(result))

    def test_excessive_nesting_is_redacted(self):
        value = {"a": {"b": {"c": "deep"}}}
        self.assertEqual(
            redact_sensitive_data(value, max_depth=2)["a"]["b"],
            "[MAX_DEPTH_REDACTED]",
        )

    def test_audit_log_redacts_before_persisting_and_keeps_chain_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            log = DurableAuditLog(str(path))
            log.append({
                "task_id": "privacy-test",
                "api_key": "private-api-key-value",
                "message": "Authorization: Bearer abcdefghijklmnop",
                "status": "PASS",
            })
            raw = path.read_text(encoding="utf-8")
            record = json.loads(raw)
            self.assertNotIn("private-api-key-value", raw)
            self.assertNotIn("abcdefghijklmnop", raw)
            self.assertEqual(record["event"]["api_key"], "[REDACTED]")
            self.assertTrue(log.verify())


if __name__ == "__main__":
    unittest.main()
