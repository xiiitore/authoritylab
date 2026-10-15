# Durable task queue and checkpoint contract

## Purpose

The SQLite-backed queue in \`task_queue.py\` gives a background worker durable task records, exclusive atomic claims, expiring leases, retries, checkpoints, and terminal outcomes. It is a persistence primitive for continuity across process restarts; it is not an LLM, planner, cloud supervisor, or sandbox.

## Minimal lifecycle

1. Enqueue a JSON-compatible task with a stable task kind and payload.
2. A worker claims one available task; the queue atomically records the worker and lease expiry.
3. The worker periodically renews the lease and saves small, JSON-compatible checkpoints after verified milestones.
4. On successful completion, the worker commits a result. On failure, it records a bounded error and either schedules a retry or marks the task failed.
5. If a process dies, another worker may reclaim the task after its lease expires. The next attempt reads the last saved checkpoint using \`get(task_id)\`.

A stale worker cannot checkpoint, heartbeat, complete, or fail a task after its lease expires or another worker claims it. Task handlers should still be idempotent: a process can die after performing an external side effect but before recording completion. The queue does not provide exactly-once execution for external actions.

## State and storage

States are \`pending\`, \`running\`, \`succeeded\`, and \`failed\`. Attempts are bounded by \`max_attempts\`. SQLite uses WAL, full synchronous commits, a write transaction for claims, and a busy timeout. The database must be on a local filesystem with reliable SQLite locking semantics; unverified network filesystems are unsupported.

Example:

\`\`\`python
from authoritylab.task_queue import DurableTaskQueue

queue = DurableTaskQueue("/var/lib/authoritylab/tasks.sqlite3")
task = queue.enqueue("repo-check", {"repository": "xiiitore/authoritylab"})
claimed = queue.claim("worker-1", lease_seconds=120)
if claimed is not None:
    queue.checkpoint(claimed.task_id, "worker-1", {"stage": "inspection"})
    queue.complete(claimed.task_id, "worker-1", {"status": "observed"})
\`\`\`

The example is illustrative; it does not configure a running service or execute repository operations. In real worker code, use the claimed task's ID, handle exceptions, heartbeat during long operations, and validate outputs before completion.

## Deployment boundary

This change does not deploy a cloud worker, supply model credentials, create an autonomous planning loop, or prove 24/7 uptime. A production worker still needs a supervised runtime, an explicit task/handler allow-list, secret management, logs/metrics, backups, recovery drills, resource budgets, and deployment-specific security review. Use a transactional server database instead of a local SQLite file for multi-host workers. Do not place credentials in task payloads or checkpoints.

## Verification

Unit tests cover checkpoint persistence after reopening the database, expired-lease recovery, exclusive claims, stale-worker rejection, bounded retries, terminal failures, and malformed inputs. These tests verify queue semantics only; they do not prove cloud deployment or end-to-end autonomous agent behavior.
