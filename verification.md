# Verification and status policy

The system separates tool execution from evidence sufficiency. A tool can return a result while acceptance remains unknown because the output does not satisfy a task-specific evidence contract.

| Status | Meaning |
|---|---|
| `PASS` | Mandatory execution checks and the configured structural evidence schema pass; if semantic mode is enabled, the registered task validator also returns `PASS`. |
| `FAIL` | A mandatory execution check or configured semantic check fails, or the handler reports failure. |
| `BLOCKED` | No handler exists, the handler is not explicitly trusted, mandatory policy configuration is invalid, a semantic validator explicitly blocks, or configured durable audit persistence fails. |
| `UNKNOWN` | No schema exists, required evidence is incomplete, or semantic mode is enabled but a validator is missing, raises an exception, or returns an invalid result. |

## Mandatory execution checks

- `result_present`: output is not `None`.
- `tool_succeeded`: the handler explicitly reports `ok=True`.

These checks are necessary but not sufficient. A successful call alone does not establish factual correctness.

## Task-specific structural evidence

Configure one `EvidenceSchema` per task kind using `task_kind` and a non-empty tuple of `required_fields`. A schema passes only when the output is a mapping containing every required field with a non-`None` value. Missing schemas or incomplete outputs produce `UNKNOWN`, not `PASS`.

This is a structural check only. It does not verify source authenticity, truth, field semantics, or resistance to fabricated evidence.

## Optional semantic validation

Inject a `SemanticValidatorRegistry` into `ResultVerifier` to enable semantic mode. Each task kind processed in that mode must have an explicit validator. The validator runs only after structural completeness passes. Missing validators, exceptions, non-mapping evidence, and invalid return types produce `UNKNOWN`; an explicit `FAIL` prevents workflow acceptance and an explicit `BLOCKED` blocks it.

A validator is application-supplied and establishes only what its code and inputs actually support. A `PASS` is not universal proof, source authentication, or independent verification. Test each validator against adversarial inputs, missing and malformed evidence, source failures, and boundary conditions. Workflows without a registry remain structural-only and must not be described as semantically verified.

## Handler trust boundary

Handlers are blocked by default and must be explicitly registered with `trusted=True`. This is a caller-controlled allow-list, not process isolation. Trusted handlers execute in-process and can access the process's resources. This implementation does not sandbox handlers, isolate credentials from trusted handlers, or impose hard resource limits/timeouts. Do not register untrusted code.

## Execution backend boundary

The default runner executes in-process. `SubprocessHandlerRunner` can enforce a wall-clock timeout and POSIX CPU, address-space, output-file, and open-file limits for importable top-level handlers. It uses JSON input/output and strips most inherited environment variables. This is process separation for reliability and resource control, not a security sandbox: the child has the same OS identity and may access files and network resources allowed to that identity.

`DockerSandboxRunner` accepts only a digest-pinned image and uses no runtime image pulls, no network, no host mounts, a read-only root filesystem, dropped capabilities, `no-new-privileges`, a non-root numeric user, and container resource limits. The image must include AuthorityLab and the handler module. The unit suite mocks Docker CLI calls; it does not prove that a real daemon, image, kernel, or deployment configuration is secure. Run adversarial integration tests in the exact target environment before using it with untrusted code.

## Durable audit

The optional local JSONL audit store assigns each event a stable ID and links records with a SHA-256 hash chain. Writes are serialized with POSIX file locking and flushed to disk. Validation streams records and enforces a configurable per-record size bound; symlink paths are rejected where `O_NOFOLLOW` is supported. Hash-chain mode detects edits and reordering but cannot prevent a privileged actor from rewriting the entire file. Optional HMAC-SHA256 signatures detect rewrites by actors who do not possess the key. Supply a secret key of at least 32 bytes from a secret manager or OS-protected configuration; never store it beside the log or in source control. Signed logs require the same key for verification and appending, and signed/unsigned records cannot be mixed. HMAC does not prevent deletion, denial of service, key compromise, or tampering by an actor who controls both key and log. Use OS permissions, independent backups, and external immutable storage for stronger assurance.


## Production release gate

Passing repository tests and CI does not establish production readiness. Before accepting untrusted handlers, complete the deployment-specific threat model, adversarial isolation tests, daemon-failure/cleanup tests, HMAC key custody and rotation, independent immutable audit anchoring, and restoration drill described in [the production security runbook](docs/production-security-runbook.md). Each applicable gate must have recorded evidence and independent review. Until then the release status is `BLOCKED`, not `PASS`.
