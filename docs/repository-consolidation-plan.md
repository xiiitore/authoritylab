# Repository consolidation and retirement plan

Status: IN PROGRESS — no source repository is approved for deletion yet.

## Target

- Consolidation target: `xiiitore/authoritylab`.
- This repository is public. Treat every committed file, issue, and branch name as public.
- PR #59 merged on 2026-10-15 as commit `d1abbfeb1c3f537e0f8d61a2f7222a90bac14d62`. The current main branch must be tested and audited at its current SHA, not assumed equivalent to a prior PR head for every workflow.

## Source disposition

### `xiiitore/xiii` (public)

- Migrated in PR #59: bounded arithmetic evaluation, numeric-claim comparison, focused tests, and consolidation documentation.
- The durable claim ledger is not copied: it stores raw claim/evidence strings and overlaps with AuthorityLab's audit log; a separate privacy and integrity design review is required.
- The HTTP MCP server is not copied: transport changes increase attack surface and dependency compatibility must be verified independently.

### `xiiitore/authority-boundary-lab` (private)

- No private code, issues, coordination documents, local paths, or comments are copied into this public repository.
- The release-decision/readback verifier and RBAC policy engine remain candidates for a later private migration branch, or a reviewed migration after the target's visibility is deliberately changed.
- The source issue and coordination history must be archived privately before source retirement.

## Required gates before deleting either source repository

1. Review and test each migration through a pull request. Record any review gap rather than assuming a merge means an independent review occurred.
2. Verify API and packaging compatibility and run the full target test suite against the exact current main commit.
3. Export complete Git bundles or equivalent archives for both source repositories, including branches, tags, issues, pull requests, comments, workflow evidence, and relevant metadata. Verify archive readability and checksums.
4. Run full-tree and Git-history secret scans on each source; rotate any exposed credential before retirement.
5. Preserve the open operational acceptance checklist from `xiiitore/xiii#3` and archive private coordination from `xiiitore/authority-boundary-lab#2`. The issue #2 comment export has been written to the private branch `archive/issue-2-comments-before-retirement` in three parts (83 comments returned by the connector). This is not yet an independently verified full backup and must not be treated as permission to delete the source.
6. Decide target visibility explicitly. If private owner data or private source code is required, make the target private before copying any such material.
7. Confirm no unique required commits, branches, release artifacts, or external dependencies remain.
8. Delete sources only after archive verification and a separate explicit final confirmation.

## Repository protection and documentation alignment

- GitHub's repository rulesets API reports ruleset ID `25089680` named `main` with `enforcement: active`. The classic branch-protection endpoint separately reports `main` as `protected: false`; rulesets and classic branch protection are separate controls.
- The active ruleset includes pull-request, deletion, non-fast-forward, CodeQL-threshold, and code-quality rules, but currently requires **0 approvals** and has **no required status checks**. It therefore does not enforce independent human approval or named CI checks before merge.
- The ruleset readback has empty include/exclude branch patterns. Verify in the GitHub UI that its scope explicitly includes `refs/heads/main` before relying on it for main-branch protection.
- PR #59 merged without any submitted review recorded by GitHub. Do not treat the merge itself as evidence of independent review. Tighten and read back the ruleset before the next production-sensitive merge.
- Repository visibility is public. GitHub metadata reports no detected license while `pyproject.toml` declares MIT and the reviewed tree has no `LICENSE` file. Legal license ownership and intent need owner review; no license was invented or added.
- Do not describe production acceptance as complete until deployment and release gates are evidenced.

## Completed in this workstream

- PR #59 merged bounded arithmetic evaluation and focused regression tests into `main`.
- PR #59's recorded CI passed Python tests for Python 3.11, 3.12, and 3.13, Docker sandbox integration, and CodeQL on its exact head SHA `1f23068af2eba4a22f9cc491f0891c358664f780`.
- The merge commit is `d1abbfeb1c3f537e0f8d61a2f7222a90bac14d62`. Re-run or verify checks on this merge commit before treating current `main` as fully validated.
- Exported all 83 issue #2 comments returned by the connector into three Markdown files on a private archive branch. Archive verification is still required.

## This documentation update

Corrects stale claims that the ruleset was disabled and records the actual incomplete enforcement state after PR #59 merged. It does not alter main, repository visibility, or ruleset settings.
