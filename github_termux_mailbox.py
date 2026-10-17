"""Outbound-only GitHub issue mailbox for a read-only Termux workspace agent.

The worker polls one configured GitHub issue and accepts only strict JSON task
comments authored by explicitly allowlisted GitHub accounts. It never executes
shell commands or arbitrary code.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from authoritylab.termux_workspace_tools import BoundedWorkspace

API_ROOT = "https://api.github.com"
TASK_MARKER = "<!-- authoritylab-task:v1 -->"
RESULT_MARKER = "<!-- authoritylab-result:v1 -->"
MAX_HTTP_BYTES = 1_000_000
MAX_RESULT_CHARS = 20_000
MAX_LIST_ITEMS = 100
MAX_WRITE_BYTES = 30_000
MAX_COMMENT_PAGES = 20
ALLOWED_ACTIONS = frozenset({"status", "list_files", "read_file", "git_status", "git_diff", "run_tests", "write_file"})
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")
SENSITIVE_PATH_COMPONENT_RE = re.compile(
    r"(?i)(?:^|[._-])(?:secret|secrets|credential|credentials|token|tokens|"
    r"password|passwd|private[_-]?key|id_rsa|id_ed25519)(?:$|[._-])"
)
SENSITIVE_PATH_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"})
SENSITIVE_PATH_NAMES = frozenset({
    ".netrc", ".npmrc", ".pypirc", ".git-credentials",
    "credentials", "credentials.json", "secrets.json",
})


def _is_sensitive_workspace_path(path: str) -> bool:
    """Conservatively deny common credential-bearing paths from mailbox I/O."""
    normalized = path.replace("\\\\", "/")
    for component in normalized.split("/"):
        name = component.casefold()
        if name.startswith(".env") or name in SENSITIVE_PATH_NAMES:
            return True
        if any(name.endswith(suffix) for suffix in SENSITIVE_PATH_SUFFIXES):
            return True
        if SENSITIVE_PATH_COMPONENT_RE.search(name):
            return True
    return False


class MailboxError(Exception):
    """Safe-to-report mailbox failure."""


def parse_task(body: str) -> dict[str, Any]:
    """Parse an exact versioned task envelope; free-form instructions are ignored."""
    if not isinstance(body, str) or not body.startswith(TASK_MARKER + "\n"):
        raise MailboxError("task_marker_missing")
    raw = body[len(TASK_MARKER) + 1 :].strip()
    try:
        task = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        raise MailboxError("task_json_invalid") from None
    if not isinstance(task, dict) or set(task) != {"version", "task_id", "action", "arguments"}:
        raise MailboxError("task_schema_invalid")
    if type(task["version"]) is not int or task["version"] != 1:
        raise MailboxError("task_version_unsupported")
    if not isinstance(task["task_id"], str) or not TASK_ID_RE.fullmatch(task["task_id"]):
        raise MailboxError("task_id_invalid")
    if not isinstance(task["action"], str) or task["action"] not in ALLOWED_ACTIONS:
        raise MailboxError("action_not_allowed")
    if not isinstance(task["arguments"], dict):
        raise MailboxError("arguments_invalid")
    if task["action"] in {"status", "list_files", "git_status", "git_diff", "run_tests"} and task["arguments"]:
        raise MailboxError("unexpected_arguments")
    if task["action"] == "read_file":
        if set(task["arguments"]) != {"path"} or not isinstance(task["arguments"]["path"], str):
            raise MailboxError("read_file_arguments_invalid")
        path = task["arguments"]["path"]
        normalized = path.replace("\\", "/")
        if (not path or len(path) > 1024 or "\x00" in path
                or path.startswith("/") or any(part == ".." for part in normalized.split("/"))):
            raise MailboxError("read_file_path_invalid")
        if _is_sensitive_workspace_path(path):
            raise MailboxError("read_file_sensitive_path_denied")
    if task["action"] == "write_file":
        if set(task["arguments"]) != {"path", "content"}:
            raise MailboxError("write_file_arguments_invalid")
        path = task["arguments"]["path"]
        content = task["arguments"]["content"]
        if not isinstance(path, str) or not isinstance(content, str):
            raise MailboxError("write_file_arguments_invalid")
        normalized = path.replace("\\", "/")
        if (not path or len(path) > 1024 or "\x00" in path
                or path.startswith("/") or any(part == ".." for part in normalized.split("/"))):
            raise MailboxError("write_file_path_invalid")
        if _is_sensitive_workspace_path(path):
            raise MailboxError("write_file_sensitive_path_denied")
        try:
            content_bytes = content.encode("utf-8")
        except UnicodeEncodeError:
            raise MailboxError("write_file_content_invalid") from None
        if len(content_bytes) > MAX_WRITE_BYTES:
            raise MailboxError("write_file_content_too_large")
    return task


def _json_request(
    token: str,
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AuthorityLab-Termux-Mailbox/0.1",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(data) > 64 * 1024:
            raise MailboxError("request_too_large")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read(MAX_HTTP_BYTES + 1)
            if len(raw) > MAX_HTTP_BYTES:
                raise MailboxError("github_response_too_large")
            if response.status not in {200, 201}:
                raise MailboxError("github_http_error")
    except urllib.error.HTTPError as exc:
        # Never echo response bodies or headers; they may contain sensitive data.
        if exc.code in {401, 403, 404, 422}:
            raise MailboxError("github_http_" + str(exc.code)) from None
        raise MailboxError("github_http_error") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise MailboxError("github_unavailable") from None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise MailboxError("github_response_invalid") from None


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"processed_comments": [], "completed_tasks": []}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise MailboxError("state_file_unreadable") from None
    if (not isinstance(state, dict)
            or set(state) != {"processed_comments", "completed_tasks"}
            or not isinstance(state["processed_comments"], list)
            or not isinstance(state["completed_tasks"], list)
            or any(not isinstance(x, (int, str)) for x in state["processed_comments"])
            or any(not isinstance(x, str) for x in state["completed_tasks"])):
        raise MailboxError("state_file_invalid")
    return state


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    fd, temporary = tempfile.mkstemp(prefix=".mailbox-state-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _issue_url(repo: str, issue_number: int, suffix: str) -> str:
    parts = repo.split("/")
    if (len(parts) != 2 or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", p) for p in parts)
            or type(issue_number) is not int or issue_number < 1):
        raise MailboxError("repository_or_issue_invalid")
    return f"{API_ROOT}/repos/{parts[0]}/{parts[1]}/issues/{issue_number}/{suffix}"


def fetch_comments(token: str, repo: str, issue_number: int) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    for page in range(1, MAX_COMMENT_PAGES + 1):
        query = urllib.parse.urlencode({"per_page": 100, "page": page})
        result = _json_request(token, _issue_url(repo, issue_number, "comments") + "?" + query)
        if not isinstance(result, list):
            raise MailboxError("github_comments_invalid")
        comments.extend(item for item in result if isinstance(item, dict))
        if len(result) < 100:
            return comments
    raise MailboxError("github_comment_history_limit_exceeded")


def post_comment(token: str, repo: str, issue_number: int, body: str) -> None:
    if not isinstance(body, str) or len(body) > 60_000:
        raise MailboxError("result_comment_too_large")
    _json_request(token, _issue_url(repo, issue_number, "comments"), method="POST", payload={"body": body})


def execute_task(workspace: BoundedWorkspace, task: dict[str, Any]) -> dict[str, Any]:
    action = task["action"]
    args = task["arguments"]
    if action == "status":
        status = workspace.status()
        return {"ready": status.get("ready") is True, "max_file_bytes": status.get("max_file_bytes")}
    if action == "list_files":
        return {"files": workspace.list_files(".")[:MAX_LIST_ITEMS]}
    if action == "read_file":
        value = workspace.read_file(args["path"])
        if not isinstance(value, str):
            raise MailboxError("file_result_invalid")
        if len(value) > MAX_RESULT_CHARS:
            raise MailboxError("file_result_too_large")
        return {"path": args["path"], "content": value}
    if action == "git_status":
        value = workspace.git_status()
        if not isinstance(value, str):
            raise MailboxError("git_status_result_invalid")
        return {"status": value[-MAX_RESULT_CHARS:]}
    if action == "git_diff":
        value = workspace.git_diff()
        if not isinstance(value, str):
            raise MailboxError("git_diff_result_invalid")
        return {"diff": value[-MAX_RESULT_CHARS:]}
    if action == "run_tests":
        value = workspace.run_tests()
        if not isinstance(value, dict):
            raise MailboxError("test_result_invalid")
        output = value.get("output", "")
        if not isinstance(output, str):
            output = ""
        return {"command": "python -m unittest discover -v", "output": output[-MAX_RESULT_CHARS:]}
    if action == "write_file":
        value = workspace.write_file(args["path"], args["content"])
        if not isinstance(value, dict):
            raise MailboxError("write_file_result_invalid")
        return {"path": value.get("path"), "bytes_written": value.get("bytes_written")}
    raise MailboxError("action_not_allowed")


def result_body(task_id: str, comment_id: int | str, *, result: Any = None, error: str | None = None) -> str:
    payload: dict[str, Any] = {"version": 1, "task_id": task_id, "source_comment_id": comment_id}
    if error is not None:
        payload.update({"status": "rejected_or_failed", "error": error})
    else:
        payload.update({"status": "completed", "result": result})
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(encoded) > MAX_RESULT_CHARS:
        encoded = json.dumps({
            "version": 1, "task_id": task_id, "source_comment_id": comment_id,
            "status": "rejected_or_failed", "error": "result_too_large",
        }, separators=(",", ":"))
    return RESULT_MARKER + "\n" + encoded


def run_once(
    *,
    token: str,
    repo: str,
    issue_number: int,
    allowed_authors: set[str],
    state_path: Path,
    workspace: BoundedWorkspace,
    api: Callable[..., Any] = _json_request,
) -> int:
    """Process newly observed allowlisted task comments; returns completed/rejected count."""
    state = _load_state(state_path)
    processed = {str(x) for x in state["processed_comments"]}
    completed = set(state["completed_tasks"])
    comments = fetch_comments(token, repo, issue_number) if api is _json_request else api(
        token, _issue_url(repo, issue_number, "comments") + "?per_page=100&page=1"
    )
    if not isinstance(comments, list):
        raise MailboxError("github_comments_invalid")
    count = 0
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        comment_id = comment.get("id")
        if comment_id is None or str(comment_id) in processed:
            continue
        user = comment.get("user")
        author = user.get("login") if isinstance(user, dict) else None
        body = comment.get("body")
        if author not in allowed_authors or not isinstance(body, str) or not body.startswith(TASK_MARKER):
            continue
        task_id = "unknown"
        try:
            task = parse_task(body)
            task_id = task["task_id"]
            if task_id in completed:
                outcome = result_body(task_id, comment_id, error="duplicate_task_id")
            else:
                try:
                    value = execute_task(workspace, task)
                    outcome = result_body(task_id, comment_id, result=value)
                except Exception as exc:
                    safe_error = str(exc) if isinstance(exc, MailboxError) else type(exc).__name__
                    outcome = result_body(task_id, comment_id, error=str(safe_error)[:120])
        except MailboxError as exc:
            outcome = result_body(task_id, comment_id, error=str(exc)[:120])
        post_comment(token, repo, issue_number, outcome)
        processed.add(str(comment_id))
        if task_id != "unknown" and "duplicate_task_id" not in outcome and '"status":"completed"' in outcome:
            completed.add(task_id)
        state = {
            "processed_comments": sorted(processed, key=str)[-5000:],
            "completed_tasks": sorted(completed)[-5000:],
        }
        _save_state(state_path, state)
        count += 1
    return count


def main() -> None:
    token = os.environ.get("AUTHORITYLAB_GITHUB_TOKEN", "")
    repo = os.environ.get("AUTHORITYLAB_GITHUB_REPO", "")
    issue_raw = os.environ.get("AUTHORITYLAB_GITHUB_ISSUE", "")
    root = os.environ.get("AUTHORITYLAB_ROOT", "")
    allowed_raw = os.environ.get("AUTHORITYLAB_GITHUB_ALLOWED_AUTHORS", "")
    state_raw = os.environ.get("AUTHORITYLAB_GITHUB_STATE", "~/.local/state/authoritylab/mailbox.json")
    if len(token) < 20:
        raise SystemExit("Set AUTHORITYLAB_GITHUB_TOKEN to a least-privilege GitHub token.")
    if not repo or not issue_raw.isdigit() or not root:
        raise SystemExit("Set AUTHORITYLAB_GITHUB_REPO, AUTHORITYLAB_GITHUB_ISSUE and AUTHORITYLAB_ROOT.")
    authors = {name.strip() for name in allowed_raw.split(",") if name.strip()}
    if not authors:
        raise SystemExit("Set AUTHORITYLAB_GITHUB_ALLOWED_AUTHORS to explicit GitHub usernames.")
    issue_number = int(issue_raw)
    workspace = BoundedWorkspace(Path(root).expanduser())
    state_path = Path(state_raw).expanduser()
    print("AuthorityLab GitHub mailbox started; actions: status, list_files, read_file, git_status, git_diff, run_tests, write_file.")
    while True:
        try:
            processed = run_once(
                token=token, repo=repo, issue_number=issue_number,
                allowed_authors=authors, state_path=state_path, workspace=workspace,
            )
            if processed:
                print(f"mailbox: handled {processed} task comment(s)")
            time.sleep(20)
        except MailboxError as exc:
            print(f"mailbox: {str(exc)[:120]}; retrying in 10 seconds")
            time.sleep(10)
        except KeyboardInterrupt:
            return
        except Exception as exc:
            print(f"mailbox: unexpected {type(exc).__name__}; retrying in 10 seconds")
            time.sleep(10)


if __name__ == "__main__":
    main()
