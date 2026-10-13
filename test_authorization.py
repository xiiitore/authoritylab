import unittest

from authoritylab import (
    AuthorizationDecision, AuthorizationRequest, CheckStatus, ExactMatchAuthorizer,
    Task, ToolResult, WorkflowCore, WorkflowStatus,
)
from authoritylab.tools import ToolRegistry


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.registry = ToolRegistry()
        self.registry.register(
            "read",
            lambda task: self.calls.append(dict(task.payload))
            or ToolResult(ok=True, output={"value": "ok"}),
            trusted=True,
        )
        self.authorizer = ExactMatchAuthorizer({("user-a", "read", "file-1")})
        self.core = WorkflowCore(self.registry, authorizer=self.authorizer)

    def request(self, subject="user-a", action="read", resource="file-1", field="resource_id"):
        return AuthorizationRequest(subject, action, resource, field)

    def test_exact_grant_allows_exact_target(self):
        report = self.core.run(
            Task("t-1", "read", {"resource_id": "file-1"}),
            authorization=self.request(),
        )
        self.assertEqual(report.status, WorkflowStatus.UNKNOWN)  # evidence schema is not configured
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(report.checks[0].name, "authorization")
        self.assertEqual(report.checks[0].status, CheckStatus.PASS)
        self.assertEqual(report.audit["authorization"]["status"], "PASS")

    def test_missing_authorizer_fails_closed_before_handler(self):
        core = WorkflowCore(self.registry)
        report = core.run(
            Task("t-2", "read", {"resource_id": "file-1"}),
            authorization=self.request(),
        )
        self.assertEqual(report.status, WorkflowStatus.BLOCKED)
        self.assertEqual(len(self.calls), 0)

    def test_missing_request_fails_closed_before_handler(self):
        report = self.core.run(Task("t-3", "read", {"resource_id": "file-1"}))
        self.assertEqual(report.status, WorkflowStatus.BLOCKED)
        self.assertEqual(len(self.calls), 0)

    def test_action_mismatch_fails_closed(self):
        report = self.core.run(
            Task("t-4", "read", {"resource_id": "file-1"}),
            authorization=self.request(action="delete"),
        )
        self.assertEqual(report.status, WorkflowStatus.BLOCKED)
        self.assertEqual(len(self.calls), 0)

    def test_target_substitution_fails_closed(self):
        report = self.core.run(
            Task("t-5", "read", {"resource_id": "file-2"}),
            authorization=self.request(resource="file-1"),
        )
        self.assertEqual(report.status, WorkflowStatus.BLOCKED)
        self.assertEqual(len(self.calls), 0)

    def test_wrong_subject_is_denied(self):
        report = self.core.run(
            Task("t-6", "read", {"resource_id": "file-1"}),
            authorization=self.request(subject="user-b"),
        )
        self.assertEqual(report.status, WorkflowStatus.BLOCKED)
        self.assertEqual(len(self.calls), 0)

    def test_authorizer_exception_fails_closed(self):
        class Broken:
            def authorize(self, task, request):
                raise RuntimeError("sensitive token")
        core = WorkflowCore(self.registry, authorizer=Broken())
        report = core.run(
            Task("t-7", "read", {"resource_id": "file-1"}),
            authorization=self.request(),
        )
        self.assertEqual(report.status, WorkflowStatus.BLOCKED)
        self.assertEqual(len(self.calls), 0)
        self.assertNotIn("sensitive token", str(report.audit))

    def test_invalid_authorizer_result_fails_closed(self):
        class Broken:
            def authorize(self, task, request):
                return True
        core = WorkflowCore(self.registry, authorizer=Broken())
        report = core.run(
            Task("t-8", "read", {"resource_id": "file-1"}),
            authorization=self.request(),
        )
        self.assertEqual(report.status, WorkflowStatus.BLOCKED)
        self.assertEqual(len(self.calls), 0)

    def test_decision_requires_explicit_boolean(self):
        with self.assertRaises(TypeError):
            AuthorizationDecision(1, "id", "reason")

    def test_mutation_of_original_target_cannot_reuse_stale_request(self):
        payload = {"resource_id": "file-1"}
        task = Task("t-9", "read", payload)
        payload["resource_id"] = "file-2"
        report = self.core.run(task, authorization=self.request(resource="file-1"))
        self.assertEqual(report.status, WorkflowStatus.BLOCKED)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
