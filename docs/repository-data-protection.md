# Repository Data Protection Plan

Status reviewed: 2026-10-14.

- **Repository visibility:** PASS — GitHub repository API currently reports this repository as private.
- **Protection for `main`:** USER-REPORTED — the owner confirmed enabling branch protection in GitHub Settings. Independent API verification was blocked with HTTP 403 (`Resource not accessible by integration`), so the exact enforced rules remain UNKNOWN to this audit.
- **Secret scanning / push protection:** UNKNOWN — not directly verified.
- **Credential and personal-data history audit:** NOT COMPLETED — searching the current default-branch tree is not a complete history audit.

## Immediate priorities

1. Keep the repository private unless there is a deliberate, reviewed reason to publish it. Re-check collaborators and automation access after visibility changes.
2. Enable GitHub secret scanning and push protection if available, then verify the settings directly.
3. Review current files and Git history for credentials and personal data. Current-tree inspection alone is insufficient.
4. If a credential was exposed, revoke/rotate it before attempting history cleanup. Deleting a file does not revoke a credential or remove copies already cloned, forked, cached, or archived.
5. Review collaborators, GitHub Apps, OAuth grants, deploy keys, webhooks, workflow permissions, repository secrets, and environments. Remove unused access and use least privilege.
6. Set workflow permissions to read-only by default. Never expose write-capable tokens or secrets to untrusted pull-request code.
7. Require review and passing checks before changes reach `main`, where repository settings and plan permit. Confirm the exact rules in GitHub Settings; this audit's connector cannot independently read the branch-protection endpoint.
8. Use synthetic test data. Never commit tokens, passwords, private keys, session cookies, recovery codes, production datasets, or unredacted personal data.
9. Redact secrets and personal identifiers from issues, PRs, CI logs, artifacts, caches, screenshots, and commit messages.
10. Treat a green CI run as evidence only for the checks actually executed, not as proof of complete security.

## Workflow review

- The CodeQL, Docker integration, and Python test workflows inspected on `main` declare read-only contents permissions, except CodeQL's required `security-events: write` permission.
- The demo workflow `.github/workflows/github-actions-demo.yml` is still present on `main` at the time of this review. Draft PR #46 proposes deleting it; the PR has not been merged, so the deletion is not active on `main`.
- The workflow review was a targeted static inspection, not a full supply-chain or runtime audit.

## Evidence labels

For each control, record the exact setting or test, date, and observed result. Use PASS only after direct verification; use UNKNOWN for settings not inspected. User-reported state must remain distinguishable from independently verified state.

## Limitations

This document records evidence and priorities; it does not itself enable security settings, revoke credentials, or complete a Git-history scan.
