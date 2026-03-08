"""Tests for user preferences persistence."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from falgen.preferences import Preferences


class TestPreferences(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._prefs_path = os.path.join(self._tmpdir, "preferences.json")
        self._patcher = patch("falgen.preferences._PREFS_PATH",
                              __import__("pathlib").Path(self._prefs_path))
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        if os.path.exists(self._prefs_path):
            os.unlink(self._prefs_path)
        os.rmdir(self._tmpdir)

    def test_empty_defaults(self):
        prefs = Preferences()
        self.assertEqual(prefs.get_defaults(), {})

    def test_set_and_get_default(self):
        prefs = Preferences()
        prefs.set_default("text-to-image", "fal-ai/flux/dev")
        self.assertEqual(prefs.get_default("text-to-image"), "fal-ai/flux/dev")

    def test_persistence_across_instances(self):
        prefs1 = Preferences()
        prefs1.set_default("text-to-video", "fal-ai/kling")
        del prefs1

        prefs2 = Preferences()
        self.assertEqual(prefs2.get_default("text-to-video"), "fal-ai/kling")

    def test_multiple_defaults(self):
        prefs = Preferences()
        prefs.set_default("text-to-image", "model-a")
        prefs.set_default("text-to-video", "model-b")

        defaults = prefs.get_defaults()
        self.assertEqual(defaults["text-to-image"], "model-a")
        self.assertEqual(defaults["text-to-video"], "model-b")

    def test_overwrite_default(self):
        prefs = Preferences()
        prefs.set_default("text-to-image", "old-model")
        prefs.set_default("text-to-image", "new-model")
        self.assertEqual(prefs.get_default("text-to-image"), "new-model")

    def test_get_nonexistent_category(self):
        prefs = Preferences()
        self.assertIsNone(prefs.get_default("nonexistent"))

    def test_format_for_system_prompt_empty(self):
        prefs = Preferences()
        self.assertEqual(prefs.format_for_system_prompt(), "")

    def test_format_for_system_prompt_with_defaults(self):
        prefs = Preferences()
        prefs.set_default("text-to-image", "fal-ai/flux/dev")
        prompt = prefs.format_for_system_prompt()
        self.assertIn("text-to-image", prompt)
        self.assertIn("fal-ai/flux/dev", prompt)

    def test_corrupted_json_file(self):
        with open(self._prefs_path, "w") as f:
            f.write("{invalid json!!!")
        prefs = Preferences()
        self.assertEqual(prefs.get_defaults(), {})

    def test_saves_valid_json(self):
        prefs = Preferences()
        prefs.set_default("text-to-image", "model-x")

        with open(self._prefs_path) as f:
            data = json.load(f)
        self.assertEqual(data["defaults"]["text-to-image"], "model-x")


if __name__ == "__main__":
    unittest.main()
