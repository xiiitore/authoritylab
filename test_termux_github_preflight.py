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

    def test_ssh_remote_query_and_fragment_are_never_returned(self):
        value = MODULE.safe_remote(
            "git@github.com:xiiitore/authoritylab.git?token=SECRET#fragment"
        )
        self.assertEqual(value, "github.com/xiiitore/authoritylab")
        self.assertNotIn("SECRET", value)
        self.assertNotIn("token", value)
        self.assertNotIn("fragment", value)

    def test_unrecognized_remote_is_withheld(self):
        value = MODULE.safe_remote("https://github.com/")
        self.assertIn("value withheld", value)

    def test_untrusted_host_is_withheld(self):
        value = MODULE.safe_remote("https://evil.example/owner/repo.git")
        self.assertIn("value withheld", value)


class OverallStatusTests(unittest.TestCase):
    def checks(self, working_tree="PASS", branch="PASS", origin="PASS"):
        return [
            {"name": "git", "status": "PASS", "detail": ""},
            {"name": "repository", "status": "PASS", "detail": ""},
            {"name": "branch", "status": branch, "detail": ""},
            {"name": "working_tree", "status": working_tree, "detail": ""},
            {"name": "origin", "status": origin, "detail": ""},
            # Optional authentication does not make a safe read-only preflight fail.
            {"name": "github_cli_auth", "status": "WARN", "detail": ""},
        ]

    def test_pass_requires_all_mandatory_checks_to_pass(self):
        self.assertEqual(MODULE.overall_status(self.checks()), "PASS")

    def test_dirty_worktree_blocks_overall_pass(self):
        self.assertEqual(
            MODULE.overall_status(self.checks(working_tree="FAIL")), "BLOCKED"
        )

    def test_missing_branch_blocks_overall_pass(self):
        self.assertEqual(
            MODULE.overall_status(self.checks(branch="FAIL")), "BLOCKED"
        )

    def test_unrecognized_origin_blocks_overall_pass(self):
        self.assertEqual(
            MODULE.overall_status(self.checks(origin="FAIL")), "BLOCKED"
        )


if __name__ == "__main__":
    unittest.main()
