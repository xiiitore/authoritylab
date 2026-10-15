# Repository Data Protection

Review date: 2026-10-15

## Verified state

- **Repository visibility: PUBLIC.** GitHub repository metadata reports `xiiitore/authoritylab` as public. Treat every committed file, issue reference, and branch name as potentially public. Do not store private-source code, private coordination, personal data, or secrets here.
- **Main branch protection: BLOCKER.** The GitHub branch endpoint reports `main` as unprotected. The observed `main` ruleset is disabled; its configuration did not require approvals or status checks. A passing CI run does not prevent an unreviewed direct push while these settings remain ineffective.
- **Workflow permissions: PASS (targeted review only).** The inspected Python and Docker workflows use read-only contents permissions. CodeQL grants `security-events: write` for scan upload.
- **Demo workflow: PASS (targeted).** The unused `.github/workflows/github-actions-demo.yml` workflow is absent from the reviewed main tree.
- **Per-action authorization: IMPLEMENTATION PRESENT, IDENTITY BOUNDARY REQUIRED.** `WorkflowCore` denies execution by default unless a configured authorizer grants a matching action and resource. `legacy_mode=True` bypasses this gate and must not be enabled in security-sensitive deployments. The core does not authenticate `subject_id`; it must be supplied by a trusted identity boundary. The included exact-match authorizer is a reference policy, not a durable production permission service.
- **Symlink/FIFO hardening: MERGED TO MAIN (PR #43).** Do not treat this as a substitute for deployment-level isolation and least privilege.
- **CodeQL: LATEST OBSERVED RUN PASSED.** The latest observed CodeQL workflow run on the consolidation branch completed successfully. This means the workflow completed; it does not prove absence of all vulnerabilities or secrets.
- **Secret scanning, push protection, and credential/personal-data history audit: UNKNOWN / NOT COMPLETED.** A targeted current-file pattern scan is not a full-tree, Git-history, or GitHub secret-scanning settings audit. Do not claim these controls are enabled without direct evidence.

## Required practical controls

1. Keep this repository public only if publication is intentional. If private owner data or private-source code must be consolidated, change visibility through GitHub repository settings before copying that content.
2. Enable an effective ruleset for `main`: require pull requests, require the Python test and security checks, dismiss stale approvals, block force pushes and branch deletion, and restrict bypass to a deliberately small set of administrators. Then read back the actual settings and verify enforcement.
3. Review collaborators, GitHub Apps, OAuth grants, deploy keys, webhooks, workflow permissions, repository secrets, and environments; remove unused access.
4. Verify secret scanning and push protection availability and actual settings. Run full-tree and Git-history secret scans. If a credential was exposed, revoke or rotate it first; deleting a file does not invalidate the credential or remove existing copies.
5. Keep workflow permissions read-only by default and never expose write-capable tokens to untrusted pull-request code.
6. Use synthetic test data. Do not commit tokens, passwords, private keys, session cookies, recovery codes, production datasets, or unnecessary personal data.
7. Treat CI as evidence only for the checks that actually ran. A successful test suite is not proof of complete security.

## Known limitations

- `privacy.py` provides best-effort pattern and sensitive-key redaction; it is not a DLP guarantee and does not scan repository history, revoke credentials, or change GitHub settings.
- The audit log hash chain detects changes to recorded entries, but without an external HMAC key it does not protect against an attacker who can rewrite the entire log.
- Repository metadata reported no detected license, while `pyproject.toml` declares MIT and no `LICENSE` file was found in the reviewed tree. Reconcile the legal license file and metadata before publishing reused or contributed code; do not assume the metadata alone grants rights to third-party material.
- Private-source coordination and issue history must be archived privately before retiring `xiiitore/authority-boundary-lab`.
- A targeted secret scan of selected files found no known token-like patterns, but a complete repository and history scan has not been evidenced.

## Evidence labels

Use **PASS** only for directly observed controls, **USER-REPORTED** for owner statements not independently verified, **BLOCKER** for a missing required control, and **UNKNOWN** when the available integration cannot inspect a setting. Record the date and exact check for future reviews.
