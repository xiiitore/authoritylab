"""Local stdio MCP server exposing bounded AuthorityLab workspace operations.

Launch this only from a trusted local MCP client. It deliberately does not bind
an HTTP listener or expose arbitrary shell commands.
"""
from __future__ import annotations

import os

from authoritylab.termux_workspace_tools import BoundedWorkspace, WorkspaceError


def main() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise SystemExit(
            "MCP SDK is optional; install with: pip install 'authoritylab[mcp]'"
        ) from None

    root = os.environ.get("AUTHORITYLAB_ROOT", os.getcwd())
    workspace = BoundedWorkspace(root)
    server = FastMCP("authoritylab-termux")

    @server.tool()
    def status() -> dict:
        """Return workspace readiness and the fixed tool allowlist."""
        return workspace.status()

    @server.tool()
    def list_files(directory: str = ".") -> list[str]:
        """List at most 200 direct entries in a workspace directory."""
        return workspace.list_files(directory)

    @server.tool()
    def read_file(path: str) -> str:
        """Read a UTF-8 file inside the workspace, capped at 200 KB."""
        return workspace.read_file(path)

    @server.tool()
    def write_file(path: str, content: str) -> dict:
        """Write at most 200 KB to a file inside the workspace."""
        return workspace.write_file(path, content)

    @server.tool()
    def git_status() -> str:
        """Return git status; no repository mutation is performed."""
        return workspace.git_status()

    @server.tool()
    def git_diff() -> str:
        """Return the unstaged diff; staged changes are not included."""
        return workspace.git_diff()

    @server.tool()
    def run_tests() -> dict:
        """Run only unittest discovery in the configured repository."""
        return workspace.run_tests()

    try:
        server.run(transport="stdio")
    except WorkspaceError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
