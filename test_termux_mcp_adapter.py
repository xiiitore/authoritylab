"""Tests for the restricted Termux MCP workflow adapter."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from authoritylab import Task, ToolResult, WorkflowCore, WorkflowStatus
from authoritylab.termux_mcp_adapter import register_read_only_mcp_tools
from authoritylab.tools import ToolRegistry


class TermuxMCPAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.status = Mock(return_value={
            "status": "ready",
            "directory_exists": True,
            "directory": "/tmp/mcp-share",
            "max_file_bytes": 200_000,
        })
        self.list_files = Mock(return_value=["notes.txt"])
        self.read_file = Mock(return_value="safe text")
        self.registry = ToolRegistry()
        register_read_only_mcp_tools(
            self.registry,
            status=self.status,
            list_files=self.list_files,
            read_file=self.read_file,
        )
        self.core = WorkflowCore(self.registry)

    def test_registers_only_the_three_read_only_tools(self) -> None:
        self.assertEqual(
            self.registry.registered_kinds(),
            ("list_files", "read_file", "status"),
        )

    def test_registration_conflict_does_not_partially_register_handlers(self) -> None:
        registry = ToolRegistry()
        registry.register("read_file", lambda task: ToolResult(ok=True, output="existing"))
        with self.assertRaisesRegex(ValueError, "handlers already registered"):
            register_read_only_mcp_tools(
                registry,
                status=self.status,
                list_files=self.list_files,
                read_file=self.read_file,
            )
        self.assertEqual(registry.registered_kinds(), ("read_file",))

    def test_status_calls_existing_tool(self) -> None:
        report = self.core.run(Task("t-status", "status"))
        self.assertEqual(report.status, WorkflowStatus.PASS)
        self.assertEqual(
            report.tool_result.output,
            {
                "status": "ready",
                "directory_exists": True,
                "directory": "/tmp/mcp-share",
                "max_file_bytes": 200_000,
            },
        )
        self.status.assert_called_once_with()

    def test_list_files_calls_existing_tool(self) -> None:
        report = self.core.run(Task("t-list", "list_files"))
        self.assertEqual(report.status, WorkflowStatus.PASS)
        self.assertEqual(report.tool_result.output, ["notes.txt"])
        self.list_files.assert_called_once_with()

    def test_read_file_calls_existing_tool_with_valid_relative_path(self) -> None:
        report = self.core.run(
            Task("t-read", "read_file", {"path": "notes.txt"})
        )
        self.assertEqual(report.status, WorkflowStatus.PASS)
        self.assertEqual(report.tool_result.output, "safe text")
        self.read_file.assert_called_once_with("notes.txt")

    def test_unknown_tool_is_blocked(self) -> None:
        report = self.core.run(Task("t-unknown", "execute_shell"))
        self.assertEqual(report.status, WorkflowStatus.BLOCKED)
        self.assertIsNone(report.route)

    def test_status_rejects_arguments_before_calling_tool(self) -> None:
        report = self.core.run(Task("t-status-args", "status", {"x": 1}))
        self.assertEqual(report.status, WorkflowStatus.FAIL)
        self.status.assert_not_called()

    def test_read_file_rejects_parent_traversal_before_calling_tool(self) -> None:
        report = self.core.run(
            Task("t-traversal", "read_file", {"path": "../private.txt"})
        )
        self.assertEqual(report.status, WorkflowStatus.FAIL)
        self.read_file.assert_not_called()

    def test_read_file_rejects_absolute_path_before_calling_tool(self) -> None:
        report = self.core.run(
            Task("t-absolute", "read_file", {"path": "/etc/passwd"})
        )
        self.assertEqual(report.status, WorkflowStatus.FAIL)
        self.read_file.assert_not_called()

    def test_read_file_requires_exact_path_argument(self) -> None:
        report = self.core.run(Task("t-missing", "read_file"))
        self.assertEqual(report.status, WorkflowStatus.FAIL)
        self.read_file.assert_not_called()

    def test_read_file_rejects_non_string_path(self) -> None:
        report = self.core.run(
            Task("t-type", "read_file", {"path": 123})
        )
        self.assertEqual(report.status, WorkflowStatus.FAIL)
        self.read_file.assert_not_called()

    def test_status_rejects_malformed_output(self) -> None:
        self.status.return_value = {"status": "ready"}
        report = self.core.run(Task("t-status-malformed", "status"))
        self.assertEqual(report.status, WorkflowStatus.FAIL)
        self.assertIn("malformed fields", report.tool_result.error)

    def test_list_files_rejects_non_string_entries(self) -> None:
        self.list_files.return_value = ["notes.txt", 7]
        report = self.core.run(Task("t-list-malformed", "list_files"))
        self.assertEqual(report.status, WorkflowStatus.FAIL)
        self.assertIn("list of strings", report.tool_result.error)

    def test_list_files_rejects_path_entries(self) -> None:
        self.list_files.return_value = ["../secret.txt"]
        report = self.core.run(Task("t-list-path", "list_files"))
        self.assertEqual(report.status, WorkflowStatus.FAIL)
        self.assertIn("direct file names", report.tool_result.error)

    def test_list_files_rejects_more_than_100_entries(self) -> None:
        self.list_files.return_value = [f"file-{i}.txt" for i in range(101)]
        report = self.core.run(Task("t-list-too-many", "list_files"))
        self.assertEqual(report.status, WorkflowStatus.FAIL)
        self.assertIn("at most 100", report.tool_result.error)

    def test_read_file_rejects_non_text_output(self) -> None:
        self.read_file.return_value = b"not text"
        report = self.core.run(
            Task("t-read-malformed", "read_file", {"path": "notes.txt"})
        )
        self.assertEqual(report.status, WorkflowStatus.FAIL)
        self.assertIn("must return text", report.tool_result.error)

    def test_tool_exception_does_not_pass(self) -> None:
        self.read_file.side_effect = OSError("read failed")
        report = self.core.run(
            Task("t-error", "read_file", {"path": "notes.txt"})
        )
        self.assertEqual(report.status, WorkflowStatus.FAIL)
        self.assertIn("OSError", report.tool_result.error)


if __name__ == "__main__":
    unittest.main()
