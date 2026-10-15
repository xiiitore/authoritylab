# Repository Data Protection

Review date: 2026-10-15

## Verified state

- **Repository visibility: PUBLIC.** GitHub repository metadata reports `xiiitore/authoritylab` as public. Treat every committed file, issue reference, and branch name as potentially public. Do not store private-source code, private coordination, personal data, or secrets here.
- **Ruleset: ACTIVE, BUT INCOMPLETE.** GitHub's repository rulesets API reports ruleset ID `25089680` named `main` with `enforcement: active`. The classic branch-protection endpoint separately reports `main` as `protected: false`; this does not by itself negate a repository ruleset. The active ruleset contains pull-request, deletion, non-fast-forward, CodeQL threshold, and code-quality rules. However, it requires **0 approvals** and its required-status-check list is **empty**. Therefore it does not enforce an independent human approval or named CI checks before merge. Do not describe review or CI as required gates until the ruleset readback confirms those settings.
- **Ruleset scope: VERIFY.** The API readback currently has empty include/exclude branch patterns. Confirm in GitHub's ruleset UI that the rule applies to `main` (and only the intended branches) before relying on it as the main-branch control.
- **PR #59: MERGED, REVIEW GAP RECORDED.** PR #59 merged into `main` at merge commit `d1abbfeb1c3f537e0f8d61a2f7222a90bac14d62`. GitHub reported no submitted PR reviews. The merge does not prove a human review occurred; the active ruleset's approval count of zero explains why approval was not enforced.
- **Workflow permissions: PASS (targeted review only).** The inspected Python and Docker workflows use read-only contents permissions. CodeQL grants `security-events: write` for scan upload.
- **Demo workflow: PASS (targeted).** The unused `.github/workflows/github-actions-demo.yml` workflow is absent from the reviewed main tree.
- **Per-action authorization: IMPLEMENTATION PRESENT, IDENTITY BOUNDARY REQUIRED.** `WorkflowCore` denies execution by default unless a configured authorizer grants a matching action and resource. `legacy_mode=True` bypasses this gate and must not be enabled in security-sensitive deployments. The core does not authenticate `subject_id`; it must be supplied by a trusted identity boundary. The included exact-match authorizer is a reference policy, not a durable production permission service.
- **Symlink/FIFO hardening: MERGED TO MAIN (PR #43).** Do not treat this as a substitute for deployment-level isolation and least privilege.
- **CodeQL: LATEST OBSERVED RUN PASSED ON THE PR #59 HEAD.** This means that workflow run completed successfully for the recorded head; it does not prove absence of all vulnerabilities or that CodeQL is a required merge check.
- **Secret scanning, push protection, and credential/personal-data history audit: UNKNOWN / NOT COMPLETED.** A targeted current-file pattern scan is not a full-tree, Git-history, or GitHub secret-scanning settings audit. Do not claim these controls are enabled without direct evidence.

## Required practical controls

1. Keep this repository public only if publication is intentional. If private owner data or private-source code must be consolidated, change visibility through GitHub repository settings before copying that content.
2. Edit and read back the active ruleset: explicitly target `refs/heads/main`; require pull requests; require at least one approval from an independent reviewer where feasible; dismiss stale approvals; require the intended Python test and security checks by their exact names; block force pushes and branch deletion; and restrict bypass to a deliberately small set of administrators. Confirm the ruleset is active and its target scope is correct.
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
- The targeted text-pattern scan recorded below was run against the pre-PR-#59 main tree. It must not be described as a scan of the current post-merge tree or Git history.

## Evidence labels

Use **PASS** only for directly observed controls, **USER-REPORTED** for owner statements not independently verified, **BLOCKER** for a missing required control, and **UNKNOWN** when the available integration cannot inspect a setting. Record the date and exact check for future reviews.

## Historical current-tree content scan — 2026-10-15, pre-PR #59 merge

- Method: retrieved the complete non-binary Git tree for the then-current `main` and inspected every returned text/config/test blob with targeted patterns for private-key headers, common GitHub/AWS/Slack token formats, credential-bearing URLs, and quoted secret assignments; also checked for non-placeholder email-like strings and Termux home paths.
- Scope: 71 non-binary/text-like files on the pre-merge `main` tree at `fc02ce667815096e2e0aaba14056436d2d8e3007`; the GitHub tree response was not truncated and no blob retrieval errors were reported.
- Result: no token/key/credential finding was confirmed as a live secret. Pattern matches were confined to test fixtures that deliberately contain fake private-key text, fake AWS/Slack tokens, and credential-bearing example URLs for redaction/preflight tests. Email-pattern matches were placeholder/test data, including `owner@example.invalid` and a URL fixture matched as an email by the simple pattern. No Termux home path was found in that pre-merge public target tree.
- Source repositories at the time of scan: `xiiitore/xiii` — 10 text files scanned, no targeted pattern hits; `xiiitore/authority-boundary-lab` — 24 text files scanned, no token/key/credential-pattern hits. The private source does contain local Termux paths in coordination handoff documentation and an owner contact email in its private plugin manifest; these files must remain private and must not be copied into this public repository.
- Limitations: this is a historical current-tree, pattern-based scan, not Git-history scanning, entropy-based detection, provider-side secret scanning, or a guarantee that all sensitive data has been found. Re-scan the current tree and history before any repository retirement.
