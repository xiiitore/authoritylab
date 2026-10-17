"""Read-only MCP stdio bridge using bounded workspace operations directly."""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from authoritylab.termux_workspace_tools import BoundedWorkspace

ALLOWED_OPERATIONS = frozenset({"status", "list_files", "read_file"})


def build_server() -> MCPServer:
    configured_root = Path(os.environ.get("AUTHORITYLAB_ROOT", os.getcwd())).expanduser()
    workspace = BoundedWorkspace(configured_root)
    root = workspace.root

    server = MCPServer(
        name="authoritylab-termux",
        version="0.2.6",
        instructions="Read-only workspace bridge. Only status, list_files, and read_file are exposed.",
    )

    def audit_report(event: Mapping[str, Any]) -> None:
        """Write metadata-only records to stderr; never include file contents or paths."""
        print(json.dumps(dict(event), sort_keys=True), file=sys.stderr, flush=True)

    def dispatch(kind: str, payload: Mapping[str, Any] | None = None) -> Any:
        # Keep this server's operation allowlist explicit. Avoid routing ordinary
        # workspace reads through WorkflowCore/ToolRegistry: their governance
        # path can reject a valid bounded filesystem operation before it runs.
        if not isinstance(kind, str) or kind not in ALLOWED_OPERATIONS:
            raise ToolError("MCP operation is not allowlisted")
        if payload is None:
            safe_payload: dict[str, Any] = {}
        elif isinstance(payload, Mapping):
            safe_payload = dict(payload)
        else:
            raise ToolError("MCP payload must be a mapping")

        if kind in {"status", "list_files"} and safe_payload:
            raise ToolError(f"{kind} does not accept arguments")
        if kind == "read_file":
            path = safe_payload.get("path")
            if set(safe_payload) != {"path"} or not isinstance(path, str) or not path:
                raise ToolError("read_file requires exactly one non-empty path argument")
            if "\\x00" in path or "\\\\" in path:
                raise ToolError("path contains a forbidden character")

        try:
            if kind == "status":
                result = {
                    "status": "ready" if workspace.status().get("ready") is True else "not_ready",
                    "directory_exists": root.is_dir(),
                    "directory": str(root),
                    "max_file_bytes": workspace.status().get("max_file_bytes"),
                }
            elif kind == "list_files":
                result = [
                    name for name in workspace.list_files(".")
                    if not name.endswith("/")
                ][:100]
            else:
                result = workspace.read_file(path)

            audit_report({"operation": kind, "status": "PASS"})
            return result
        except Exception as exc:
            try:
                audit_report({
                    "operation": kind,
                    "status": "FAIL",
                    "error_type": type(exc).__name__,
                })
            except Exception:
                pass
            # Do not expose raw exception text, which may contain local paths.
            raise ToolError(f"{kind} failed: {type(exc).__name__}") from None

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
