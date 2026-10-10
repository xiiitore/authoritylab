# Authority-boundary regression matrix

Run from an environment where the project is installed:

```bash
python -m authoritylab.authority_boundary_matrix
```

The command emits a deterministic JSON report and exits nonzero if any observed
workflow status differs from the expected status. The matrix covers complete
structural evidence, missing schemas and fields, handler failure, missing and
rejecting semantic validators, validator exceptions, an untrusted handler, and
audit-persistence failure.

The `execution_only_baseline_accepts` field models a deliberately weak rule:
accept whenever an executed handler reports success and returns a non-null
output. A `baseline_false_accept` means that rule would accept a case that
AuthorityLab did not mark `PASS`. This is a local illustrative baseline, not
a benchmark against Microsoft, OpenAI, Agent Guard, or any other external
project. Its purpose is to make failure modes visible and reproducible, not to
claim comparative superiority.

A passing matrix is regression evidence for these specific scenarios only. It
does not establish semantic truth outside the configured test validator,
resistance to all adversarial inputs, production isolation, or production
security. Continue to treat the production acceptance gates in
`production-security-runbook.md` and `production-acceptance-evidence-template.md`
as blocked until target-environment evidence and independent review exist.
