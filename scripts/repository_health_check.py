#!/usr/bin/env python3
"""Fast, dependency-free repository contract checks for AuthorityLab.

This is a structural health check, not a security audit or test-suite substitute.
It intentionally reports inventory entries as unverified rather than inferring
that a declared capability can safely execute.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_PATHS = (
    "README.md",
    "WORKFLOW_GOVERNANCE.md",
    "architecture.md",
    "verification.md",
    "pyproject.toml",
    ".github/workflows/python-package-conda.yml",
    "docs/capability-registry.schema.json",
    "tests/test_capability_registry.py",
)


def _load_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{path.name}: cannot read valid UTF-8 JSON ({type(exc).__name__})")
        return None
    if not isinstance(value, dict):
        errors.append(f"{path.name}: top-level JSON value must be an object")
        return None
    return value


def check_repository(root: Path) -> list[str]:
    """Return deterministic, human-readable contract violations; empty means pass."""
    root = Path(root)
    errors: list[str] = []

    for relative in REQUIRED_PATHS:
        if not (root / relative).is_file():
            errors.append(f"required file missing: {relative}")

    registry_path = root / "capability-registry.json"
    registry = _load_json(registry_path, errors) if registry_path.is_file() else None
    if not registry_path.is_file():
        errors.append("required file missing: capability-registry.json")

    if registry is not None:
        entries = registry.get("tools")
        if not isinstance(entries, list):
            errors.append("capability registry: 'tools' must be an array")
            entries = []

        if registry.get("registry_schema_version") != "1.0.0":
            errors.append("capability registry: unsupported registry_schema_version")
        if registry.get("status") != "INVENTORY_ONLY_NOT_EXECUTION_VERIFIED":
            errors.append("capability registry: status must not imply execution verification")
        if registry.get("tool_count") != len(entries):
            errors.append("capability registry: tool_count does not match tools length")

        ids: list[str] = []
        providers: list[str] = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                errors.append(f"capability registry: tools[{index}] must be an object")
                continue
            tool_id = entry.get("tool_id")
            provider = entry.get("provider")
            if not isinstance(tool_id, str) or not tool_id.strip():
                errors.append(f"capability registry: tools[{index}].tool_id must be nonempty")
            else:
                ids.append(tool_id)
            if not isinstance(provider, str) or not provider.strip():
                errors.append(f"capability registry: tools[{index}].provider must be nonempty")
            else:
                providers.append(provider)
            if entry.get("execution_verified") is not False:
                errors.append(
                    f"capability registry: tools[{index}] must remain explicitly unverified"
                )

        if len(ids) != len(set(ids)):
            errors.append("capability registry: tool_id values must be unique")
        expected_counts = dict(Counter(providers))
        if registry.get("provider_counts") != expected_counts:
            errors.append("capability registry: provider_counts does not match tools entries")

    return errors


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(args[0]).resolve() if args else Path(__file__).resolve().parents[1]
    errors = check_repository(root)
    if errors:
        print("Repository health: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Repository health: PASS")
    print("Checked required project artifacts and capability-registry invariants.")
    print("This result is not a substitute for tests, security review, or execution verification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
