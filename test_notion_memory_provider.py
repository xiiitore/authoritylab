import io
import json
import unittest
from http.client import HTTPMessage
from unittest.mock import patch
from urllib.error import HTTPError

from authoritylab.notion_memory_provider import (
    NotionAPIClient,
    NotionAPIError,
    NotionMemoryProvider,
    extract_page_properties,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def paragraph(text):
    return {
        "object": "block", "type": "paragraph", "has_children": False,
        "paragraph": {"rich_text": [{"plain_text": text}]},
    }


def page(page_id, properties, edited="2026-11-01T00:00:00Z"):
    return {
        "object": "page", "id": page_id,
        "last_edited_time": edited, "properties": properties,
    }


class NotionAPIClientTests(unittest.TestCase):
    def client(self, responses):
        return NotionAPIClient(
            "secret-test-token", opener=FakeOpener(responses),
            sleeper=lambda delay: None, min_interval=0,
        )

    def test_query_uses_current_data_source_endpoint_and_version(self):
        opener = FakeOpener([FakeResponse({"results": [], "has_more": False})])
        client = NotionAPIClient(
            "secret-test-token", opener=opener, sleeper=lambda delay: None,
            min_interval=0,
        )
        self.assertEqual(client.query_data_source("source-id"), [])
        request = opener.requests[0]
        self.assertEqual(
            request.full_url,
            "https://api.notion.com/v1/data_sources/source-id/query",
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Notion-version"), "2026-03-11")
        self.assertEqual(
            request.get_header("Authorization"), "Bearer secret-test-token"
        )

    def test_query_rejects_non_page_results(self):
        opener = FakeOpener([
            FakeResponse({
                "results": [{"object": "data_source"}], "has_more": False,
            })
        ])
        client = NotionAPIClient(
            "token", opener=opener, sleeper=lambda delay: None, min_interval=0,
        )
        with self.assertRaises(NotionAPIError) as raised:
            client.query_data_source("ds")
        self.assertEqual(raised.exception.code, "invalid_page")

    def test_query_paginates_with_cursor(self):
        opener = FakeOpener([
            FakeResponse({
                "results": [{"object": "page", "id": "one"}],
                "has_more": True, "next_cursor": "next",
            }),
            FakeResponse({
                "results": [{"object": "page", "id": "two"}],
                "has_more": False,
            }),
        ])
        client = NotionAPIClient(
            "token", opener=opener, sleeper=lambda delay: None, min_interval=0,
        )
        results = client.query_data_source("ds", page_size=1)
        self.assertEqual([item["id"] for item in results], ["one", "two"])
        second_body = json.loads(opener.requests[1].data)
        self.assertEqual(second_body["start_cursor"], "next")

    def test_block_children_recurses_into_nested_blocks(self):
        nested = {
            "object": "block", "id": "nested", "type": "toggle",
            "has_children": True,
            "toggle": {"rich_text": [{"plain_text": "Parent"}]},
        }
        opener = FakeOpener([
            FakeResponse({
                "results": [nested, paragraph("Sibling")], "has_more": False,
            }),
            FakeResponse({"results": [paragraph("Child")], "has_more": False}),
        ])
        client = NotionAPIClient(
            "token", opener=opener, sleeper=lambda delay: None, min_interval=0,
        )
        self.assertEqual(
            client.block_children_text("page"), "Parent\nChild\nSibling"
        )

    def test_unauthorized_response_is_sanitized(self):
        headers = HTTPMessage()
        body = io.BytesIO(b'{"code":"unauthorized","message":"secret detail"}')
        error = HTTPError(
            "https://api.notion.com", 401, "Unauthorized", headers, body
        )
        client = self.client([error])
        with self.assertRaises(NotionAPIError) as raised:
            client.query_data_source("ds")
        self.assertEqual(raised.exception.status, 401)
        self.assertEqual(raised.exception.code, "unauthorized")
        self.assertNotIn("secret detail", str(raised.exception))
        self.assertNotIn("secret-test-token", str(raised.exception))

    def test_rate_limit_retries_with_retry_after(self):
        headers = HTTPMessage()
        headers.add_header("Retry-After", "0")
        error = HTTPError(
            "https://api.notion.com", 429, "Rate limited", headers,
            io.BytesIO(b'{"code":"rate_limited"}'),
        )
        opener = FakeOpener([
            error, FakeResponse({"results": [], "has_more": False})
        ])
        client = NotionAPIClient(
            "token", opener=opener, sleeper=lambda delay: None,
            min_interval=0, max_retries=1,
        )
        self.assertEqual(client.query_data_source("ds"), [])
        self.assertEqual(len(opener.requests), 2)

    def test_page_properties_extract_common_types(self):
        result = extract_page_properties({"properties": {
            "Title": {"type": "title", "title": [{"plain_text": "A title"}]},
            "Status": {"type": "status", "status": {"name": "VERIFIED"}},
            "Tags": {
                "type": "multi_select", "multi_select": [{"name": "memory"}]
            },
            "Notes": {
                "type": "rich_text", "rich_text": [{"plain_text": "detail"}]
            },
            "Email": {"type": "email", "email": "private@example.invalid"},
            "Phone": {"type": "phone_number", "phone_number": "+10000000000"},
        }})
        self.assertEqual(result["Title"], "A title")
        self.assertEqual(result["Status"], "VERIFIED")
        self.assertEqual(result["Tags"], ["memory"])
        self.assertEqual(result["Notes"], "detail")
        self.assertNotIn("Email", result)
        self.assertNotIn("Phone", result)


class NotionMemoryProviderTests(unittest.TestCase):
    def build_provider(self, responses, **kwargs):
        opener = FakeOpener(responses)
        client = NotionAPIClient(
            "token", opener=opener, sleeper=lambda delay: None, min_interval=0,
        )
        provider = NotionMemoryProvider(
            client, allowed_subject_id="subject-1",
            data_sources={
                "Memories": "mem-ds", "Memory Archive": "archive-ds"
            },
            pages={"About": "about-page", "Operating Rules": "rules-page"},
            clock=lambda: 1_800_000_000.0, **kwargs,
        )
        return provider, opener

    def test_builds_snapshot_from_memories_archive_and_required_pages(self):
        memory = page("memory-page", {
            "Title": {
                "type": "title", "title": [{"plain_text": "User preference"}]
            },
            "Type": {"type": "select", "select": {"name": "Preference"}},
        })
        archive = page("archive-page", {
            "Content": {
                "type": "title",
                "title": [{"plain_text": "Verified project fact"}],
            },
            "Status": {"type": "select", "select": {"name": "VERIFIED"}},
            "Notes": {
                "type": "rich_text",
                "rich_text": [{"plain_text": "Evidence note"}],
            },
        })
        responses = [
            FakeResponse({"results": [memory], "has_more": False}),
            FakeResponse({
                "results": [paragraph("Preference body")], "has_more": False,
            }),
            FakeResponse({"results": [archive], "has_more": False}),
            FakeResponse({
                "results": [paragraph("Archive body")], "has_more": False,
            }),
            FakeResponse({
                "object": "page", "id": "about-page",
                "last_edited_time": "2026-11-01T00:00:00Z",
            }),
            FakeResponse({
                "results": [paragraph("About context")], "has_more": False,
            }),
            FakeResponse({
                "object": "page", "id": "rules-page",
                "last_edited_time": "2026-11-01T00:00:00Z",
            }),
            FakeResponse({
                "results": [paragraph("Mandatory operating rules")],
                "has_more": False,
            }),
        ]
        provider, opener = self.build_provider(responses)
        snapshot = provider.retrieve("subject-1")
        self.assertIn("User preference", snapshot.content)
        self.assertIn("Preference body", snapshot.content)
        self.assertIn("Verified project fact", snapshot.content)
        self.assertIn("VERIFIED", snapshot.content)
        self.assertIn("About context", snapshot.content)
        self.assertIn("Mandatory operating rules", snapshot.content)
        self.assertIn("memory-page", snapshot.source_ids)
        self.assertIn("archive-page", snapshot.source_ids)
        self.assertEqual(len(snapshot.version), 64)
        self.assertEqual(len(opener.requests), 8)

    def test_wrong_subject_is_rejected_before_network(self):
        provider, opener = self.build_provider([])
        with self.assertRaises(PermissionError):
            provider.retrieve("other-subject")
        self.assertEqual(opener.requests, [])

    def test_context_limit_fails_closed(self):
        memory = page("memory-page", {
            "Title": {
                "type": "title", "title": [{"plain_text": "Preference"}]
            },
        })
        responses = [
            FakeResponse({"results": [memory], "has_more": False}),
            FakeResponse({
                "results": [paragraph("x" * 200)], "has_more": False,
            }),
            FakeResponse({"results": [], "has_more": False}),
            FakeResponse({
                "object": "page", "id": "about-page", "last_edited_time": "v1"
            }),
            FakeResponse({"results": [paragraph("About")], "has_more": False}),
            FakeResponse({
                "object": "page", "id": "rules-page", "last_edited_time": "v1"
            }),
            FakeResponse({"results": [paragraph("Rules")], "has_more": False}),
        ]
        provider, _ = self.build_provider(responses, max_context_bytes=100)
        with self.assertRaises(NotionAPIError) as raised:
            provider.retrieve("subject-1")
        self.assertEqual(raised.exception.code, "context_limit")

    def test_from_env_requires_server_side_credentials(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(NotionAPIError) as raised:
                NotionMemoryProvider.from_env()
        self.assertEqual(raised.exception.code, "configuration_missing")


if __name__ == "__main__":
    unittest.main()
