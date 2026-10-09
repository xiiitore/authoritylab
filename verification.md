# Verification and status policy

The system separates tool execution from evidence sufficiency. A tool can return a result while acceptance remains unknown because the output does not satisfy a task-specific evidence contract.

| Status | Meaning |
|---|---|
| `PASS` | Mandatory execution checks pass and the configured structural evidence schema is satisfied. |
| `FAIL` | A mandatory execution check fails, or the handler reports failure. |
| `BLOCKED` | No handler exists or mandatory policy configuration is invalid. |
| `UNKNOWN` | No schema exists for the task kind or required evidence fields are missing/empty. |

## Mandatory execution checks

- `result_present`: output is not `None`.
- `tool_succeeded`: the handler explicitly reports `ok=True`.

These checks are necessary but not sufficient. A successful call alone does not establish factual correctness.

## Task-specific structural evidence

Configure one `EvidenceSchema` per task kind using `task_kind` and a non-empty tuple of `required_fields`. A schema passes only when the output is a mapping containing every required field with a non-`None` value. Missing schemas or incomplete outputs produce `UNKNOWN`, not `PASS`.

This is a structural check only. It does not verify source authenticity, truth, field semantics, or resistance to fabricated evidence. Domain-specific semantic validators and provenance checks must be supplied by the application before factual verification or acceptance.

## Security boundary

Handlers execute in-process and are trusted code. This implementation does not sandbox handlers, isolate credentials, impose hard resource limits/timeouts, or persist a tamper-evident audit log. Do not use it as a production execution boundary for untrusted code.
