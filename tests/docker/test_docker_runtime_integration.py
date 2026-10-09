"""Real Docker integration tests; skipped unless CI supplies a digest-pinned image."""
from __future__ import annotations

import os
import socket
import tempfile
import time
import unittest
from unittest.mock import patch

from authoritylab import Task, ToolResult
from authoritylab.execution import DockerSandboxRunner, ExecutionBlockedError


def echo_handler(task):
    return ToolResult(ok=True, output={"task_id": task.task_id, "kind": task.kind})


def inspect_container_handler(task):
    non_root = hasattr(os, "geteuid") and os.geteuid() != 0
    write_blocked = False
    try:
        with open("/opt/authoritylab-test/write-probe", "w", encoding="utf-8") as stream:
            stream.write("must not persist")
    except OSError:
        write_blocked = True

    network_blocked = False
    try:
        with socket.create_connection(("1.1.1.1", 53), timeout=0.5):
            pass
    except OSError:
        network_blocked = True

    return ToolResult(
        ok=True,
        output={
            "non_root": non_root,
            "root_filesystem_read_only": write_blocked,
            "network_disabled": network_blocked,
            "host_secret_not_inherited": "AUTHORITYLAB_HOST_SECRET" not in os.environ,
            "host_file_not_mounted": not os.path.exists(task.payload.get("host_path", "/definitely-not-present")),
        },
    )


def sleep_handler(task):
    time.sleep(30)
    return ToolResult(ok=True, output={"unexpected": "completed"})


_IMAGE = os.environ.get("AUTHORITYLAB_DOCKER_TEST_IMAGE")
_SKIP = not _IMAGE


@unittest.skipUnless(_IMAGE, "requires AUTHORITYLAB_DOCKER_TEST_IMAGE and a working Docker daemon")
class DockerRuntimeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.runner = DockerSandboxRunner(
            _IMAGE,
            timeout_seconds=8,
            memory_limit_bytes=536_870_912,
            max_output_bytes=65_536,
        )

    def test_real_container_executes_handler_and_preserves_json_result(self):
        result = self.runner.run(echo_handler, Task("integration-1", "echo"))
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.output, {"task_id": "integration-1", "kind": "echo"})

    def test_real_container_enforces_non_root_read_only_no_network_and_no_host_access(self):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as host_file:
            host_file.write("host-only-secret")
            host_file.flush()
            with patch.dict(os.environ, {"AUTHORITYLAB_HOST_SECRET": "must-not-cross-boundary"}):
                result = self.runner.run(
                    inspect_container_handler,
                    Task("integration-2", "inspect", {"host_path": host_file.name}),
                )
        self.assertTrue(result.ok, result.error)
        self.assertEqual(
            result.output,
            {
                "non_root": True,
                "root_filesystem_read_only": True,
                "network_disabled": True,
                "host_secret_not_inherited": True,
                "host_file_not_mounted": True,
            },
        )

    def test_real_container_timeout_stops_execution(self):
        result = self.runner.run(sleep_handler, Task("integration-3", "sleep"))
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "sandbox handler execution timed out")


if __name__ == "__main__":
    unittest.main()
