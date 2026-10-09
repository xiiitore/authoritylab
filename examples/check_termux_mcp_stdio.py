"""End-to-end smoke check for the reference Termux MCP server over stdio.

Run in the Termux virtual environment with AuthorityLab installed in a target
directory and that directory included in PYTHONPATH. The script never prints
file contents and uses an isolated temporary home for its read fixture.
"""

from __future__ import annotations

import ast
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVER = Path(__file__).with_name("termux_mcp_server_authoritylab.py")
EXPECTED_TOOLS = {"status", "list_files", "read_file"}


def _extract_string_list(result: object) -> list[str]:
    """Decode list_files output across common MCP SDK result encodings."""
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, list) and all(isinstance(x, str) for x in structured):
        return structured
    if isinstance(structured, dict):
        for key in ("result", "value", "files"):
            value = structured.get(key)
            if isinstance(value, list) and all(isinstance(x, str) for x in value):
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
            if isinstance(value, list) and all(isinstance(x, str) for x in value):
                return value
    return []


async def main() -> None:
    if not SERVER.is_file():
        raise RuntimeError(f"Reference server not found: {SERVER}")

    # Seed a valid fixture in a temporary HOME. This does not touch the user's
    # real ~/mcp-share directory and lets the smoke test require a positive read.
    with tempfile.TemporaryDirectory(prefix="authoritylab-mcp-stdio-") as temp_home:
        share = Path(temp_home) / "mcp-share"
        share.mkdir()
        (share / "authoritylab-smoke-test.txt").write_text(
            "AuthorityLab isolated read test\\n", encoding="utf-8"
        )

        child_env = dict(os.environ)
        child_env["HOME"] = temp_home
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(SERVER)],
            env=child_env,
        )

        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                listed = await session.list_tools()
                names = {tool.name for tool in listed.tools}
                if names != EXPECTED_TOOLS or len(listed.tools) != len(EXPECTED_TOOLS):
                    raise AssertionError(f"Unexpected MCP tool surface: {sorted(names)!r}")
                print("PASS: MCP initialize and exact three-tool allowlist")

                status = await session.call_tool("status", {})
                if status.is_error:
                    raise AssertionError("status tool returned an MCP error")
                print("PASS: status tool call over stdio")

                listing = await session.call_tool("list_files", {})
                if listing.is_error:
                    raise AssertionError("list_files tool returned an MCP error")
                print("PASS: list_files tool call over stdio")

                listed_names = _extract_string_list(listing)
                fixture_name = "authoritylab-smoke-test.txt"
                if fixture_name not in listed_names:
                    raise AssertionError(
                        f"Isolated fixture missing from list_files: {listed_names!r}"
                    )

                read_result = await session.call_tool("read_file", {"path": fixture_name})
                if read_result.is_error:
                    raise AssertionError("read_file failed on the isolated fixture")
                print("PASS: read_file tool call over stdio (fixture content withheld)")

                rejected = await session.call_tool(
                    "read_file", {"path": "../authoritylab-outside-root-check"}
                )
                if not rejected.is_error:
                    raise AssertionError("parent-traversal read was not rejected")
                print("PASS: parent-traversal request rejected over stdio")


if __name__ == "__main__":
    asyncio.run(main())
