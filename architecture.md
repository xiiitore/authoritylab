# Architecture

## Components

- `WorkflowCore`: routes a task by its declared `kind`, invokes one registered handler, and sends the result to verification.
- `ToolRegistry`: explicit mapping from task kind to handler. Duplicate registrations are rejected.
- `GovernancePolicy`: preserves mandatory execution checks and configures task-specific structural evidence schemas.
- `SemanticValidatorRegistry`: optional registry of application-supplied, task-kind-specific validators.
- `ResultVerifier`: computes a final status from execution, structural, and any configured semantic check results.
- `LoopDetector`: bounded run-scoped detector for repeated calls/outcomes, short oscillations, and consecutive failure cascades; a detected pattern latches `WorkflowCore` into `BLOCKED` until a trusted progress event is supplied.
- `InProcessRunner`: compatibility backend that invokes a handler in the current process.
- `SubprocessHandlerRunner`: optional child-process backend with JSON IPC, a wall-clock timeout, and POSIX resource limits.
- `DockerSandboxRunner`: optional digest-pinned Docker backend with disabled networking, no host mounts, a read-only root filesystem, dropped capabilities, a non-root identity, and container resource limits.
- `WorkflowReport`: returns route, tool result, check results, and a compact audit record.

## Execution path

1. Validate task identity and kind.
2. Resolve a handler. An absent handler produces `BLOCKED`.
3. Run the handler. Exceptions and malformed handler returns become explicit failure results.
4. Feed each routed task attempt, arguments, outcome, and unique per-instance event ID to the bounded loop detector, including missing-handler and execution-backend-blocked outcomes. A finding marks the report `BLOCKED` and latches the core so subsequent handler calls do not execute until a progress event is supplied.
5. Evaluate mandatory execution checks and structural evidence completeness.
6. If semantic mode is enabled by injecting a `SemanticValidatorRegistry`, require a validator for every task kind and run it only after structural completeness passes. Missing validators yield `UNKNOWN`.
7. Determine the overall status from all check results, including the loop guard.
8. Return the report; no external side effects or persistence are implied.

## Loop-guard limits

The detector sees only events observed by this `WorkflowCore` instance and uses deterministic signatures over JSON-compatible arguments/results. The call that crosses the detection threshold has already run; only later calls are blocked. A progress event resets the detector only when the caller supplies `progress=True` and an event ID, so the host must independently establish that the milestone is real. This library-level integration does not intercept ChatGPT runtime calls or external plugins. If an observation cannot be fingerprinted, the loop check is `UNKNOWN`, not `PASS`.

## Evidence levels

Structural completeness and semantic validation are separate checks. A structural schema establishes that required fields are present, not that the fields are true. A semantic validator is supplied by the application and can enforce only its implemented domain rules. A validator's `PASS` is not source authentication or independent proof unless those mechanisms are actually implemented and their evidence is checked. Validator exceptions and invalid return types produce `UNKNOWN`; they do not produce `PASS`.

Semantic validation is opt-in for compatibility. Without a registry, the workflow retains structural-only behavior and must not be described as semantically verified. With a registry, missing task-specific validators fail closed to `UNKNOWN`. Applications requiring semantic verification must register validators for the relevant task kinds and test their domain-specific assumptions, adversarial inputs, and source dependencies.

## Boundaries

The default runner is in-process. The optional subprocess runner adds process separation and resource limits but is not a security sandbox: it uses the same OS identity and does not isolate filesystem or network access. The optional Docker runner provides a stronger container boundary only when the target Docker daemon, host, and digest-pinned image are trusted and correctly configured. It accepts only importable top-level handlers and JSON-serializable task data/results; the handler module must be present in the image. Unit tests mock Docker CLI execution, so a real deployment still needs target-environment and adversarial integration tests. The project does not implement plugin discovery, authentication, or distributed scheduling.
