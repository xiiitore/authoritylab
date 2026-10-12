# Workflow Governance and Release Contract

This document defines the canonical operating contract for AuthorityLab and connected workflow/plugin work. It is a repository-level specification, not evidence that external plugins, the EAV bridge, ChatGPT runtime, or a deployment currently enforce it.

## 1. Canonical authority boundaries

- **WORKFLOW CORE** is the sole primary coordinator. It classifies the task, selects the minimum sufficient capabilities, checks authority and dependencies, orders execution, tracks observed states, and hands evidence to verification.
- **Plugin Detector** is advisory. It resolves capability gaps, inventory completeness, exact identities, canonical ownership, and duplicate suppression. It does not authorize actions or execute plugins.
- **Workflow Tools** owns procedural workflow and programming knowledge. It is not a second coordinator.
- **Specialist tools** perform the concrete operation: retrieval, calculation, code execution, repository mutation, or external action.
- **Execution Verification** measures execution and reproducibility.
- **Evidence Verifier** performs a distinct-method audit of material evidence and claims. A different plugin name is not evidence of independence.
- **EAV** performs structured evidence-to-action checks. The EAV Independent MCP Bridge uses the same logical EAV core and is a transport/package companion, not an independent vote. Use one surface per audit when both are available.
- **OVERALGORITHM** is the governance and release authority. It does not replace WORKFLOW CORE as coordinator.
- **Memory Archive** stores durable decisions, provenance, versions, conflicts, and supersession history. Memory is not evidence and archival is not verification.

Legacy adapters remain only for compatibility. They must defer to their canonical owner and must not create a competing authority. Do not delete an adapter solely because it is redundant: first identify dependent references, migration requirements, and rollback.

## 2. Canonical execution sequence

`INTAKE → CLASSIFY → CAPABILITY_ROUTE → AUTHORITY_CHECK → DEPENDENCY_PLAN → EXECUTE → OBSERVE → VERIFY → AUDIT → DECIDE → ARCHIVE`

1. **INTAKE:** restate the requested outcome and identify external side effects.
2. **CLASSIFY:** define task type, consequence, scope, falsifiable claim, and acceptance criteria.
3. **CAPABILITY_ROUTE:** inspect current tool schemas and inventory when availability, identity, overlap, or independence materially affects correctness. Select the smallest capability-complete set.
4. **AUTHORITY_CHECK:** verify the exact target, permission, policy, reversibility, and side-effect scope before mutation.
5. **DEPENDENCY_PLAN:** establish a directed acyclic dependency graph; run only ready steps and recompute after material failures or state changes.
6. **EXECUTE:** make the smallest sufficient change. Keep unrelated refactors separate.
7. **OBSERVE:** capture actual tool outputs, postconditions, source IDs, timestamps, versions, commit SHAs, and relevant hashes/excerpts.
8. **VERIFY:** test positive, negative, missing-evidence, boundary, adversarial, and regression cases appropriate to the risk.
9. **AUDIT:** use a materially different method, invariant, source, oracle, or failure mode for independent verification where required. Explicitly record shared dependencies.
10. **DECIDE:** OVERALGORITHM evaluates all applicable mandatory gates and evidence; it does not infer missing evidence from plausibility.
11. **ARCHIVE:** preserve the decision and provenance only after recording the real outcome and limitations.

## 3. State transitions and claims

Use explicit state transitions:

`UNKNOWN → AVAILABLE → SELECTED → AUTHORIZED → INVOKED → OUTPUT_OBSERVED → OUTPUT_VALIDATED → COMMITTED`

Each transition requires its own evidence. Selection does not imply invocation; invocation does not imply a correct result; a tool-reported success does not establish the external postcondition; a committed change does not imply release acceptance.

When reporting execution, distinguish:
- requested;
- attempted;
- tool returned;
- postcondition observed;
- independently verified;
- committed or released.

Never claim a plugin, bridge, test suite, deployment, or runtime path was invoked or verified without the corresponding observable result. If the trace is incomplete, use `UNKNOWN`.

## 4. Status and release gate

- **PASS:** all applicable mandatory checks passed with evidence that supports the exact claim and scope.
- **FAIL / REFUTED:** a relevant check or authoritative observation contradicts the claim.
- **BLOCKED:** a required action/check cannot proceed because of authority, dependency, safety, configuration, or execution constraints.
- **UNKNOWN:** evidence is absent, incomplete, unauthenticated, stale, ambiguous, or insufficient.
- **REVISE:** a concrete defect or unresolved requirement needs correction and rerun.
- **PARTIAL:** limited support exists but one or more required verification gates remain unresolved.
- **VERIFIED:** reserved for a claim whose applicable authoritative and independent checks actually passed within the stated scope.
- **KILL:** a research or implementation branch is rejected by a documented decisive contradiction or failure criterion; preserve the evidence and do not silently revive it.

A release cannot be PASS/VERIFIED while any applicable required gate is missing, UNKNOWN, BLOCKED, failed, or lacks evidence references. If runtime verification is not required, record the explicit policy and evidence for why it is not applicable; do not use a placeholder or self-asserted exemption. Package integrity, CI success, memory, repeated tool output, and plausibility are not substitutes for independent evidence.

## 5. Loop detection versus factual verification

These are separate controls:

- A **loop detector** observes a complete-enough execution trace and identifies configured repeated calls, cycles, failure cascades, or lack of progress. It requires stable run/event identifiers, bounded windows and budgets, explicit intervention behavior, and evidence of enforcement.
- A **factual-claim auditor** checks whether claims are supported, contradicted, or unknown based on source provenance, exact evidence, transformations, and entailment.
- Neither control is a universal hallucination detector. Successful execution does not prove factual correctness.
- A progress marker counts only when a harness or external observer records a concrete milestone; model self-report alone is insufficient.
- If only one execution layer is instrumented, state that coverage boundary. Do not claim global protection for uninstrumented tools, plugins, or runtimes.

## 6. Duplicate and independence policy

Resolve each overlapping capability to one canonical owner. Adapters may preserve compatibility but must defer and must not be selected as a second authority. In particular:

- WORKFLOW CORE, not Universal Workflow Engine or Workflow Control Core, owns primary coordination.
- Canonical Workflow Tools owns procedural/programming knowledge; the compatibility entry does not replace it.
- OVERALGORITHM Engine owns release governance; historical OVERALGORITHM entries are adapters.
- Evidence Verifier owns independent audit; it is not the coordinator or release authority.
- EAV and EAV Independent MCP Bridge share the same logical evidence path and are not independent confirmations.
- Canonical Research Auditor, Memory Archive, and Music Analysis Research Tool own their respective domains; historical compatibility entries must defer to them.

For every claimed independent check, record the method, source, implementation/provenance, and shared dependencies. If independence cannot be established, mark it UNKNOWN and do not count it as an independent vote.

## 7. Repository and plugin change protocol

1. Inspect the exact current branch, target, version/release ID, relevant files, tests, and dependencies.
2. Create a focused branch; do not write to `main` for unreviewed changes.
3. Keep unrelated fixes in separate changesets.
4. Add tests before or with the behavior change. Include expected failures and boundary cases, not only the happy path.
5. Run local checks where available and record the environment. Then inspect fresh CI results for the exact head SHA.
6. Review the actual diff, including security, compatibility, side effects, and rollback.
7. Retarget dependent PRs only after their dependency is merged; rerun required checks after retarget/rebase.
8. Keep changes unmerged until the explicit release gate passes. A green CI is necessary where required, not sufficient.
9. After plugin updates, read back the exact release and manifests. This verifies package state only, not host runtime integration.
10. For Termux, tunnels, MCP bridges, or external runtimes, verify the actual process, authenticated transport, exposed tools, harmless end-to-end call, and postcondition separately. Never infer these from repository or package metadata.

## 8. Required audit record

For every material change, retain:
- claim and acceptance criteria;
- repository/plugin identity and exact version/release/branch/commit;
- authority and dependency decisions;
- files changed and rationale;
- commands/tools actually executed and their raw result summaries;
- positive, negative, boundary, and regression test outcomes;
- independent method and shared dependencies;
- final OVERALGORITHM decision with evidence references;
- blockers, residual unknowns, known limitations, and rollback path.

If an item was not checked, label it `NOT_CHECKED` or `UNKNOWN`; do not silently convert it to PASS.

## 9. Current implementation boundary

This contract is documentation until executable checks enforce it. The existing loop-guard PRs are separate proposals: PR #35 supplies the detector primitive; PR #36 integrates it into the repository's WorkflowCore on a branch based on PR #35. Neither PR being open or CI passing proves that this contract is active in external plugins, the EAV bridge, ChatGPT runtime, or a deployed service.
