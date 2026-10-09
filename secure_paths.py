"""Descriptor-based, read-only access confined to a directory."""

from __future__ import annotations

import os
import stat
from pathlib import Path, PurePosixPath


def _open_confined_root(root: str | os.PathLike[str]) -> int:
    """Open the configured root itself without following a final symlink."""
    directory = getattr(os, "O_DIRECTORY", None)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if directory is None or nofollow is None:
        raise OSError("Platform lacks required safe directory-open features")

    # abspath normalizes the path without resolving/following symlinks.
    root_path = Path(os.path.abspath(os.fspath(root)))
    descriptor = os.open(str(root_path), os.O_RDONLY | directory | nofollow)
    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise ValueError("Permitted root must be a directory")
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def list_confined_files(
    root: str | os.PathLike[str],
    *,
    max_entries: int = 100,
) -> list[str]:
    """List regular, single-link files directly in root, without following links."""
    if type(max_entries) is not int or max_entries < 0:
        raise ValueError("max_entries must be a non-negative integer")
    if os.stat not in os.supports_dir_fd or os.stat not in os.supports_follow_symlinks:
        raise OSError("Platform lacks required safe relative-stat features")

    root_fd = _open_confined_root(root)
    try:
        names = sorted(os.listdir(root_fd))
        result: list[str] = []
        for name in names:
            try:
                metadata = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            except FileNotFoundError:
                # The entry disappeared during listing; fail closed for this entry.
                continue
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                continue
            result.append(name)
            if len(result) >= max_entries:
                break
        return result
    finally:
        os.close(root_fd)


def read_confined_text_file(
    root: str | os.PathLike[str],
    relative_path: str,
    *,
    max_bytes: int,
) -> str:
    """Read a UTF-8 regular file beneath root without following symlinks.

    Opens the root and each path component relative to held directory
    descriptors, using O_NOFOLLOW. Rejects hard links, and reads at most
    max_bytes + 1 bytes to enforce the limit even if the file grows after
    fstat. Fails closed when the required POSIX features are unavailable.
    """

    if not isinstance(relative_path, str):
        raise TypeError("relative_path must be a string")
    if not relative_path or "\x00" in relative_path or "\\" in relative_path:
        raise ValueError("Provide a non-empty relative POSIX path")
    if type(max_bytes) is not int or max_bytes < 0:
        raise ValueError("max_bytes must be a non-negative integer")

    candidate = PurePosixPath(relative_path)
    parts = candidate.parts
    if candidate.is_absolute() or not parts or ".." in parts:
        raise ValueError("Path must remain inside the permitted directory")

    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None or os.open not in os.supports_dir_fd:
        raise OSError("Platform lacks required safe relative-open features")

    descriptors: list[int] = []
    try:
        descriptors.append(_open_confined_root(root))
        directory_flags = os.O_RDONLY | directory | nofollow
        file_flags = os.O_RDONLY | nofollow
        for component in parts[:-1]:
            descriptors.append(
                os.open(component, directory_flags, dir_fd=descriptors[-1])
            )

        file_descriptor = os.open(
            parts[-1], file_flags, dir_fd=descriptors[-1]
        )
        try:
            metadata = os.fstat(file_descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("Target must be a regular file")
            if metadata.st_nlink != 1:
                raise ValueError("Hard-linked files are not permitted")
            if metadata.st_size > max_bytes:
                raise ValueError(f"File exceeds the {max_bytes}-byte limit")

            with os.fdopen(file_descriptor, "rb") as stream:
                file_descriptor = -1
                content = stream.read(max_bytes + 1)
            if len(content) > max_bytes:
                raise ValueError(f"File exceeds the {max_bytes}-byte limit")
            return content.decode("utf-8")
        finally:
            if file_descriptor >= 0:
                os.close(file_descriptor)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
