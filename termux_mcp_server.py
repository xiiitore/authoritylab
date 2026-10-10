"""Local stdio MCP server exposing bounded AuthorityLab workspace operations.

It does not open a network listener or expose a generic shell.
"""
from __future__ import annotations

import os

from authoritylab.termux_workspace_tools import BoundedWorkspace


def main() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise SystemExit("Install optional dependency with: pip install 'authoritylab[mcp]'") from None

    workspace = BoundedWorkspace(os.environ.get("AUTHORITYLAB_ROOT", os.getcwd()))
    server = FastMCP("authoritylab-termux")

    @server.tool()
    def status() -> dict:
        """Return the workspace root, limits, and fixed allowlist."""
        return workspace.status()

    @server.tool()
    def list_files(directory: str = ".") -> list[str]:
        """List up to 200 direct entries in a repository directory."""
        return workspace.list_files(directory)

    @server.tool()
    def read_file(path: str) -> str:
        """Read a UTF-8 file inside the repository, capped at 200 KB."""
        return workspace.read_file(path)

    @server.tool()
    def write_file(path: str, content: str) -> dict:
        """Write up to 200 KB to a file inside the repository."""
        return workspace.write_file(path, content)

    @server.tool()
    def git_status() -> str:
        """Return git status without modifying the repository."""
        return workspace.git_status()

    @server.tool()
    def git_diff() -> str:
        """Return the unstaged diff without modifying the repository."""
        return workspace.git_diff()

    @server.tool()
    def run_tests() -> dict:
        """Run only unittest discovery; repository code is executed."""
        return workspace.run_tests()

    @server.tool()
    def diagnostics() -> dict:
        """Report fixed process identity and interpreter path metadata."""
        return workspace.diagnostics()

    server.run(transport="stdio")


if __name__ == "__main__":
    main()
