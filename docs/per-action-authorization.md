# Per-action authorization contract

## Default behavior

`WorkflowCore` denies handler execution unless an authorizer and a valid
`AuthorizationRequest` are supplied. The request must match the task action
(`request.action == task.kind`) and its resource ID must match the task payload
field named by `request.target_field`. The core snapshots caller-owned payload
data before checking authorization.

The authorizer must return an `AuthorizationDecision`. Missing, malformed,
denied, or failing authorization blocks execution. The audit report records the
decision ID and reason; it does not copy the request payload.

## Minimal example

```python
from authoritylab import (
    AuthorizationRequest, ExactMatchAuthorizer, Task, ToolResult, WorkflowCore,
)
from authoritylab.tools import ToolRegistry

registry = ToolRegistry()
registry.register("read", lambda task: ToolResult(True, {"value": "ok"}), trusted=True)
authorizer = ExactMatchAuthorizer({("user-1", "read", "record-7")})
core = WorkflowCore(registry, authorizer=authorizer)
task = Task("request-1", "read", {"record_id": "record-7"})
report = core.run(
    task,
    authorization=AuthorizationRequest("user-1", "read", "record-7", "record_id"),
)
```

## Trust boundary and limitations

- `subject_id` must come from an authenticated, trusted caller. The core does
  not authenticate identities.
- `ExactMatchAuthorizer` is a small reference policy, not a production policy
  engine or durable permissions database.
- A task kind is the action identifier. Resource binding is explicit through
  `target_field`; applications must choose the correct field and include every
  security-relevant scope in their policy design.
- `legacy_mode=True` exists only for migration and compatibility tests. It
  bypasses authorization and must not be enabled in security-sensitive use.
- This gate does not isolate handler code, validate cryptographic tokens, or
  make arbitrary handler side effects transactional.

## Existing read-only MCP adapter

The bundled Termux MCP server and its reference example explicitly use
`legacy_mode=True` because they already implement a separate restricted
dispatch boundary: only three read-only operations are registered, operation
names are allow-listed, and payloads/relative paths are validated before the
handler is called. This compatibility exception is narrower than general
workflow use, but it does **not** authenticate individual MCP callers. Do not
reuse this exception for general-purpose or multi-user tools. A future adapter
revision should pass a verified caller identity and explicit resource scope
through the new authorization contract.
