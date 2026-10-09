"""Execution backends for trusted, importable handlers.

The subprocess backend adds process separation, timeouts, and POSIX resource
limits. It is not an OS security sandbox: the child runs as the same user and
can still access permitted files and network resources.
"""
from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from typing import Protocol

from .models import Task, ToolResult

Handler = Callable[[Task], ToolResult]


class ExecutionBlockedError(RuntimeError):
    """The configured execution backend cannot safely accept this request."""


class HandlerRunner(Protocol):
    def run(self, handler: Handler, task: Task) -> ToolResult: ...


class InProcessRunner:
    """Compatibility backend; handlers run in the current process."""

    def run(self, handler: Handler, task: Task) -> ToolResult:
        return handler(task)


class SubprocessHandlerRunner:
    """Run an importable top-level handler in a resource-limited child process."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        memory_limit_bytes: int = 512 * 1024 * 1024,
        max_input_bytes: int = 1_048_576,
        max_output_bytes: int = 1_048_576,
        max_open_files: int = 64,
    ) -> None:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a finite positive number")
        for name, value in (("memory_limit_bytes", memory_limit_bytes), ("max_input_bytes", max_input_bytes), ("max_output_bytes", max_output_bytes), ("max_open_files", max_open_files)):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if os.name != "posix":
            raise ValueError("SubprocessHandlerRunner requires POSIX resource limits")
        self.timeout_seconds = float(timeout_seconds)
        self.memory_limit_bytes = memory_limit_bytes
        self.max_input_bytes = max_input_bytes
        self.max_output_bytes = max_output_bytes
        self.max_open_files = max_open_files

    @staticmethod
    def _handler_reference(handler: Handler) -> tuple[str, str]:
        module = getattr(handler, "__module__", None)
        qualname = getattr(handler, "__qualname__", None)
        if (
            not isinstance(module, str) or not module or module == "__main__"
            or not isinstance(qualname, str) or not qualname
            or "<locals>" in qualname or "<lambda>" in qualname
        ):
            raise ExecutionBlockedError("subprocess runner requires an importable top-level handler")
        return module, qualname

    def _limits(self) -> None:
        # Imported only in the child before exec; the parent remains unaffected.
        import resource
        cpu_seconds = max(1, math.ceil(self.timeout_seconds))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        resource.setrlimit(resource.RLIMIT_AS, (self.memory_limit_bytes, self.memory_limit_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (self.max_output_bytes, self.max_output_bytes))
        resource.setrlimit(resource.RLIMIT_NOFILE, (self.max_open_files, self.max_open_files))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    def run(self, handler: Handler, task: Task) -> ToolResult:
        module, qualname = self._handler_reference(handler)
        request = {"module": module, "qualname": qualname, "task": {
            "task_id": task.task_id, "kind": task.kind, "payload": dict(task.payload)
        }}
        try:
            payload = json.dumps(request, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError):
            raise ExecutionBlockedError("task input is not JSON serializable") from None
        if len(payload) > self.max_input_bytes:
            raise ExecutionBlockedError("task input exceeds max_input_bytes")

        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONPATH": os.pathsep.join(path for path in sys.path if path and os.path.isdir(path)),
        }
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            try:
                process = subprocess.Popen(
                    [sys.executable, "-m", "authoritylab.subprocess_worker"],
                    stdin=subprocess.PIPE,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    env=environment,
                    close_fds=True,
                    start_new_session=True,
                    preexec_fn=self._limits,
                )
            except OSError:
                raise ExecutionBlockedError("could not start subprocess execution backend") from None
            try:
                process.communicate(payload, timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                return ToolResult(ok=False, error="handler execution timed out")
            stdout_file.seek(0)
            output = stdout_file.read(self.max_output_bytes + 1)
            if len(output) > self.max_output_bytes:
                return ToolResult(ok=False, error="handler output exceeded max_output_bytes")
            if process.returncode != 0:
                return ToolResult(ok=False, error=f"subprocess handler exited with code {process.returncode}")
        try:
            response = json.loads(output)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return ToolResult(ok=False, error="subprocess handler returned malformed output")
        if not isinstance(response, dict) or type(response.get("ok")) is not bool:
            return ToolResult(ok=False, error="subprocess handler returned malformed output")
        if response["ok"]:
            return ToolResult(ok=True, output=response.get("output"))
        error = response.get("error")
        return ToolResult(ok=False, error=error if isinstance(error, str) else "subprocess handler failed")

class DockerSandboxRunner:
    """Run an importable handler inside a hardened, network-disabled Docker container.

    The supplied image must be pinned by SHA-256 digest and contain both
    AuthorityLab and the handler module. Runtime does not pull images or mount
    host paths. A real deployment must still verify its Docker daemon, image
    provenance, and host security configuration.
    """

    def __init__(
        self,
        image: str,
        *,
        timeout_seconds: float = 10.0,
        memory_limit_bytes: int = 536_870_912,
        cpus: float = 1.0,
        pids_limit: int = 32,
        max_input_bytes: int = 1_048_576,
        max_output_bytes: int = 1_048_576,
        max_open_files: int = 64,
    ) -> None:
        import re
        if not isinstance(image, str) or not re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", image) or image.startswith("-"):
            raise ValueError("image must be pinned by a full sha256 digest")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a finite positive number")
        if isinstance(cpus, bool) or not isinstance(cpus, (int, float)) or not math.isfinite(cpus) or cpus <= 0:
            raise ValueError("cpus must be a finite positive number")
        for name, value in (("memory_limit_bytes", memory_limit_bytes), ("pids_limit", pids_limit), ("max_input_bytes", max_input_bytes), ("max_output_bytes", max_output_bytes), ("max_open_files", max_open_files)):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if os.name != "posix":
            raise ValueError("DockerSandboxRunner requires POSIX process controls")
        self.image = image
        self.timeout_seconds = float(timeout_seconds)
        self.memory_limit_bytes = memory_limit_bytes
        self.cpus = float(cpus)
        self.pids_limit = pids_limit
        self.max_input_bytes = max_input_bytes
        self.max_output_bytes = max_output_bytes
        self.max_open_files = max_open_files

    def _minimal_environment(self) -> dict[str, str]:
        return {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}

    def _host_output_limit(self) -> None:
        import resource
        resource.setrlimit(resource.RLIMIT_FSIZE, (self.max_output_bytes, self.max_output_bytes))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    def _stop_container(self, name: str) -> None:
        environment = self._minimal_environment()
        for args in (["docker", "kill", name], ["docker", "rm", "-f", name]):
            try:
                subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=5, check=False, env=environment)
            except (OSError, subprocess.TimeoutExpired):
                pass

    def run(self, handler: Handler, task: Task) -> ToolResult:
        import uuid
        module, qualname = SubprocessHandlerRunner._handler_reference(handler)
        request = {"module": module, "qualname": qualname, "task": {
            "task_id": task.task_id, "kind": task.kind, "payload": dict(task.payload)
        }}
        try:
            payload = json.dumps(request, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError):
            raise ExecutionBlockedError("task input is not JSON serializable") from None
        if len(payload) > self.max_input_bytes:
            raise ExecutionBlockedError("task input exceeds max_input_bytes")

        name = "authoritylab-" + uuid.uuid4().hex
        command = [
            "docker", "run", "--rm", "--interactive", "--name", name,
            "--pull=never", "--network=none", "--read-only",
            "--memory", str(self.memory_limit_bytes), "--cpus", str(self.cpus),
            "--pids-limit", str(self.pids_limit), "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true", "--user", "65534:65534",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
            "--ulimit", f"nofile={self.max_open_files}:{self.max_open_files}",
            "--ulimit", f"fsize={self.max_output_bytes}:{self.max_output_bytes}",
            "--env", "PYTHONUNBUFFERED=1", "--env", "PYTHONIOENCODING=utf-8",
            self.image, "python", "-m", "authoritylab.subprocess_worker",
        ]
        environment = self._minimal_environment()
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            try:
                process = subprocess.Popen(
                    command, stdin=subprocess.PIPE, stdout=stdout_file, stderr=stderr_file,
                    env=environment, close_fds=True, start_new_session=True,
                    preexec_fn=self._host_output_limit,
                )
            except OSError:
                raise ExecutionBlockedError("Docker sandbox backend could not be started") from None
            try:
                process.communicate(payload, timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                self._stop_container(name)
                return ToolResult(ok=False, error="sandbox handler execution timed out")

            stdout_file.seek(0)
            output = stdout_file.read(self.max_output_bytes + 1)
            if len(output) > self.max_output_bytes:
                self._stop_container(name)
                return ToolResult(ok=False, error="sandbox handler output exceeded max_output_bytes")
            if process.returncode != 0:
                stderr_file.seek(0)
                error_output = stderr_file.read(self.max_output_bytes + 1)
                if len(error_output) > self.max_output_bytes:
                    error_output = error_output[:self.max_output_bytes]
                self._stop_container(name)
                raise ExecutionBlockedError("Docker sandbox container failed to start or complete")
        try:
            response = json.loads(output)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return ToolResult(ok=False, error="sandbox handler returned malformed output")
        if not isinstance(response, dict) or type(response.get("ok")) is not bool:
            return ToolResult(ok=False, error="sandbox handler returned malformed output")
        if response["ok"]:
            return ToolResult(ok=True, output=response.get("output"))
        error = response.get("error")
        return ToolResult(ok=False, error=error if isinstance(error, str) else "sandbox handler failed")
