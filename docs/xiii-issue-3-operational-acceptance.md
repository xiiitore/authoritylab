# Preserved operational acceptance checklist — xiiitore/xiii issue #3

Source issue: https://github.com/xiiitore/xiii/issues/3
Source status at export: OPEN
Export date: 2026-10-15

## Implemented in source project (per issue body; not independently re-tested here)

- POSIX advisory lock file for JSON ledger operations across cooperating processes.
- Multiprocessing regression test with six writers and 120 records.
- HTTP service defaults to loopback; non-loopback requires explicit remote-bind and trusted TLS-termination assertions.
- MCP ASGI route tests for missing/wrong credentials and authenticated protocol requests; malformed/duplicate Authorization headers rejected.
- Ledger corruption and I/O errors fail closed without raw decoder/filesystem details.
- Documentation for token injection/rotation, backup/restore, incident response, and reverse-proxy boundary.

## Deployment assumptions and limitations

- Locking supports POSIX local filesystems with reliable `flock`; network filesystems are unsupported.
- `TRUSTED_TLS_TERMINATION=1` is an operator assertion, not proof of deployed TLS.
- JSON ledger is a small local store; a transactional database is preferable for production multi-worker deployment.

## Required operational acceptance (still open)

- [ ] Verify TLS termination in the actual deployment.
- [ ] Verify direct service-port access is restricted.
- [ ] Verify secrets are injected securely and rotation works.
- [ ] Execute and verify backup and restore.
- [ ] Verify incident-response procedure.
- [ ] Attach evidence and close the source issue only after the above checks pass.

This file preserves the issue's reported acceptance requirements; it does not prove the deployment is secure and does not replace the source repository's full backup.
