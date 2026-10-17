"""Outbound-only Termux worker for remote_mcp_relay.py.

Only status, list_files and read_file are implemented. No shell or Git commands
are accepted. Use HTTPS for any non-loopback gateway URL.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from termux_workspace_tools import BoundedWorkspace

MAX_RESPONSE_BYTES = 256 * 1024
ALLOWED_TOOLS = frozenset({"status", "list_files", "read_file"})


class RelayAgentError(Exception):
    pass


def _endpoint(base_url: str, path: str) -> str:
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise RelayAgentError("gateway_url_invalid")
    if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
        raise RelayAgentError("https_required_for_remote_gateway")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RelayAgentError("gateway_url_invalid")
    return base_url.rstrip("/") + path


def _request(url: str, token: str, *, payload: Any = None, timeout: float = 12.0) -> Any:
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    data = None
    method = "GET"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(data) > 64 * 1024:
            raise RelayAgentError("request_too_large")
        headers["Content-Type"] = "application/json"
        method = "POST"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise RelayAgentError("gateway_response_too_large")
            if response.status != 200:
                raise RelayAgentError("gateway_http_error")
    except urllib.error.HTTPError as exc:
        # Do not echo response bodies or headers that may contain sensitive data.
        raise RelayAgentError("gateway_http_" + str(exc.code)) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RelayAgentError("gateway_unavailable") from None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RelayAgentError("gateway_response_invalid") from None


def dispatch(workspace: BoundedWorkspace, tool: str, arguments: dict[str, Any]) -> Any:
    if tool not in ALLOWED_TOOLS or not isinstance(arguments, dict):
        raise RelayAgentError("tool_not_allowed")
    if tool == "status":
        if arguments:
            raise RelayAgentError("unexpected_arguments")
        status = workspace.status()
        return {
            "status": "ready" if status.get("ready") is True else "not_ready",
            "max_file_bytes": status.get("max_file_bytes"),
        }
    if tool == "list_files":
        if arguments:
            raise RelayAgentError("unexpected_arguments")
        return [name for name in workspace.list_files(".") if not name.endswith("/")][:100]
    if set(arguments) != {"path"} or not isinstance(arguments.get("path"), str):
        raise RelayAgentError("invalid_arguments")
    result = workspace.read_file(arguments["path"])
    if not isinstance(result, str) or len(result.encode("utf-8")) > 200_000:
        raise RelayAgentError("file_read_rejected")
    return result


def run_agent() -> None:
    base_url = os.environ.get("AUTHORITYLAB_RELAY_URL", "").rstrip("/")
    token = os.environ.get("AUTHORITYLAB_AGENT_TOKEN", "")
    root = os.environ.get("AUTHORITYLAB_ROOT", "").strip()
    if len(token) < 32:
        raise SystemExit("Set AUTHORITYLAB_AGENT_TOKEN to the agent-only 32+ character secret.")
    if not base_url or not root:
        raise SystemExit("Set AUTHORITYLAB_RELAY_URL and AUTHORITYLAB_ROOT.")
    _endpoint(base_url, "/agent/next")
    workspace = BoundedWorkspace(Path(root).expanduser())
    print("AuthorityLab Termux relay agent started; tools: status, list_files, read_file.")
    while True:
        try:
            payload = _request(_endpoint(base_url, "/agent/next"), token, timeout=12.0)
            task = payload.get("request") if isinstance(payload, dict) else None
            if task is None:
                continue
            if not isinstance(task, dict) or set(task) != {"id", "tool", "arguments"}:
                continue
            request_id = task.get("id")
            if not isinstance(request_id, str) or len(request_id) > 128:
                continue
            try:
                result = dispatch(workspace, task.get("tool"), task.get("arguments"))
                response = {"id": request_id, "result": result}
            except Exception:
                # Do not return local exception messages, paths or file contents.
                response = {"id": request_id, "error": True}
            try:
                _request(_endpoint(base_url, "/agent/result"), token, payload=response)
            except RelayAgentError:
                # Results are not automatically replayed: broker requests expire.
                pass
        except RelayAgentError:
            time.sleep(2.0)


if __name__ == "__main__":
    run_agent()
