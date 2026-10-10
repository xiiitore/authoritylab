"""Tests for the bounded Termux workspace operations."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dulwich import porcelain

from authoritylab.termux_workspace_tools import BoundedWorkspace, WorkspaceError


class BoundedWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        porcelain.init(str(self.root))
        (self.root / "README.md").write_text("hello\n", encoding="utf-8")
        porcelain.add(str(self.root), paths=["README.md"])
        porcelain.commit(
            str(self.root),
            message=b"initial",
            author=b"Test User <test@example.com>",
            committer=b"Test User <test@example.com>",
        )
        self.workspace = BoundedWorkspace(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_status_has_fixed_allowlist(self):
        status = self.workspace.status()
        self.assertTrue(status["ready"])
        self.assertNotIn("shell", status["allowed_operations"])

    def test_list_skips_git_and_symlinks(self):
        outside = Path(self.temp.name) / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        (self.root / "link.txt").symlink_to(outside)
        entries = self.workspace.list_files()
        self.assertIn("README.md", entries)
        self.assertNotIn(".git/", entries)
        self.assertNotIn("link.txt", entries)

    def test_read_and_write_inside_workspace(self):
        self.assertEqual(self.workspace.read_file("README.md"), "hello\n")
        self.workspace.write_file("new.txt", "world")
        self.assertEqual((self.root / "new.txt").read_text(encoding="utf-8"), "world")

    def test_rejects_absolute_parent_and_backslash_paths(self):
        for path in ("/etc/passwd", "../outside.txt", "sub/../../outside.txt", "a\\b"):
            with self.subTest(path=path), self.assertRaises(WorkspaceError):
                self.workspace.read_file(path)

    def test_rejects_git_metadata_reads_and_writes(self):
        (self.root / ".git" / "config").write_text("[remote]", encoding="utf-8")
        for path in (".git/config", ".git/hooks/pre-commit", "nested/.git/config"):
            with self.subTest(path=path), self.assertRaises(WorkspaceError):
                self.workspace.read_file(path)
            with self.subTest(path=path), self.assertRaises(WorkspaceError):
                self.workspace.write_file(path, "changed")
        self.assertEqual(
            (self.root / ".git" / "config").read_text(encoding="utf-8"),
            "[remote]",
        )

    def test_rejects_symlink_reads_and_writes(self):
        outside = Path(self.temp.name) / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        (self.root / "link.txt").symlink_to(outside)
        with self.assertRaises(WorkspaceError):
            self.workspace.read_file("link.txt")
        with self.assertRaises(WorkspaceError):
            self.workspace.write_file("link.txt", "changed")
        self.assertEqual(outside.read_text(encoding="utf-8"), "secret")

    def test_rejects_large_content(self):
        with self.assertRaises(WorkspaceError):
            self.workspace.write_file("large.txt", "x" * 200_001)

    def test_rejects_non_git_directory(self):
        other = Path(self.temp.name) / "not-repo"
        other.mkdir()
        with self.assertRaises(ValueError):
            BoundedWorkspace(other)

    def test_rejects_directory_as_write_target(self):
        with self.assertRaises(WorkspaceError):
            self.workspace.write_file(".git", "not a directory")

    def test_git_status_reports_clean_branch_without_subprocess(self):
        status = self.workspace.git_status()
        self.assertTrue(status.startswith("## "))
        self.assertNotIn("?? ", status)
        self.assertNotIn(" M ", status)

    def test_git_status_reports_untracked_and_staged_changes(self):
        (self.root / "untracked.txt").write_text("new", encoding="utf-8")
        (self.root / "staged.txt").write_text("staged", encoding="utf-8")
        porcelain.add(str(self.root), paths=["staged.txt"])

        status = self.workspace.git_status()
        self.assertIn("?? untracked.txt", status)
        self.assertIn("A  staged.txt", status)

    def test_git_status_reports_unstaged_changes(self):
        (self.root / "README.md").write_text("changed\n", encoding="utf-8")
        status = self.workspace.git_status()
        self.assertIn(" M README.md", status)

    def test_git_diff_returns_unstaged_patch_without_subprocess(self):
        (self.root / "README.md").write_text("changed\n", encoding="utf-8")
        diff = self.workspace.git_diff()
        self.assertIn("README.md", diff)
        self.assertIn("-hello", diff)
        self.assertIn("+changed", diff)

    def test_git_diff_is_empty_for_clean_tree(self):
        self.assertEqual(self.workspace.git_diff(), "")

    def test_run_tests_reports_os_error_without_exposing_filename(self):
        error = PermissionError(13, "permission denied", "TOKEN_SENTINEL")
        with patch(
            "authoritylab.termux_workspace_tools.subprocess.run",
            side_effect=error,
        ):
            with self.assertRaises(WorkspaceError) as raised:
                self.workspace.run_tests()

        message = str(raised.exception)
        self.assertIn("operation could not start: PermissionError", message)
        self.assertIn("permission denied", message)
        self.assertIn("errno=13", message)
        self.assertNotIn("TOKEN_SENTINEL", message)
        self.assertNotIn("Traceback", message)


if __name__ == "__main__":
    unittest.main()
