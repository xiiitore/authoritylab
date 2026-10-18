"""Tests for the dependency-free repository health check."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.repository_health_check import check_repository


class RepositoryHealthCheckTests(unittest.TestCase):
    def _make_repo(self, root: Path) -> None:
        for relative in (
            "README.md",
            "WORKFLOW_GOVERNANCE.md",
            "architecture.md",
            "verification.md",
            "pyproject.toml",
            ".github/workflows/python-package-conda.yml",
            "docs/capability-registry.schema.json",
            "tests/test_capability_registry.py",
        ):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("placeholder\n", encoding="utf-8")
        registry = {
            "registry_schema_version": "1.0.0",
            "status": "INVENTORY_ONLY_NOT_EXECUTION_VERIFIED",
            "tool_count": 2,
            "provider_counts": {"local": 2},
            "tools": [
                {"tool_id": "local.status", "provider": "local", "execution_verified": False},
                {"tool_id": "local.read", "provider": "local", "execution_verified": False},
            ],
        }
        (root / "capability-registry.json").write_text(
            json.dumps(registry), encoding="utf-8"
        )

    def test_valid_repository_contract_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repo(root)
            self.assertEqual(check_repository(root), [])

    def test_duplicate_ids_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repo(root)
            path = root / "capability-registry.json"
            registry = json.loads(path.read_text(encoding="utf-8"))
            registry["tools"][1]["tool_id"] = registry["tools"][0]["tool_id"]
            path.write_text(json.dumps(registry), encoding="utf-8")
            self.assertIn(
                "capability registry: tool_id values must be unique",
                check_repository(root),
            )

    def test_claimed_execution_verification_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repo(root)
            path = root / "capability-registry.json"
            registry = json.loads(path.read_text(encoding="utf-8"))
            registry["tools"][0]["execution_verified"] = True
            path.write_text(json.dumps(registry), encoding="utf-8")
            self.assertTrue(any("explicitly unverified" in e for e in check_repository(root)))

    def test_missing_required_artifact_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_repo(root)
            (root / "architecture.md").unlink()
            self.assertIn("required file missing: architecture.md", check_repository(root))


if __name__ == "__main__":
    unittest.main()
