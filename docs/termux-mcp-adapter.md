# Termux MCP read-only adapter

This adapter connects the existing AuthorityLab workflow engine to the three
already-restricted Termux MCP operations: `status`, `list_files`, and
`read_file`. It does not create a server and does not itself limit filesystem
access; the supplied functions must retain their own path and file-size checks.

## Integration pattern

A complete reference server is provided at
[`examples/termux_mcp_server_authoritylab.py`](../examples/termux_mcp_server_authoritylab.py).
It preserves the `~/mcp-share` directory boundary, the 200 KB file limit, UTF-8
reading, and the three read-only MCP endpoints while routing calls through
AuthorityLab. File reads use descriptor-relative opens with `O_NOFOLLOW` for
path components and fail closed if the platform lacks the required features.

The example is deliberately a separate file. It does **not** replace or edit
`~/termux_mcp_server.py` automatically. Compare it against the local server
before adopting it, and keep the original as a rollback copy.

Do not expose the internal implementations as separate decorated MCP tools;
otherwise clients could bypass the workflow wrappers. The exposed endpoints
should be only the three wrappers that call `dispatch_read_only_mcp_tool`.

## Enforcement semantics

- The dispatch function checks the operation allowlist before invoking the
  workflow engine.
- The registered handlers validate arguments before calling the supplied
  implementation functions.
- Unknown operations and any workflow result other than `PASS` raise
  `MCPAdapterError`, which the MCP wrapper should convert to `ToolError`.
- `PASS` means the configured AuthorityLab result checks passed. It is not a
  security certification and does not replace filesystem-level validation.
- Audit records remain in memory unless the host application persists them.
- The reader rejects a symlinked root, rejects symlinked path components, and
  rejects files with multiple hard links. Directory listing also uses a held
  directory descriptor and excludes symlinks and hard-linked entries.
- These controls reduce path-substitution risk; they do not protect against
  every same-user filesystem threat. Audit records are not durable by default.

## Tests

Run from the repository root in the project's Python environment:

```bash
python -m pip install -e .
python -m unittest test_termux_mcp_adapter test_termux_mcp_dispatch -v
python -m unittest discover -v
```

In the existing Termux environment where the MCP SDK is installed, also run:

```bash
python examples/termux_mcp_server_authoritylab.py --check
```

This last command checks that the reference server can load and call its
registered `status` tool. It is a separate platform/integration check; the
GitHub CI job does not install or emulate the Termux MCP runtime.
