# AuthorityLab

AuthorityLab is a small, executable reference implementation for evidence-aware workflow orchestration. It is a foundation to extend—not a claim that an autonomous or production-grade governance system already exists.

## What it does

- **Workflow Core** classifies a task and routes it to an explicitly registered handler.
- **Workflow Tools** are registered handlers with declared names and predictable inputs/outputs.
- **OVERALGORITHM** is represented by governance rules that define required evidence and acceptance gates.
- **Verification** evaluates a result against required checks and keeps execution status separate from acceptance status.
- **Audit records** capture task, route, result, checks, and final status in structured data.

The names describe module responsibilities in this repository. They do not imply a connection to external plugins or a privileged system layer.

## Requirements

- Python 3.11 or newer
- Runtime uses only the Python standard library

## Run

From the repository root:

```bash
python -m unittest discover -s tests -v
```

Example:

```python
from authoritylab import WorkflowCore, Task, ToolResult
from authoritylab.tools import ToolRegistry
from authoritylab.governance import GovernancePolicy
from authoritylab.verification import ResultVerifier, Check

registry = ToolRegistry()
registry.register("echo", lambda task: ToolResult(ok=True, output={"echo": task.payload}))
core = WorkflowCore(registry, GovernancePolicy(required_checks=("result_present",)))
report = core.run(Task(task_id="demo-1", kind="echo", payload={"message": "hello"}))
print(report.status.value)
```

For a runnable example, see `examples/basic_workflow.py` in the repository.

## Status semantics

- `PASS`: all required checks were executed and passed.
- `FAIL`: a required check ran and failed, or the routed tool failed.
- `BLOCKED`: a required check was not executed or the route/tool was unavailable.
- `UNKNOWN`: evidence is insufficient to decide.

A successful tool call alone is not acceptance. Acceptance is determined separately by the required checks. Never treat missing evidence as a pass.

## Architecture

```text
Task -> WorkflowCore -> ToolRegistry -> ToolResult
                   \-> GovernancePolicy -> ResultVerifier -> WorkflowReport
```

See `docs/architecture.md` and `docs/verification.md` for design details and limitations.

## Development

```bash
python -m unittest discover -s tests -v
```

Keep core logic deterministic and side-effect-light. Put network, filesystem, and external-service actions behind explicit tool adapters. Add positive, negative, missing-evidence, and boundary tests for new gates.

## Current limitations

- No external plugin integrations are implemented.
- No persistent database, authentication, web API, or distributed execution is included.
- Registered handlers run in-process and are not sandboxed.
- Audit records are returned in memory; durable storage must be added explicitly.
- This is a starting implementation, not a security certification or production-readiness claim.
