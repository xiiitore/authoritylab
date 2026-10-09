"""Tests for confined file reading and symlink-resistant path traversal."""

from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from authoritylab.secure_paths import (
    is_confined_directory,
    list_confined_files,
    read_confined_text_file,
)


class ConfinedReadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "share"
        self.root.mkdir()
        (self.root / "note.txt").write_text("safe text", encoding="utf-8")
        (self.root / "nested").mkdir()
        (self.root / "nested" / "inner.txt").write_text("inside", encoding="utf-8")
        self.outside = Path(self.temp.name) / "outside.txt"
        self.outside.write_text("outside", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def read(self, path: str, max_bytes: int = 200_000) -> str:
        return read_confined_text_file(self.root, path, max_bytes=max_bytes)

    def test_rejects_symlinked_root(self) -> None:
        alias = Path(self.temp.name) / "root-link"
        try:
            alias.symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation is unavailable")
        self.assertFalse(is_confined_directory(alias))
        with self.assertRaises(OSError):
            self.read_root(alias, "note.txt")

    def read_root(self, root: Path, path: str) -> str:
        return read_confined_text_file(root, path, max_bytes=200_000)

    def test_lists_only_direct_regular_files_and_excludes_symlinks(self) -> None:
        link = self.root / "nested-link.txt"
        try:
            link.symlink_to(self.outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation is unavailable")
        self.assertEqual(list_confined_files(self.root), ["note.txt"])

    def test_listing_excludes_entries_reported_as_hard_linked(self) -> None:
        real_stat = os.stat

        def stat_with_multiple_links(path, *args, **kwargs):
            metadata = real_stat(path, *args, **kwargs)
            if path == "note.txt" and kwargs.get("dir_fd") is not None:
                return SimpleNamespace(st_mode=metadata.st_mode, st_nlink=2)
            return metadata

        with patch(
            "authoritylab.secure_paths.os.stat",
            side_effect=stat_with_multiple_links,
        ):
            self.assertEqual(list_confined_files(self.root), [])

    def test_listing_excludes_real_hard_link_when_supported(self) -> None:
        if not callable(getattr(os, "link", None)):
            self.skipTest("This Python build does not expose os.link")
        try:
            os.link(self.outside, self.root / "hard-link.txt")
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Hard-link creation is unavailable: {exc}")
        self.assertEqual(list_confined_files(self.root), ["note.txt"])

    def test_listing_limit_zero_returns_empty(self) -> None:
        self.assertEqual(list_confined_files(self.root, max_entries=0), [])

    def test_listing_rejects_symlinked_root(self) -> None:
        alias = Path(self.temp.name) / "root-link"
        try:
            alias.symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation is unavailable")
        with self.assertRaises(OSError):
            list_confined_files(alias)

    def test_reads_regular_file(self) -> None:
        self.assertEqual(self.read("note.txt"), "safe text")

    def test_reads_nested_regular_file(self) -> None:
        self.assertEqual(self.read("nested/inner.txt"), "inside")

    def test_rejects_parent_traversal(self) -> None:
        with self.assertRaises(ValueError):
            self.read("../outside.txt")

    def test_rejects_absolute_path(self) -> None:
        with self.assertRaises(ValueError):
            self.read(str(self.outside))

    def test_rejects_empty_and_dot_paths(self) -> None:
        for path in ("", ".", "./"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.read(path)

    def test_rejects_backslashes_and_nul(self) -> None:
        for path in ("nested\\inner.txt", "note\x00.txt"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.read(path)

    def test_rejects_file_symlink(self) -> None:
        link = self.root / "linked.txt"
        try:
            link.symlink_to(self.outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation is unavailable")
        with self.assertRaises(OSError):
            self.read("linked.txt")

    def test_rejects_symlinked_parent_directory(self) -> None:
        link = self.root / "linked-dir"
        try:
            link.symlink_to(self.outside.parent, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation is unavailable")
        with self.assertRaises(OSError):
            self.read("linked-dir/outside.txt")

    def test_rejects_file_reported_as_hard_linked(self) -> None:
        real_fstat = os.fstat

        def fstat_with_multiple_links(fd):
            metadata = real_fstat(fd)
            if stat.S_ISREG(metadata.st_mode):
                return SimpleNamespace(
                    st_mode=metadata.st_mode,
                    st_nlink=2,
                    st_size=metadata.st_size,
                )
            return metadata

        with patch(
            "authoritylab.secure_paths.os.fstat",
            side_effect=fstat_with_multiple_links,
        ):
            with self.assertRaisesRegex(ValueError, "Hard-linked"):
                self.read("note.txt")

    def test_rejects_real_hard_link_to_file_outside_root_when_supported(self) -> None:
        link_function = getattr(os, "link", None)
        if not callable(link_function):
            self.skipTest("This Python build does not expose os.link")
        link = self.root / "linked-outside.txt"
        try:
            link_function(self.outside, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Hard-link creation is unavailable: {exc}")
        with self.assertRaisesRegex(ValueError, "Hard-linked"):
            self.read("linked-outside.txt")

    def test_enforces_size_limit(self) -> None:
        (self.root / "large.bin").write_bytes(b"12345")
        with self.assertRaisesRegex(ValueError, "limit"):
            self.read("large.bin", max_bytes=4)

    def test_rejects_invalid_utf8(self) -> None:
        (self.root / "invalid.txt").write_bytes(b"\xff")
        with self.assertRaises(UnicodeDecodeError):
            self.read("invalid.txt")

    def test_rejects_non_regular_target(self) -> None:
        with self.assertRaises((OSError, ValueError)):
            self.read("nested")

    def test_rejects_invalid_limit(self) -> None:
        for value in (-1, True, "200"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                read_confined_text_file(self.root, "note.txt", max_bytes=value)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
