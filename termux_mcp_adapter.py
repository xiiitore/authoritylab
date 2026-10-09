"""Narrow, read-only adapter for the existing Termux MCP file bridge.

This module wraps already-defined MCP tool callables. It does not create an MCP
server, widen filesystem access, or provide shell/file mutation operations.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Any

from .models import Task, ToolResult
from .tools import ToolRegistry


StatusTool = Callable[[], Any]
ListFilesTool = Callable[[], Any]
ReadFileTool = Callable[[str], Any]


def _empty_payload(task: Task) -> ToolResult | None:
    if task.payload:
        return ToolResult(
            ok=False,
            error=f"{task.kind} does not accept arguments",
        )
    return None


def _validated_read_path(task: Task) -> str | ToolResult:
    if set(task.payload) != {"path"}:
        return ToolResult(
            ok=False,
            error="read_file requires exactly one argument: path",
        )

    path = task.payload["path"]
    if not isinstance(path, str) or not path:
        return ToolResult(ok=False, error="path must be a non-empty string")
    if "\x00" in path or "\\" in path:
        return ToolResult(ok=False, error="path contains a forbidden character")

    candidate = PurePosixPath(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return ToolResult(ok=False, error="path must remain inside the permitted directory")
    if path in {".", "./"}:
        return ToolResult(ok=False, error="path must name a file")

    return path


def register_read_only_mcp_tools(
    registry: ToolRegistry,
    *,
    status: StatusTool,
    list_files: ListFilesTool,
    read_file: ReadFileTool,
) -> None:
    """Register exactly status, list_files, and read_file workflow handlers.

    The supplied callables should be the existing, already-restricted MCP tool
    functions. Input validation occurs before calling those functions. Runtime
    exceptions are left to WorkflowCore, which records them as failed results.
    """

    if not callable(status) or not callable(list_files) or not callable(read_file):
        raise TypeError("all MCP tool arguments must be callable")

    def status_handler(task: Task) -> ToolResult:
        invalid = _empty_payload(task)
        if invalid is not None:
            return invalid
        return ToolResult(ok=True, output=status())

    def list_files_handler(task: Task) -> ToolResult:
        invalid = _empty_payload(task)
        if invalid is not None:
            return invalid
        return ToolResult(ok=True, output=list_files())

    def read_file_handler(task: Task) -> ToolResult:
        path = _validated_read_path(task)
        if isinstance(path, ToolResult):
            return path
        return ToolResult(ok=True, output=read_file(path))

    registry.register("status", status_handler)
    registry.register("list_files", list_files_handler)
    registry.register("read_file", read_file_handler)
