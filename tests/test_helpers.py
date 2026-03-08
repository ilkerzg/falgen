"""Tests for helper functions in app.py and config.py."""

import unittest

from falgen.app import _detect_file_paths, _detect_media_type, _extract_media_urls
from falgen.config import build_system_prompt
from falgen.preferences import Preferences


class TestDetectMediaType(unittest.TestCase):
    def test_image_extensions(self):
        for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
            self.assertEqual(_detect_media_type(f"https://cdn.example.com/file{ext}"), "image")

    def test_video_extensions(self):
        for ext in (".mp4", ".webm", ".mov", ".avi", ".mkv"):
            self.assertEqual(_detect_media_type(f"https://cdn.example.com/file{ext}"), "video")

    def test_audio_extensions(self):
        for ext in (".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a"):
            self.assertEqual(_detect_media_type(f"https://cdn.example.com/file{ext}"), "audio")

    def test_url_with_query_params(self):
        self.assertEqual(_detect_media_type("https://cdn.com/video.mp4?token=abc"), "video")

    def test_unknown_extension_defaults_to_image(self):
        self.assertEqual(_detect_media_type("https://cdn.com/file.xyz"), "image")

    def test_fal_media_url(self):
        self.assertEqual(_detect_media_type("https://fal.media/files/output"), "image")


class TestExtractMediaUrls(unittest.TestCase):
    def test_simple_image_url(self):
        result = {"images": [{"url": "https://fal.media/out.png"}]}
        urls = _extract_media_urls(result)
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0], ("https://fal.media/out.png", "image"))

    def test_video_url(self):
        result = {"video": {"url": "https://fal.media/out.mp4"}}
        urls = _extract_media_urls(result)
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0][1], "video")

    def test_audio_url(self):
        result = {"audio": {"url": "https://fal.media/out.mp3"}}
        urls = _extract_media_urls(result)
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0][1], "audio")

    def test_nested_urls(self):
        result = {
            "output": {
                "images": [
                    {"url": "https://fal.media/1.png"},
                    {"url": "https://fal.media/2.png"},
                ]
            }
        }
        urls = _extract_media_urls(result)
        self.assertEqual(len(urls), 2)

    def test_fal_cdn_url_without_extension(self):
        result = {"url": "https://fal-cdn.example.com/abcdef"}
        urls = _extract_media_urls(result)
        self.assertEqual(len(urls), 1)

    def test_no_media_urls(self):
        result = {"status": "ok", "message": "done"}
        urls = _extract_media_urls(result)
        self.assertEqual(urls, [])

    def test_non_http_strings_ignored(self):
        result = {"url": "not-a-url", "name": "test.png"}
        urls = _extract_media_urls(result)
        self.assertEqual(urls, [])

    def test_mixed_media_types(self):
        result = {
            "image": {"url": "https://fal.media/img.png"},
            "video": {"url": "https://fal.media/vid.mp4"},
            "audio": {"url": "https://fal.media/aud.wav"},
        }
        urls = _extract_media_urls(result)
        types = {t for _, t in urls}
        self.assertEqual(types, {"image", "video", "audio"})


class TestDetectFilePaths(unittest.TestCase):
    def test_no_paths(self):
        self.assertEqual(_detect_file_paths("generate a cat"), [])

    def test_nonexistent_file(self):
        self.assertEqual(_detect_file_paths("/nonexistent/file.png"), [])

    def test_real_file(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake")
            tmp = f.name
        try:
            paths = _detect_file_paths(f"generate from {tmp}")
            self.assertEqual(len(paths), 1)
            self.assertEqual(paths[0][1], tmp)
        finally:
            import os
            os.unlink(tmp)

    def test_multiple_extensions(self):
        # Just test the regex matching — files don't exist
        text = "use /tmp/test.mp4 and /tmp/test.wav"
        # These don't exist so should return empty
        self.assertEqual(_detect_file_paths(text), [])

    def test_ignores_non_media(self):
        self.assertEqual(_detect_file_paths("read /etc/passwd"), [])
        self.assertEqual(_detect_file_paths("edit ~/code/main.py"), [])


class TestBuildSystemPrompt(unittest.TestCase):
    def test_base_prompt_contains_tools(self):
        prompt = build_system_prompt()
        self.assertIn("best_models", prompt)
        self.assertIn("search_models", prompt)
        self.assertIn("generate", prompt)

    def test_with_preferences(self):
        from unittest.mock import MagicMock
        prefs = MagicMock(spec=Preferences)
        prefs.format_for_system_prompt.return_value = "  - text-to-image: fal-ai/flux/dev"

        prompt = build_system_prompt(prefs)
        self.assertIn("fal-ai/flux/dev", prompt)

    def test_without_preferences(self):
        prompt = build_system_prompt(None)
        self.assertNotIn("User's default models", prompt)


if __name__ == "__main__":
    unittest.main()
