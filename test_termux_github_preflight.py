"""Regression tests for the read-only Termux GitHub preflight."""
import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).parent / "scripts" / "termux_github_preflight.py"
SPEC = importlib.util.spec_from_file_location("termux_github_preflight", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SafeRemoteTests(unittest.TestCase):
    def test_https_remote_does_not_expose_userinfo_or_query(self):
        value = MODULE.safe_remote(
            "https://user:secret-token@github.com/xiiitore/authoritylab.git?token=other-secret"
        )
        self.assertEqual(value, "github.com/xiiitore/authoritylab")
        self.assertNotIn("secret", value)
        self.assertNotIn("token", value)

    def test_ssh_remote_is_normalized(self):
        self.assertEqual(
            MODULE.safe_remote("git@github.com:xiiitore/authoritylab.git"),
            "github.com/xiiitore/authoritylab",
        )

    def test_unrecognized_remote_is_withheld(self):
        value = MODULE.safe_remote("https://github.com/")
        self.assertIn("value withheld", value)


if __name__ == "__main__":
    unittest.main()
