"""End-to-end smoke check for the reference Termux MCP server over stdio.

Run in the Termux virtual environment with AuthorityLab installed in a target
directory and that directory included in PYTHONPATH. The script never prints
file contents and never writes to the shared directory.
"""

from __future__ import annotations

import ast
import asyncio
import json
import os
import sys
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

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER)],
        env=dict(os.environ),
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
            if status.isError:
                raise AssertionError("status tool returned an MCP error")
            print("PASS: status tool call over stdio")

            listing = await session.call_tool("list_files", {})
            if listing.isError:
                raise AssertionError("list_files tool returned an MCP error")
            print("PASS: list_files tool call over stdio")

            # Exercise a successful read without printing its contents.
            names_in_share = _extract_string_list(listing)
            if names_in_share:
                read_result = await session.call_tool(
                    "read_file", {"path": names_in_share[0]}
                )
                if read_result.isError:
                    raise AssertionError("read_file failed on a listed file")
                print("PASS: read_file tool call over stdio (content withheld)")
            else:
                print("SKIP: valid read_file call; mcp-share contains no listed files")

            rejected = await session.call_tool(
                "read_file", {"path": "../authoritylab-outside-root-check"}
            )
            if not rejected.isError:
                raise AssertionError("parent-traversal read was not rejected")
            print("PASS: parent-traversal request rejected over stdio")


if __name__ == "__main__":
    asyncio.run(main())
