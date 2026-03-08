import unittest

from falgen.app import FalChatApp
from falgen.widgets import ChatInput


class TerminalGarbageTest(unittest.TestCase):
    def test_chat_input_strips_caret_style_terminal_sequences(self) -> None:
        cleaned = ChatInput._GARBAGE_RE.sub("", "hello ^[6;14;7t")
        self.assertEqual(cleaned, "hello ")

    def test_chat_input_strips_raw_escape_terminal_sequences(self) -> None:
        cleaned = ChatInput._GARBAGE_RE.sub("", "\x1b[6;14;7t")
        self.assertEqual(cleaned, "")

    def test_flush_cleanup_strips_terminal_suffix_without_touching_normal_ratios(self) -> None:
        dirty = "draft^[6;14;7t"
        while dirty and FalChatApp._TERM_GARBAGE_RE.search(dirty):
            updated = FalChatApp._TERM_GARBAGE_RE.sub("", dirty)
            if updated == dirty:
                break
            dirty = updated
        self.assertEqual(dirty, "draft")
        self.assertEqual(FalChatApp._TERM_GARBAGE_RE.sub("", "aspect 16;9"), "aspect 16;9")


if __name__ == "__main__":
    unittest.main()
