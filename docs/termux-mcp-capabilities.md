# Termux MCP bridge: bounded local autonomy

This adds a local stdio MCP server for a trusted checkout. It is a practical
bridge for a local MCP client such as Codex CLI; it does **not** connect this
Android phone directly to the ChatGPT mobile session.

## Exposed tools

The installed server `python -m authoritylab.termux_mcp_server` exposes exactly
four tools:

- `status`: bounded workspace readiness and file-size limit.
- `list_files`: at most 100 direct file names; excludes directories and unsafe
  entries.
- `read_file`: UTF-8 files within the configured repository, maximum 200 KB.
- `diagnostics`: bounded runtime metadata; it does not return file contents.

It does **not** expose `write_file`, `git_status`, `git_diff`, or `run_tests`.
Those names may exist as internal `BoundedWorkspace` methods, but they are not
MCP endpoints in this server. The separate example
`examples/termux_mcp_server_authoritylab.py` exposes only the three read-only
tools `status`, `list_files`, and `read_file`.

Neither server exposes a generic shell tool, arbitrary command input, Git push,
Git commit, or credential access. Reads remain confined to the configured
workspace.

## SDK compatibility

The repository's MCP extra targets the MCP Python SDK v2 API (`mcp>=2.3,<3`). Keep the same major version in the Termux virtual environment and run the included stdio smoke check after installation.

## Fresh-checkout Termux verification

These commands leave the existing `~/authoritylab` checkout untouched. Activate the virtual environment where you want to run the client; if it is not `~/mcp-venv`, substitute its actual path.

```bash
source "$HOME/mcp-venv/bin/activate" || exit 1
AUDIT_DIR="$HOME/authoritylab-main-audit"
if [ -e "$AUDIT_DIR" ]; then
  echo "Audit path already exists; choose a new AUDIT_DIR."
  exit 1
fi
git clone --branch main --single-branch https://github.com/xiiitore/authoritylab.git "$AUDIT_DIR" || exit 1
SITE_DIR="$(mktemp -d "$HOME/authoritylab-main-site.XXXXXX")" || exit 1
python -m pip install --target "$SITE_DIR" "$AUDIT_DIR[mcp,test]" || exit 1
cd "$AUDIT_DIR" || exit 1
PYTHONPATH="$SITE_DIR" python examples/check_termux_mcp_stdio.py || exit 1
PYTHONPATH="$SITE_DIR" python examples/check_termux_workspace_stdio.py || exit 1
PYTHONPATH="$SITE_DIR" python -m unittest discover -v
```

The first smoke test checks the three-tool read-only example server. The second checks the installed four-tool server against a disposable Git repository: status, list, read, bounded diagnostics, and parent-traversal rejection. It also verifies that `write_file` is not exposed. It does not touch the user's actual checkout. Keep the audit checkout and target directory until the output has been reviewed.

## Install in Termux

From the repository root, activate the existing virtual environment first.
Then run:

```bash
cd ~/authoritylab
source ~/mcp-venv/bin/activate
python -m pip install -e '.[mcp]'
export AUTHORITYLAB_ROOT="$PWD"
python -m authoritylab.termux_mcp_server
```

The last command runs the server in the foreground. Stop it with Ctrl-C after
confirming it starts. It uses stdio and opens no listening network port.

## Register with Codex CLI

In a second Termux session, with the repository and virtual environment
available, run:

```bash
cd ~/authoritylab
source ~/mcp-venv/bin/activate
codex mcp add authoritylab-termux --env AUTHORITYLAB_ROOT="$PWD" -- "$VIRTUAL_ENV/bin/python" -m authoritylab.termux_mcp_server
codex mcp list
```

Restart Codex CLI after adding the server if it was already running. Confirm
that exactly `status`, `list_files`, `read_file`, and `diagnostics` appear.
Do not expect `write_file`, `git_status`, `git_diff`, or `run_tests` to be
available through this server.

If your venv is not `~/mcp-venv`, activate the actual environment where the
`mcp` package was installed. Do not put access tokens or passwords into this
repository or into the command history.

## Limits and security

This is least-privilege application logic, not a kernel-enforced sandbox.
Path checks reject absolute paths, parent traversal, backslashes, NULs, and
symbolic links, but they are not race-free against a hostile concurrent local
process. The server does not expose a test runner or mutation operations.
Restrict `AUTHORITYLAB_ROOT` to the intended repository, not all of `$HOME` or
shared storage.

A stdio MCP server is local to its host process. Connecting it to ChatGPT from
outside Termux requires a separate supported remote MCP endpoint or secure
authenticated relay; do not expose a public unauthenticated HTTP listener.


## Verification boundary

The CI stdio smoke test verifies SDK compatibility and the local tool surface on the CI host. It does not establish a live connection from ChatGPT mobile to the Android device. Local stdio is consumed by its host process; a remote ChatGPT connection requires a separately reviewed, authenticated relay or supported remote MCP endpoint. See [the capability matrix](capability-matrix.md) for current evidence and remaining gates.
