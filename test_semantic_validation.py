import unittest

from authoritylab import CheckStatus
from authoritylab.semantic_validation import (
    SemanticValidationResult,
    SemanticValidatorRegistry,
)


class SemanticValidatorRegistryTests(unittest.TestCase):
    def test_registered_validator_passes_explicit_domain_check(self):
        registry = SemanticValidatorRegistry()
        registry.register("lookup", lambda evidence: SemanticValidationResult(
            CheckStatus.PASS, "source identifier matches the domain contract"
        ))
        result = registry.validate("lookup", {"source_id": "source-1"})
        self.assertEqual(result.status, CheckStatus.PASS)

    def test_validator_can_reject_semantically_invalid_evidence(self):
        registry = SemanticValidatorRegistry()
        registry.register("lookup", lambda evidence: SemanticValidationResult(
            CheckStatus.FAIL, "source identifier is not in the trusted catalogue"
        ))
        result = registry.validate("lookup", {"source_id": "untrusted"})
        self.assertEqual(result.status, CheckStatus.FAIL)

    def test_missing_validator_is_unknown(self):
        registry = SemanticValidatorRegistry()
        result = registry.validate("lookup", {"source_id": "x"})
        self.assertEqual(result.status, CheckStatus.UNKNOWN)

    def test_validator_exception_fails_closed_without_leaking_message(self):
        registry = SemanticValidatorRegistry()
        def broken(evidence):
            raise RuntimeError("private token value")
        registry.register("lookup", broken)
        result = registry.validate("lookup", {"source_id": "x"})
        self.assertEqual(result.status, CheckStatus.UNKNOWN)
        self.assertIn("RuntimeError", result.detail)
        self.assertNotIn("private token", result.detail)

    def test_invalid_return_type_is_unknown(self):
        registry = SemanticValidatorRegistry()
        registry.register("lookup", lambda evidence: True)
        self.assertEqual(
            registry.validate("lookup", {}).status, CheckStatus.UNKNOWN
        )

    def test_duplicate_and_invalid_registrations_are_rejected(self):
        registry = SemanticValidatorRegistry()
        validator = lambda evidence: SemanticValidationResult(CheckStatus.PASS, "ok")
        registry.register(" lookup ", validator)
        with self.assertRaises(ValueError):
            registry.register("lookup", validator)
        with self.assertRaises(TypeError):
            registry.register("other", None)
        with self.assertRaises(ValueError):
            registry.register(" ", validator)

    def test_result_requires_valid_status_and_detail(self):
        with self.assertRaises(TypeError):
            SemanticValidationResult("PASS", "ok")
        with self.assertRaises(ValueError):
            SemanticValidationResult(CheckStatus.PASS, " ")


if __name__ == "__main__":
    unittest.main()
