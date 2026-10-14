# Repository Data Protection

Review date: 2026-10-14

## Verified state

- **Repository visibility: PASS.** GitHub repository metadata reports `xiiitore/authoritylab` as private.
- **Workflow permissions: PASS (targeted review).** The inspected Python and Docker workflows use read-only contents permissions. CodeQL also grants `security-events: write` for its scan upload.
- **Demo workflow: PASS.** The unused `.github/workflows/github-actions-demo.yml` workflow is no longer present on `main`.
- **Per-action authorization: PASS (implementation present).** `WorkflowCore` now denies execution by default unless a configured authorizer grants a matching action and resource. `legacy_mode=True` bypasses this gate and must not be enabled in security-sensitive deployments.
- **Authorization identity: LIMITATION.** The core does not authenticate `subject_id`; the caller must provide it from a trusted identity boundary. The included exact-match authorizer is a reference policy, not a durable production permission service.
- **Main branch protection: UNKNOWN.** The GitHub integration cannot read the branch-protection endpoint (HTTP 403), so required reviews/checks and enforcement rules have not been independently verified here.
- **Secret scanning and push protection: UNKNOWN.** Settings were not directly verified.
- **Credential/personal-data history audit: NOT COMPLETED.** Current-tree review is not a complete Git-history scan.

## Practical controls

1. Keep this repository private unless publication is deliberate and reviewed.
2. Review collaborators, GitHub Apps, OAuth grants, deploy keys, webhooks, workflow permissions, repository secrets, and environments; remove unused access.
3. Enable secret scanning and push protection if available, then verify the actual settings.
4. Review the current tree and Git history for credentials and personal data. If a credential was exposed, revoke or rotate it first; deleting a file does not invalidate the credential or remove existing copies.
5. Keep workflow permissions read-only by default and never expose write-capable tokens to untrusted pull-request code.
6. Use synthetic test data. Do not commit tokens, passwords, private keys, session cookies, recovery codes, production datasets, or unnecessary personal data.
7. Treat CI as evidence only for the checks that actually ran. A successful test suite is not proof of complete security.

## Known limitations

- `privacy.py` provides best-effort pattern and sensitive-key redaction; it is not a DLP guarantee and does not scan repository history, revoke credentials, or change GitHub settings.
- The audit log hash chain detects changes to recorded entries, but without an external HMAC key it does not protect against an attacker who can rewrite the entire log.
- The symlink-ancestor and FIFO hardening proposed in PR #43 is not yet on `main`.
- The latest CodeQL workflow result must be checked separately; earlier runs reported a GitHub integration access/configuration error after scan results were generated. That is not evidence that the scan found no issues.

## Evidence labels

Use **PASS** only for directly observed controls, **USER-REPORTED** for owner statements not independently verified, and **UNKNOWN** when the available integration cannot inspect a setting. Record the date and exact check for future reviews.
