"""Tests for the experimental GitHub-to-Termux read-only task mailbox."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from authoritylab import github_termux_mailbox as mailbox


def task_body(task: dict) -> str:
    return mailbox.TASK_MARKER + "\n" + json.dumps(task)


class FakeWorkspace:
    def status(self):
        return {"ready": True, "root": "/private/path", "max_file_bytes": 200000,
                "allowed_operations": ["status", "write_file"]}

    def list_files(self, path="."):
        return ["README.md", "docs/"]

    def read_file(self, path):
        if path == "README.md":
            return "safe content"
        raise ValueError("private path details must not leak")


class TaskValidationTests(unittest.TestCase):
    def valid_task(self, **updates):
        value = {"version": 1, "task_id": "probe-001", "action": "status", "arguments": {}}
        value.update(updates)
        return value

    def test_valid_task(self):
        parsed = mailbox.parse_task(task_body(self.valid_task()))
        self.assertEqual(parsed["action"], "status")

    def test_missing_marker_rejected(self):
        with self.assertRaisesRegex(mailbox.MailboxError, "task_marker_missing"):
            mailbox.parse_task('{"version":1}')

    def test_extra_fields_rejected(self):
        with self.assertRaisesRegex(mailbox.MailboxError, "task_schema_invalid"):
            mailbox.parse_task(task_body(self.valid_task(extra="no")))

    def test_unknown_action_rejected(self):
        with self.assertRaisesRegex(mailbox.MailboxError, "action_not_allowed"):
            mailbox.parse_task(task_body(self.valid_task(action="shell")))

    def test_unhashable_action_rejected_cleanly(self):
        with self.assertRaisesRegex(mailbox.MailboxError, "action_not_allowed"):
            mailbox.parse_task(task_body(self.valid_task(action=["shell"])))

    def test_boolean_version_is_not_integer_version_one(self):
        with self.assertRaisesRegex(mailbox.MailboxError, "task_version_unsupported"):
            mailbox.parse_task(task_body(self.valid_task(version=True)))

    def test_path_traversal_rejected(self):
        with self.assertRaisesRegex(mailbox.MailboxError, "read_file_path_invalid"):
            mailbox.parse_task(task_body(self.valid_task(
                action="read_file", arguments={"path": "../secret"})))

    def test_write_file_requires_exact_arguments_and_confined_path(self):
        valid = self.valid_task(action="write_file", arguments={"path": "README.md", "content": "safe"})
        self.assertEqual(mailbox.parse_task(task_body(valid))["action"], "write_file")
        for path in ("../secret", "/tmp/secret", "dir/../../secret"):
            invalid = self.valid_task(action="write_file", arguments={"path": path, "content": "x"})
            with self.assertRaisesRegex(mailbox.MailboxError, "write_file_path_invalid"):
                mailbox.parse_task(task_body(invalid))

    def test_write_file_content_is_bounded(self):
        invalid = self.valid_task(action="write_file", arguments={
            "path": "README.md", "content": "x" * (mailbox.MAX_WRITE_BYTES + 1)})
        with self.assertRaisesRegex(mailbox.MailboxError, "write_file_content_too_large"):
            mailbox.parse_task(task_body(invalid))

    def test_git_status_diff_tests_and_write_file_actions(self):
        class GitWorkspace(FakeWorkspace):
            def git_status(self):
                return "## main\\n M README.md\\n"
            def git_diff(self):
                return "diff --git a/README.md b/README.md"
            def run_tests(self):
                return {"command": "ignored", "output": "Ran 1 test"}
            def write_file(self, path, content):
                return {"path": path, "bytes_written": len(content.encode("utf-8"))}

        workspace = GitWorkspace()
        self.assertEqual(mailbox.execute_task(workspace, self.valid_task(
            action="git_status"))["status"], "## main\\n M README.md\\n")
        self.assertEqual(mailbox.execute_task(workspace, self.valid_task(
            action="git_diff"))["diff"], "diff --git a/README.md b/README.md")
        self.assertEqual(mailbox.execute_task(workspace, self.valid_task(
            action="run_tests"))["output"], "Ran 1 test")
        self.assertEqual(mailbox.execute_task(workspace, self.valid_task(
            action="write_file", arguments={"path": "README.md", "content": "safe"})),
            {"path": "README.md", "bytes_written": 4})

    def test_status_does_not_expose_root_or_capabilities(self):
        result = mailbox.execute_task(FakeWorkspace(), self.valid_task())
        self.assertEqual(result, {"ready": True, "max_file_bytes": 200000})
        self.assertNotIn("root", json.dumps(result))
        self.assertNotIn("write_file", json.dumps(result))

    def test_read_file_returns_bounded_content(self):
        task = self.valid_task(action="read_file", arguments={"path": "README.md"})
        self.assertEqual(mailbox.execute_task(FakeWorkspace(), task)["content"], "safe content")

    def test_large_file_result_rejected(self):
        workspace = FakeWorkspace()
        workspace.read_file = lambda path: "x" * (mailbox.MAX_RESULT_CHARS + 1)
        task = self.valid_task(action="read_file", arguments={"path": "README.md"})
        with self.assertRaisesRegex(mailbox.MailboxError, "file_result_too_large"):
            mailbox.execute_task(workspace, task)


class MailboxStateTests(unittest.TestCase):
    def test_state_file_round_trip_and_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state" / "mailbox.json"
            state = {"processed_comments": ["123"], "completed_tasks": ["probe-001"]}
            mailbox._save_state(path, state)
            self.assertEqual(mailbox._load_state(path), state)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_allowlisted_task_is_processed_once(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            comment = {
                "id": 123,
                "user": {"login": "xiiitore"},
                "body": task_body({"version": 1, "task_id": "probe-001",
                                   "action": "status", "arguments": {}}),
            }
            with patch.object(mailbox, "fetch_comments", return_value=[comment]), \
                 patch.object(mailbox, "post_comment") as post:
                count = mailbox.run_once(
                    token="not-a-real-token", repo="owner/repo", issue_number=7,
                    allowed_authors={"xiiitore"}, state_path=path,
                    workspace=FakeWorkspace(),
                )
                self.assertEqual(count, 1)
                self.assertEqual(post.call_count, 1)
                self.assertIn('"status":"completed"', post.call_args.args[3])
            with patch.object(mailbox, "fetch_comments", return_value=[comment]), \
                 patch.object(mailbox, "post_comment") as post:
                count = mailbox.run_once(
                    token="not-a-real-token", repo="owner/repo", issue_number=7,
                    allowed_authors={"xiiitore"}, state_path=path,
                    workspace=FakeWorkspace(),
                )
                self.assertEqual(count, 0)
                post.assert_not_called()

    def test_unexpected_workspace_error_does_not_leak_exception_text(self):
        class LeakyWorkspace(FakeWorkspace):
            def status(self):
                raise RuntimeError("SECRET_LOCAL_OUTPUT /private/path/token-value")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            comment = {
                "id": 125,
                "user": {"login": "xiiitore"},
                "body": task_body({"version": 1, "task_id": "probe-error-001",
                                   "action": "status", "arguments": {}}),
            }
            with patch.object(mailbox, "fetch_comments", return_value=[comment]), \
                 patch.object(mailbox, "post_comment") as post:
                count = mailbox.run_once(
                    token="not-a-real-token", repo="owner/repo", issue_number=7,
                    allowed_authors={"xiiitore"}, state_path=path,
                    workspace=LeakyWorkspace(),
                )
            self.assertEqual(count, 1)
            body = post.call_args.args[3]
            self.assertIn('"error":"RuntimeError"', body)
            self.assertNotIn("SECRET_LOCAL_OUTPUT", body)
            self.assertNotIn("/private/path", body)
            self.assertNotIn("token-value", body)
    def test_non_allowlisted_author_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            comment = {
                "id": 124, "user": {"login": "untrusted"},
                "body": task_body({"version": 1, "task_id": "probe-002",
                                   "action": "status", "arguments": {}}),
            }
            with patch.object(mailbox, "fetch_comments", return_value=[comment]), \
                 patch.object(mailbox, "post_comment") as post:
                count = mailbox.run_once(
                    token="not-a-real-token", repo="owner/repo", issue_number=7,
                    allowed_authors={"xiiitore"}, state_path=path,
                    workspace=FakeWorkspace(),
                )
            self.assertEqual(count, 0)
            post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
