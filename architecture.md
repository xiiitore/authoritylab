# Architecture

## Components

- `WorkflowCore`: routes a task by its declared `kind`, invokes one registered handler, and sends the result to verification.
- `ToolRegistry`: explicit mapping from task kind to handler. Duplicate registrations are rejected.
- `GovernancePolicy`: preserves mandatory execution checks and configures task-specific structural evidence schemas.
- `SemanticValidatorRegistry`: optional registry of application-supplied, task-kind-specific validators.
- `ResultVerifier`: computes a final status from execution, structural, and any configured semantic check results.
- `InProcessRunner`: compatibility backend that invokes a handler in the current process.
- `SubprocessHandlerRunner`: optional child-process backend with JSON IPC, a wall-clock timeout, and POSIX resource limits.
- `WorkflowReport`: returns route, tool result, check results, and a compact audit record.

## Execution path

1. Validate task identity and kind.
2. Resolve a handler. An absent handler produces `BLOCKED`.
3. Run the handler. Exceptions and malformed handler returns become explicit failure results.
4. Evaluate mandatory execution checks and structural evidence completeness.
5. If semantic mode is enabled by injecting a `SemanticValidatorRegistry`, require a validator for every task kind and run it only after structural completeness passes. Missing validators yield `UNKNOWN`.
6. Determine the overall status from all check results.
7. Return the report; no external side effects or persistence are implied.

## Evidence levels

Structural completeness and semantic validation are separate checks. A structural schema establishes that required fields are present, not that the fields are true. A semantic validator is supplied by the application and can enforce only its implemented domain rules. A validator's `PASS` is not source authentication or independent proof unless those mechanisms are actually implemented and their evidence is checked. Validator exceptions and invalid return types produce `UNKNOWN`; they do not produce `PASS`.

Semantic validation is opt-in for compatibility. Without a registry, the workflow retains structural-only behavior and must not be described as semantically verified. With a registry, missing task-specific validators fail closed to `UNKNOWN`. Applications requiring semantic verification must register validators for the relevant task kinds and test their domain-specific assumptions, adversarial inputs, and source dependencies.

## Boundaries

The default runner is in-process. The optional subprocess runner adds a process boundary and resource limits but is not a security sandbox: it uses the same OS identity and does not isolate filesystem or network access. It accepts only importable top-level handlers and JSON-serializable task data/results. The project still does not provide a container/OS sandbox, plugin discovery, authentication, or distributed scheduling. Such features require their own threat model and tests.
