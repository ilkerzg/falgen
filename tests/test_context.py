"""Tests for context window management."""

import unittest
from unittest.mock import MagicMock

from falgen.context import (
    estimate_tokens,
    get_context_limit,
    needs_summarization,
    summarize_messages,
    KEEP_RECENT,
)


class TestEstimateTokens(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(estimate_tokens([]), 0)

    def test_simple_messages(self):
        msgs = [
            {"role": "user", "content": "Hello world"},  # 11 chars
            {"role": "assistant", "content": "Hi there"},  # 8 chars
        ]
        tokens = estimate_tokens(msgs)
        # ~19 / 3.5 = ~5
        self.assertGreater(tokens, 0)
        self.assertLess(tokens, 20)

    def test_tool_calls_counted(self):
        msgs = [
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "tc1", "function": {"name": "search", "arguments": '{"q": "test"}'}}
            ]},
        ]
        tokens = estimate_tokens(msgs)
        self.assertGreater(tokens, 0)

    def test_none_content(self):
        msgs = [{"role": "assistant", "content": None}]
        tokens = estimate_tokens(msgs)
        self.assertEqual(tokens, 0)


class TestGetContextLimit(unittest.TestCase):
    def test_anthropic(self):
        self.assertEqual(get_context_limit("anthropic/claude-sonnet-4.6"), 200000)

    def test_openai(self):
        self.assertEqual(get_context_limit("openai/gpt-5.4"), 128000)

    def test_google(self):
        self.assertEqual(get_context_limit("google/gemini-3-flash"), 1000000)

    def test_unknown_model(self):
        self.assertEqual(get_context_limit("unknown/model"), 128000)


class TestNeedsSummarization(unittest.TestCase):
    def test_small_conversation(self):
        msgs = [{"role": "user", "content": "hi"}]
        self.assertFalse(needs_summarization(msgs, "anthropic/claude-sonnet-4.6"))

    def test_large_conversation(self):
        # Create messages that exceed 75% of 200K tokens (~525K chars)
        big_content = "x" * 600000
        msgs = [{"role": "user", "content": big_content}]
        self.assertTrue(needs_summarization(msgs, "anthropic/claude-sonnet-4.6"))


class TestSummarizeMessages(unittest.TestCase):
    def test_too_few_messages(self):
        msgs = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hi"},
        ]
        result = summarize_messages(msgs, MagicMock(), "test")
        self.assertEqual(result, msgs)

    def test_summarization_replaces_old_messages(self):
        # Build enough messages to trigger summarization
        msgs = [{"role": "system", "content": "system prompt"}]
        for i in range(20):
            msgs.append({"role": "user", "content": f"message {i}"})
            msgs.append({"role": "assistant", "content": f"response {i}"})

        # Mock provider that returns a summary
        mock_provider = MagicMock()
        mock_provider.stream_chat.return_value = iter([
            ("content", "Summary of conversation"),
            ("done", {"role": "assistant", "content": "Summary of conversation"}),
        ])

        result = summarize_messages(msgs, mock_provider, "test")

        # Should have: system + summary + last KEEP_RECENT
        self.assertEqual(result[0]["role"], "system")
        self.assertIn("[Summary", result[1]["content"])
        self.assertEqual(len(result), 1 + 1 + KEEP_RECENT)

    def test_summarization_error_falls_back(self):
        msgs = [{"role": "system", "content": "sys"}]
        for i in range(20):
            msgs.append({"role": "user", "content": f"msg {i}"})

        mock_provider = MagicMock()
        mock_provider.stream_chat.return_value = iter([
            ("error", "API error"),
        ])

        result = summarize_messages(msgs, mock_provider, "test")
        # Should fall back to system + recent
        self.assertEqual(result[0]["role"], "system")
        self.assertEqual(len(result), 1 + KEEP_RECENT)

    def test_preserves_system_and_recent(self):
        msgs = [{"role": "system", "content": "sys"}]
        for i in range(30):
            msgs.append({"role": "user", "content": f"msg {i}"})

        mock_provider = MagicMock()
        mock_provider.stream_chat.return_value = iter([
            ("content", "Summary"),
            ("done", {"role": "assistant", "content": "Summary"}),
        ])

        result = summarize_messages(msgs, mock_provider, "test")
        # Last message should be the last one from original
        self.assertEqual(result[-1]["content"], "msg 29")


if __name__ == "__main__":
    unittest.main()
