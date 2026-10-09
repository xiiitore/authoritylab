"""Tests for the explicit MCP dispatch gate."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from authoritylab import Task, WorkflowCore, WorkflowStatus
from authoritylab.termux_mcp_adapter import (
    MCPAdapterError,
    dispatch_read_only_mcp_tool,
    register_read_only_mcp_tools,
)
from authoritylab.tools import ToolRegistry


class DispatchGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.status = Mock(return_value={
            "status": "ready",
            "directory_exists": True,
            "directory": "/tmp/mcp-share",
            "max_file_bytes": 200_000,
        })
        self.list_files = Mock(return_value=[])
        self.read_file = Mock(return_value="contents")
        registry = ToolRegistry()
        register_read_only_mcp_tools(
            registry,
            status=self.status,
            list_files=self.list_files,
            read_file=self.read_file,
        )
        self.core = WorkflowCore(registry)

    def test_allowlisted_operation_returns_verified_output(self) -> None:
        result = dispatch_read_only_mcp_tool(
            self.core, kind="status", payload={}
        )
        self.assertEqual(result, {"status": "ready"})
        self.status.assert_called_once_with()

    def test_unknown_operation_is_rejected_before_workflow(self) -> None:
        core = Mock()
        with self.assertRaises(MCPAdapterError):
            dispatch_read_only_mcp_tool(core, kind="execute_shell", payload={})
        core.run.assert_not_called()

    def test_nonpassing_report_raises_adapter_error(self) -> None:
        with self.assertRaisesRegex(MCPAdapterError, "did not pass"):
            dispatch_read_only_mcp_tool(
                self.core,
                kind="read_file",
                payload={"path": "../secret.txt"},
            )
        self.read_file.assert_not_called()

    def test_non_mapping_payload_is_rejected(self) -> None:
        with self.assertRaisesRegex(MCPAdapterError, "payload must be a mapping"):
            dispatch_read_only_mcp_tool(
                self.core, kind="status", payload=["unexpected"]  # type: ignore[arg-type]
            )
        self.status.assert_not_called()


if __name__ == "__main__":
    unittest.main()
