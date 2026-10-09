"""Worker entry point for SubprocessHandlerRunner; input/output are JSON only."""
from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys
from collections.abc import Mapping

from .models import Task, ToolResult


def _resolve(module_name: str, qualname: str):
    target = importlib.import_module(module_name)
    for part in qualname.split("."):
        if part.startswith("<") or not part:
            raise ValueError("handler reference is not importable")
        target = getattr(target, part)
    if not callable(target):
        raise TypeError("handler reference is not callable")
    return target


def main() -> int:
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict) or not isinstance(request.get("task"), dict):
            raise ValueError("malformed request")
        task_data = request["task"]
        if not isinstance(task_data.get("payload"), Mapping):
            raise ValueError("malformed task payload")
        task = Task(task_data["task_id"], task_data["kind"], task_data["payload"])
        handler = _resolve(request["module"], request["qualname"])
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = handler(task)
        if not isinstance(result, ToolResult):
            result = ToolResult(ok=False, error="handler returned a non-ToolResult value")
        response = {"ok": result.ok, "output": result.output, "error": result.error}
        encoded = json.dumps(response, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except Exception as exc:
        encoded = json.dumps({"ok": False, "error": f"handler raised {type(exc).__name__}"})
    sys.__stdout__.write(encoded)
    sys.__stdout__.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
