"""Regression tests for the read-only Termux MCP server wrapper."""
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from authoritylab.termux_mcp_server import build_server


class FakeServer:
    def __init__(self, **kwargs):
        self.options = kwargs
        self.registered = {}

    def tool(self):
        def register(function):
            self.registered[function.__name__] = function
            return function
        return register


class FakeWorkspace:
    def __init__(self, root: Path):
        self.root = root
        self.status_calls = 0

    def status(self):
        self.status_calls += 1
        return {"ready": True, "max_file_bytes": 12345}

    def list_files(self, path="."):
        return ["README.md"]

    def diagnostics(self):
        return {"ready": True}

    def read_file(self, path):
        return "content"


class TermuxMCPServerTests(unittest.TestCase):
    def test_status_calls_workspace_status_once(self) -> None:
        workspace = FakeWorkspace(Path("."))
        with (
            patch("authoritylab.termux_mcp_server.MCPServer", FakeServer),
            patch("authoritylab.termux_mcp_server.BoundedWorkspace", return_value=workspace),
            redirect_stderr(io.StringIO()),
        ):
            server = build_server()
            result = server.registered["status"]()

        self.assertEqual(workspace.status_calls, 1)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["max_file_bytes"], 12345)


if __name__ == "__main__":
    unittest.main()
