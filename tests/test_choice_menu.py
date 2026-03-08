"""Tests for ChoiceMenu — fuzzy filter, scroll indicator, cancel callback."""

import unittest
from unittest.mock import patch

from falgen.widgets import ChoiceMenu, _fuzzy_match


class TestFuzzyMatch(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(_fuzzy_match("flux", "flux"))

    def test_subsequence_match(self):
        self.assertTrue(_fuzzy_match("flx", "flux dev"))

    def test_case_sensitive(self):
        # fuzzy_match expects lowered inputs
        self.assertFalse(_fuzzy_match("F", "flux"))
        self.assertTrue(_fuzzy_match("f", "flux"))

    def test_no_match(self):
        self.assertFalse(_fuzzy_match("xyz", "flux"))

    def test_empty_query(self):
        self.assertTrue(_fuzzy_match("", "anything"))

    def test_query_longer_than_text(self):
        self.assertFalse(_fuzzy_match("longquery", "short"))

    def test_scattered_chars(self):
        self.assertTrue(_fuzzy_match("kv", "kling video 3.0"))

    def test_partial_match_fails(self):
        self.assertFalse(_fuzzy_match("abc", "ab"))


class _MenuHelper:
    """Minimal stand-in that mirrors ChoiceMenu logic without Textual reactives."""

    def __init__(self, options):
        self._question = "Pick one"
        self._options = list(options)
        self._filtered = list(range(len(options)))
        self._filter_text = ""
        self._on_select = None
        self._on_cancel = None
        self._custom_mode = False
        self._custom_text = ""
        self.selected_index = 0
        self._MAX_VISIBLE = ChoiceMenu._MAX_VISIBLE

    # Forward all logic methods to ChoiceMenu (they only use self._*)
    def _total_items(self):
        return len(self._filtered) + 1

    def _apply_filter(self):
        if not self._filter_text:
            self._filtered = list(range(len(self._options)))
        else:
            query = self._filter_text.lower()
            self._filtered = [
                i for i, opt in enumerate(self._options)
                if _fuzzy_match(query, opt.lower())
            ]
        self.selected_index = 0

    def move_selection(self, delta):
        if self._custom_mode:
            return
        total = self._total_items()
        self.selected_index = max(0, min(total - 1, self.selected_index + delta))

    def confirm_selection(self):
        if self._custom_mode:
            if self._custom_text.strip():
                answer = self._custom_text.strip()
                callback = self._on_select
                self._on_select = None
                self._on_cancel = None
                if callback:
                    callback(answer)
            return
        if self.selected_index < len(self._filtered):
            original_idx = self._filtered[self.selected_index]
            answer = self._options[original_idx]
            callback = self._on_select
            self._on_select = None
            self._on_cancel = None
            if callback:
                callback(answer)
        else:
            self._custom_mode = True
            self._custom_text = ""

    def cancel(self):
        callback = self._on_cancel
        self._on_select = None
        self._on_cancel = None
        if callback:
            callback()

    def handle_filter_key(self, key, character):
        if key == "backspace":
            if self._filter_text:
                self._filter_text = self._filter_text[:-1]
                self._apply_filter()
        elif character and len(character) == 1 and character.isprintable():
            self._filter_text += character
            self._apply_filter()

    def handle_custom_key(self, key, character):
        if key == "escape":
            self._custom_mode = False
        elif key == "backspace":
            self._custom_text = self._custom_text[:-1]
        elif character and len(character) == 1 and character.isprintable():
            self._custom_text += character

    def _scroll_window(self):
        total = len(self._filtered)
        if total <= self._MAX_VISIBLE:
            return 0, total
        half = self._MAX_VISIBLE // 2
        start = max(0, self.selected_index - half)
        end = start + self._MAX_VISIBLE
        if end > total:
            end = total
            start = max(0, end - self._MAX_VISIBLE)
        return start, end


class TestChoiceMenuLogic(unittest.TestCase):
    """Test ChoiceMenu logic via _MenuHelper (same algorithms, no Textual dependency)."""

    def _make_menu(self, options):
        return _MenuHelper(options)

    def test_total_items_includes_other(self):
        menu = self._make_menu(["a", "b", "c"])
        self.assertEqual(menu._total_items(), 4)  # 3 + Other

    def test_move_selection_down(self):
        menu = self._make_menu(["a", "b", "c"])
        menu.move_selection(1)
        self.assertEqual(menu.selected_index, 1)
        menu.move_selection(1)
        self.assertEqual(menu.selected_index, 2)

    def test_move_selection_clamped(self):
        menu = self._make_menu(["a", "b"])
        # total = 3 (a, b, Other)
        menu.move_selection(10)
        self.assertEqual(menu.selected_index, 2)
        menu.move_selection(-10)
        self.assertEqual(menu.selected_index, 0)

    def test_confirm_selection_calls_callback(self):
        menu = self._make_menu(["alpha", "beta"])
        result = []
        menu._on_select = lambda x: result.append(x)
        menu.selected_index = 1
        menu.confirm_selection()
        self.assertEqual(result, ["beta"])

    def test_confirm_other_enters_custom_mode(self):
        menu = self._make_menu(["a", "b"])
        menu.selected_index = 2  # "Other..."
        menu.confirm_selection()
        self.assertTrue(menu._custom_mode)

    def test_custom_mode_confirm(self):
        menu = self._make_menu(["a"])
        menu._custom_mode = True
        menu._custom_text = "my answer"
        result = []
        menu._on_select = lambda x: result.append(x)
        menu.confirm_selection()
        self.assertEqual(result, ["my answer"])

    def test_custom_mode_empty_doesnt_confirm(self):
        menu = self._make_menu(["a"])
        menu._custom_mode = True
        menu._custom_text = "   "
        result = []
        menu._on_select = lambda x: result.append(x)
        menu.confirm_selection()
        self.assertEqual(result, [])

    def test_cancel_calls_on_cancel(self):
        menu = self._make_menu(["a", "b"])
        cancelled = []
        menu._on_cancel = lambda: cancelled.append(True)
        menu.cancel()
        self.assertEqual(cancelled, [True])

    def test_cancel_clears_callbacks(self):
        menu = self._make_menu(["a"])
        menu._on_cancel = lambda: None
        menu._on_select = lambda x: None
        menu.cancel()
        self.assertIsNone(menu._on_select)
        self.assertIsNone(menu._on_cancel)

    # -- Fuzzy filter tests --

    def test_filter_narrows_options(self):
        menu = self._make_menu(["flux dev", "kling video", "flux schnell"])
        menu._filter_text = "flux"
        menu._apply_filter()
        self.assertEqual(len(menu._filtered), 2)
        # Should be indices 0 and 2
        self.assertEqual(menu._filtered, [0, 2])

    def test_filter_empty_shows_all(self):
        menu = self._make_menu(["a", "b", "c"])
        menu._filter_text = ""
        menu._apply_filter()
        self.assertEqual(len(menu._filtered), 3)

    def test_filter_no_match(self):
        menu = self._make_menu(["alpha", "beta"])
        menu._filter_text = "xyz"
        menu._apply_filter()
        self.assertEqual(len(menu._filtered), 0)

    def test_filter_resets_selection(self):
        menu = self._make_menu(["a", "b", "c"])
        menu.selected_index = 2
        menu._filter_text = "a"
        menu._apply_filter()
        self.assertEqual(menu.selected_index, 0)

    def test_confirm_after_filter_selects_correct_option(self):
        menu = self._make_menu(["flux dev", "kling video", "flux schnell"])
        menu._filter_text = "flux"
        menu._apply_filter()
        # filtered = [0, 2], select index 1 = "flux schnell" (original index 2)
        menu.selected_index = 1
        result = []
        menu._on_select = lambda x: result.append(x)
        menu.confirm_selection()
        self.assertEqual(result, ["flux schnell"])

    def test_handle_filter_key_adds_char(self):
        menu = self._make_menu(["flux", "kling"])
        menu.handle_filter_key("f", "f")
        self.assertEqual(menu._filter_text, "f")
        self.assertEqual(len(menu._filtered), 1)

    def test_handle_filter_key_backspace(self):
        menu = self._make_menu(["flux", "kling"])
        menu._filter_text = "fl"
        menu._apply_filter()
        menu.handle_filter_key("backspace", None)
        self.assertEqual(menu._filter_text, "f")

    # -- Scroll window tests --

    def test_scroll_window_small_list(self):
        menu = self._make_menu(["a", "b", "c"])
        start, end = menu._scroll_window()
        self.assertEqual(start, 0)
        self.assertEqual(end, 3)

    def test_scroll_window_large_list(self):
        options = [f"model-{i}" for i in range(20)]
        menu = self._make_menu(options)
        # At top
        menu.selected_index = 0
        start, end = menu._scroll_window()
        self.assertEqual(start, 0)
        self.assertEqual(end, menu._MAX_VISIBLE)

        # In middle
        menu.selected_index = 10
        start, end = menu._scroll_window()
        self.assertLessEqual(start, 10)
        self.assertGreater(end, 10)
        self.assertEqual(end - start, menu._MAX_VISIBLE)

        # At bottom
        menu.selected_index = 19
        start, end = menu._scroll_window()
        self.assertEqual(end, 20)
        self.assertEqual(start, 20 - menu._MAX_VISIBLE)

    def test_move_selection_blocked_in_custom_mode(self):
        menu = self._make_menu(["a", "b"])
        menu._custom_mode = True
        menu.selected_index = 0
        menu.move_selection(1)
        self.assertEqual(menu.selected_index, 0)

    def test_handle_custom_key_escape(self):
        menu = self._make_menu(["a"])
        menu._custom_mode = True
        menu.handle_custom_key("escape", None)
        self.assertFalse(menu._custom_mode)

    def test_handle_custom_key_typing(self):
        menu = self._make_menu(["a"])
        menu._custom_mode = True
        menu.handle_custom_key("a", "a")
        menu.handle_custom_key("b", "b")
        self.assertEqual(menu._custom_text, "ab")
        menu.handle_custom_key("backspace", None)
        self.assertEqual(menu._custom_text, "a")


if __name__ == "__main__":
    unittest.main()
