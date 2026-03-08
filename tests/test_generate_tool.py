"""Tests for the generate tool — job submission, polling, and error handling."""

import unittest
from unittest.mock import MagicMock, patch, call

import httpx

from falgen.tools.generate import GenerateTool


def _mock_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"{status_code}", request=MagicMock(), response=resp
        )
    return resp


class TestGenerateTool(unittest.TestCase):
    def setUp(self):
        self.tool = GenerateTool()

    def test_schema(self):
        schema = self.tool.to_openai_schema()
        self.assertEqual(schema["function"]["name"], "generate")
        self.assertIn("endpoint_id", schema["function"]["parameters"]["properties"])
        self.assertIn("input", schema["function"]["parameters"]["properties"])

    @patch("falgen.tools.generate.httpx.get")
    @patch("falgen.tools.generate.httpx.post")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key test"})
    def test_successful_generation(self, mock_auth, mock_post, mock_get):
        # Submit returns request_id
        mock_post.return_value = _mock_response(200, {
            "request_id": "req-123",
            "status_url": "https://queue.fal.run/fal-ai/flux/requests/req-123/status",
            "response_url": "https://queue.fal.run/fal-ai/flux/requests/req-123",
        })

        # First poll: IN_PROGRESS, second poll: COMPLETED
        mock_get.side_effect = [
            _mock_response(200, {"status": "IN_PROGRESS", "logs": []}),
            _mock_response(200, {"status": "COMPLETED"}),
            # Result fetch
            _mock_response(200, {"images": [{"url": "https://fal.media/out.png"}]}),
        ]

        result = self.tool.execute({
            "endpoint_id": "fal-ai/flux/dev",
            "input": {"prompt": "a cat"},
        })

        self.assertTrue(result["ok"])
        self.assertEqual(result["request_id"], "req-123")
        self.assertIn("images", result["result"])

    @patch("falgen.tools.generate.httpx.post")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key test"})
    def test_422_validation_error(self, mock_auth, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.json.return_value = {"detail": [{"msg": "invalid field"}]}
        mock_post.return_value = mock_resp

        result = self.tool.execute({
            "endpoint_id": "fal-ai/flux/dev",
            "input": {"bad_param": "x"},
        })

        self.assertFalse(result["ok"])
        self.assertIn("422", result["error"])
        self.assertIn("hint", result)

    @patch("falgen.tools.generate.httpx.post")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key test"})
    def test_submit_network_error(self, mock_auth, mock_post):
        mock_post.side_effect = Exception("Connection refused")

        result = self.tool.execute({
            "endpoint_id": "fal-ai/flux/dev",
            "input": {"prompt": "test"},
        })

        self.assertFalse(result["ok"])
        self.assertIn("Submit failed", result["error"])

    @patch("falgen.auth.get_auth_headers", return_value={})
    def test_not_authenticated(self, mock_auth):
        result = self.tool.execute({
            "endpoint_id": "fal-ai/flux/dev",
            "input": {"prompt": "test"},
        })

        self.assertFalse(result["ok"])
        self.assertIn("Not authenticated", result["error"])

    @patch("falgen.tools.generate.httpx.get")
    @patch("falgen.tools.generate.httpx.post")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key test"})
    def test_background_mode(self, mock_auth, mock_post, mock_get):
        mock_post.return_value = _mock_response(200, {"request_id": "bg-req-456"})

        result = self.tool.execute({
            "endpoint_id": "fal-ai/flux/dev",
            "input": {"prompt": "test"},
            "background": True,
        })

        self.assertTrue(result["ok"])
        self.assertTrue(result["background"])
        self.assertEqual(result["request_id"], "bg-req-456")
        # Should NOT poll
        mock_get.assert_not_called()

    @patch("falgen.tools.generate.httpx.get")
    @patch("falgen.tools.generate.httpx.post")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key test"})
    def test_execution_error_during_poll(self, mock_auth, mock_post, mock_get):
        mock_post.return_value = _mock_response(200, {"request_id": "req-err"})

        mock_get.return_value = _mock_response(200, {
            "status": "FAILED",
            "error": "Out of memory",
        })

        result = self.tool.execute({
            "endpoint_id": "fal-ai/flux/dev",
            "input": {"prompt": "test"},
        })

        self.assertFalse(result["ok"])
        self.assertIn("Execution failed", result["error"])

    @patch("falgen.tools.generate.httpx.get")
    @patch("falgen.tools.generate.httpx.post")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key test"})
    def test_progress_callback_called(self, mock_auth, mock_post, mock_get):
        mock_post.return_value = _mock_response(200, {"request_id": "req-prog"})

        mock_get.side_effect = [
            _mock_response(200, {"status": "IN_QUEUE", "queue_position": 3}),
            _mock_response(200, {"status": "COMPLETED"}),
            _mock_response(200, {"result": "ok"}),
        ]

        progress_calls = []

        result = self.tool.execute(
            {
                "endpoint_id": "fal-ai/flux/dev",
                "input": {"prompt": "test"},
            },
            on_progress=lambda info: progress_calls.append(info),
        )

        self.assertTrue(result["ok"])
        # Should have: SUBMITTING, IN_QUEUE, COMPLETED (at least)
        states = [p["state"] for p in progress_calls]
        self.assertIn("SUBMITTING", states)
        self.assertIn("COMPLETED", states)

    @patch("falgen.tools.generate.httpx.post")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key test"})
    def test_extra_params_at_top_level(self, mock_auth, mock_post):
        """When LLM puts params at top level instead of inside 'input'."""
        mock_post.return_value = _mock_response(200, {"request_id": "req-extra"})

        # Simulate: endpoint_id + prompt at top level, input is empty
        self.tool.execute({
            "endpoint_id": "fal-ai/flux/dev",
            "input": {},
            "prompt": "a cat",
            "image_size": "landscape_16_9",
            "background": True,
        })

        # The POST body should include prompt and image_size
        post_call = mock_post.call_args
        posted_json = post_call.kwargs.get("json") or post_call[1].get("json")
        self.assertIn("prompt", posted_json)
        self.assertEqual(posted_json["prompt"], "a cat")

    @patch("falgen.tools.generate.httpx.get")
    @patch("falgen.tools.generate.httpx.post")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key test"})
    def test_result_fetch_422(self, mock_auth, mock_post, mock_get):
        mock_post.return_value = _mock_response(200, {"request_id": "req-r422"})

        mock_get.side_effect = [
            _mock_response(200, {"status": "COMPLETED"}),
            # Result fetch returns 422
            MagicMock(status_code=422, json=MagicMock(return_value={"detail": "bad"}), text="bad"),
        ]

        result = self.tool.execute({
            "endpoint_id": "fal-ai/flux/dev",
            "input": {"prompt": "test"},
        })

        self.assertFalse(result["ok"])
        self.assertIn("Result fetch 422", result["error"])


if __name__ == "__main__":
    unittest.main()
