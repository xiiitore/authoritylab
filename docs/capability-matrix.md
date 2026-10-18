# Capability Matrix — Evidence Snapshot

> The original matrix below is a historical snapshot from 2026-10-11, not a live status page. The dated follow-up below records later observations without rewriting the historical evidence.

## Follow-up — 2026-10-18

- **Draft PR #80:** [Improve repository preflight and Termux bridge efficiency](https://github.com/xiiitore/authoritylab/pull/80) is open and unmerged. It adds a dependency-free repository health preflight, wires it into Python CI, corrects Termux MCP capability documentation, adds a confined-path anchor regression test, and removes a duplicate `workspace.status()` call.
- **Latest verified implementation/documentation head:** `c47780aa4f233247c47505d5445fbb9f035f29f0` passed Python CI, CodeQL, and Docker sandbox integration. The Python 3.13 suite reported 291 passed and 3 skipped on the preceding implementation head `f971513831623485d496ac4fb1279160c5314257`; the `c47780a` commit corrected the Termux MCP capability documentation. The current evidence-matrix update is at `808a63fcc3876fa5a046c1aa5e8afe8e6ba4517a`; its Python CI was queued when this follow-up was last checked.
- **Termux mailbox:** `status` returned `ready` with a 200,000-byte file limit. Sequential `read_file` checks succeeded for multiple existing files. The mailbox protocol permits only `status`, `list_files`, and `read_file`; it cannot execute tests or Git commands.
- **Local/GitHub divergence:** the Termux workspace does not contain `scripts/repository_health_check.py` yet (`FileNotFoundError`). Its `termux_mcp_server.py` also differs from the GitHub `main` version inspected in this session. The mailbox does not expose the local branch or commit SHA, so the exact divergence point is **UNKNOWN**. Device-side execution of the new preflight is therefore **NOT VERIFIED**.
- **Local backup artifact:** the workspace listing contains `secure_paths.py.bak`; its content lacks the home-anchor adjustment present in the current local `secure_paths.py`. It was inspected but not deleted or modified. The file was not present in the inspected GitHub `main` tree.

The historical table and gates below retain the evidence and limitations known on 2026-10-11.

**Snapshot date:** 2026-10-11  
**Scope:** current ChatGPT session, connected GitHub integration, AuthorityLab repository, and the current OVERALGORITHM plugin listing.

This matrix distinguishes registered interfaces from capabilities that have actually been exercised. A PASS applies only to the stated test and version/commit, not to an entire provider or system.

## Status at snapshot date (2026-10-11)

| Capability | Status | Evidence / limit |
|---|---|---|
| Session tool inventory | PARTIAL | 441 registered interfaces in 26 namespaces were captured in capability-registry.json. Metadata count is not a runtime test. |
| GitHub repository inspection and branch writes | PASS | Read-back verified for new files, branches, CI, and pull requests. PR #29, #30, and #32 are merged to main; superseded PR #31 is closed. |
| Capability Registry integrity | PASS | Python CI on checked commit 9cc2142 passed for Python 3.11, 3.12, and 3.13; registry JSON Schema validation, compile, blocking lint, Docker integration, and CodeQL passed. |
| Workspace atomic write hardening | PASS / PLATFORM UNKNOWN | Merged via PR #30 at commit f81ddf7. Python CI, Docker integration, and CodeQL passed on head 19e3c77, including invalid-Unicode rejection. Actual Android/Termux filesystem behavior and hard-link behavior remain untested on-device. |
| MCP SDK v2 stdio bridge | PASS / PLATFORM UNKNOWN | Merged via PR #32 at commit 6ece6d4. Latest checked main commit 7a807f1 passed Python CI on Python 3.11–3.13, Docker integration, and CodeQL. CI now tests both the three-tool read-only reference server and the seven-tool workspace server, including bounded write/read, parent-traversal rejection, symlink rejection, and hard-link write rejection on Linux. Actual Android/Termux behavior remains unverified. |
| Direct ChatGPT mobile access to a local stdio server | BLOCKED BY TRANSPORT MODEL | A local stdio MCP process serves its local host process. Direct ChatGPT access requires a supported remote MCP endpoint or authenticated relay; neither is deployed by these changes. |
| Termux device runtime | UNKNOWN | No registered Codex remote environment was returned and no direct execution channel to the phone is available in this session. A local smoke check on the device is still required. |
| OVERALGORITHM plugin release | PARTIAL | Current release remains 1.2.12. All 21 release-decision schema tests passed on the current schema files across Python 3.11–3.13. The 51-test combined audit initially exposed stale release-gate contract expectations; an isolated candidate copy corrected the version assertion and made the runtime-policy evidence wording explicit, then all 51 tests passed across Python 3.11–3.13 in private draft PR #3. The actual plugin remains 1.2.12; candidate 1.2.13 has not been published or read back as a release. |
| Hosting/deployment capability | AVAILABLE, NOT VERIFIED HERE | DigitalOcean and Render interfaces are registered. No remote bridge or public endpoint has been deployed in this workflow. |
| Automation capability | AVAILABLE, NOT VERIFIED HERE | Automation interfaces are registered. No recurring job was created as part of this task. |

## Pull request record

1. [#29 — Add initial capability registry and integrity tests](https://github.com/xiiitore/authoritylab/pull/29) — merged as `558f01b`.
2. [#30 — Harden workspace writes with descriptor-relative atomic replacement](https://github.com/xiiitore/authoritylab/pull/30) — merged as `f81ddf7`.
3. [#31 — Align Termux MCP bridge and smoke test with SDK v2](https://github.com/xiiitore/authoritylab/pull/31) — closed without merge because its base was superseded.
4. [#32 — Align Termux MCP bridge and smoke test with SDK v2](https://github.com/xiiitore/authoritylab/pull/32) — merged as `6ece6d4` from a clean branch based on updated main.
5. [Private audit PR #3 — OVERALGORITHM v1.2.12 schema/contract tests](https://github.com/xiiitore/authority-boundary-lab/pull/3) — draft only, private repo; 51 tests passed on the candidate audit snapshot, not a plugin release.

## Next gates as of the snapshot date (2026-10-11)

1. Wait for post-merge CodeQL on `6ece6d4` to finish and confirm success.
2. Run the documented stdio, hard-link, and write-safety checks on the actual Termux device in a fresh checkout and the user's actual MCP virtual environment.
3. Verify the seven-tool workspace server separately from the three-tool read-only reference server; the Linux smoke test covers only the latter.
4. Decide whether a remote authenticated relay is needed. If so, design auth, rate limits, request size limits, path/command allowlists, logging without secrets, and revocation before deployment. No relay has been deployed.
5. Retrieve a runnable copy of the current OVERALGORITHM 1.2.12 archive and execute the full schema suite before any release candidate is considered.

## Status rule

Registered ≠ tested. A successful unit test ≠ a security certification. A passing Linux CI job ≠ a passing Android/Termux test. A draft PR ≠ a merged release.
