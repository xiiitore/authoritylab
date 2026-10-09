# Termux MCP read-only adapter

This adapter connects the existing AuthorityLab workflow engine to the three
already-restricted Termux MCP operations: `status`, `list_files`, and
`read_file`. It does not create a server and does not itself limit filesystem
access; the supplied functions must retain their own path and file-size checks.

## Integration pattern

In the Termux server, keep the current implementations as internal functions
(e.g. `_status_impl`, `_list_files_impl`, and `_read_file_impl`) and register
those implementations with the workflow registry. Expose MCP-decorated wrapper
functions that dispatch through AuthorityLab:

```python
from authoritylab import GovernancePolicy, WorkflowCore
from authoritylab.tools import ToolRegistry
from authoritylab.termux_mcp_adapter import (
    MCPAdapterError,
    dispatch_read_only_mcp_tool,
    register_read_only_mcp_tools,
)

registry = ToolRegistry()
register_read_only_mcp_tools(
    registry,
    status=_status_impl,
    list_files=_list_files_impl,
    read_file=_read_file_impl,
)
workflow = WorkflowCore(registry, GovernancePolicy())

def _dispatch(kind, payload):
    try:
        return dispatch_read_only_mcp_tool(
            workflow, kind=kind, payload=payload
        )
    except MCPAdapterError as exc:
        raise ToolError(str(exc)) from None

@server.tool()
def status() -> dict:
    return _dispatch("status", {})

@server.tool()
def list_files() -> list[str]:
    return _dispatch("list_files", {})

@server.tool()
def read_file(path: str) -> str:
    return _dispatch("read_file", {"path": path})
```

Do not leave the original implementations decorated as exposed MCP tools;
otherwise clients can bypass the workflow wrappers. Keep their existing
filesystem confinement, symlink checks, UTF-8 handling, and 200 KB limit.

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

## Tests

Run from the repository root:

```bash
python -m unittest test_termux_mcp_adapter test_termux_mcp_dispatch -v
python -m unittest discover -v
```
