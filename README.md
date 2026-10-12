# AuthorityLab

AuthorityLab is a reference implementation for evidence-aware workflow orchestration. It is a foundation to extend, not a production-grade governance or autonomous security system.

## Responsibilities

- **Workflow Core** routes tasks only to explicitly registered and trusted handlers.
- **Workflow Tools** are handlers with predictable inputs and outputs.
- **Governance Policy** preserves mandatory execution checks and configures task-specific structural evidence schemas.
- **Verification** separates execution outcomes, structural completeness, and optional domain-specific semantic checks.
- **Audit records** can be persisted to a local append-only JSONL file with event IDs, provenance fields, a SHA-256 hash chain, and optional HMAC-SHA256 signatures.

These module names describe this repository only. They do not imply access to external plugins or privileged system layers.

## Requirements and tests

Python 3.11 or newer. Runtime code uses the standard library. The durable audit log uses POSIX `flock` and is supported only on local filesystems with reliable locking semantics.

From the repository root:

```bash
python -m unittest -v test_workflow test_audit_log test_audit_integration test_semantic_validation test_subprocess_runner
```

CI also installs the project and runs the test suite using pytest. The import package is configured in `pyproject.toml`.

## Loop and unsupported-execution-claim guardrails

`WorkflowCore` now observes task attempts routed through that instance—including missing-handler and execution-backend-blocked outcomes—with a bounded, per-instance `LoopDetector`. It can detect repeated identical calls with unchanged outcomes, short repeated call cycles, and consecutive failure cascades. Once a configured pattern is detected, the current report is `BLOCKED` and subsequent handler calls through that same `WorkflowCore` instance are blocked before execution.

A caller may clear the latch only by calling `reset_loop_guard()` with a `ToolObservation` marked `progress=True` and carrying an event ID. The integration can validate the event shape, but it cannot authenticate the underlying milestone by itself: production callers must create progress observations from trusted, externally observable events, not model-authored assertions. The call that crosses the detection threshold has already executed; this guard prevents subsequent calls, not the triggering call.

Example:

```python
from authoritylab import LoopDetector, ToolObservation, WorkflowCore

core = WorkflowCore(registry, policy=policy, loop_detector=LoopDetector())
# After the harness verifies a concrete progress milestone:
core.reset_loop_guard(ToolObservation(
    tool_name="harness.progress",
    arguments={"milestone": "verified-new-strategy"},
    result={"verified": True},
    progress=True,
    event_id="progress-event-17",
))
```

Non-JSON-compatible arguments or results cannot be fingerprinted; the loop check becomes `UNKNOWN` rather than silently passing. Detection is a bounded heuristic over observations supplied to one `WorkflowCore` instance. It is not integrated into ChatGPT's private runtime or external plugin calls, and it does not prove semantic correctness. `audit_execution_claim()` separately compares a claim about a named tool's success with the observed trace; `SUPPORTED` means a matching successful observation exists, not that its output is true.

## Example

See `basic_workflow.py` in the repository root. Architecture and status definitions are documented in `architecture.md` and `verification.md`.

## Status semantics

- `PASS`: both mandatory execution checks passed and a configured task-specific structural evidence schema is satisfied; when semantic mode is enabled, a registered validator must also return `PASS`.
- `FAIL`: a mandatory execution check or configured semantic check failed.
- `BLOCKED`: no handler exists, a handler is registered but not allow-listed as trusted, mandatory policy configuration is invalid, or configured durable audit storage fails.
- `UNKNOWN`: no structural schema is configured, required evidence fields are missing, or semantic mode is enabled but a task validator is missing or cannot produce a valid decision.

Configure a schema with `EvidenceSchema(task_kind="lookup", required_fields=("source_id", "claim"))` and pass it through `GovernancePolicy(evidence_schemas=(... ,))`. Required fields must exist and be non-`None`. This is only a structural completeness check: it does not authenticate a source, prove a claim, or validate the meaning of arbitrary values.

### Optional semantic validation

Register a domain-specific validator and inject the registry into `ResultVerifier`:

```python
from authoritylab import (
    CheckStatus,
    SemanticValidationResult,
    SemanticValidatorRegistry,
)
from authoritylab.verification import ResultVerifier

validators = SemanticValidatorRegistry()
validators.register(
    "lookup",
    lambda evidence: SemanticValidationResult(
        CheckStatus.PASS if evidence["source_id"] in {"source-1", "source-2"}
        else CheckStatus.FAIL,
        "source identifier accepted by the configured catalogue"
        if evidence["source_id"] in {"source-1", "source-2"}
        else "source identifier is not in the configured catalogue",
    ),
)
verifier = ResultVerifier(semantic_validators=validators)
```

Supplying a registry enables semantic mode. Every task kind processed in that mode must have a registered validator; missing validators yield `UNKNOWN`, and validators run only after structural completeness passes. Exceptions and invalid return types also produce `UNKNOWN` without exposing exception messages. The example demonstrates a domain rule only; it is not a universal source-authentication mechanism. A validator can establish only what its own implementation and evidence support; independent source authentication and truth verification remain application-specific responsibilities. Workflows that do not inject a registry retain the prior structural-only behavior and must not describe their results as semantically verified.

Handlers are blocked by default. To execute one, the caller must explicitly register it with `trusted=True`. This is a trust allow-list, not a sandbox: the caller must only mark reviewed code it controls as trusted. Untrusted code must not be loaded into this process.

For importable top-level handlers, `WorkflowCore(..., execution_runner=SubprocessHandlerRunner(...))` adds a child-process boundary, a wall-clock timeout, and POSIX CPU, address-space, output-file, and open-file limits. Inputs and outputs must be JSON-serializable. On Android/Termux, the address-space limit is intentionally skipped because Bionic's linker can abort during startup when `RLIMIT_AS` is imposed; memory use is therefore less constrained on that platform. The backend strips most inherited environment variables and kills the child process group on timeout. It is a reliability/resource-control layer, **not a security sandbox**: the child runs as the same operating-system user and may still access files and network resources permitted to that user.

For a container boundary, use `DockerSandboxRunner(image="registry.example/app@sha256:...")` with a full image digest. The Docker CLI path defaults to `/usr/bin/docker`; set `docker_executable` to an explicitly trusted absolute path on systems that install it elsewhere. The image must already exist locally and contain AuthorityLab plus the importable handler module. The runner uses `--pull=never`, disables container networking, mounts no host paths, makes the root filesystem read-only, drops Linux capabilities, enables `no-new-privileges`, runs as a non-root numeric user, and applies memory, CPU, PID, file-size, open-file, output, and wall-clock limits. A real deployment still depends on the Docker daemon, host kernel, and image provenance; CI tests the command contract with mocks and does not certify a live Docker deployment. Do not run hostile code until the exact target environment has passed adversarial container tests.

To persist audit events, construct `DurableAuditLog("/secure/local/path/audit.jsonl")` and pass it as `audit_log=` to `WorkflowCore`. A configured audit write failure changes the workflow status to `BLOCKED`. Hash-chain mode detects record edits/reordering, but a privileged actor able to rewrite the entire file can rebuild the chain. For stronger integrity, provide `DurableAuditLog(path, integrity_key=secret_key)`, where `secret_key` is at least 32 bytes obtained from a secret manager or OS-protected configuration. Never commit the key or store it beside the log. Signed logs cannot be verified or extended without the same key; unsigned and signed records cannot be mixed in one chain. Records are size-bounded, and symbolic-link audit paths are rejected on platforms supporting `O_NOFOLLOW`.

## Current limitations

- No external plugin integrations, authentication, web API, or distributed execution.
- The default runner executes trusted handlers in-process. `SubprocessHandlerRunner` adds resource limits but is not a security sandbox. `DockerSandboxRunner` is an optional container boundary, not a production security certification; its assurance depends on the host kernel, Docker daemon, image provenance, and runtime configuration. The real-container CI suite checks selected isolation properties but cannot prove resistance to every container escape or host compromise. **Do not run hostile code until deployment-specific adversarial review and threat-model gates pass.**
- Durable audit is optional and local-filesystem-only. HMAC signatures improve tamper detection only while the key remains secret; they do not prevent log deletion, key compromise, denial of service, or tampering by an actor who controls both key and log.
- Structural schemas do not establish factual truth, source provenance, or resistance to fabricated evidence. Semantic validators are explicit application-supplied checks, not a general truth oracle.
- The project is not a security certification or production-readiness claim.

For new gates, add positive, negative, missing-evidence, and boundary tests. Keep network, filesystem, and external-service actions behind explicit adapters. Before production deployment, complete the [security and recovery runbook](docs/production-security-runbook.md); CI success alone is not a production security certification.
