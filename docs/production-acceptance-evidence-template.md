# Production acceptance evidence record

Status: **BLOCKED until every applicable gate has evidence and independent review.**

This template is a record, not a certification. Do not place secrets, tokens, private keys, customer data, or raw sensitive environment variables in this file. Store full logs in an access-controlled evidence store and reference them by opaque ID or checksum.

## Deployment identity

- Record ID:
- Date/time (UTC):
- Environment name / owner:
- Deployment revision / Git SHA:
- Handler image digest(s):
- Image build/provenance record:
- Host OS and version:
- Kernel version:
- Docker Engine / API version:
- Container runtime version:
- Tester:
- Independent reviewer:
- Evidence store reference:

## Gate ledger

Use only: `PASS`, `FAIL`, `BLOCKED`, `UNKNOWN`, `NOT_APPLICABLE`.
A `PASS` must link to retained evidence. `NOT_APPLICABLE` requires a written rationale and reviewer approval.

| ID | Gate | Status | Evidence reference / SHA-256 | Operator | Reviewer | Notes / residual risk |
|---|---|---|---|---|---|---|
| ENV-01 | Host, kernel, Docker daemon and runtime match approved baseline | BLOCKED | | | | |
| ENV-02 | Runtime UID/GID, user namespaces and filesystem permissions reviewed | BLOCKED | | | | |
| ENV-03 | No privileged mode, host namespaces, device mounts, host mounts, or Docker socket exposed to workload | BLOCKED | | | | |
| IMG-01 | Handler image provenance reviewed and image pinned by immutable digest | BLOCKED | | | | |
| IMG-02 | Image vulnerability scan reviewed; exceptions documented | BLOCKED | | | | |
| NET-01 | Egress, DNS, metadata-service and host-network reachability tested from workload | BLOCKED | | | | |
| NET-02 | Host firewall policy independently verified; `--network=none` not treated as sole host defense | BLOCKED | | | | |
| RES-01 | CPU, memory, PID, file-size, open-file, disk, concurrency, request/output and wall-clock limits tested | BLOCKED | | | | |
| RES-02 | Infinite loop, process flood, memory pressure, disk/output flood and child cleanup tested | BLOCKED | | | | |
| ERR-01 | Docker daemon unavailable, slow, restarted and malformed/error responses tested | BLOCKED | | | | |
| ERR-02 | Fail-closed behavior and orphan-container cleanup verified | BLOCKED | | | | |
| AUD-01 | Audit tampering, truncation, deletion and reordering detected | BLOCKED | | | | |
| AUD-02 | HMAC key creation, access boundaries, missing/wrong key and rotation tested | BLOCKED | | | | |
| AUD-03 | Independently administered immutable copy/checkpoint verified | BLOCKED | | | | |
| REC-01 | Backup restored in a test environment; chain and external checkpoints verified | BLOCKED | | | | |
| REC-02 | Recovery point, recovery time, alerts and emergency disable/rollback exercised | BLOCKED | | | | |
| CON-01 | Concurrent workload and audit writes tested under resource pressure | BLOCKED | | | | |
| SEC-01 | No secrets in task payloads, logs, artifacts, environment dumps or evidence records | BLOCKED | | | | |
| REV-01 | Independent reviewer approved threat model and residual risks | BLOCKED | | | | |

## Test case record

Create one record per test. Do not write only "passed"; record the expected and observed result.

- Test ID:
- Gate ID:
- Date/time (UTC):
- Exact deployment SHA and image digest:
- Tool versions / configuration revision:
- Tester:
- Preconditions:
- Action and command/script reference:
- Expected security property:
- Observed result:
- Evidence reference and SHA-256:
- Cleanup / recovery result:
- Status:
- Deviations / residual risk:
- Independent reviewer and decision:

## Explicit acceptance decision

- All applicable mandatory gates have retained evidence: YES / NO
- Failures and deviations resolved or formally accepted: YES / NO
- Independent reviewer approval recorded: YES / NO
- Emergency disable/rollback tested: YES / NO

Final status: **BLOCKED** until all required answers are YES and the reviewer signs below.

- Decision:
- Decision date (UTC):
- Reviewer identity / approval record:
- Approved scope and exclusions:
- Accepted residual risks:
- Next review date:

## Interpretation limits

- Passing CI does not prove the deployed host or daemon is secure.
- A container configuration is not proof against kernel or daemon vulnerabilities.
- A local hash chain or HMAC does not prevent deletion or denial of service by an actor controlling storage.
- A successful test proves only the tested configuration, image, host, and conditions.
