"""Read-only Notion adapter for the user's Memory Gate context sources."""
from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .memory_gate import MemorySnapshot

NOTION_VERSION = "2026-03-11"
DEFAULT_DATA_SOURCES = {
    "Memories": "4080fddd-05e9-81c1-bf7e-000b2c8bb6e3",
    "Memory Archive": "6bb60bcc-5cad-47c1-a156-8b4a33deadb5",
    "Memory Projects": "ba636895-0457-4106-ac33-edbb991b5e54",
    "Memory Relations": "1fd47b72-0162-4e78-96f9-7af31163e3a0",
    "Memory Sources": "db1e7c07-fa66-4f66-ace6-899d3a93f016",
}
DEFAULT_PAGES = {
    "About": "4080fddd-05e9-818a-b1b6-e356ffef2f46",
    "Operating Rules": "4020fddd-05e9-818a-9776-e080fb09a993",
}


class NotionAPIError(RuntimeError):
    def __init__(self, status: int | None, code: str, message: str):
        detail = f"Notion API {status or 'network'}: {code}: {message}"
        super().__init__(detail)
        self.status = status
        self.code = code


def _plain_text(items: object) -> str:
    if not isinstance(items, list):
        return ""
    parts = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = item.get("plain_text")
        if not isinstance(text, str):
            text_obj = item.get("text")
            text = (
                text_obj.get("content", "")
                if isinstance(text_obj, dict) else ""
            )
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def extract_page_properties(page: Mapping[str, Any]) -> dict[str, Any]:
    """Extract Notion property values without leaking user objects."""
    properties = page.get("properties")
    if not isinstance(properties, dict):
        raise NotionAPIError(None, "invalid_page", "page properties missing")
    extracted: dict[str, Any] = {}
    for name, prop in properties.items():
        if not isinstance(name, str) or not isinstance(prop, dict):
            continue
        kind = prop.get("type")
        value = prop.get(kind) if isinstance(kind, str) else None
        if kind in ("title", "rich_text"):
            result = _plain_text(value)
        elif kind in ("select", "status"):
            result = value.get("name") if isinstance(value, dict) else None
        elif kind == "multi_select":
            result = (
                [x.get("name") for x in value if isinstance(x, dict)]
                if isinstance(value, list) else []
            )
        elif kind in ("number", "checkbox"):
            result = value
        elif kind == "date":
            result = value.get("start") if isinstance(value, dict) else None
        elif kind in ("created_time", "last_edited_time"):
            result = value
        elif kind == "unique_id" and isinstance(value, dict):
            result = f"{value.get('prefix', '')}{value.get('number', '')}"
        elif kind == "relation" and isinstance(value, list):
            result = [x.get("id") for x in value if isinstance(x, dict)]
        else:
            continue
        if result not in (None, "", []):
            extracted[name] = result
    return extracted


def _block_text(block: Mapping[str, Any]) -> str:
    kind = block.get("type")
    if not isinstance(kind, str):
        return ""
    value = block.get(kind)
    if not isinstance(value, dict):
        return ""
    if kind == "table_row":
        cells = value.get("cells", [])
        return (
            " | ".join(_plain_text(cell) for cell in cells)
            if isinstance(cells, list) else ""
        )
    if kind in ("child_page", "child_database"):
        title = value.get("title")
        return title if isinstance(title, str) else ""
    if kind == "to_do":
        text = _plain_text(value.get("rich_text"))
        return f"[{'x' if value.get('checked') else ' '}] {text}"
    if kind == "equation":
        expression = value.get("expression")
        return expression if isinstance(expression, str) else ""
    text = _plain_text(value.get("rich_text"))
    if not text:
        text = _plain_text(value.get("title"))
    if kind.startswith("heading_") and text:
        return f"{('#' * int(kind[-1]))} {text}"
    if kind == "code" and text:
        language = value.get("language", "text")
        return f"[{language}] {text}"
    return text


class NotionAPIClient:
    """Small read-only Notion REST client with pagination and rate limiting."""

    def __init__(
        self,
        token: str,
        *,
        version: str = NOTION_VERSION,
        timeout: float = 15,
        opener: Callable[..., Any] = urlopen,
        sleeper: Callable[[float], Any] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        min_interval: float = 0.34,
        max_retries: int = 2,
    ) -> None:
        if not isinstance(token, str) or not token.strip():
            raise ValueError("Notion integration token is required")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("Notion API version is required")
        if type(timeout) not in (int, float) or timeout <= 0:
            raise ValueError("timeout must be positive")
        if type(min_interval) not in (int, float) or min_interval < 0:
            raise ValueError("min_interval must be non-negative")
        if type(max_retries) is not int or max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        self._token = token
        self.version = version
        self.timeout = float(timeout)
        self.opener = opener
        self.sleeper = sleeper
        self.monotonic = monotonic
        self.min_interval = float(min_interval)
        self.max_retries = max_retries
        self._last_request = 0.0
        self._rate_lock = threading.Lock()

    def _throttle(self) -> None:
        with self._rate_lock:
            elapsed = self.monotonic() - self._last_request
            delay = self.min_interval - elapsed
            if delay > 0:
                self.sleeper(delay)
            self._last_request = self.monotonic()

    def _request(
        self, method: str, path: str, body: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(
            f"https://api.notion.com/v1{path}", data=data, method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Notion-Version": self.version,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                with self.opener(request, timeout=self.timeout) as response:
                    status = getattr(response, "status", None)
                    if status is None:
                        status = response.getcode() or 200
                    raw = response.read()
            except HTTPError as error:
                status = error.code
                raw = error.read()
                if status == 429 and attempt < self.max_retries:
                    try:
                        headers = error.headers or {}
                        delay = float(headers.get("Retry-After", "1"))
                    except (TypeError, ValueError):
                        delay = 1.0
                    self.sleeper(min(max(delay, 0.1), 5.0))
                    continue
                raise self._api_error(status, raw) from None
            except (URLError, TimeoutError, OSError) as error:
                raise NotionAPIError(
                    None, "network_error", type(error).__name__
                ) from None
            if status >= 400:
                raise self._api_error(status, raw)
            try:
                result = json.loads(raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                raise NotionAPIError(
                    status, "invalid_json", "response was not JSON"
                ) from None
            if not isinstance(result, dict):
                raise NotionAPIError(
                    status, "invalid_response", "expected JSON object"
                )
            return result
        raise NotionAPIError(429, "rate_limited", "retry limit reached")

    @staticmethod
    def _api_error(status: int, raw: bytes) -> NotionAPIError:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            payload = {}
        code = (
            payload.get("code", "http_error")
            if isinstance(payload, dict) else "http_error"
        )
        return NotionAPIError(status, str(code), "request failed")

    def retrieve_page(self, page_id: str) -> dict[str, Any]:
        if not isinstance(page_id, str) or not page_id.strip():
            raise ValueError("page_id is required")
        result = self._request("GET", f"/pages/{quote(page_id, safe='')}")
        if result.get("object") != "page":
            raise NotionAPIError(None, "invalid_page", "expected page object")
        return result

    def query_data_source(
        self, data_source_id: str, *, page_size: int = 100,
        max_pages: int = 20, max_results: int = 1000,
    ) -> list[dict[str, Any]]:
        if not isinstance(data_source_id, str) or not data_source_id.strip():
            raise ValueError("data_source_id is required")
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        if type(max_pages) is not int or max_pages < 1:
            raise ValueError("max_pages must be positive")
        if type(max_results) is not int or max_results < 1:
            raise ValueError("max_results must be positive")
        pages: list[dict[str, Any]] = []
        cursor = None
        for _ in range(max_pages):
            body: dict[str, Any] = {"page_size": page_size}
            if cursor:
                body["start_cursor"] = cursor
            path = f"/data_sources/{quote(data_source_id, safe='')}/query"
            result = self._request("POST", path, body)
            batch = result.get("results")
            if not isinstance(batch, list):
                raise NotionAPIError(
                    None, "invalid_response", "query results missing"
                )
            if any(
                not isinstance(item, dict) or item.get("object") != "page"
                for item in batch
            ):
                raise NotionAPIError(
                    None, "invalid_page",
                    "data source returned a non-page item",
                )
            pages.extend(batch)
            if len(pages) > max_results:
                raise NotionAPIError(
                    None, "result_limit", "too many memory pages"
                )
            if not result.get("has_more"):
                return pages
            cursor = result.get("next_cursor")
            if not isinstance(cursor, str) or not cursor:
                raise NotionAPIError(
                    None, "pagination_error", "next_cursor missing"
                )
        raise NotionAPIError(None, "pagination_limit", "too many query pages")

    def block_children_text(
        self, block_id: str, *, max_depth: int = 8, max_blocks: int = 2000
    ) -> str:
        if not isinstance(block_id, str) or not block_id.strip():
            raise ValueError("block_id is required")
        if type(max_depth) is not int or max_depth < 0:
            raise ValueError("max_depth must be non-negative")
        if type(max_blocks) is not int or max_blocks < 1:
            raise ValueError("max_blocks must be positive")
        count = [0]

        def read_children(parent_id: str, depth: int) -> list[str]:
            if depth > max_depth:
                raise NotionAPIError(
                    None, "depth_limit", "block nesting too deep"
                )
            cursor = None
            lines: list[str] = []
            while True:
                query = {"page_size": 100}
                if cursor:
                    query["start_cursor"] = cursor
                path = (
                    f"/blocks/{quote(parent_id, safe='')}/children?"
                    f"{urlencode(query)}"
                )
                result = self._request("GET", path)
                blocks = result.get("results")
                if not isinstance(blocks, list):
                    raise NotionAPIError(
                        None, "invalid_response", "block results missing"
                    )
                for block in blocks:
                    if not isinstance(block, dict):
                        continue
                    count[0] += 1
                    if count[0] > max_blocks:
                        raise NotionAPIError(
                            None, "block_limit", "too many page blocks"
                        )
                    text = _block_text(block)
                    if text:
                        lines.append(text)
                    if block.get("has_children"):
                        child_id = block.get("id")
                        if not isinstance(child_id, str) or not child_id:
                            raise NotionAPIError(
                                None, "invalid_block", "child block id missing"
                            )
                        lines.extend(read_children(child_id, depth + 1))
                if not result.get("has_more"):
                    return lines
                cursor = result.get("next_cursor")
                if not isinstance(cursor, str) or not cursor:
                    raise NotionAPIError(
                        None, "pagination_error", "block cursor missing"
                    )

        return "\n".join(read_children(block_id, 0))


class NotionMemoryProvider:
    """Build a bounded, provenance-carrying Notion memory snapshot."""

    def __init__(
        self,
        client: NotionAPIClient,
        *,
        allowed_subject_id: str,
        data_sources: Mapping[str, str] = DEFAULT_DATA_SOURCES,
        pages: Mapping[str, str] = DEFAULT_PAGES,
        max_context_bytes: int = 32_768,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if (
            not isinstance(allowed_subject_id, str)
            or not allowed_subject_id.strip()
        ):
            raise ValueError("allowed_subject_id is required")
        if not isinstance(data_sources, Mapping) or not data_sources:
            raise ValueError("data_sources must be a non-empty mapping")
        if not isinstance(pages, Mapping) or not pages:
            raise ValueError("pages must be a non-empty mapping")
        if type(max_context_bytes) is not int or max_context_bytes < 1:
            raise ValueError("max_context_bytes must be positive")
        if not callable(clock):
            raise ValueError("clock must be callable")
        self.client = client
        self.allowed_subject_id = allowed_subject_id
        self.data_sources = dict(data_sources)
        self.pages = dict(pages)
        self.max_context_bytes = max_context_bytes
        self.clock = clock

    @classmethod
    def from_env(
        cls, *, max_context_bytes: int = 32_768
    ) -> "NotionMemoryProvider":
        token = os.environ.get("NOTION_API_KEY")
        subject_id = os.environ.get("MEMORY_GATE_SUBJECT_ID")
        if not token or not subject_id:
            raise NotionAPIError(
                None, "configuration_missing",
                "NOTION_API_KEY and MEMORY_GATE_SUBJECT_ID are required",
            )
        return cls(
            NotionAPIClient(token), allowed_subject_id=subject_id,
            max_context_bytes=max_context_bytes,
        )

    def retrieve(self, subject_id: str) -> MemorySnapshot:
        if subject_id != self.allowed_subject_id:
            raise PermissionError(
                "memory scope does not match authenticated subject"
            )
        parts: list[str] = []
        source_ids: list[str] = []
        version_material: list[tuple[str, str]] = []

        for source_name, data_source_id in self.data_sources.items():
            pages = self.client.query_data_source(data_source_id)
            source_ids.append(data_source_id)
            parts.append(f"## {source_name}")
            for page in pages:
                page_id = page.get("id")
                if not isinstance(page_id, str) or not page_id:
                    raise NotionAPIError(
                        None, "invalid_page", "page id missing"
                    )
                source_ids.append(page_id)
                properties = extract_page_properties(page)
                title = next(
                    (str(value) for key, value in properties.items()
                     if key in ("Title", "Content", "Project", "Relation")),
                    "Untitled memory",
                )
                parts.append(f"### {title}")
                for key, value in properties.items():
                    if key not in ("Title", "Content", "Project", "Relation"):
                        parts.append(f"{key}: {value}")
                if source_name in (
                    "Memories", "Memory Archive", "Memory Projects"
                ):
                    body = self.client.block_children_text(page_id)
                    if body:
                        parts.append(body)
                edited = page.get("last_edited_time", "")
                version_material.append((page_id, str(edited)))

        for page_name, page_id in self.pages.items():
            page = self.client.retrieve_page(page_id)
            source_ids.append(page_id)
            version_material.append(
                (page_id, str(page.get("last_edited_time", "")))
            )
            parts.append(f"## {page_name}")
            body = self.client.block_children_text(page_id)
            if not body:
                raise NotionAPIError(
                    None, "empty_page", f"{page_name} page is empty"
                )
            parts.append(body)

        content = "\n\n".join(parts)
        if len(content.encode("utf-8")) > self.max_context_bytes:
            raise NotionAPIError(
                None, "context_limit",
                "memory context exceeds configured limit",
            )
        unique_sources = tuple(dict.fromkeys(source_ids))
        version_payload = json.dumps(
            sorted(version_material), separators=(",", ":"), ensure_ascii=False
        )
        version = hashlib.sha256(version_payload.encode("utf-8")).hexdigest()
        retrieved_at = self.clock()
        if (
            type(retrieved_at) not in (int, float)
            or not math.isfinite(retrieved_at)
        ):
            raise NotionAPIError(
                None, "clock_unavailable", "invalid retrieval timestamp"
            )
        return MemorySnapshot(
            subject_id=subject_id,
            source_ids=unique_sources,
            content=content,
            retrieved_at=float(retrieved_at),
            version=version,
        )
