# Repository Data Protection Plan

Status reviewed: 2026-10-14. Repository visibility was observed as public.

## Immediate priorities

1. Decide whether this repository is intentionally public. If any non-public operational details, personal data, credentials, or private plans belong here, change visibility in GitHub Settings > General > Danger Zone > Change visibility. Confirm collaborator and automation impact first.
2. Enable GitHub secret scanning and push protection if available, then verify the settings directly.
3. Review current files and Git history for credentials and personal data. Current-tree inspection alone is insufficient.
4. If a credential was exposed, revoke/rotate it before attempting history cleanup. Deleting a file does not revoke a credential or remove copies already cloned, forked, cached, or archived.
5. Review collaborators, GitHub Apps, OAuth grants, deploy keys, webhooks, workflow permissions, repository secrets, and environments. Remove unused access and use least privilege.
6. Set workflow permissions to read-only by default. Never expose write-capable tokens or secrets to untrusted pull-request code.
7. Require review and passing checks before changes reach main, where repository settings and plan permit.
8. Use synthetic test data. Never commit tokens, passwords, private keys, session cookies, recovery codes, production datasets, or unredacted personal data.
9. Redact secrets and personal identifiers from issues, PRs, CI logs, artifacts, caches, screenshots, and commit messages.
10. Treat a green CI run as evidence only for the checks actually executed, not as proof of complete security.

## Evidence labels

For each control, record the exact setting or test, date, and observed result. Use PASS only after direct verification; use UNKNOWN for settings not inspected.

## Limitations

This plan does not change repository visibility or enable any GitHub security setting. Those changes must be performed and verified in GitHub.
