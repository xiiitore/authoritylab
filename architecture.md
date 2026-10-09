# Architecture

## Components

- `WorkflowCore`: routes a task by its declared `kind`, invokes one registered handler, and sends the result to verification.
- `ToolRegistry`: explicit mapping from task kind to handler. Duplicate registrations are rejected.
- `GovernancePolicy`: enumerates required checks; unknown checks are rejected rather than silently ignored.
- `ResultVerifier`: computes a final status from check results.
- `WorkflowReport`: returns route, tool result, check results, and a compact audit record.

## Execution path

1. Validate task identity and kind.
2. Resolve a handler. An absent handler produces `BLOCKED`.
3. Run the handler. Exceptions and malformed handler returns become explicit failure results.
4. Execute each required check.
5. Determine the overall status from the check results.
6. Return the report; no external side effects or persistence are implied.

## Boundaries

This implementation is a local, in-process reference. It does not implement plugin discovery, privilege separation, sandboxing, authentication, persistent audit storage, or distributed scheduling. Such features require their own threat model and tests.
