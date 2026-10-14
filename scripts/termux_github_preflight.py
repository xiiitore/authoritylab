#!/usr/bin/env python3
"""Read-only preflight for using a local Termux checkout with GitHub.

This script does not fetch, push, edit files, or print credential-bearing URLs.
Run it from inside the repository: python scripts/termux_github_preflight.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=10,
    )


def safe_remote(value: str) -> str:
    """Return only a GitHub host/path; discard userinfo, query, and fragment."""
    value = value.strip()
    if value.startswith("git@") and ":" in value:
        host, path = value[4:].split(":", 1)
    else:
        parsed = urlsplit(value if "://" in value else "https://" + value)
        host, path = parsed.hostname or "", parsed.path.lstrip("/")
    path = path.removesuffix(".git").strip("/")
    if not host or not path or any(part in {"", ".", ".."} for part in path.split("/")):
        return "configured (unrecognized format; value withheld)"
    return f"{host}/{path}"


def main() -> int:
    report: dict[str, object] = {"checks": []}
    checks: list[dict[str, str]] = report["checks"]  # type: ignore[assignment]
    cwd = Path.cwd()

    if not shutil.which("git"):
        checks.append({"name": "git", "status": "FAIL", "detail": "git executable not found"})
        report["overall"] = "BLOCKED"
        print(json.dumps(report, indent=2))
        return 2

    root = run(["git", "rev-parse", "--show-toplevel"], cwd)
    if root.returncode:
        checks.append({"name": "repository", "status": "FAIL", "detail": "run this script inside a Git checkout"})
        report["overall"] = "BLOCKED"
        print(json.dumps(report, indent=2))
        return 2

    repo = Path(root.stdout.strip())
    branch = run(["git", "branch", "--show-current"], repo)
    status = run(["git", "status", "--porcelain"], repo)
    remote = run(["git", "remote", "get-url", "origin"], repo)

    checks.append({"name": "git", "status": "PASS", "detail": "git executable available"})
    checks.append({"name": "repository", "status": "PASS", "detail": str(repo)})
    checks.append({
        "name": "branch",
        "status": "PASS" if branch.returncode == 0 and branch.stdout.strip() else "WARN",
        "detail": branch.stdout.strip() or "detached HEAD or branch unavailable",
    })
    checks.append({
        "name": "working_tree",
        "status": "PASS" if status.returncode == 0 and not status.stdout.strip() else "WARN",
        "detail": "clean" if status.returncode == 0 and not status.stdout.strip() else "uncommitted changes present or status unavailable",
    })

    if remote.returncode == 0:
        checks.append({"name": "origin", "status": "PASS", "detail": safe_remote(remote.stdout)})
    else:
        checks.append({"name": "origin", "status": "WARN", "detail": "no origin remote configured"})

    gh = shutil.which("gh")
    if gh:
        auth = run([gh, "auth", "status"], repo)
        checks.append({
            "name": "github_cli_auth",
            "status": "PASS" if auth.returncode == 0 else "WARN",
            "detail": "authenticated according to gh" if auth.returncode == 0 else "not authenticated or auth check failed; output withheld",
        })
    else:
        checks.append({
            "name": "github_cli_auth",
            "status": "WARN",
            "detail": "gh CLI not installed; Git SSH or another credential method may still work",
        })

    report["overall"] = "PASS" if root.returncode == 0 and remote.returncode == 0 else "PARTIAL"
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
