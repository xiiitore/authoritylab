"""Tests for the bounded Termux workspace operations."""
from __future__ import annotations

import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from dulwich import porcelain

from authoritylab import termux_mcp_server, termux_workspace_tools
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
        self.assertIn("diagnostics", status["allowed_operations"])

    def test_registered_diagnostics_tool_has_no_arguments(self):
        servers = []

        class FakeFastMCP:
            def __init__(self, name):
                self.name = name
                self.handlers = {}
                servers.append(self)

            def tool(self):
                def register(handler):
                    self.handlers[handler.__name__] = handler
                    return handler
                return register

            def run(self, transport):
                self.transport = transport

        mcp = ModuleType("mcp")
        mcp.__path__ = []
        server_package = ModuleType("mcp.server")
        server_package.__path__ = []
        fastmcp_module = ModuleType("mcp.server.fastmcp")
        fastmcp_module.FastMCP = FakeFastMCP
        with patch.dict(
            sys.modules,
            {
                "mcp": mcp,
                "mcp.server": server_package,
                "mcp.server.fastmcp": fastmcp_module,
            },
        ), patch.object(
            termux_mcp_server.os,
            "getcwd",
            return_value=str(self.root),
        ):
            termux_mcp_server.main()

        handler = servers[0].handlers["diagnostics"]
        self.assertEqual(list(inspect.signature(handler).parameters), [])

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

    def test_run_tests_reports_os_error_details_without_extra_data(self):
        with patch(
            "authoritylab.termux_workspace_tools.subprocess.run",
            side_effect=PermissionError(13, "permission denied"),
        ):
            with self.assertRaises(WorkspaceError) as raised:
                self.workspace.run_tests()

        message = str(raised.exception)
        self.assertIn("operation could not start: PermissionError", message)
        self.assertIn("permission denied", message)
        self.assertIn("errno=13", message)
        self.assertNotIn("Traceback", message)
        self.assertNotIn("TOKEN_SENTINEL", message)

    def test_diagnostics_has_fixed_scope_and_never_starts_subprocesses(self):
        files = "/data/data/com.termux/files"
        home = files + "/home"
        termux_usr = files + "/usr"
        expected_paths = {
            "root": "/",
            "data": "/data",
            "data_data": "/data/data",
            "termux_app": "/data/data/com.termux",
            "termux_files": files,
            "termux_usr": termux_usr,
            "termux_bin": termux_usr + "/bin",
            "home": home,
            "venv": home + "/mcp-venv",
            "venv_bin": home + "/mcp-venv/bin",
            "python_link": home + "/mcp-venv/bin/python",
            "python_target_link": termux_usr + "/bin/python",
            "python_binary": termux_usr + "/bin/python3.13",
        }
        self.assertEqual(
            list(inspect.signature(BoundedWorkspace.diagnostics).parameters),
            ["self"],
        )

        with (
            patch.object(
                termux_workspace_tools.os,
                "stat",
                wraps=termux_workspace_tools.os.stat,
            ) as stat_call,
            patch.object(
                termux_workspace_tools.os,
                "access",
                wraps=termux_workspace_tools.os.access,
            ) as access_call,
            patch.object(
                termux_workspace_tools.subprocess,
                "run",
                side_effect=AssertionError(
                    "diagnostics must not spawn a process"
                ),
            ),
        ):
            result = self.workspace.diagnostics()

        self.assertEqual(
            {
                label: path
                for label, path in termux_workspace_tools._DIAGNOSTIC_PATHS
            },
            expected_paths,
        )
        self.assertEqual(set(result["paths"]), set(expected_paths))
        self.assertEqual(
            {call.args[0] for call in stat_call.call_args_list},
            set(expected_paths.values()),
        )
        self.assertEqual(
            {call.args[0] for call in access_call.call_args_list},
            set(expected_paths.values()),
        )
        self.assertIn("uid", result)
        self.assertIn("euid", result)
        self.assertIn("sys_executable", result)
        self.assertIn("selinux_context", result)
        self.assertNotIn("/data/data", json.dumps(result))

    def test_diagnostics_sanitizes_access_and_proc_read_errors(self):
        with (
            patch.object(
                termux_workspace_tools.os,
                "stat",
                side_effect=PermissionError(13, "secret path TOKEN_SENTINEL"),
            ),
            patch.object(
                termux_workspace_tools.os,
                "access",
                side_effect=PermissionError(13, "secret path TOKEN_SENTINEL"),
            ),
            patch(
                "builtins.open",
                side_effect=PermissionError(13, "TOKEN_SENTINEL"),
            ),
        ):
            result = self.workspace.diagnostics()

        encoded = json.dumps(result)
        self.assertEqual(result["selinux_context"]["error"], "PermissionError")
        self.assertEqual(
            result["paths"]["python_link"]["stat"]["error"], "PermissionError"
        )
        self.assertEqual(
            result["paths"]["python_link"]["access_x"]["error"],
            "PermissionError",
        )
        self.assertNotIn("TOKEN_SENTINEL", encoded)
        self.assertNotIn("secret path", encoded)


if __name__ == "__main__":
    unittest.main()
