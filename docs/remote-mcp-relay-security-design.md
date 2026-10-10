# Remote MCP relay security design — proposal only

**Status:** DESIGN ONLY — NOT DEPLOYED  
**Purpose:** Make a trusted Termux workspace reachable from a supported remote MCP host without opening a public listener on the Android device.

## Decision

A remote relay is required if the goal is to call Termux-hosted tools from a remote ChatGPT MCP host. A local stdio process is only available to its parent process. This document proposes a design; it is not evidence that the ChatGPT mobile client supports or has configured the required custom remote MCP connection.

## Topology

1. **Remote MCP gateway:** HTTPS endpoint on a managed host. It accepts MCP requests only from an authenticated, explicitly configured client.
2. **Termux agent:** an outbound-only connection from the Android device to the gateway. The device does not accept inbound Internet connections and does not run a public listener.
3. **Request broker:** associates each authenticated request with the current device session, assigns a unique request ID, and expires work that is not acknowledged within a short deadline.
4. **Local tool adapter:** invokes the existing fixed tool allowlist. It must not accept arbitrary shell commands, executable paths, arbitrary environment variables, or arbitrary filesystem roots.

## Authentication and authorization

- Require a supported OAuth flow or a high-entropy per-client bearer credential. Prefer short-lived credentials and scoped authorization.
- Store server secrets in the host's secret manager; never put them in Git, a URL, a command-line argument, or logs.
- Store the Termux agent credential outside the repository in a private file with restrictive permissions or a platform-backed secret store. Never commit it.
- Authenticate the device agent separately from the remote MCP client. The agent must prove possession of its own credential; knowledge of a client token must not grant device-agent authority.
- Support immediate revocation, credential rotation, and a kill switch that stops dispatch and disconnects the device agent.
- Deny by default when identity, scope, policy, or device session is missing or ambiguous.

## Tool policy

- Default remote allowlist: `status`, `list_files`, and `read_file`, rooted in a dedicated directory such as `~/mcp-share`.
- Do not expose `write_file`, `run_tests`, arbitrary Git mutations, or generic shell execution through the first relay release.
- If mutation tools are later enabled, require a separate explicit policy, narrow path scope, bounded input, pre/post state evidence, and an independent approval gate. No `git push`, `git commit`, credential access, or unrestricted process execution.
- Enforce path confinement and file-size limits in the device process, not only in the gateway. Reject traversal, symlinks, unsupported filesystem semantics, and unexpected file types.
- Validate tool names and argument schemas on both gateway and device agent.

## Abuse and resource limits

Initial values are conservative defaults to validate in tests, not claims about measured capacity:

- Maximum request body: 64 KiB.
- Maximum response body: 256 KiB.
- Maximum file read: 200,000 bytes.
- Maximum queued requests per device: 4.
- Per-client rate limit: 30 requests/minute, with a burst of 5.
- Request deadline: 15 seconds for metadata/list/read operations; cancellation on expiry.
- Reject oversized inputs before parsing large payloads; cap log fields and response serialization.
- No retry that repeats a mutation automatically. Read-only retries must use bounded attempts and request IDs.

The initial limits should be configurable and lowered if load or security testing indicates risk.

## Session and replay protection

- Use TLS for every network hop.
- Give each request a cryptographically unpredictable ID, expiry timestamp, and authenticated client/device context.
- Reject duplicate or expired request IDs; do not dispatch the same request twice after an uncertain acknowledgement.
- Bind the active device session to a unique agent identity and a lease. On disconnect or lease expiry, mark the device unavailable and fail closed.
- Do not accept arbitrary callback URLs or let a request choose its own downstream target.

## Audit and privacy

- Log timestamp, request ID, authenticated principal ID, tool name, decision/status, latency, byte counts, and reason codes.
- Never log bearer tokens, authorization headers, file contents, request bodies by default, or environment variables.
- Redact paths where they may reveal private project structure; do not include sensitive content in error messages.
- Set a short retention period and restrict log access. Record security events and revocations without recording secrets.

## Deployment gates

Deployment is **BLOCKED** until all are satisfied:

1. Confirm that the target ChatGPT host/account supports configuring the required remote MCP endpoint and authentication.
2. Review the exact gateway and agent code, dependency lock, deployment permissions, and secret handling.
3. Test authentication failures, expired/revoked credentials, cross-client isolation, replay, queue exhaustion, oversized payloads, timeouts, cancellation, and device disconnects.
4. Test path traversal, symlinks, hard links, file-size limits, and attempts to invoke tools outside the allowlist on the actual Termux filesystem.
5. Demonstrate that the device makes outbound connections only and that the gateway exposes no unauthenticated route.
6. Run independent security review and verify rollback, revocation, and kill-switch behavior.
7. Deploy to a private/staging endpoint first. Verify endpoint identity and tool allowlist from the remote MCP client before allowing any real repository access.
8. Require explicit approval before enabling write or execution tools.

## Current evidence boundary

The AuthorityLab stdio smoke tests run on GitHub-hosted Linux and exercise local subprocess transports. They do not validate a network relay, OAuth, Internet exposure, ChatGPT connector configuration, or Android/Termux behavior. No relay, public endpoint, or remote credential has been created by this work.
