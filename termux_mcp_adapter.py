"""Narrow, read-only adapter for the existing Termux MCP file bridge.

This module wraps already-defined MCP tool callables. It does not create an MCP
server, widen filesystem access, or provide shell/file mutation operations.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import PurePosixPath
from typing import Any
from uuid import uuid4

from .core import WorkflowCore
from .governance import EvidenceSchema, GovernancePolicy
from .models import Task, ToolResult, WorkflowReport, WorkflowStatus
from .tools import ToolRegistry


ALLOWED_TOOL_NAMES = frozenset({"status", "list_files", "read_file"})


def read_only_mcp_governance_policy() -> GovernancePolicy:
    """Return evidence schemas for the three restricted MCP operations."""
    return GovernancePolicy(evidence_schemas=(
        EvidenceSchema("status", ("status", "directory_exists", "directory", "max_file_bytes")),
        EvidenceSchema("list_files", ("files",)),
        EvidenceSchema("read_file", ("text",)),
    ))


class MCPAdapterError(RuntimeError):
    """Raised when a read-only MCP workflow is rejected or does not pass."""


StatusTool = Callable[[], Any]
ListFilesTool = Callable[[], Any]
ReadFileTool = Callable[[str], Any]
AuditSink = Callable[[Mapping[str, Any]], None]


def _audit_event(report: WorkflowReport) -> dict[str, Any]:
    """Build a metadata-only event; never pass tool output to audit sinks."""
    return {
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


def _empty_payload(task: Task) -> ToolResult | None:
    if task.payload:
        return ToolResult(
            ok=False,
            error=f"{task.kind} does not accept arguments",
        )
    return None


def _status_output(value: Any) -> ToolResult:
    if not isinstance(value, Mapping):
        return ToolResult(ok=False, error="status tool returned a non-mapping result")
    if (
        value.get("status") != "ready"
        or type(value.get("directory_exists")) is not bool
        or not isinstance(value.get("directory"), str)
        or not value.get("directory")
        or type(value.get("max_file_bytes")) is not int
        or value["max_file_bytes"] <= 0
    ):
        return ToolResult(ok=False, error="status tool returned malformed fields")
    return ToolResult(ok=True, output=dict(value))


def _list_files_output(value: Any) -> ToolResult:
    if (
        not isinstance(value, list)
        or len(value) > 100
        or any(
            not isinstance(item, str)
            or not item
            or item in {".", ".."}
            or "/" in item
            or "\\" in item
            or "\x00" in item
            for item in value
        )
    ):
        return ToolResult(
            ok=False,
            error="list_files tool must return at most 100 direct file names",
        )
    return ToolResult(ok=True, output={"files": value})


def _read_file_output(value: Any) -> ToolResult:
    if not isinstance(value, str):
        return ToolResult(ok=False, error="read_file tool must return text")
    return ToolResult(ok=True, output={"text": value})


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
    conflicts = {name for name in ALLOWED_TOOL_NAMES if registry.is_registered(name)}
    if conflicts:
        raise ValueError(
            f"handlers already registered for: {', '.join(sorted(conflicts))}"
        )

    def status_handler(task: Task) -> ToolResult:
        invalid = _empty_payload(task)
        if invalid is not None:
            return invalid
        return _status_output(status())

    def list_files_handler(task: Task) -> ToolResult:
        invalid = _empty_payload(task)
        if invalid is not None:
            return invalid
        return _list_files_output(list_files())

    def read_file_handler(task: Task) -> ToolResult:
        path = _validated_read_path(task)
        if isinstance(path, ToolResult):
            return path
        return _read_file_output(read_file(path))

    registry.register("status", status_handler, trusted=True)
    registry.register("list_files", list_files_handler, trusted=True)
    registry.register("read_file", read_file_handler, trusted=True)


def dispatch_read_only_mcp_tool(
    core: WorkflowCore,
    *,
    kind: str,
    payload: Mapping[str, Any] | None = None,
    audit_sink: AuditSink | None = None,
) -> Any:
    """Run one allowlisted MCP operation through WorkflowCore and return output.

    Call this from each exposed MCP tool wrapper. The allowlist is checked before
    WorkflowCore is invoked, and any non-PASS report becomes an MCPAdapterError.
    This function does not itself register or expose MCP endpoints.
    """

    if not isinstance(kind, str) or kind not in ALLOWED_TOOL_NAMES:
        raise MCPAdapterError(f"MCP operation is not allowlisted: {kind!r}")
    if audit_sink is not None and not callable(audit_sink):
        raise MCPAdapterError("audit_sink must be callable")
    if payload is None:
        safe_payload: dict[str, Any] = {}
    elif isinstance(payload, Mapping):
        safe_payload = dict(payload)
    else:
        raise MCPAdapterError("MCP payload must be a mapping")

    report = core.run(
        Task(task_id=f"mcp-{uuid4().hex}", kind=kind, payload=safe_payload)
    )
    if audit_sink is not None:
        try:
            audit_sink(_audit_event(report))
        except Exception:
            raise MCPAdapterError("MCP audit sink failed; result withheld") from None
    if report.status != WorkflowStatus.PASS or report.tool_result is None:
        detail = report.tool_result.error if report.tool_result is not None else None
        suffix = f": {detail}" if detail else ""
        raise MCPAdapterError(f"MCP operation {kind!r} did not pass ({report.status.value}){suffix}")
    output = report.tool_result.output
    if kind == "list_files":
        return output["files"]
    if kind == "read_file":
        return output["text"]
    return output
