"""CI coverage for the executable authority-boundary matrix."""
import unittest

from authoritylab.authority_boundary_matrix import cases, execute_case


class AuthorityBoundaryMatrixTests(unittest.TestCase):
    def test_every_scenario_matches_its_declared_status(self):
        rows = [execute_case(case) for case in cases()]
        self.assertEqual(len(rows), 9)
        failures = [row for row in rows if not row["case_pass"]]
        self.assertEqual(failures, [])

    def test_execution_only_baseline_false_accepts_are_explicit_and_reproducible(self):
        rows = [execute_case(case) for case in cases()]
        false_accepts = [row["case"] for row in rows if row["baseline_false_accept"]]
        self.assertEqual(
            false_accepts,
            [
                "schema_missing",
                "required_field_missing",
                "semantic_validator_missing",
                "semantic_validator_rejects",
                "semantic_validator_raises",
                "audit_persistence_fails",
            ],
        )

    def test_untrusted_handler_is_not_executed(self):
        row = execute_case(next(case for case in cases() if case["name"] == "handler_not_trusted"))
        self.assertEqual(row["observed"], "BLOCKED")
        self.assertEqual(row["handler_calls"], 0)
        self.assertFalse(row["baseline_false_accept"])


if __name__ == "__main__":
    unittest.main()
