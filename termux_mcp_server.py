"""Read-only MCP stdio bridge governed by AuthorityLab WorkflowCore."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from authoritylab.core import WorkflowCore
from authoritylab.tools import ToolRegistry
from authoritylab.termux_workspace_tools import BoundedWorkspace
from authoritylab.termux_mcp_adapter import (
    MCPAdapterError,
    dispatch_read_only_mcp_tool,
    read_only_mcp_governance_policy,
    register_read_only_mcp_tools,
)


def build_server() -> Server:
    root = Path(os.environ.get("AUTHORITYLAB_ROOT", os.getcwd())).resolve()
    workspace = BoundedWorkspace(str(root))
    registry = ToolRegistry()

    register_read_only_mcp_tools(
        registry,
        status=lambda: {
            "status": "ready" if workspace.status().get("ready") is True else "not_ready",
            "directory_exists": root.is_dir(),
            "directory": str(root),
            "max_file_bytes": workspace.status().get("max_file_bytes"),
        },
        list_files=lambda: [
            name
            for name in workspace.list_files(".")
            if not name.endswith("/")
        ][:100],
        read_file=lambda path: workspace.read_file(path),
    )
    core = WorkflowCore(registry, policy=read_only_mcp_governance_policy())
    server = Server(
        "authoritylab-termux",
        version="0.2.3",
        instructions="Read-only workspace bridge. Only status, list_files, and read_file are exposed.",
    )

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="status",
                description="Get bounded workspace status.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            ),
            types.Tool(
                name="list_files",
                description="List direct file names in the workspace root.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            ),
            types.Tool(
                name="read_file",
                description="Read a UTF-8 file by relative path.",
                inputSchema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                    "additionalProperties": False,
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict[str, Any]
    ) -> list[types.TextContent]:
        if name in {"status", "list_files"}:
            if arguments:
                raise ValueError(f"{name} does not accept arguments")
            payload = {}
        elif name == "read_file":
            payload = arguments
        else:
            raise ValueError(f"Tool not allowlisted: {name}")

        try:
            result = dispatch_read_only_mcp_tool(
                core,
                kind=name,
                payload=payload,
            )
        except MCPAdapterError as exc:
            raise ValueError(str(exc)) from None

        return [
            types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False),
            )
        ]

    return server


async def main_async() -> None:
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
