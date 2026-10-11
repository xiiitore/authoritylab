"""End-to-end smoke test for the read-only MCP server over stdio.

Uses a fresh temporary Git repository and never accesses the user's checkout.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {"status", "list_files", "read_file"}


def is_error(result: object) -> bool:
    return bool(getattr(result, "isError", getattr(result, "is_error", False)))


def text_result(result: object) -> str:
    content = getattr(result, "content", [])
    if not content:
        raise AssertionError("MCP tool returned no content")
    value = getattr(content[0], "text", None)
    if not isinstance(value, str):
        raise AssertionError("MCP tool did not return text content")
    return value


async def main() -> None:
    project_root = str(Path(__file__).resolve().parents[1])
    with tempfile.TemporaryDirectory(prefix="authoritylab-workspace-stdio-") as temp:
        root = Path(temp) / "repo"
        root.mkdir()
        (root / "sample.txt").write_text("read-only smoke test\n", encoding="utf-8")
        (root / "nested").mkdir()
        (root / "nested" / "inside.txt").write_text("nested fixture\n", encoding="utf-8")
        subprocess.run(
            ["git", "init", str(root)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        child_env = {
            "AUTHORITYLAB_ROOT": str(root),
            "HOME": temp,
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": os.pathsep.join(
                part for part in (project_root, os.environ.get("PYTHONPATH", "")) if part
            ),
        }
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "authoritylab.termux_mcp_server"],
            env=child_env,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                listed = await session.list_tools()
                names = {tool.name for tool in listed.tools}
                if names != EXPECTED_TOOLS or len(listed.tools) != len(EXPECTED_TOOLS):
                    raise AssertionError(f"Unexpected MCP tools: {sorted(names)!r}")
                print("PASS: server exposes exactly status, list_files, read_file")

                status = await session.call_tool("status", arguments={})
                if is_error(status) or '"status": "ready"' not in text_result(status):
                    raise AssertionError("status did not report a ready workspace")
                print("PASS: status")

                files = await session.call_tool("list_files", arguments={})
                if is_error(files):
                    raise AssertionError("list_files failed")
                file_text = text_result(files)
                if "sample.txt" not in file_text or "inside.txt" in file_text:
                    raise AssertionError("list_files did not return direct files only")
                print("PASS: list_files returns direct file names only")

                read = await session.call_tool("read_file", arguments={"path": "sample.txt"})
                if is_error(read) or "read-only smoke test" not in text_result(read):
                    raise AssertionError("read_file failed on an in-workspace file")
                print("PASS: read_file")

                rejected = await session.call_tool(
                    "read_file", arguments={"path": "../outside-read-check.txt"}
                )
                if not is_error(rejected):
                    raise AssertionError("parent traversal was not rejected")
                print("PASS: parent traversal rejected")

                unknown = await session.call_tool("write_file", arguments={})
                if not is_error(unknown):
                    raise AssertionError("unexposed write_file tool was not rejected")
                print("PASS: write_file is not exposed")


if __name__ == "__main__":
    asyncio.run(main())
