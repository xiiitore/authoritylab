"""End-to-end smoke test for the read-only MCP server over stdio.

Uses a fresh temporary Git repository and never accesses the user's checkout.
"""
from __future__ import annotations

import ast
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import Client, StdioServerParameters

EXPECTED_TOOLS = {"status", "list_files", "read_file", "diagnostics"}


def _extract_string_list(result: object) -> list[str]:
    structured = getattr(result, "structured_content", None)
    if structured is None:
        structured = getattr(result, "structuredContent", None)
    if isinstance(structured, list) and all(isinstance(item, str) for item in structured):
        return structured
    if isinstance(structured, dict):
        for key in ("result", "value", "files"):
            value = structured.get(key)
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                return value
    for block in getattr(result, "content", []):
        raw = getattr(block, "text", None)
        if not isinstance(raw, str):
            continue
        for parser in (json.loads, ast.literal_eval):
            try:
                value = parser(raw)
            except (TypeError, ValueError, SyntaxError):
                continue
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                return value
    return []


def _status_data(result: object) -> dict[str, object]:
    structured = getattr(result, "structured_content", None)
    if structured is None:
        structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        value = structured.get("result", structured)
        if isinstance(value, dict):
            return value
    for block in getattr(result, "content", []):
        raw = getattr(block, "text", None)
        if isinstance(raw, str):
            try:
                value = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if isinstance(value, dict):
                return value
    return {}


async def main() -> None:
    project_root = str(Path(__file__).resolve().parents[1])
    with tempfile.TemporaryDirectory(prefix="authoritylab-workspace-stdio-") as temp:
        root = Path(temp) / "repo"
        root.mkdir()
        (root / "sample.txt").write_text("read-only smoke test\n", encoding="utf-8")
        (root / "nested").mkdir()
        (root / "nested" / "inside.txt").write_text("nested fixture\n", encoding="utf-8")
        import subprocess
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

        async with Client(params) as client:
            listed = await client.list_tools()
            names = {tool.name for tool in listed.tools}
            if names != EXPECTED_TOOLS or len(listed.tools) != len(EXPECTED_TOOLS):
                raise AssertionError(f"Unexpected MCP tools: {sorted(names)!r}")
            print("PASS: server exposes exactly status, list_files, read_file, diagnostics")

            status = await client.call_tool("status", {})
            if status.is_error or _status_data(status).get("status") != "ready":
                raise AssertionError("status did not report a ready workspace")
            print("PASS: status")

            diagnostics = await client.call_tool("diagnostics", {})
            if diagnostics.is_error:
                raise AssertionError("diagnostics failed")
            diagnostic_data = _status_data(diagnostics)
            if not isinstance(diagnostic_data.get("python_version"), str):
                raise AssertionError("diagnostics did not return bounded Python metadata")
            if "paths" not in diagnostic_data or "selinux_context" not in diagnostic_data:
                raise AssertionError("diagnostics omitted expected runtime metadata")
            print("PASS: diagnostics returns bounded runtime metadata")

            files = await client.call_tool("list_files", {})
            if files.is_error:
                raise AssertionError("list_files failed")
            file_names = _extract_string_list(files)
            if "sample.txt" not in file_names or "nested" in file_names or "inside.txt" in file_names:
                raise AssertionError(f"list_files did not return direct file names only: {file_names!r}")
            print("PASS: list_files returns direct file names only")

            read = await client.call_tool("read_file", {"path": "sample.txt"})
            if read.is_error or "read-only smoke test" not in repr(read):
                raise AssertionError("read_file failed on an in-workspace file")
            print("PASS: read_file")

            rejected = await client.call_tool(
                "read_file", {"path": "../outside-read-check.txt"}
            )
            if not rejected.is_error:
                raise AssertionError("parent traversal was not rejected")
            print("PASS: parent traversal rejected")

            unknown = await client.call_tool("write_file", {})
            if not unknown.is_error:
                raise AssertionError("unexposed write_file tool was not rejected")
            print("PASS: write_file is not exposed")


if __name__ == "__main__":
    asyncio.run(main())
