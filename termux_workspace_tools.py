"""Bounded workspace operations for a local MCP bridge.

This is a least-privilege convenience layer, not an operating-system sandbox.
"""
from __future__ import annotations

import os
import subprocess
import sys
import stat
import secrets
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any

MAX_FILE_BYTES = 200_000
MAX_OUTPUT_CHARS = 20_000
MAX_LIST_ENTRIES = 200
DEFAULT_TIMEOUT_SECONDS = 120
_EXCLUDED = {".git", ".venv", "venv", "__pycache__", "node_modules"}


class WorkspaceError(RuntimeError):
    """A bounded workspace operation was rejected or failed."""


class BoundedWorkspace:
    """Expose a fixed set of operations rooted at one Git checkout."""

    def __init__(self, root: str | Path, *, timeout: int = DEFAULT_TIMEOUT_SECONDS):
        candidate = Path(root).expanduser()
        if candidate.is_symlink():
            raise ValueError("workspace root must not be a symlink")
        self.root = candidate.resolve(strict=True)
        if not self.root.is_dir() or not (self.root / ".git").exists():
            raise ValueError("workspace root must be a Git repository directory")
        if type(timeout) is not int or not 1 <= timeout <= 600:
            raise ValueError("timeout must be an integer from 1 to 600 seconds")
        self.timeout = timeout

    def status(self) -> dict[str, Any]:
        return {"ready": True, "root": str(self.root),
                "max_file_bytes": MAX_FILE_BYTES,
                "allowed_operations": ["status", "list_files", "read_file",
                                       "write_file", "git_status", "git_diff",
                                       "run_tests"]}

    def _path(self, relative: str, *, must_exist: bool = False) -> Path:
        if not isinstance(relative, str) or not relative:
            raise WorkspaceError("path must be a non-empty relative string")
        if "\x00" in relative or "\\" in relative:
            raise WorkspaceError("path contains a forbidden character")
        parsed = PurePosixPath(relative)
        if (parsed.is_absolute() or ".." in parsed.parts
                or ".git" in parsed.parts or relative in {".", "./"}):
            raise WorkspaceError("path must name an allowed item inside the workspace")
        target = self.root
        for part in parsed.parts:
            if part in {"", "."}:
                continue
            target = target / part
            if target.is_symlink():
                raise WorkspaceError("symbolic links are not permitted")
        resolved = target.resolve(strict=must_exist)
        if resolved != self.root and self.root not in resolved.parents:
            raise WorkspaceError("path escapes the workspace")
        if must_exist and not resolved.exists():
            raise WorkspaceError("path does not exist")
        return resolved

    def list_files(self, directory: str = ".") -> list[str]:
        target = self.root if directory in {".", "./"} else self._path(directory, must_exist=True)
        if not target.is_dir():
            raise WorkspaceError("directory path is not a directory")
        result = []
        for child in sorted(target.iterdir(), key=lambda item: item.name):
            if child.name in _EXCLUDED or child.is_symlink():
                continue
            result.append(child.name + ("/" if child.is_dir() else ""))
            if len(result) >= MAX_LIST_ENTRIES:
                break
        return result

    def read_file(self, path: str) -> str:
        target = self._path(path, must_exist=True)
        if not target.is_file():
            raise WorkspaceError("path is not a regular file")
        if target.stat().st_size > MAX_FILE_BYTES:
            raise WorkspaceError(f"file exceeds {MAX_FILE_BYTES} bytes")
        try:
            return target.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise WorkspaceError(f"file could not be read: {type(exc).__name__}") from None

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        """Atomically replace one bounded regular file without following symlinks."""
        if not isinstance(content, str):
            raise WorkspaceError("content must be text")
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_FILE_BYTES:
            raise WorkspaceError(f"content exceeds {MAX_FILE_BYTES} bytes")
        if not isinstance(path, str) or not path:
            raise WorkspaceError("path must be a non-empty relative string")
        if "\x00" in path or "\\" in path:
            raise WorkspaceError("path contains a forbidden character")
        parsed = PurePosixPath(path)
        if (parsed.is_absolute() or ".." in parsed.parts or ".git" in parsed.parts
                or path in {".", "./"} or not parsed.parts):
            raise WorkspaceError("path must name an allowed item inside the workspace")

        nofollow = getattr(os, "O_NOFOLLOW", None)
        directory = getattr(os, "O_DIRECTORY", None)
        if nofollow is None or directory is None or os.open not in os.supports_dir_fd:
            raise WorkspaceError("platform lacks required safe relative-open features")

        descriptors: list[int] = []
        temporary_name: str | None = None
        try:
            descriptors.append(os.open(str(self.root), os.O_RDONLY | directory | nofollow))
            for component in parsed.parts[:-1]:
                descriptors.append(os.open(
                    component, os.O_RDONLY | directory | nofollow,
                    dir_fd=descriptors[-1],
                ))
            parent_fd = descriptors[-1]
            final_name = parsed.parts[-1]

            try:
                existing = os.stat(final_name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                existing = None
            except OSError:
                raise WorkspaceError("target could not be inspected safely") from None

            if existing is not None:
                if not stat.S_ISREG(existing.st_mode):
                    raise WorkspaceError("target must be a regular file and not a symlink")
                if existing.st_nlink != 1:
                    raise WorkspaceError("hard-linked targets are not permitted")
                if existing.st_size > MAX_FILE_BYTES:
                    raise WorkspaceError("existing file exceeds the permitted size")

            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow
            temporary_fd = -1
            for _ in range(5):
                temporary_name = ".authoritylab-write-" + secrets.token_hex(12) + ".tmp"
                try:
                    temporary_fd = os.open(
                        temporary_name, flags, 0o600, dir_fd=parent_fd,
                    )
                    break
                except FileExistsError:
                    temporary_name = None
            if temporary_fd < 0 or temporary_name is None:
                raise WorkspaceError("could not allocate a safe temporary file")

            try:
                view = memoryview(encoded)
                while view:
                    written = os.write(temporary_fd, view)
                    if written <= 0:
                        raise WorkspaceError("temporary file write did not make progress")
                    view = view[written:]
                os.fsync(temporary_fd)
            finally:
                os.close(temporary_fd)

            # Rename is descriptor-relative and atomic; a raced symlink/hardlink at
            # the destination is replaced as a directory entry, never followed.
            os.replace(
                temporary_name, final_name,
                src_dir_fd=parent_fd, dst_dir_fd=parent_fd,
            )
            temporary_name = None
            try:
                os.fsync(parent_fd)
            except OSError:
                # Some filesystems do not support directory fsync; the atomic
                # replacement has already succeeded, so do not misreport failure.
                pass
            return {"path": parsed.as_posix(), "bytes_written": len(encoded)}
        except WorkspaceError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise WorkspaceError(
                f"file could not be written safely: {type(exc).__name__}"
            ) from None
        finally:
            if temporary_name is not None and descriptors:
                try:
                    os.unlink(temporary_name, dir_fd=descriptors[-1])
                except OSError:
                    pass
            for descriptor in reversed(descriptors):
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def git_status(self) -> str:
        """Return a short Git-like status without spawning a Termux executable."""
        from dulwich import porcelain

        try:
            branch = porcelain.active_branch(str(self.root)).decode("utf-8", "replace")
        except (IndexError, KeyError, ValueError):
            branch = "HEAD (detached)"
        result = porcelain.status(str(self.root))
        entries: dict[bytes, list[str]] = {}
        staged_codes = {
            "add": "A",
            "modify": "M",
            "delete": "D",
            "rename": "R",
            "copy": "C",
        }
        for kind, paths in result.staged.items():
            normalized_kind = kind.decode("utf-8", "replace") if isinstance(kind, bytes) else str(kind)
            code = staged_codes.get(normalized_kind, "M")
            for path in paths:
                key = path if isinstance(path, bytes) else os.fsencode(path)
                entries.setdefault(key, [" ", " "])[0] = code
        for path in result.unstaged:
            key = path if isinstance(path, bytes) else os.fsencode(path)
            target = self.root / os.fsdecode(key)
            entries.setdefault(key, [" ", " "])[1] = "M" if target.exists() else "D"
        for path in result.untracked:
            key = path if isinstance(path, bytes) else os.fsencode(path)
            entries[key] = ["?", "?"]

        lines = [f"## {branch}"]
        for path, codes in sorted(entries.items()):
            lines.append(f"{codes[0]}{codes[1]} {os.fsdecode(path)}")
        return "\n".join(lines) + "\n"

    def git_diff(self) -> str:
        """Return the unstaged diff using Dulwich instead of an external Git process."""
        from dulwich.diff import diff_working_tree_to_index
        from dulwich.repo import Repo

        output = BytesIO()
        repo = Repo(str(self.root))
        try:
            diff_working_tree_to_index(repo, output)
        finally:
            repo.close()
        return output.getvalue().decode("utf-8", "replace")[-MAX_OUTPUT_CHARS:]

    def run_tests(self) -> dict[str, Any]:
        """Run only unittest discovery; repository code is executed."""
        output = self._run([sys.executable, "-m", "unittest", "discover", "-v"])
        return {"command": "python -m unittest discover -v", "output": output}

    def _run(self, argv: list[str]) -> str:
        env = {"PATH": os.environ.get("PATH", ""),
               "HOME": os.environ.get("HOME", str(self.root)),
               "LANG": "C.UTF-8", "TERM": "dumb"}
        try:
            completed = subprocess.run(
                argv, cwd=self.root, env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                errors="replace", timeout=self.timeout, check=False, shell=False)
        except subprocess.TimeoutExpired:
            raise WorkspaceError(f"operation timed out after {self.timeout} seconds") from None
        except OSError as exc:
            errno = getattr(exc, "errno", None)
            errno_detail = errno if errno is not None else "unavailable"
            # Avoid str(exc): OSError may append a sensitive filename/path.
            reason = getattr(exc, "strerror", None)
            if not isinstance(reason, str) or not reason:
                reason = "unavailable"
            reason = reason[:200]
            raise WorkspaceError(
                f"operation could not start: {type(exc).__name__}: "
                f"{reason} (errno={errno_detail})"
            ) from None
        output = completed.stdout[-MAX_OUTPUT_CHARS:]
        if completed.returncode:
            raise WorkspaceError(f"operation exited with status {completed.returncode}:\n{output}")
        return output
