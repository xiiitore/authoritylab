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

## Durable audit

The optional local JSONL audit store assigns each event a stable ID and links records with a SHA-256 hash chain. Writes are serialized with POSIX file locking and flushed to disk. Validation streams records and enforces a configurable per-record size bound; symlink paths are rejected where `O_NOFOLLOW` is supported. Hash-chain mode detects edits and reordering but cannot prevent a privileged actor from rewriting the entire file. Optional HMAC-SHA256 signatures detect rewrites by actors who do not possess the key. Supply a secret key of at least 32 bytes from a secret manager or OS-protected configuration; never store it beside the log or in source control. Signed logs require the same key for verification and appending, and signed/unsigned records cannot be mixed. HMAC does not prevent deletion, denial of service, key compromise, or tampering by an actor who controls both key and log. Use OS permissions, independent backups, and external immutable storage for stronger assurance.
