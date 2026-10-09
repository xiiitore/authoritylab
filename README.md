# AuthorityLab

AuthorityLab is a small reference implementation for evidence-aware workflow orchestration. It is a foundation to extend, not a production-grade governance or autonomous security system.

## Responsibilities

- **Workflow Core** routes tasks only to explicitly registered handlers.
- **Workflow Tools** are handlers with predictable inputs and outputs.
- **Governance Policy** defines which checks must run.
- **Verification** keeps execution outcomes separate from acceptance decisions.
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

- `PASS`: all configured checks ran and passed.
- `FAIL`: a required check ran and failed, or the handler reported failure.
- `BLOCKED`: a required check was not executable or the route was unavailable.
- `UNKNOWN`: reserved for a future explicit insufficient-evidence check; current built-in checks do not emit it.

A successful tool call alone is not acceptance. The current checks only verify output presence and the handler's success flag; they do not establish factual correctness.

## Current limitations

- No external plugin integrations, authentication, web API, sandbox, or distributed execution.
- Registered handlers run in-process and can access the process's resources.
- Audit records are returned in memory and are not durable or tamper-evident.
- Exceptions are represented as failure evidence; this is not a sandbox.
- The project is not a security certification or production-readiness claim.

For new gates, add positive, negative, missing-evidence, and boundary tests. Keep network, filesystem, and external-service actions behind explicit adapters.
