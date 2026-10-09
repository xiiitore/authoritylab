"""Tests for confined file reading and symlink-resistant path traversal."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from authoritylab.secure_paths import read_confined_text_file


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

    def test_rejects_hard_link_to_file_outside_root(self) -> None:
        link = self.root / "linked-outside.txt"
        try:
            os.link(self.outside, link)
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
