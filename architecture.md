# Architecture

## Components

- `WorkflowCore`: routes a task by its declared `kind`, invokes one registered handler, and sends the result to verification.
- `ToolRegistry`: explicit mapping from task kind to handler. Duplicate registrations are rejected.
- `GovernancePolicy`: preserves mandatory execution checks and configures task-specific structural evidence schemas.
- `SemanticValidatorRegistry`: optional registry of application-supplied, task-kind-specific validators.
- `ResultVerifier`: computes a final status from execution, structural, and any configured semantic check results.
- `WorkflowReport`: returns route, tool result, check results, and a compact audit record.

## Execution path

1. Validate task identity and kind.
2. Resolve a handler. An absent handler produces `BLOCKED`.
3. Run the handler. Exceptions and malformed handler returns become explicit failure results.
4. Evaluate mandatory execution checks and structural evidence completeness.
5. If a semantic validator is configured for the task kind, run it only after structural completeness passes.
6. Determine the overall status from all check results.
7. Return the report; no external side effects or persistence are implied.

## Evidence levels

Structural completeness and semantic validation are separate checks. A structural schema establishes that required fields are present, not that the fields are true. A semantic validator is supplied by the application and can enforce only its implemented domain rules. A validator's `PASS` is not source authentication or independent proof unless those mechanisms are actually implemented and their evidence is checked. Validator exceptions and invalid return types produce `UNKNOWN`; they do not produce `PASS`.

Semantic validation is opt-in for compatibility. If no validator is registered for a task kind, the workflow does not claim semantic verification for that task. Applications requiring semantic verification must register validators for the relevant task kinds and test their domain-specific assumptions, adversarial inputs, and source dependencies.

## Boundaries

This implementation is a local, in-process reference. It does not implement plugin discovery, privilege separation, sandboxing, authentication, persistent audit storage, or distributed scheduling. Such features require their own threat model and tests.
