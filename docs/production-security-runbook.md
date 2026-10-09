# Production security and recovery runbook

This checklist is a deployment gate, not a claim that the reference implementation is independently certified.

## 1. Before enabling untrusted workloads

- [ ] Threat model reviewed by an engineer other than the implementer; document assets, attacker capabilities, trust boundaries, abuse cases, and accepted residual risks.
- [ ] Host OS, kernel, Docker Engine, container runtime, and daemon configuration patched and pinned to an approved baseline.
- [ ] Runtime is not given a Docker socket, privileged mode, host PID/network namespaces, host mounts, device access, or ambient host credentials.
- [ ] Handler image is built by a controlled pipeline, scanned, pinned by digest, provenance recorded, and promoted only after review.
- [ ] Runtime identity has no broad group membership or access to sensitive host files. Check UID mapping and user namespaces on the target host.
- [ ] CPU, memory, PID, file size, open files, disk quota, concurrency, request size, output size, and wall-clock limits are tested under load.
- [ ] Secrets are not placed in task payloads unless required; use narrowly scoped credentials from a secret broker, not inherited host environment.
- [ ] Network egress is denied outside the container and host firewall policy; `--network=none` alone is not a host firewall or host-compromise defense.
- [ ] Hostile-code execution has an explicit approval boundary and emergency disable/rollback path.

## 2. Audit integrity, key custody, and recovery

- [ ] HMAC key is generated cryptographically, at least 32 bytes, stored outside the audit directory and source control.
- [ ] Key access is limited to audit writer/verifier; key rotation and old-key verification are documented and tested.
- [ ] Audit records are shipped to a separately administered append-only or immutable store. A local hash chain/HMAC does not prevent deletion or denial of service.
- [ ] Backups are encrypted, independently permissioned, and periodically restored in a test environment.
- [ ] Alert on write/verification failures, missing records, unexpected truncation, disk pressure, and clock anomalies.
- [ ] Recovery drill restores an immutable copy, verifies the chain/signatures, compares externally anchored checkpoints, and records recovery point.
- [ ] Retention, privacy, and access policies meet deployment requirements.

## 3. Required adversarial tests on the exact target environment

Record test date, environment/image digests, tool versions, tester, logs, and pass/fail evidence.

- [ ] Handler attempts to read known host-only files and environment secrets.
- [ ] Handler attempts network egress, DNS, metadata-service access, and daemon-socket access.
- [ ] Infinite loop, process flood, memory exhaustion, disk/output flood, file-descriptor exhaustion, and long-running child cleanup.
- [ ] Docker daemon unavailable, slow, restarted, or returns malformed/error output; verify fail-closed behavior and no orphan container.
- [ ] Concurrent requests and audit writes under resource pressure.
- [ ] Tamper, truncate, delete, reorder, and replace audit records; verify detection and immutable-copy recovery.
- [ ] HMAC key missing, wrong, rotated, exposed, and unavailable; verify safe failure and documented recovery.
- [ ] Verify deployed handlers cannot obtain broader credentials or mounts through wrapper configuration.

## 4. Release decision

Passing unit tests and CI is necessary but not sufficient. Mark production `PASS` only after applicable deployment gates have recorded evidence and an independent reviewer approves residual risks. Otherwise use `BLOCKED` and keep issue #4 open.
