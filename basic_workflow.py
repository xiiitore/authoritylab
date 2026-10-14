from authoritylab import AuthorizationRequest, EvidenceSchema, ExactMatchAuthorizer, GovernancePolicy, Task, ToolResult, WorkflowCore
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
core = WorkflowCore(
    registry,
    policy,
    authorizer=ExactMatchAuthorizer({("demo-user", "echo", "demo-resource")}),
)
task = Task(task_id="demo-1", kind="echo", payload={"message": "hello", "resource_id": "demo-resource"})
report = core.run(
    task,
    authorization=AuthorizationRequest("demo-user", "echo", "demo-resource", "resource_id"),
)
print({"status": report.status.value, "output": report.tool_result.output if report.tool_result else None})
