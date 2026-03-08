"""Tests for the OpenRouter streaming provider."""

import json
import unittest
from unittest.mock import MagicMock, patch

from falgen.providers.openrouter import OpenRouterProvider, _dump_error


class TestDumpError(unittest.TestCase):
    @patch("falgen.providers.openrouter.os.makedirs")
    def test_truncates_long_content(self, mock_makedirs):
        from unittest.mock import mock_open
        long_content = "x" * 1000

        m = mock_open()
        with patch("builtins.open", m):
            _dump_error("error body", {
                "model": "test",
                "messages": [{"role": "user", "content": long_content}],
                "tools": [],
            })

        written = m().write.call_args_list
        full_written = "".join(c.args[0] for c in written)
        data = json.loads(full_written)
        self.assertIn("truncated", data["messages"][0]["content"])

    @patch("falgen.providers.openrouter.os.makedirs")
    def test_handles_empty_messages(self, mock_makedirs):
        from unittest.mock import mock_open
        m = mock_open()
        with patch("builtins.open", m):
            _dump_error("err", {"model": "x", "messages": [], "tools": [1, 2]})

        written = "".join(c.args[0] for c in m().write.call_args_list)
        data = json.loads(written)
        self.assertEqual(data["tools_count"], 2)


class TestOpenRouterProvider(unittest.TestCase):
    def setUp(self):
        self.provider = OpenRouterProvider()

    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key test"})
    def test_get_auth_key(self, mock_headers):
        key = self.provider.get_auth_key()
        self.assertEqual(key, "Key test")

    @patch("falgen.providers.openrouter.httpx.stream")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key test"})
    def test_stream_content(self, mock_auth, mock_stream):
        lines = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" world"}}]}',
            'data: [DONE]',
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter(lines)
        mock_stream.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_stream.return_value.__exit__ = MagicMock(return_value=False)

        events = list(self.provider.stream_chat("test-model", [{"role": "user", "content": "hi"}], []))

        content_events = [(t, d) for t, d in events if t == "content"]
        self.assertEqual(len(content_events), 2)
        self.assertEqual(content_events[0][1], "Hello")
        self.assertEqual(content_events[1][1], " world")

        done_events = [(t, d) for t, d in events if t == "done"]
        self.assertEqual(len(done_events), 1)
        self.assertEqual(done_events[0][1]["content"], "Hello world")

    @patch("falgen.providers.openrouter.httpx.stream")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key test"})
    def test_stream_tool_calls(self, mock_auth, mock_stream):
        lines = [
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"tc1","function":{"name":"search","arguments":"{\\"q\\""}}]}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":": \\"flux\\"}"}}]}}]}',
            'data: [DONE]',
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter(lines)
        mock_stream.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_stream.return_value.__exit__ = MagicMock(return_value=False)

        events = list(self.provider.stream_chat("model", [{"role": "user", "content": "hi"}], []))

        tc_events = [(t, d) for t, d in events if t == "tool_calls"]
        self.assertEqual(len(tc_events), 1)
        self.assertEqual(tc_events[0][1][0]["function"]["name"], "search")
        self.assertEqual(tc_events[0][1][0]["function"]["arguments"], '{"q": "flux"}')

    @patch("falgen.providers.openrouter.httpx.stream")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key test"})
    def test_api_error(self, mock_auth, mock_stream):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.read.return_value = b'{"error":{"message":"Invalid API key"}}'
        mock_stream.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_stream.return_value.__exit__ = MagicMock(return_value=False)

        with patch("falgen.providers.openrouter._dump_error"):
            events = list(self.provider.stream_chat("model", [{"role": "user", "content": "hi"}], []))

        error_events = [(t, d) for t, d in events if t == "error"]
        self.assertEqual(len(error_events), 1)
        self.assertIn("401", error_events[0][1])

    @patch("falgen.providers.openrouter.httpx.stream")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key test"})
    def test_none_content_sanitized(self, mock_auth, mock_stream):
        """Messages with None content should be replaced with empty string."""
        lines = ['data: {"choices":[{"delta":{"content":"ok"}}]}', 'data: [DONE]']
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter(lines)
        mock_stream.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_stream.return_value.__exit__ = MagicMock(return_value=False)

        messages = [{"role": "assistant", "content": None}, {"role": "user", "content": "test"}]
        events = list(self.provider.stream_chat("model", messages, []))

        # Should not raise — None content sanitized to ""
        call_args = mock_stream.call_args
        sent_body = call_args.kwargs.get("json") or call_args[1].get("json")
        self.assertEqual(sent_body["messages"][0]["content"], "")

    @patch("falgen.providers.openrouter.httpx.stream")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key test"})
    def test_malformed_json_chunks_skipped(self, mock_auth, mock_stream):
        lines = [
            'data: not-json',
            'data: {"choices":[{"delta":{"content":"ok"}}]}',
            'data: [DONE]',
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter(lines)
        mock_stream.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_stream.return_value.__exit__ = MagicMock(return_value=False)

        events = list(self.provider.stream_chat("model", [{"role": "user", "content": "hi"}], []))
        content = [d for t, d in events if t == "content"]
        self.assertEqual(content, ["ok"])

    @patch("falgen.providers.openrouter.httpx.stream")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key test"})
    def test_empty_content_results_in_empty_string(self, mock_auth, mock_stream):
        lines = ['data: [DONE]']
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter(lines)
        mock_stream.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_stream.return_value.__exit__ = MagicMock(return_value=False)

        events = list(self.provider.stream_chat("model", [{"role": "user", "content": "hi"}], []))
        done = [d for t, d in events if t == "done"]
        self.assertEqual(done[0]["content"], "")


if __name__ == "__main__":
    unittest.main()
