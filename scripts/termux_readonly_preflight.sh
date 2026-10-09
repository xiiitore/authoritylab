#!/data/data/com.termux/files/usr/bin/bash
# Read-only AuthorityLab Termux preflight.
# No network access, no package installation, no Docker commands that mutate state,
# no environment-variable dumps, no secret/key/token reads.
set -u
umask 077

section() { printf '\n## %s\n' "$1"; }
command_status() {
  if command -v "$1" >/dev/null 2>&1; then
    printf '%s: available (%s)\n' "$1" "$(command -v "$1")"
  else
    printf '%s: unavailable\n' "$1"
  fi
}

printf 'AuthorityLab Termux read-only preflight\n'
printf 'Timestamp UTC: '
date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || printf 'UNKNOWN\n'
printf 'This report intentionally excludes environment variables, credentials, home-file listings, and private data.\n'

section 'Device/runtime'
printf 'uname: '; uname -srm 2>/dev/null || printf 'UNKNOWN\n'
printf 'Android release: '
getprop ro.build.version.release 2>/dev/null | head -n 1 || true
printf 'Termux prefix: %s\n' "${PREFIX:-UNKNOWN}"
printf 'Architecture: %s\n' "${HOSTTYPE:-UNKNOWN}"

section 'Tool availability'
for cmd in python python3 pip git bash clang make pkg-config docker podman proot-distro; do
  command_status "$cmd"
done
if command -v python >/dev/null 2>&1; then
  python --version 2>&1
elif command -v python3 >/dev/null 2>&1; then
  python3 --version 2>&1
fi
if command -v git >/dev/null 2>&1; then
  git --version 2>&1
fi

section 'Container runtime (read-only probes)'
if command -v docker >/dev/null 2>&1; then
  docker --version 2>&1 || true
  # Read-only info query only; failure is reported, not treated as proof of absence.
  docker info --format '{{.ServerVersion}}' 2>&1 | sed -n '1,3p' || true
else
  printf 'Docker CLI unavailable; this does not establish whether a remote/container service exists.\n'
fi
if command -v podman >/dev/null 2>&1; then
  podman --version 2>&1 || true
  podman info --format '{{.Host.OCIRuntime.Name}}' 2>&1 | sed -n '1,3p' || true
else
  printf 'Podman CLI unavailable.\n'
fi

section 'Repository metadata'
repo="${HOME:-}/authoritylab"
if [ -d "$repo/.git" ]; then
  printf 'Repository: %s\n' "$repo"
  git -C "$repo" rev-parse --show-toplevel 2>&1 || true
  printf 'HEAD: '; git -C "$repo" rev-parse HEAD 2>&1 || printf 'UNKNOWN\n'
  printf 'Branch: '; git -C "$repo" branch --show-current 2>&1 || printf 'UNKNOWN\n'
  printf 'Working tree status (filenames only):\n'
  git -C "$repo" status --short 2>&1 | sed -n '1,40p'
  printf 'Origin URL: '
  # Deliberately strip embedded userinfo and query strings to avoid credential leakage.
  git -C "$repo" remote get-url origin 2>/dev/null | sed -E 's#(https?://)[^/@]+:[^/@]+@#\1[REDACTED]@#; s#\?.*$##' | sed -E 's#(https?://)[^/]+/([^/]+/[^/]+).*#\1github.com/\2#' | head -n 1
  printf 'Tracked project files present: '
  for f in pyproject.toml README.md core.py test_workflow.py; do
    [ -f "$repo/$f" ] && printf '%s ' "$f"
  done
  printf '\n'
else
  printf 'Repository not found at %s; no files were changed.\n' "$repo"
fi

section 'Python package/test preflight (no tests executed)'
if [ -d "${HOME:-}/authoritylab" ]; then
  if command -v python >/dev/null 2>&1; then py=python
  elif command -v python3 >/dev/null 2>&1; then py=python3
  else py=''
  fi
  if [ -n "$py" ]; then
    "$py" -c 'import sys; print("Python executable:", sys.executable); print("Python version:", sys.version.split()[0])' 2>&1 || true
    "$py" -m pip --version 2>&1 || true
    "$py" -m pytest --version 2>&1 || true
  fi
fi

section 'Interpretation'
printf 'This is inventory only. It does not test sandbox isolation, hostile workloads, audit integrity, key custody, recovery, or production security.\n'
printf 'A missing Docker CLI in Termux is not a failure if the intended design runs handlers elsewhere, but the actual execution boundary must then be identified and tested.\n'
printf 'No changes were intentionally made to the repository, packages, device configuration, or running services.\n'
