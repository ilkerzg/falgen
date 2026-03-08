"""Tests for authentication and API helpers."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from falgen.auth import _read_cached_key, api_get, get_auth_headers, save_key, upload_file


class TestReadCachedKey(unittest.TestCase):
    def test_returns_none_when_file_missing(self):
        with patch("falgen.auth._CACHED_KEY_FILE", "/nonexistent/path"):
            self.assertIsNone(_read_cached_key())

    def test_reads_key_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".key", delete=False) as f:
            f.write("  my-test-key  \n")
            f.flush()
            with patch("falgen.auth._CACHED_KEY_FILE", f.name):
                self.assertEqual(_read_cached_key(), "my-test-key")
        os.unlink(f.name)

    def test_returns_none_for_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".key", delete=False) as f:
            f.write("   \n")
            f.flush()
            with patch("falgen.auth._CACHED_KEY_FILE", f.name):
                self.assertIsNone(_read_cached_key())
        os.unlink(f.name)


class TestSaveKey(unittest.TestCase):
    def test_saves_and_reads_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            key_file = os.path.join(tmpdir, "subdir", "api_key")
            with patch("falgen.auth._CACHED_KEY_FILE", key_file), \
                 patch("falgen.auth._CACHE_DIR", os.path.join(tmpdir, "subdir")):
                save_key("  test-key-123  ")
                self.assertTrue(os.path.exists(key_file))
                with open(key_file) as f:
                    self.assertEqual(f.read(), "test-key-123")
                # Check permissions
                stat = os.stat(key_file)
                self.assertEqual(stat.st_mode & 0o777, 0o600)


class TestGetAuthHeaders(unittest.TestCase):
    @patch.dict(os.environ, {"FAL_KEY": "env-key-123"})
    def test_uses_env_var(self):
        headers = get_auth_headers()
        self.assertEqual(headers["Authorization"], "Key env-key-123")

    @patch.dict(os.environ, {"FAL_KEY": "id:secret"})
    def test_colon_format_key(self):
        headers = get_auth_headers()
        self.assertEqual(headers["Authorization"], "Key id:secret")

    @patch.dict(os.environ, {}, clear=True)
    def test_falls_back_to_cached_key(self):
        with patch("falgen.auth._read_cached_key", return_value="cached-key"):
            headers = get_auth_headers()
            self.assertEqual(headers["Authorization"], "Key cached-key")

    @patch.dict(os.environ, {}, clear=True)
    def test_returns_empty_when_no_key(self):
        with patch("falgen.auth._read_cached_key", return_value=None):
            headers = get_auth_headers()
            self.assertEqual(headers, {})

    @patch.dict(os.environ, {"FAL_KEY": "   "})
    def test_empty_env_var_falls_through(self):
        with patch("falgen.auth._read_cached_key", return_value="cached"):
            headers = get_auth_headers()
            self.assertEqual(headers["Authorization"], "Key cached")


class TestApiGet(unittest.TestCase):
    @patch("falgen.auth.httpx.get")
    def test_successful_request(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": "test"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = api_get("/models", params={"q": "flux"}, headers={"Authorization": "Key x"})
        self.assertEqual(result, {"data": "test"})
        mock_get.assert_called_once_with(
            "https://api.fal.ai/v1/models",
            params={"q": "flux"},
            headers={"Authorization": "Key x"},
            timeout=15,
        )

    @patch("falgen.auth.httpx.get")
    def test_network_error_raises(self, mock_get):
        import httpx
        mock_get.side_effect = httpx.ConnectError("refused")
        with self.assertRaises(httpx.ConnectError):
            api_get("/models")

    @patch("falgen.auth.httpx.get")
    def test_http_error_raises(self, mock_get):
        import httpx
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )
        mock_get.return_value = mock_resp
        with self.assertRaises(httpx.HTTPStatusError):
            api_get("/models")


class TestUploadFile(unittest.TestCase):
    @patch("falgen.auth.httpx.post")
    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    def test_successful_upload(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"access_url": "https://v3.fal.media/files/abc123.png"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        url = upload_file(b"\x89PNG\r\n\x1a\nfakedata", "image/png", "test.png")
        self.assertEqual(url, "https://v3.fal.media/files/abc123.png")

        call_kwargs = mock_post.call_args
        self.assertEqual(call_kwargs.kwargs.get("content") or call_kwargs[1].get("content"),
                         b"\x89PNG\r\n\x1a\nfakedata")

    @patch("falgen.auth.httpx.post")
    @patch.dict(os.environ, {"FAL_KEY": "test-key"})
    def test_upload_network_error(self, mock_post):
        mock_post.side_effect = Exception("Connection refused")
        with self.assertRaises(Exception):
            upload_file(b"data", "image/png")

    @patch.dict(os.environ, {}, clear=True)
    def test_upload_not_authenticated(self):
        with patch("falgen.auth._read_cached_key", return_value=None):
            with self.assertRaises(RuntimeError, msg="Not authenticated"):
                upload_file(b"data", "image/png")


if __name__ == "__main__":
    unittest.main()
