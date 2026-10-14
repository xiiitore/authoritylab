"""Read-only MCP stdio bridge governed by AuthorityLab WorkflowCore."""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from authoritylab.core import WorkflowCore
from authoritylab.tools import ToolRegistry
from authoritylab.termux_workspace_tools import BoundedWorkspace
from authoritylab.termux_mcp_adapter import (
    MCPAdapterError,
    dispatch_read_only_mcp_tool,
    read_only_mcp_governance_policy,
    register_read_only_mcp_tools,
)


def build_server() -> MCPServer:
    configured_root = Path(os.environ.get("AUTHORITYLAB_ROOT", os.getcwd())).expanduser()
    workspace = BoundedWorkspace(configured_root)
    root = workspace.root
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
    # This bridge applies its own operation allow-list and validates every payload
    # before invoking these three read-only handlers. It is a deliberate legacy
    # adapter boundary, not a general WorkflowCore authorization example.
    core = WorkflowCore(
        registry, policy=read_only_mcp_governance_policy(), legacy_mode=True
    )
    server = MCPServer(
        name="authoritylab-termux",
        version="0.2.5",
        instructions="Read-only workspace bridge. Only status, list_files, and read_file are exposed.",
    )

    def audit_report(event: Mapping[str, Any]) -> None:
        """Write metadata-only workflow records to stderr, never file contents."""
        print(json.dumps(dict(event), sort_keys=True), file=sys.stderr, flush=True)

    def dispatch(kind: str, payload: dict[str, Any]) -> Any:
        try:
            return dispatch_read_only_mcp_tool(
                core,
                kind=kind,
                payload=payload,
                audit_sink=audit_report,
            )
        except MCPAdapterError as exc:
            raise ToolError(str(exc)) from None

    @server.tool()
    def status() -> dict[str, Any]:
        """Return bounded workspace status."""
        return dispatch("status", {})

    @server.tool()
    def list_files() -> list[str]:
        """List direct file names in the workspace root."""
        return dispatch("list_files", {})

    @server.tool()
    def read_file(path: str) -> str:
        """Read a UTF-8 file by relative path."""
        return dispatch("read_file", {"path": path})

    return server


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
