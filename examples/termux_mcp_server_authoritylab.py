"""Reference integration of AuthorityLab with a read-only Termux MCP bridge.

Review before use. This is an example file, not an automatic installer; it does
not modify ~/termux_mcp_server.py. It preserves the existing mcp-share boundary.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import sys
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from authoritylab import GovernancePolicy, WorkflowCore, WorkflowReport
from authoritylab.secure_paths import (
    is_confined_directory,
    list_confined_files,
    read_confined_text_file,
)
from authoritylab.termux_mcp_adapter import (
    MCPAdapterError,
    dispatch_read_only_mcp_tool,
    register_read_only_mcp_tools,
)
from authoritylab.tools import ToolRegistry


ROOT = Path.home() / "mcp-share"
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
        "directory_exists": is_confined_directory(ROOT),
        "directory": str(ROOT),
        "max_file_bytes": MAX_FILE_BYTES,
    }


def _list_files_impl() -> list[str]:
    if not is_confined_directory(ROOT):
        return []
    return list_confined_files(ROOT, max_entries=100)


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


def _audit_report(report: WorkflowReport) -> None:
    """Write metadata-only audit records to stderr, never file contents."""
    record = {
        "audit": dict(report.audit),
        "status": report.status.value,
        "checks": [
            {"name": check.name, "status": check.status.value}
            for check in report.checks
        ],
        "tool_succeeded": (
            report.tool_result.ok if report.tool_result is not None else None
        ),
    }
    print(json.dumps(record, sort_keys=True), file=sys.stderr, flush=True)


def _dispatch(kind: str, payload: dict[str, Any]) -> Any:
    try:
        return dispatch_read_only_mcp_tool(
            workflow,
            kind=kind,
            payload=payload,
            audit_sink=_audit_report,
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
    names = [tool.name for tool in tools]
    print("Registered tools:")
    for name in names:
        print("-", name)
    expected = {"status", "list_files", "read_file"}
    if len(names) != len(expected) or set(names) != expected:
        raise RuntimeError(f"Unexpected MCP tool surface: {names!r}")

    result = await _resolve(server.call_tool("status", {}))
    if result is None:
        raise RuntimeError("Status tool returned no result")
    print("Status test:", result)


if __name__ == "__main__":
    if "--check" in sys.argv:
        asyncio.run(_check_server())
    else:
        server.run(transport="stdio")
