"""Tests for the bounded Termux workspace operations."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from authoritylab.termux_workspace_tools import BoundedWorkspace, WorkspaceError


class BoundedWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        (self.root / ".git").mkdir()
        (self.root / "README.md").write_text("hello", encoding="utf-8")
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
        self.assertEqual(self.workspace.read_file("README.md"), "hello")
        self.workspace.write_file("new.txt", "world")
        self.assertEqual((self.root / "new.txt").read_text(encoding="utf-8"), "world")

    def test_rejects_absolute_parent_and_backslash_paths(self):
        for path in ("/etc/passwd", "../outside.txt", "sub/../../outside.txt", "a\\b"):
            with self.subTest(path=path), self.assertRaises(WorkspaceError):
                self.workspace.read_file(path)

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


if __name__ == "__main__":
    unittest.main()
