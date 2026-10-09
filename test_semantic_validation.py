import unittest

from authoritylab import (
    CheckStatus,
    EvidenceSchema,
    GovernancePolicy,
    SemanticValidationResult,
    SemanticValidatorRegistry,
    ToolResult,
    WorkflowStatus,
)
from authoritylab.verification import ResultVerifier


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
        self.assertEqual(registry.validate("lookup", {}).status, CheckStatus.UNKNOWN)

    def test_non_mapping_evidence_is_unknown_without_calling_validator(self):
        calls = []
        registry = SemanticValidatorRegistry()
        registry.register("lookup", lambda evidence: calls.append(True) or SemanticValidationResult(
            CheckStatus.PASS, "must not run"
        ))
        result = registry.validate("lookup", ["not", "a", "mapping"])
        self.assertEqual(result.status, CheckStatus.UNKNOWN)
        self.assertEqual(calls, [])

    def test_registered_task_kind_is_normalized_for_lookup(self):
        registry = SemanticValidatorRegistry()
        validator = lambda evidence: SemanticValidationResult(CheckStatus.PASS, "ok")
        registry.register(" lookup ", validator)
        self.assertIs(registry.resolve("lookup"), validator)
        self.assertIs(registry.resolve(" lookup "), validator)
        self.assertIsNone(registry.resolve("  "))

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


class SemanticVerifierIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.policy = GovernancePolicy(
            evidence_schemas=(EvidenceSchema("lookup", ("source_id", "claim")),)
        )

    def test_semantic_failure_prevents_workflow_pass(self):
        registry = SemanticValidatorRegistry()
        registry.register("lookup", lambda evidence: SemanticValidationResult(
            CheckStatus.FAIL, "claim conflicts with the registered source record"
        ))
        checks, status = ResultVerifier(registry).verify(
            ToolResult(ok=True, output={"source_id": "s-1", "claim": "wrong"}),
            self.policy, "lookup",
        )
        self.assertEqual(status, WorkflowStatus.FAIL)
        semantic = next(c for c in checks if c.name == "semantic_evidence_valid")
        self.assertEqual(semantic.status, CheckStatus.FAIL)

    def test_incomplete_structure_skips_semantic_validator(self):
        calls = []
        registry = SemanticValidatorRegistry()
        registry.register("lookup", lambda evidence: calls.append(True) or SemanticValidationResult(
            CheckStatus.PASS, "should not be reached"
        ))
        checks, status = ResultVerifier(registry).verify(
            ToolResult(ok=True, output={"source_id": "s-1"}), self.policy, "lookup"
        )
        self.assertEqual(status, WorkflowStatus.UNKNOWN)
        self.assertEqual(calls, [])
        semantic = next(c for c in checks if c.name == "semantic_evidence_valid")
        self.assertEqual(semantic.status, CheckStatus.UNKNOWN)

    def test_semantic_pass_is_reported_separately_from_structural_pass(self):
        registry = SemanticValidatorRegistry()
        registry.register("lookup", lambda evidence: SemanticValidationResult(
            CheckStatus.PASS, "source record and claim satisfy the domain rule"
        ))
        checks, status = ResultVerifier(registry).verify(
            ToolResult(ok=True, output={"source_id": "s-1", "claim": "valid"}),
            self.policy, "lookup",
        )
        self.assertEqual(status, WorkflowStatus.PASS)
        self.assertEqual([c.status for c in checks[-2:]], [CheckStatus.PASS, CheckStatus.PASS])

    def test_missing_task_validator_prevents_pass_when_semantic_mode_enabled(self):
        checks, status = ResultVerifier(SemanticValidatorRegistry()).verify(
            ToolResult(ok=True, output={"source_id": "s-1", "claim": "present"}),
            self.policy, "lookup",
        )
        self.assertEqual(status, WorkflowStatus.UNKNOWN)
        semantic = next(c for c in checks if c.name == "semantic_evidence_valid")
        self.assertEqual(semantic.status, CheckStatus.UNKNOWN)

    def test_semantic_registry_type_is_checked(self):
        with self.assertRaises(TypeError):
            ResultVerifier(object())


if __name__ == "__main__":
    unittest.main()
