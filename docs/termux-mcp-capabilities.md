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
