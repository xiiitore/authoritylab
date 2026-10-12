# Loop and execution-claim guardrails

`loop_guardrails.py` provides dependency-free, deterministic checks over tool observations supplied by a harness.

## Signals

- `EXACT_REPEAT_NO_PROGRESS`: same canonical tool/argument fingerprint and same outcome fingerprint repeat.
- `OSCILLATION_NO_PROGRESS`: a short sequence of tool/outcome pairs repeats without an observed progress milestone.
- `CONSECUTIVE_FAILURE_CASCADE`: consecutive tool outcomes are all error/failed/blocked/timeout, even if tool names differ.
- `audit_execution_claim`: checks whether a claim that a tool ran successfully is supported, contradicted, or unknown from the supplied trace.

The detector does not store raw arguments in findings; it uses SHA-256 fingerprints. Arguments and results must be JSON-serializable. Callers should keep raw trace data in a controlled audit store and apply their own retention/redaction policy.

## Integration contract

1. Create one detector per run.
2. Pass every relevant tool observation to `observe`, including stable run/event IDs and outcome.
3. Set `progress=True` only when the harness observes a concrete milestone (changed artifact, changed verified state, or completed independent check). A model's own statement that it made progress is not sufficient.
4. On a high-severity finding, interrupt automatic retries and require a changed strategy. On a critical failure cascade, stop the run or open a circuit breaker.
5. Record detector version, run ID, event IDs, finding code, intervention, and final outcome.
6. Keep hard call/time/token budgets: this detector is not a replacement for resource limits.

## Hallucination boundary

This is **not** a general natural-language truth detector. It catches a narrower, auditable failure class: unsupported or contradicted claims about tool execution, provided the harness supplies an honest trace-completeness flag. A successful tool observation supports only the claim that the tool reported success; it does not prove that its output is correct, that the source is authentic, or that a factual conclusion follows.

For material factual claims, add a separate evidence ledger containing claim IDs, source IDs, exact supporting excerpts/data, transformations, timestamps, and an independent contradiction check. If provenance or trace completeness is unknown, return `UNKNOWN`, not `PASS`.

## Known limitations

- Only events supplied by the host are visible; uninstrumented tools can bypass observation.
- Legitimate polling/retries can resemble loops. Changed outcomes and explicit verified progress reduce false positives, but policy-specific allowlists may still be needed.
- Near-duplicate semantic calls are not detected; this version deliberately avoids an LLM judge and similarity thresholds.
- This is a library primitive, not yet wired into the live WORKFLOW CORE or EAV bridge. Do not claim runtime enforcement until an integration and end-to-end test prove it.
