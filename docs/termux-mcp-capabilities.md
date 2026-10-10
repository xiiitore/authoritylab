# Termux MCP bridge: bounded local autonomy

This adds a local stdio MCP server for a trusted checkout. It is a practical
bridge for a local MCP client such as Codex CLI; it does **not** connect this
Android phone directly to the ChatGPT mobile session.

## Exposed tools

- `status`: configured repository root and fixed tool allowlist.
- `list_files`: at most 200 direct entries; skips common generated directories
  and symbolic links.
- `read_file`: UTF-8 files within the repository, maximum 200 KB.
- `write_file`: write or replace UTF-8 files within the repository, maximum
  200 KB. Parent directories must already exist.
- `git_status` and `git_diff`: inspect repository state.
- `run_tests`: runs only `python -m unittest discover -v`, with a timeout.

There is no generic shell tool, arbitrary command input, network client, Git
push, Git commit, credential access, or access to paths outside the configured
repository. The test runner executes code from the checkout; only use it with a
repository you trust.

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

The first smoke test checks the three-tool read-only reference server. The second checks the separate seven-tool workspace server against a disposable Git repository, including bounded write/read and path/symlink/hard-link rejection. A hard-link `SKIP` means that filesystem did not permit the test; it is not a PASS. Keep the audit checkout and target directory until the output has been reviewed.

For the bounded workspace server (seven tools), the repository now includes `examples/check_termux_workspace_stdio.py`. It launches the server against a fresh temporary Git repository and checks the tool allowlist, status/list/read/write, git status/diff, test runner, parent-traversal rejection, symlink rejection, and hard-link write rejection where the filesystem supports hard links. It does not touch the user's actual checkout. The three-tool `check_termux_mcp_stdio.py` remains a separate read-only reference-server test.

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
the server tools appear, then test `status`, `git_status`, and `read_file`
before using `write_file` or `run_tests`.

If your venv is not `~/mcp-venv`, activate the actual environment where the
`mcp` package was installed. Do not put access tokens or passwords into this
repository or into the command history.

## Limits and security

This is least-privilege application logic, not a kernel-enforced sandbox.
Path checks reject absolute paths, parent traversal, backslashes, NULs, and
symbolic links, but they are not race-free against a hostile concurrent local
process. Test execution has a timeout but still runs as the Termux user.
Restrict `AUTHORITYLAB_ROOT` to the repository, not all of `$HOME` or shared
storage. Review diffs before committing or pushing.

A stdio MCP server is local to its host process. Connecting it to ChatGPT from
outside Termux requires a separate supported remote MCP endpoint or secure
authenticated relay; do not expose a public unauthenticated HTTP listener.


## Verification boundary

The CI stdio smoke test verifies SDK compatibility and the local tool surface on the CI host. It does not establish a live connection from ChatGPT mobile to the Android device. Local stdio is consumed by its host process; a remote ChatGPT connection requires a separately reviewed, authenticated relay or supported remote MCP endpoint. See [the capability matrix](capability-matrix.md) for current evidence and remaining gates.
