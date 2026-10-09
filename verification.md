# Verification and status policy

The system separates tool execution from acceptance. A tool can return a result while acceptance still fails because evidence is missing or a required check fails.

| Status | Meaning |
|---|---|
| `PASS` | Every configured required check ran and passed. |
| `FAIL` | A required check failed, or the handler reported failure. |
| `BLOCKED` | No handler exists or a required check cannot be executed. |
| `UNKNOWN` | Evidence is insufficient to decide. |

The initial policy provides two checks:

- `result_present`: output is not `None`.
- `tool_succeeded`: the handler explicitly reports `ok=True`.

These are deliberately minimal checks, not proof that output is factually correct, safe, or useful. Domain-specific checks must be added for each real workflow. Missing checks must never be counted as passing checks.
