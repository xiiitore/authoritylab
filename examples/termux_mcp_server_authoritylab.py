"""Reference integration of AuthorityLab with a read-only Termux MCP bridge.

Review before use. This is an example file, not an automatic installer; it does
not modify ~/termux_mcp_server.py. It preserves the existing mcp-share boundary.
"""

from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from authoritylab import GovernancePolicy, WorkflowCore
from authoritylab.secure_paths import read_confined_text_file
from authoritylab.termux_mcp_adapter import (
    MCPAdapterError,
    dispatch_read_only_mcp_tool,
    register_read_only_mcp_tools,
)
from authoritylab.tools import ToolRegistry


ROOT = (Path.home() / "mcp-share").resolve()
MAX_FILE_BYTES = 200_000

server = MCPServer(
    name="termux-authoritylab",
    version="0.2.0",
    instructions=(
        "Restricted Termux file bridge. "
        "Only inspect text files inside the dedicated mcp-share directory. "
        "Never execute shell commands or modify files."
    ),
)


def _status_impl() -> dict[str, Any]:
    return {
        "status": "ready",
        "directory_exists": ROOT.is_dir(),
        "directory": str(ROOT),
        "max_file_bytes": MAX_FILE_BYTES,
    }


def _list_files_impl() -> list[str]:
    if not ROOT.is_dir():
        return []

    result: list[str] = []
    for item in sorted(ROOT.iterdir()):
        if item.is_symlink() or not item.is_file():
            continue
        result.append(item.name)
        if len(result) >= 100:
            break

    return result


def _read_file_impl(relative_path: str) -> str:
    try:
        return read_confined_text_file(
            ROOT,
            relative_path,
            max_bytes=MAX_FILE_BYTES,
        )
    except (ValueError, FileNotFoundError, OSError, UnicodeError) as exc:
        raise ToolError(str(exc)) from None


registry = ToolRegistry()
register_read_only_mcp_tools(
    registry,
    status=_status_impl,
    list_files=_list_files_impl,
    read_file=_read_file_impl,
)
workflow = WorkflowCore(
    registry,
    GovernancePolicy(required_checks=("result_present", "tool_succeeded")),
)


def _dispatch(kind: str, payload: dict[str, Any]) -> Any:
    try:
        return dispatch_read_only_mcp_tool(
            workflow,
            kind=kind,
            payload=payload,
        )
    except MCPAdapterError as exc:
        raise ToolError(str(exc)) from None


@server.tool()
def status() -> dict[str, Any]:
    """Return bridge status and the permitted directory."""
    return _dispatch("status", {})


@server.tool()
def list_files() -> list[str]:
    """List regular files directly inside the permitted directory."""
    return _dispatch("list_files", {})


@server.tool()
def read_file(path: str) -> str:
    """Read a UTF-8 text file inside the permitted directory, up to 200 KB."""
    return _dispatch("read_file", {"path": path})


async def _resolve(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _check_server() -> None:
    tools = await _resolve(server.list_tools())
    print("Registered tools:")
    for tool in tools:
        print("-", tool.name)

    result = await _resolve(server.call_tool("status", {}))
    print("Status test:", result)


if __name__ == "__main__":
    if "--check" in sys.argv:
        asyncio.run(_check_server())
    else:
        server.run(transport="stdio")
