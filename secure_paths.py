"""Race-resistant, read-only file access confined to a directory."""

from __future__ import annotations

import os
import stat
from pathlib import Path, PurePosixPath


def read_confined_text_file(
    root: str | os.PathLike[str],
    relative_path: str,
    *,
    max_bytes: int,
) -> str:
    """Read a UTF-8 regular file beneath root without following symlinks.

    Opens each path component relative to an already-open directory descriptor,
    with O_NOFOLLOW. Reads at most max_bytes + 1 bytes to enforce the limit even
    if a same-user process grows the file after the initial fstat check.

    Fails closed on platforms lacking the required POSIX open flags.
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

    root_path = Path(root).resolve(strict=True)
    if not root_path.is_dir():
        raise ValueError("Permitted root must be a directory")

    directory_flags = os.O_RDONLY | directory | nofollow
    file_flags = os.O_RDONLY | nofollow
    descriptors: list[int] = []

    try:
        descriptors.append(os.open(str(root_path), directory_flags))
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
