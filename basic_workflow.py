from authoritylab import EvidenceSchema, GovernancePolicy, Task, ToolResult, WorkflowCore
from authoritylab.tools import ToolRegistry

registry = ToolRegistry()
registry.register(
    "echo",
    lambda task: ToolResult(ok=True, output={"echo": dict(task.payload)}),
    trusted=True,
)
policy = GovernancePolicy(
    evidence_schemas=(EvidenceSchema("echo", ("echo",)),)
)
core = WorkflowCore(registry, policy)
report = core.run(Task(task_id="demo-1", kind="echo", payload={"message": "hello"}))
print({"status": report.status.value, "output": report.tool_result.output if report.tool_result else None})
