# Capability Registry — Initial Inventory

**Status:** INVENTORY ONLY — NOT EXECUTION-VERIFIED  
**Snapshot date:** 2026-10-11  
**Repository:** xiiitore/authoritylab  
**Scope:** current session tool catalog and inspected repository/plugin surfaces.

## Scope and limits

This is an inventory, not proof that listed interfaces are callable, authorized, stable, or correct. Every item has execution_verified=false. Effect classes are text heuristics and are not a security boundary. Descriptions longer than 360 characters are truncated in the JSON and marked accordingly.

## Snapshot

- Registered interfaces: **441**.
- Namespaces: **26**.
- No credentials or private file contents are included.

## Provider counts

| Provider / namespace | Interfaces |
|---|---:|
| GitHub | 89 |
| DigitalOcean | 54 |
| Notion | 51 |
| Todoist | 47 |
| Coda | 38 |
| Elicit | 36 |
| Dropbox | 24 |
| Render | 23 |
| Mamble_Calculators | 21 |
| Plugin_Creator | 7 |
| Automations | 7 |
| files | 7 |
| Plugin_Management | 6 |
| Codex_Tasks | 5 |
| Private_PDF_Tools | 4 |
| Consensus | 4 |
| DSCR_Loan_Calculator | 4 |
| Wolfram | 3 |
| user_settings | 2 |
| SciSpace | 2 |
| skills | 2 |
| B12_Website_Generator | 1 |
| Insta_Website_Builder | 1 |
| 2_2_Calculator | 1 |
| Premom_Ovulation_Calculator | 1 |
| z3 | 1 |

## Verified project facts

- xiiitore/authoritylab is public, default branch main; connected GitHub identity reports admin/push permissions.
- README describes AuthorityLab as a reference implementation, not a production-grade governance/security system.
- README says the project itself has no external plugin integrations, authentication, web API, or distributed execution.
- README explicitly states the subprocess runner is not a security sandbox; Docker assurance depends on host/runtime/image trust.
- pyproject.toml declares optional MCP dependencies mcp>=1.26,<2 and dulwich>=0.22,<1 in the original inventory. PR #31 upgrades the optional MCP dependency to >=2.3,<3 and adds an SDK v2 stdio smoke test; CI and on-device Termux verification must both pass.
- Codex Tasks returned no registered remote environments in this run; this does not prove Termux is unreachable through every possible method.
- overalgorithm-engine current version is 1.2.12. Full current schema tests have not run in this environment; do not publish a candidate based only on static checks.

## Priority gaps

1. **MCP dependency compatibility:** PR #31 pins the supported SDK major range to >=2.3,<3; re-run CI on main and verify on the actual Termux installation.
2. **Tool verification:** add positive, negative, permission-denied, timeout, malformed-output, and regression tests. A provider is not verified by one successful call.
3. **Termux bridge:** allow-listed operations only, not arbitrary shell execution; default read-only; canonical path checks; timeouts/output caps; no inherited secrets; structured audit logs; explicit gates for mutation.
4. **Reproducible tests:** clean checkout/install test; align README commands with CI; preserve backup/quarantine files unless reviewed.
5. **Release integrity:** stage candidate, run complete tests, inspect artifact, and read back published release. No PASS without execution evidence.
6. **Observability:** record run IDs, redacted inputs, versions, result status, test outputs, and artifact hashes. Never log credentials.

## Status semantics

- PASS: all applicable mandatory gates executed and validated.
- PARTIAL: some checks passed; one or more mandatory checks remain unexecuted.
- UNKNOWN: evidence is insufficient.
- BLOCKED: execution cannot safely or validly continue.
- FAIL: an executed required check failed.
- KILL: a required condition is contradicted.

## Next sequence

1. Add a schema and registry tests.
2. Audit repository tree, test discovery, CI, and clean dependency resolution.
3. Build the bridge on an isolated branch and test allow-list and rejection paths.
4. Independently review security boundaries before network exposure.
5. Open a PR for review; do not merge automatically.

## Provenance

Generated from current session tool metadata on 2026-10-11. Counts vary by session/account and do not prove runtime success. Repository facts came from live GitHub metadata plus README.md, pyproject.toml, and architecture.md. Plugin version came from Plugin Creator metadata.

## Related capability matrix

See [capability-matrix.md](capability-matrix.md) for task-level status, verification evidence, and remaining execution gates.

## Related capability matrix

See [capability-matrix.md](capability-matrix.md) for task-level status, verification evidence, and remaining execution gates.
