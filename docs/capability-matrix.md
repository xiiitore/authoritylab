# Capability Matrix — Evidence Snapshot

**Snapshot date:** 2026-10-11  
**Scope:** current ChatGPT session, connected GitHub integration, AuthorityLab repository, and the current OVERALGORITHM plugin listing.

This matrix distinguishes registered interfaces from capabilities that have actually been exercised. A PASS applies only to the stated test and version/commit, not to an entire provider or system.

## Current status

| Capability | Status | Evidence / limit |
|---|---|---|
| Session tool inventory | PARTIAL | 441 registered interfaces in 26 namespaces were captured in capability-registry.json. Metadata count is not a runtime test. |
| GitHub repository inspection and branch writes | PASS | Read-back verified for new files, commits, branches, and draft PRs in xiiitore/authoritylab. No changes merged to main. |
| Capability Registry integrity | PASS | Python CI on checked commit 9cc2142 passed for Python 3.11, 3.12, and 3.13; registry JSON Schema validation, compile, blocking lint, Docker integration, and CodeQL passed. |
| Workspace atomic write hardening | PASS / REVIEW REQUIRED | Python CI, Docker integration, and CodeQL passed on checked commit 39a6e9d of PR #30. The PR is ready for review but not merged; Android/Termux filesystem behavior remains untested. |
| MCP SDK v2 stdio bridge candidate | PASS / PLATFORM UNKNOWN | Python CI and Docker integration passed on checked head 7401318, including the real stdio smoke test for the exact tool allowlist, status/list/read, and parent-traversal rejection. This is GitHub-hosted Linux CI, not an actual Android/Termux run. CodeQL has not yet been confirmed for this chained PR; require it after PR #29 merges and PR #31 is retargeted to main. |
| Direct ChatGPT mobile access to a local stdio server | BLOCKED BY TRANSPORT MODEL | A local stdio MCP process serves its local host process. Direct ChatGPT access requires a supported remote MCP endpoint or authenticated relay; neither is deployed by these changes. |
| Termux device runtime | UNKNOWN | No registered Codex remote environment was returned and no direct execution channel to the phone is available in this session. A local smoke check on the device is still required. |
| OVERALGORITHM plugin release | PARTIAL | Current release remains 1.2.12. Twelve static schema/contract checks passed. The full current schema test suite (21 tests) has not been executed against a runnable copy of the current archive; no candidate release was published. |
| Hosting/deployment capability | AVAILABLE, NOT VERIFIED HERE | DigitalOcean and Render interfaces are registered. No remote bridge or public endpoint has been deployed in this workflow. |
| Automation capability | AVAILABLE, NOT VERIFIED HERE | Automation interfaces are registered. No recurring job was created as part of this task. |

## Current draft pull requests

1. [#29 — Add initial capability registry and integrity tests](https://github.com/xiiitore/authoritylab/pull/29)  
   Base branch for the subsequent SDK alignment PR. Python, Docker, and CodeQL checks passed on the checked commit.
2. [#30 — Harden workspace writes with descriptor-relative atomic replacement](https://github.com/xiiitore/authoritylab/pull/30)  
   Separate security hardening change. Python, Docker, and CodeQL checks passed on the checked commit. Not merged.
3. [#31 — Align Termux MCP bridge and smoke test with SDK v2](https://github.com/xiiitore/authoritylab/pull/31)  
   Based on #29. Python CI, including the stdio smoke test, passed on the checked head. Docker CI status must be rechecked before treating the candidate as fully verified. The actual Termux runtime still needs a device-side check.

All three remain unmerged. Because #31 is based on #29, review/merge order must be #29 before #31. Do not merge any PR while a required check is pending or failing.

## Next gates

1. Confirm all CI jobs on the current heads of #29, #30, and #31 have completed successfully.
2. Review PR diffs and dependency changes; merge only in dependency order after explicit review.
3. Run the documented read-only and write-safety checks in a fresh Termux checkout and the user's actual MCP virtual environment.
4. Confirm the actual exposed MCP tools from the device; never infer device compatibility from Linux CI alone.
5. Decide whether a remote authenticated relay is needed. If so, design auth, rate limits, request size limits, path/command allowlists, logging without secrets, and revocation before deployment.
6. Retrieve a runnable copy of the current OVERALGORITHM 1.2.12 archive and execute the full schema suite before any release candidate is considered.

## Status rule

Registered ≠ tested. A successful unit test ≠ a security certification. A passing Linux CI job ≠ a passing Android/Termux test. A draft PR ≠ a merged release.
