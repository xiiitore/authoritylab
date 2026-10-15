# Consolidation migration: release read-back gate

This branch migrates the deterministic release read-back gate and its behavioral regression tests from `xiiitore/authority-boundary-lab` into the `xiiitore/authoritylab` public target.

## Scope
- `release_readback_gate.py`: conservative status assessment from caller-supplied release identifiers, runtime policy, and mandatory test evidence.
- `test_release_readback_gate.py`: tests for PASS, BLOCKED, UNKNOWN, and REVISE outcomes, including sentinel and malformed evidence.

## Security and authority boundary
- A `PASS` means only that the supplied fields satisfy this helper's checks. It does not authenticate the evidence, prove that a host runtime executed, or authorize a production release.
- The private RBAC engine is intentionally not copied because it overlaps with `authorization.py`; integration requires a single policy model and a separate design review.
- The private release-decision verifier and schema are not yet migrated; their versioning and catalog-evidence contracts require compatibility review.
- The `xiiitore/xiii` ledger lock and HTTP MCP server remain excluded: the ledger overlaps with audit-log semantics and may store raw claim/evidence text; the HTTP server expands the remote attack surface.
- No private issues, coordination notes, comments, local paths, credentials, or owner contact data are included.

## Merge gates
- Run the target's full CI and review the diff.
- Review the complete source/destination tree and Git history for secrets.
- Export and verify complete archives of both source repositories and their relevant GitHub metadata.
- Confirm no unique required code, commits, branches, releases, or dependencies remain.
- Do not delete either source repository until all gates pass and the retirement operation is ready.

This PR is a partial migration and does not authorize source repository deletion.
