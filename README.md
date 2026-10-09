# AuthorityLab

AuthorityLab is a reference implementation for evidence-aware workflow orchestration. It is a foundation to extend, not a production-grade governance or autonomous security system.

## Responsibilities

- **Workflow Core** routes tasks only to explicitly registered and trusted handlers.
- **Workflow Tools** are handlers with predictable inputs and outputs.
- **Governance Policy** preserves mandatory execution checks and configures task-specific structural evidence schemas.
- **Verification** separates execution outcomes, structural completeness, and optional domain-specific semantic checks.
- **Audit records** can be persisted to a local append-only JSONL file with event IDs, provenance fields, and a SHA-256 hash chain.

These module names describe this repository only. They do not imply access to external plugins or privileged system layers.

## Requirements and tests

Python 3.11 or newer. Runtime code uses the standard library. The durable audit log uses POSIX `flock` and is supported only on local filesystems with reliable locking semantics.

From the repository root:

```bash
python -m unittest -v test_workflow test_audit_log test_audit_integration test_semantic_validation test_subprocess_runner
```

CI also installs the project and runs the test suite using pytest. The import package is configured in `pyproject.toml`.

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

For importable top-level handlers, `WorkflowCore(..., execution_runner=SubprocessHandlerRunner(...))` adds a child-process boundary, a wall-clock timeout, and POSIX CPU, address-space, output-file, and open-file limits. Inputs and outputs must be JSON-serializable. The backend strips most inherited environment variables and kills the child process group on timeout. It is a reliability/resource-control layer, **not a security sandbox**: the child runs as the same operating-system user and may still access files and network resources permitted to that user.

For a container boundary, use `DockerSandboxRunner(image="registry.example/app@sha256:...")` with a full image digest. The image must already exist locally and contain AuthorityLab plus the importable handler module. The runner uses `--pull=never`, disables container networking, mounts no host paths, makes the root filesystem read-only, drops Linux capabilities, enables `no-new-privileges`, runs as a non-root numeric user, and applies memory, CPU, PID, file-size, open-file, output, and wall-clock limits. A real deployment still depends on the Docker daemon, host kernel, and image provenance; CI tests the command contract with mocks and does not certify a live Docker deployment. Do not run hostile code until the exact target environment has passed adversarial container tests.

To persist audit events, construct `DurableAuditLog("/secure/local/path/audit.jsonl")` and pass it as `audit_log=` to `WorkflowCore`. A configured audit write failure changes the workflow status to `BLOCKED`. The log detects record edits/reordering through a hash chain; it is not signed, and a privileged actor able to rewrite the entire file can rebuild that chain.

## Current limitations

- No external plugin integrations, authentication, web API, sandbox, or distributed execution.
- Trusted handlers run in-process and can access the process's resources. **Do not mark untrusted handlers as trusted.** Exception handling is not a sandbox; this repository does not yet provide OS/container isolation, hard resource limits, or reliable handler timeouts.
- Durable audit is optional, local-filesystem-only, and tamper-evident rather than tamper-proof. Protect the file and directory with OS permissions and independent backups.
- Structural schemas do not establish factual truth, source provenance, or resistance to fabricated evidence. Semantic validators are explicit application-supplied checks, not a general truth oracle.
- The project is not a security certification or production-readiness claim.

For new gates, add positive, negative, missing-evidence, and boundary tests. Keep network, filesystem, and external-service actions behind explicit adapters.
