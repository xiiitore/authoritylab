# AuthorityLab

AuthorityLab is a reference implementation for evidence-aware workflow orchestration. It is a foundation to extend, not a production-grade governance or autonomous security system.

## Responsibilities

- **Workflow Core** routes tasks only to explicitly registered and trusted handlers.
- **Workflow Tools** are handlers with predictable inputs and outputs.
- **Governance Policy** preserves mandatory execution checks and configures task-specific structural evidence schemas.
- **Verification** keeps execution outcomes separate from evidence sufficiency.
- **Audit records** record the route, check outcomes, status, and non-sensitive result metadata.

These module names describe this repository only. They do not imply access to external plugins or privileged system layers.

## Requirements and tests

Python 3.11 or newer. Runtime code uses the standard library.

From the repository root:

```bash
python -m unittest -v test_workflow
```

CI also installs the project and runs the test suite using pytest. The import package is configured in `pyproject.toml`.

## Example

See `basic_workflow.py` in the repository root. Architecture and status definitions are documented in `architecture.md` and `verification.md`.

## Status semantics

- `PASS`: both mandatory execution checks passed and a configured task-specific structural evidence schema is satisfied.
- `FAIL`: a mandatory execution check failed or the handler reported failure.
- `BLOCKED`: no handler exists, a handler is registered but not allow-listed as trusted, or mandatory policy configuration is invalid.
- `UNKNOWN`: no schema is configured for the task kind, or the output does not provide the required fields. The workflow cannot infer truth from missing or structurally insufficient evidence.

Configure a schema with `EvidenceSchema(task_kind="lookup", required_fields=("source", "claim"))` and pass it through `GovernancePolicy(evidence_schemas=(... ,))`. Required fields must exist and be non-`None`. This is only a structural completeness check: it does not authenticate a source, prove a claim, or validate the meaning of arbitrary values. Domain-specific semantic validators are still required before treating an output as factually verified or accepted.

Handlers are blocked by default. To execute one, the caller must explicitly register it with `trusted=True`. This is a trust allow-list, not a sandbox: the caller must only mark reviewed code it controls as trusted. Untrusted code must not be loaded into this process.

The mandatory baseline checks cannot be disabled by configuration. The verifier repeats this invariant so bypassing policy-object validation cannot produce a PASS with missing output. A successful tool call alone is not acceptance.

## Current limitations

- No external plugin integrations, authentication, web API, sandbox, or distributed execution.
- Trusted handlers run in-process and can access the process's resources. **Do not mark untrusted handlers as trusted.** Exception handling is not a sandbox; this repository does not yet provide OS/container isolation, hard resource limits, or reliable handler timeouts.
- Audit records are returned in memory and are not durable or tamper-evident.
- Structural schemas do not establish factual truth, source provenance, or resistance to fabricated evidence.
- The project is not a security certification or production-readiness claim.

For new gates, add positive, negative, missing-evidence, and boundary tests. Keep network, filesystem, and external-service actions behind explicit adapters.
