"""Tests for SQLite session persistence."""

import os
import tempfile
import unittest

from falgen.session import SessionStore


class TestSessionStore(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._db_path = os.path.join(self._tmpdir, "test.db")
        self.store = SessionStore(db_path=self._db_path)

    def tearDown(self):
        self.store.close()
        if os.path.exists(self._db_path):
            os.unlink(self._db_path)
        os.rmdir(self._tmpdir)

    def test_create_session(self):
        sid = self.store.create_session("gpt-4", title="Test chat")
        self.assertIsInstance(sid, str)
        self.assertEqual(len(sid), 12)

    def test_get_session(self):
        sid = self.store.create_session("claude-3", title="My session")
        session = self.store.get_session(sid)
        self.assertIsNotNone(session)
        self.assertEqual(session["title"], "My session")
        self.assertEqual(session["model"], "claude-3")

    def test_get_nonexistent_session(self):
        self.assertIsNone(self.store.get_session("nonexistent"))

    def test_save_and_load_messages(self):
        sid = self.store.create_session("model-x")

        self.store.save_message(sid, {"role": "user", "content": "Hello"})
        self.store.save_message(sid, {"role": "assistant", "content": "Hi there!"})

        messages = self.store.load_messages(sid)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "Hello")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[1]["content"], "Hi there!")

    def test_save_message_with_tool_calls(self):
        sid = self.store.create_session("model-x")
        tool_calls = [{"id": "tc1", "type": "function", "function": {"name": "search", "arguments": "{}"}}]
        self.store.save_message(sid, {
            "role": "assistant",
            "content": "",
            "tool_calls": tool_calls,
        })

        messages = self.store.load_messages(sid)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["tool_calls"], tool_calls)

    def test_save_message_with_tool_call_id(self):
        sid = self.store.create_session("model-x")
        self.store.save_message(sid, {
            "role": "tool",
            "content": '{"ok": true}',
            "tool_call_id": "tc1",
        })

        messages = self.store.load_messages(sid)
        self.assertEqual(messages[0]["tool_call_id"], "tc1")

    def test_message_without_tool_calls_has_no_extra_keys(self):
        sid = self.store.create_session("model-x")
        self.store.save_message(sid, {"role": "user", "content": "test"})

        messages = self.store.load_messages(sid)
        self.assertNotIn("tool_calls", messages[0])
        self.assertNotIn("tool_call_id", messages[0])

    def test_load_empty_session(self):
        sid = self.store.create_session("model-x")
        messages = self.store.load_messages(sid)
        self.assertEqual(messages, [])

    def test_update_title(self):
        sid = self.store.create_session("model-x", title="old")
        self.store.update_title(sid, "new title")
        session = self.store.get_session(sid)
        self.assertEqual(session["title"], "new title")

    def test_update_model(self):
        sid = self.store.create_session("old-model")
        self.store.update_model(sid, "new-model")
        session = self.store.get_session(sid)
        self.assertEqual(session["model"], "new-model")

    def test_list_sessions(self):
        self.store.create_session("m1", title="First")
        self.store.create_session("m2", title="Second")
        self.store.create_session("m3", title="Third")

        sessions = self.store.list_sessions()
        self.assertEqual(len(sessions), 3)
        # Most recent first
        self.assertEqual(sessions[0]["title"], "Third")

    def test_list_sessions_limit(self):
        for i in range(5):
            self.store.create_session("m", title=f"Session {i}")

        sessions = self.store.list_sessions(limit=2)
        self.assertEqual(len(sessions), 2)

    def test_get_last_session_id(self):
        self.store.create_session("m1")
        last_sid = self.store.create_session("m2")
        self.assertEqual(self.store.get_last_session_id(), last_sid)

    def test_get_last_session_id_empty(self):
        self.assertIsNone(self.store.get_last_session_id())

    def test_messages_ordered_by_insertion(self):
        sid = self.store.create_session("m")
        for i in range(5):
            self.store.save_message(sid, {"role": "user", "content": f"msg-{i}"})

        messages = self.store.load_messages(sid)
        for i, msg in enumerate(messages):
            self.assertEqual(msg["content"], f"msg-{i}")

    def test_multiple_sessions_isolated(self):
        sid1 = self.store.create_session("m")
        sid2 = self.store.create_session("m")

        self.store.save_message(sid1, {"role": "user", "content": "session1"})
        self.store.save_message(sid2, {"role": "user", "content": "session2"})

        self.assertEqual(len(self.store.load_messages(sid1)), 1)
        self.assertEqual(self.store.load_messages(sid1)[0]["content"], "session1")
        self.assertEqual(self.store.load_messages(sid2)[0]["content"], "session2")


    def test_save_and_load_media(self):
        sid = self.store.create_session("m")
        self.store.save_media(sid, "https://fal.media/img.png", "image", "fal-ai/flux")
        self.store.save_media(sid, "https://fal.media/vid.mp4", "video", "fal-ai/kling")

        media = self.store.load_media(sid)
        self.assertEqual(len(media), 2)
        # Most recent first
        self.assertEqual(media[0]["media_type"], "video")
        self.assertEqual(media[1]["url"], "https://fal.media/img.png")

    def test_load_media_empty(self):
        sid = self.store.create_session("m")
        self.assertEqual(self.store.load_media(sid), [])

    def test_media_isolated_between_sessions(self):
        sid1 = self.store.create_session("m")
        sid2 = self.store.create_session("m")
        self.store.save_media(sid1, "https://url1.png", "image")
        self.store.save_media(sid2, "https://url2.png", "image")

        self.assertEqual(len(self.store.load_media(sid1)), 1)
        self.assertEqual(self.store.load_media(sid1)[0]["url"], "https://url1.png")

    def test_load_media_limit(self):
        sid = self.store.create_session("m")
        for i in range(10):
            self.store.save_media(sid, f"https://url{i}.png", "image")
        media = self.store.load_media(sid, limit=3)
        self.assertEqual(len(media), 3)


if __name__ == "__main__":
    unittest.main()
