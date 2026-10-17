"""Tests for the read-only Termux relay agent dispatch boundary."""
from __future__ import annotations

import unittest

from authoritylab.termux_relay_agent import RelayAgentError, dispatch


class FakeWorkspace:
    def status(self):
        return {"ready": True, "max_file_bytes": 200_000}

    def list_files(self, directory="."):
        return ["README.md", "docs/", "notes.txt"]

    def read_file(self, path):
        return "content:" + path


class AgentDispatchTests(unittest.TestCase):
    def setUp(self):
        self.workspace = FakeWorkspace()

    def test_status_returns_bounded_fields(self):
        self.assertEqual(
            dispatch(self.workspace, "status", {}),
            {"status": "ready", "max_file_bytes": 200_000},
        )

    def test_list_files_omits_directories(self):
        self.assertEqual(
            dispatch(self.workspace, "list_files", {}),
            ["README.md", "notes.txt"],
        )

    def test_read_file_dispatches_only_relative_path_argument(self):
        self.assertEqual(
            dispatch(self.workspace, "read_file", {"path": "README.md"}),
            "content:README.md",
        )
        with self.assertRaisesRegex(RelayAgentError, "invalid_arguments"):
            dispatch(self.workspace, "read_file", {"path": "README.md", "extra": True})

    def test_unknown_tool_is_rejected(self):
        with self.assertRaisesRegex(RelayAgentError, "tool_not_allowed"):
            dispatch(self.workspace, "run_shell", {"command": "id"})


if __name__ == "__main__":
    unittest.main()
