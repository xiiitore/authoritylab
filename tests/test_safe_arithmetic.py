import math
import unittest

from authoritylab.safe_arithmetic import check_number, safe_eval


class SafeArithmeticTests(unittest.TestCase):
    def test_arithmetic_and_allowlisted_functions(self):
        self.assertEqual(safe_eval("2 + 3 * 4"), 14)
        self.assertAlmostEqual(safe_eval("sqrt(9) + pi"), 3 + math.pi)
        self.assertEqual(safe_eval("max(2, 5, 3)"), 5)

    def test_rejects_code_unknown_names_and_keywords(self):
        for expression in (
            "__import__('os')",
            "x + 1",
            "open('x')",
            "sqrt(9, unexpected=1)",
            "[x for x in (1, 2)]",
        ):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                safe_eval(expression)

    def test_rejects_invalid_or_resource_heavy_expressions(self):
        for expression in ("", "   ", "1" * 513, "+".join(["1"] * 80), "2 ** 101"):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                safe_eval(expression)

    def test_rejects_non_finite_and_arithmetic_errors(self):
        for expression in ("1e309", "exp(10000)", "1 / 0", "sqrt(-1)"):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                safe_eval(expression)

    def test_rejects_non_text_input(self):
        with self.assertRaises(TypeError):
            safe_eval(4)  # type: ignore[arg-type]

    def test_check_number_and_tolerance_validation(self):
        self.assertTrue(check_number("2 + 2", 4)["match"])
        self.assertFalse(check_number("2 + 2", 5)["match"])
        for claimed in (True, float("nan"), float("inf"), "2"):
            with self.subTest(claimed=claimed), self.assertRaises(ValueError):
                check_number("2", claimed)  # type: ignore[arg-type]
        for tolerance in (-1, float("nan"), float("inf"), 2, True):
            with self.subTest(tolerance=tolerance), self.assertRaises(ValueError):
                check_number("2", 2, tolerance)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
