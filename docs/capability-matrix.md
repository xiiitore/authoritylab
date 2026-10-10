# Capability Matrix — Evidence Snapshot

**Snapshot date:** 2026-10-11  
**Scope:** current ChatGPT session, connected GitHub integration, AuthorityLab repository, and the current OVERALGORITHM plugin listing.

This matrix distinguishes registered interfaces from capabilities that have actually been exercised. A PASS applies only to the stated test and version/commit, not to an entire provider or system.

## Current status

| Capability | Status | Evidence / limit |
|---|---|---|
| Session tool inventory | PARTIAL | 441 registered interfaces in 26 namespaces were captured in capability-registry.json. Metadata count is not a runtime test. |
| GitHub repository inspection and branch writes | PASS | Read-back verified for new files, branches, CI, and pull requests. PR #29, #30, and #32 are merged to main; superseded PR #31 is closed. |
| Capability Registry integrity | PASS | Python CI on checked commit 9cc2142 passed for Python 3.11, 3.12, and 3.13; registry JSON Schema validation, compile, blocking lint, Docker integration, and CodeQL passed. |
| Workspace atomic write hardening | PASS / PLATFORM UNKNOWN | Merged via PR #30 at commit f81ddf7. Python CI, Docker integration, and CodeQL passed on head 19e3c77, including invalid-Unicode rejection. Actual Android/Termux filesystem behavior and hard-link behavior remain untested on-device. |
| MCP SDK v2 stdio bridge | PASS / PLATFORM UNKNOWN | Merged via PR #32 at commit 6ece6d4. Python CI passed on Python 3.11–3.13, Docker integration passed, and CodeQL is being checked post-merge. The stdio smoke test verifies the separate read-only reference server's three-tool surface on Linux; it does not test the Android device or the seven-tool workspace server. |
| Direct ChatGPT mobile access to a local stdio server | BLOCKED BY TRANSPORT MODEL | A local stdio MCP process serves its local host process. Direct ChatGPT access requires a supported remote MCP endpoint or authenticated relay; neither is deployed by these changes. |
| Termux device runtime | UNKNOWN | No registered Codex remote environment was returned and no direct execution channel to the phone is available in this session. A local smoke check on the device is still required. |
| OVERALGORITHM plugin release | PARTIAL | Current release remains 1.2.12. Twelve static schema/contract checks passed. The full current schema test suite (21 tests) has not been executed against a runnable copy of the current archive; no candidate release was published. |
| Hosting/deployment capability | AVAILABLE, NOT VERIFIED HERE | DigitalOcean and Render interfaces are registered. No remote bridge or public endpoint has been deployed in this workflow. |
| Automation capability | AVAILABLE, NOT VERIFIED HERE | Automation interfaces are registered. No recurring job was created as part of this task. |

## Pull request record

1. [#29 — Add initial capability registry and integrity tests](https://github.com/xiiitore/authoritylab/pull/29) — merged as `558f01b`.
2. [#30 — Harden workspace writes with descriptor-relative atomic replacement](https://github.com/xiiitore/authoritylab/pull/30) — merged as `f81ddf7`.
3. [#31 — Align Termux MCP bridge and smoke test with SDK v2](https://github.com/xiiitore/authoritylab/pull/31) — closed without merge because its base was superseded.
4. [#32 — Align Termux MCP bridge and smoke test with SDK v2](https://github.com/xiiitore/authoritylab/pull/32) — merged as `6ece6d4` from a clean branch based on updated main.

## Next gates

1. Wait for post-merge CodeQL on `6ece6d4` to finish and confirm success.
2. Run the documented stdio, hard-link, and write-safety checks on the actual Termux device in a fresh checkout and the user's actual MCP virtual environment.
3. Verify the seven-tool workspace server separately from the three-tool read-only reference server; the Linux smoke test covers only the latter.
4. Decide whether a remote authenticated relay is needed. If so, design auth, rate limits, request size limits, path/command allowlists, logging without secrets, and revocation before deployment. No relay has been deployed.
5. Retrieve a runnable copy of the current OVERALGORITHM 1.2.12 archive and execute the full schema suite before any release candidate is considered.

## Status rule

Registered ≠ tested. A successful unit test ≠ a security certification. A passing Linux CI job ≠ a passing Android/Termux test. A draft PR ≠ a merged release.
