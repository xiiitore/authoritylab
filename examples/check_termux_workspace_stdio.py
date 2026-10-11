"""End-to-end smoke test for the bounded workspace MCP server over stdio.

Uses a fresh temporary Git repository. It never reads or writes the user's
actual checkout and never prints fixture file contents.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from mcp import Client, StdioServerParameters

EXPECTED_TOOLS = {
    "status", "list_files", "read_file", "write_file",
    "git_status", "git_diff", "run_tests", "diagnostics",
}
MARKER = "authoritylab-safe-write-check"


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="authoritylab-workspace-stdio-") as temp:
        root = Path(temp) / "repo"
        root.mkdir()
        subprocess.run(
            ["git", "init", str(root)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        (root / "test_smoke.py").write_text(
            "import unittest\n\nclass WorkspaceSmoke(unittest.TestCase):\n"
            "    def test_fixture(self):\n        self.assertTrue(True)\n",
            encoding="utf-8",
        )

        child_env = {
            "AUTHORITYLAB_ROOT": str(root),
            "HOME": temp,
            "PATH": os.environ.get("PATH", ""),
            "LD_PRELOAD": os.environ.get("LD_PRELOAD", ""),
        }
        python_path = os.environ.get("PYTHONPATH")
        if python_path:
            child_env["PYTHONPATH"] = python_path

        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "authoritylab.termux_mcp_server"],
            env=child_env,
        )
        async with Client(params) as client:
            listed = await client.list_tools()
            names = {tool.name for tool in listed.tools}
            if names != EXPECTED_TOOLS or len(listed.tools) != len(EXPECTED_TOOLS):
                raise AssertionError(f"Unexpected workspace MCP tools: {sorted(names)!r}")
            print("PASS: workspace server exposes exactly eight allow-listed tools")

            for name, arguments in (
                ("status", {}),
                ("list_files", {}),
                ("git_status", {}),
                ("git_diff", {}),
                ("run_tests", {}),
                ("diagnostics", {}),
            ):
                result = await client.call_tool(name, arguments)
                if result.is_error:
                    raise AssertionError(f"{name} failed on a fresh temporary repository")
                print(f"PASS: {name} tool call")

            written = await client.call_tool(
                "write_file",
                {"path": "smoke.txt", "content": MARKER + "\\n"},
            )
            if written.is_error:
                raise AssertionError("write_file failed on the temporary repository")
            readback = await client.call_tool("read_file", {"path": "smoke.txt"})
            if readback.is_error or MARKER not in repr(readback):
                raise AssertionError("read_file did not return the temporary fixture marker")
            print("PASS: bounded write/read round-trip (fixture content withheld)")

            rejected_read = await client.call_tool(
                "read_file", {"path": "../outside-read-check.txt"}
            )
            if not rejected_read.is_error:
                raise AssertionError("parent-traversal read was not rejected")
            rejected_write = await client.call_tool(
                "write_file",
                {"path": "../outside-write-check.txt", "content": MARKER},
            )
            if not rejected_write.is_error:
                raise AssertionError("parent-traversal write was not rejected")
            if (Path(temp) / "outside-write-check.txt").exists():
                raise AssertionError("rejected write created a file outside the workspace")
            print("PASS: parent-traversal read/write rejected")

            outside = Path(temp) / "outside-link-target.txt"
            outside.write_text(MARKER, encoding="utf-8")
            os.symlink(outside, root / "symlink.txt")
            symlink_read = await client.call_tool("read_file", {"path": "symlink.txt"})
            symlink_write = await client.call_tool(
                "write_file", {"path": "symlink.txt", "content": "should-not-write"}
            )
            if not symlink_read.is_error or not symlink_write.is_error:
                raise AssertionError("symlink read/write was not rejected")
            if outside.read_text(encoding="utf-8") != MARKER:
                raise AssertionError("symlink operation changed the outside target")
            print("PASS: symlink read/write rejected")

            if not callable(getattr(os, "link", None)):
                print("SKIP: os.link unavailable; hard-link behavior not tested")
            else:
                source = root / "hardlink-source.txt"
                target = root / "hardlink-target.txt"
                source.write_text(MARKER, encoding="utf-8")
                try:
                    os.link(source, target)
                except (OSError, NotImplementedError) as exc:
                    print(
                        "SKIP: filesystem does not permit hard links "
                        f"({type(exc).__name__})"
                    )
                else:
                    hardlink_write = await client.call_tool(
                        "write_file",
                        {"path": "hardlink-target.txt", "content": "should-not-write"},
                    )
                    if not hardlink_write.is_error:
                        raise AssertionError("hard-linked target write was not rejected")
                    if source.read_text(encoding="utf-8") != MARKER:
                        raise AssertionError("hard-link rejection changed the source file")
                    print("PASS: hard-linked target write rejected")

if __name__ == "__main__":
    asyncio.run(main())
