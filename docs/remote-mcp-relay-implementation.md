# Remote MCP relay prototype — implementation notes

**Status: EXPERIMENTAL / NOT DEPLOYED.** This branch adds a staging prototype only.
It does not create a cloud service, DNS record, tunnel, credential, or ChatGPT
connector. Do not merge or expose it publicly before the gates below pass.

## Components

- `remote_mcp_relay.py`: stateless HTTP/JSON-RPC MCP gateway with an in-memory,
  bounded request broker. It exposes only `status`, `list_files`, and
  `read_file`. The listener refuses non-loopback bind addresses.
- `termux_relay_agent.py`: outbound polling worker for Termux. It uses the
  existing `BoundedWorkspace` and does not accept shell commands, arbitrary
  executable paths, Git writes, or caller-selected workspace roots.
- `test_remote_mcp_relay.py`: broker, authentication, allowlist, size-limit,
  and HTTP round-trip tests.

The broker is in memory. Restarting the gateway drops pending requests; expired
or late results are rejected. No automatic retry is performed. This is intended
to fail closed, not to provide durable queue semantics.

## Local-only smoke test

Use a disposable checkout and Python 3.11+ on a trusted machine. Generate two
independent random secrets using a secret manager; do not commit them or put
them in shell command history. Both must be at least 32 characters.

Gateway process (local test only):

```sh
read -rsp "Client token: " AUTHORITYLAB_CLIENT_TOKEN; printf '\\n'
export AUTHORITYLAB_CLIENT_TOKEN
read -rsp "Agent token: " AUTHORITYLAB_AGENT_TOKEN; printf '\\n'
export AUTHORITYLAB_AGENT_TOKEN
python remote_mcp_relay.py
```

The default listener is `127.0.0.1:8765`. It is intentionally not reachable
from another device. For a real remote connection, the gateway must remain
loopback-bound behind an authenticated TLS reverse proxy or an equivalent
reviewed ingress. Never bind the Python server directly to a public interface.

Termux agent (only after a reviewed HTTPS gateway exists):

```sh
export AUTHORITYLAB_RELAY_URL='https://<reviewed-gateway-host>'
read -rsp "Agent token: " AUTHORITYLAB_AGENT_TOKEN; printf '\\n'
export AUTHORITYLAB_AGENT_TOKEN
export AUTHORITYLAB_ROOT="$HOME/mcp-share"
python termux_relay_agent.py
```

Use an existing, narrowly scoped directory for `AUTHORITYLAB_ROOT`; do not
point it at the whole home directory or shared storage. Keep the agent token in
a private configuration file or secret store with restrictive permissions.
The client token is separate and must never be installed on the phone.

## Test

```sh
python -m unittest -v test_remote_mcp_relay.py
```

These tests exercise local HTTP on loopback. They do not establish TLS, public
ingress security, Android/Termux compatibility, ChatGPT connector compatibility,
or production readiness. CI is not a substitute for the actual device smoke test.

## Blocking deployment gates

1. Run this branch's tests and the full repository suite; inspect all failures.
2. Independently review HTTP/JSON-RPC handling, authentication, queue races,
   path confinement, body limits, logs, and timeout/disconnect behavior.
3. Verify the exact MCP protocol version and authentication method supported by
   the intended ChatGPT remote connector. Do not assume the mobile app can add
   an arbitrary custom MCP server.
4. Deploy to private staging behind HTTPS with separate client and agent
   credentials. Verify credential revocation and a kill switch.
5. On the actual Termux device, verify the active Python environment, the
   `BoundedWorkspace` import, path/symlink/hard-link rejection, file-size
   limits, and that the agent initiates outbound connections only.
6. Confirm that unauthenticated requests, replayed/expired results, oversized
   messages, and tool names outside the allowlist are rejected.
7. Do not enable write, test-execution, Git mutation, or arbitrary shell tools
   in this relay. Those require a separate authorization design and review.

Until all applicable gates pass, the result is a **prototype**, not a usable or
certified bridge. No remote endpoint is active as a result of this branch.
