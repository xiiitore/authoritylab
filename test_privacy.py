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
            "AWS access key AKIAABCDEFGHIJKLMNOP",
            "Slack token xoxb-1234567890-abcdefghij",
            "GitLab token glpat-123456789012345678901234",
            "npm token npm_123456789012345678901234",
            "PyPI token pypi-123456789012345678901234",
            "Google token ya29.123456789012345678901234",
            "-----BEGIN ENCRYPTED PRIVATE KEY-----\nencrypted-only-material\n-----END ENCRYPTED PRIVATE KEY-----",
            "-----BEGIN PRIVATE KEY-----\nprivate-material\n-----END PRIVATE KEY-----",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                result = redact_text(sample)
                self.assertNotIn("abcdefghijklmnop", result)
                self.assertNotIn("hunter2", result)
                self.assertNotIn("user:password", result)
                self.assertNotIn("ghp_" + ("A" * 25), result)
                self.assertNotIn("github_pat_" + ("B" * 25), result)
                self.assertNotIn("AKIAABCDEFGHIJKLMNOP", result)
                self.assertNotIn("xoxb-1234567890-abcdefghij", result)
                self.assertNotIn("glpat-123456789012345678901234", result)
                self.assertNotIn("npm_123456789012345678901234", result)
                self.assertNotIn("pypi-123456789012345678901234", result)
                self.assertNotIn("ya29.123456789012345678901234", result)
                self.assertNotIn("private-material", result)
                self.assertNotIn("encrypted-only-material", result)

    def test_sensitive_url_query_parameters_are_redacted(self):
        samples = [
            "https://example.invalid/callback?access_token=ACCESS_SECRET&state=keep-me",
            "https://example.invalid/callback?refresh_token=REFRESH_SECRET",
            "https://example.invalid/callback?id_token=ID_SECRET",
            "https://example.invalid/callback?client_secret=CLIENT_SECRET",
            "https://example.invalid/callback?api_key=API_SECRET",
            "https://example.invalid/callback?token=TOKEN_SECRET",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                result = redact_text(sample)
                for secret in (
                    "ACCESS_SECRET", "REFRESH_SECRET", "ID_SECRET",
                    "CLIENT_SECRET", "API_SECRET", "TOKEN_SECRET",
                ):
                    self.assertNotIn(secret, result)
        self.assertIn("state=keep-me", redact_text(samples[0]))
        self.assertIn("access_token=[REDACTED]", redact_text(samples[0]))

    def test_additional_sensitive_url_query_parameters_are_redacted(self):
        samples = [
            "https://example.invalid/callback?authorization=AUTH_SECRET&state=keep-me",
            "https://example.invalid/callback?cookie=COOKIE_SECRET",
            "https://example.invalid/callback?session_id=SESSION_SECRET",
            "https://example.invalid/callback?client_assertion=ASSERTION_SECRET",
            "https://example.invalid/callback?private_key=PRIVATE_KEY_SECRET",
            "https://example.invalid/callback?signature=SIGNATURE_SECRET",
        ]
        secrets = (
            "AUTH_SECRET", "COOKIE_SECRET", "SESSION_SECRET",
            "ASSERTION_SECRET", "PRIVATE_KEY_SECRET", "SIGNATURE_SECRET",
        )
        for sample, secret in zip(samples, secrets):
            with self.subTest(sample=sample):
                result = redact_text(sample)
                self.assertNotIn(secret, result)
                self.assertIn("[REDACTED]", result)
        self.assertIn("state=keep-me", redact_text(samples[0]))

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
