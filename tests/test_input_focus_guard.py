import unittest

from falgen.app import FalChatApp
from falgen.widgets import ChatInput


class InputFocusGuardTest(unittest.IsolatedAsyncioTestCase):
    async def test_suspended_input_does_not_accept_terminal_leak_keys(self) -> None:
        app = FalChatApp()

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", ChatInput)
            input_widget.focus()
            input_widget.value = "draft"
            await pilot.pause()

            restore = app._suspend_input_focus()
            await pilot.press("^", "[", "6", ";", "1", "4", ";", "7", "t")
            await pilot.pause()

            self.assertTrue(restore)
            self.assertEqual(input_widget.value, "draft")

            app._restore_input_focus(restore)
            input_widget.value = "draft"
            await pilot.pause()
            await pilot.press("^", "[", "6", ";", "1", "4", ";", "7", "t")
            await pilot.pause()

            self.assertEqual(input_widget.value, "")


if __name__ == "__main__":
    unittest.main()
