# GitHub-to-Termux task mailbox (experimental)

**Status: experimental; not yet device-verified.** This channel avoids the need for
ChatGPT mobile to connect directly to a custom MCP server. ChatGPT can place a
strictly formatted task comment on a dedicated GitHub issue; a Termux worker
polls that issue over outbound HTTPS and posts a result comment.

It does not create a public listener, tunnel, or direct device connection. The
worker must be running, online, and configured with a GitHub token. A GitHub
issue comment is a transport, not a guarantee that ChatGPT can autonomously
continue working between turns.

## Current allowed actions

- `status`: reports readiness and the file-size limit.
- `list_files`: lists a bounded set of names in the configured workspace.
- `read_file`: reads one allowed relative path, with a 20,000-character result cap.

No shell, arbitrary Python, write, Git mutation, test execution, or filesystem
path outside the preconfigured `AUTHORITYLAB_ROOT` is exposed by this mailbox.
Free-form prose is never interpreted as executable instructions.

## Task envelope

A task is a GitHub issue comment authored by a username explicitly listed in
`AUTHORITYLAB_GITHUB_ALLOWED_AUTHORS`. The body must start with the marker
below, followed immediately by one JSON object:

```text
<!-- authoritylab-task:v1 -->
{"version":1,"task_id":"probe-001","action":"status","arguments":{}}
```

Supported actions and arguments:

```json
{"version":1,"task_id":"probe-002","action":"list_files","arguments":{}}
{"version":1,"task_id":"probe-003","action":"read_file","arguments":{"path":"README.md"}}
```

Task IDs must be unique. Results use the `<!-- authoritylab-result:v1 -->`
marker and include a task ID, source comment ID, status, and bounded result or
safe error code. The worker keeps a local state file to avoid processing the
same comment twice.

## Required configuration

Use a dedicated GitHub issue as the mailbox; do not use an implementation or
security-tracking issue as a live mailbox. Configure:

- `AUTHORITYLAB_GITHUB_TOKEN`: fine-grained token restricted to this repository,
  with only the Issues read/write permissions needed to read and post comments.
- `AUTHORITYLAB_GITHUB_REPO`: `owner/repository`.
- `AUTHORITYLAB_GITHUB_ISSUE`: the dedicated mailbox issue number.
- `AUTHORITYLAB_GITHUB_ALLOWED_AUTHORS`: explicit comma-separated GitHub logins.
- `AUTHORITYLAB_ROOT`: an existing, narrowly scoped Git checkout.
- Optional `AUTHORITYLAB_GITHUB_STATE`: local state file path.

Never put the token in a repository, issue, command argument, or screenshot. Keep
it in a private Termux shell environment or protected configuration file. Do not
allow untrusted authors. A token that can post issue comments should not also
have Contents write, Actions write, or administration permissions.

## Start / stop

Install the reviewed branch in a disposable checkout first. Ensure the active
Python environment can import `authoritylab.termux_workspace_tools`. Start with
the dedicated workspace and environment variables above, then run:

```sh
python -m authoritylab.github_termux_mailbox
```

Stop with Ctrl-C. The worker only makes outbound HTTPS requests to GitHub.
This does not establish that the Android runtime, account permissions, or
end-to-end workflow work until the local smoke test is performed.

## Blocking validation

Before relying on this:

1. Run unit tests and Python 3.11–3.13 CI.
2. Review API token permissions and the configured author allowlist.
3. Test duplicate comments/task IDs, malformed JSON, unknown actions, path
   traversal, oversized file results, API rate limits, and lost network.
4. Test in Termux using a dedicated repository containing no secrets.
5. Verify a task can be posted and a result read back without exposing the token.
6. Keep the worker read-only. Write/execute operations require a separate design.

This is an initial transport milestone, not a production-certified agent.
