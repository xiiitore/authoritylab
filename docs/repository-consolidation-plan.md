# Repository consolidation and retirement plan

Status: IN PROGRESS — no source repository is approved for deletion yet.

## Target
- Consolidation target: `xiiitore/authoritylab`.
- This repository is currently public. Treat all content added here as public.
- Main remains unchanged by this branch; review and CI are required before merge.

## Source disposition

### `xiiitore/xiii` (public)
- Candidate migrated in this change: bounded arithmetic evaluation and numeric-claim comparison only.
- The durable claim ledger is not copied: it stores raw claim/evidence strings and overlaps with AuthorityLab's audit log; a separate privacy and integrity design review is required.
- The HTTP MCP server is not copied: transport changes increase attack surface and dependency compatibility must be verified independently.

### `xiiitore/authority-boundary-lab` (private)
- No private code, issues, coordination documents, local paths, or comments are copied into this public repository.
- The release-decision/readback verifier and RBAC policy engine remain candidates for a later private migration branch, or a reviewed migration after the target's visibility is deliberately changed.
- The source issue and coordination history must be archived privately before source retirement.

## Required gates before deleting either source repository

1. Review and merge the migration PR only after CI passes and a human reviews the diff.
2. Verify API and packaging compatibility and run the full target test suite.
3. Export complete Git bundles or equivalent archives for both source repositories, including branches, tags, issues, pull requests, comments, workflow evidence, and relevant metadata. Verify archive readability and checksums.
4. Run full-tree and Git-history secret scans on each source; rotate any exposed credential before retirement.
5. Preserve the open operational acceptance checklist from `xiiitore/xiii#3` and archive private coordination from `xiiitore/authority-boundary-lab#2`.
6. Decide target visibility explicitly. If private owner data or private source code is required, make the target private before copying any such material.
7. Confirm no unique required commits, branches, release artifacts, or external dependencies remain.
8. Delete sources only after archive verification and a separate explicit final confirmation.

## Repository protection and documentation alignment

- Current observed target state: `main` is unprotected and the `main` ruleset is disabled. This branch does not change repository administration settings.
- Before accepting production changes, enable an effective ruleset requiring pull requests and required CI checks, with force-push and branch deletion restricted.
- Repository visibility, license metadata, and a real license file must agree. The project metadata declares MIT, but the repository API reported no license and the reviewed tree did not establish a `LICENSE` file; resolve this before publishing migrated code.
- Do not describe production acceptance as complete until the release gates are evidenced.

## This change

Adds the public arithmetic evaluator and focused tests from the public `xiiitore/xiii` source. It does not migrate the claim ledger, HTTP server, or any private-source content. It does not alter `main`, repository visibility, rulesets, or either source repository.
