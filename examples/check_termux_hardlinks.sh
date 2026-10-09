#!/data/data/com.termux/files/usr/bin/bash
# Create real hard links using the Termux shell, then test AuthorityLab guards.
# Uses only a fresh temporary directory under HOME and removes only that directory.
set -eu

: "${PYTHONPATH:?Set PYTHONPATH to the fresh AuthorityLab target-install directory}"
TMP_ROOT="$(mktemp -d "$HOME/authoritylab-hardlink-check.XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT
ROOT="$TMP_ROOT/confined"
mkdir "$ROOT"
printf 'inside target\n' > "$ROOT/original.txt"
printf 'outside target\n' > "$TMP_ROOT/outside.txt"

if ! ln "$ROOT/original.txt" "$ROOT/alias.txt" 2>/dev/null; then
  echo "SKIP: shell ln could not create a hard link on this filesystem"
  exit 0
fi
if ! ln "$TMP_ROOT/outside.txt" "$ROOT/outside-alias.txt" 2>/dev/null; then
  echo "SKIP: shell ln could not create a hard link on this filesystem"
  exit 0
fi

python - "$ROOT" <<'PY'
import os
import sys
from pathlib import Path
from authoritylab.secure_paths import list_confined_files, read_confined_text_file

root = Path(sys.argv[1])
for name in ("original.txt", "alias.txt", "outside-alias.txt"):
    metadata = os.stat(root / name)
    print(f"Observed {name}: st_nlink={metadata.st_nlink}")
    if metadata.st_nlink < 2:
        raise SystemExit(f"FAIL: {name} is not observed as a hard-linked file")

listed = list_confined_files(root)
if listed:
    raise SystemExit(f"FAIL: hard-linked entries appeared in listing: {listed!r}")
print("PASS: listing excludes all actual hard-linked entries")

for name in ("original.txt", "alias.txt", "outside-alias.txt"):
    try:
        read_confined_text_file(root, name)
    except (OSError, ValueError):
        print(f"PASS: read rejected for {name}")
    else:
        raise SystemExit(f"FAIL: read unexpectedly accepted {name}")
PY
