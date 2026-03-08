"""Tests for the best_models (leaderboard) tool."""

import unittest
from unittest.mock import MagicMock, patch

from falgen.tools.leaderboard import BestModelsTool, _extract_overall_elo, _extract_specializations

# -- Sample API responses --

SAMPLE_IMAGE_MODELS = {
    "models": [
        {
            "name": "Model Alpha",
            "slug": "model-alpha",
            "isCurrent": True,
            "pricePer1kImages": 50,
            "creator": {"name": "CreatorA"},
            "family": {"name": "Alpha"},
            "elos": [
                {"elo": 1300.5, "winRate": 0.75, "appearances": 1000, "wins": 750, "tag": None},
                {"elo": 1350.0, "winRate": 0.80, "appearances": 200, "wins": 160,
                 "tag": {"label": "Photorealistic", "slug": "photo"}},
            ],
        },
        {
            "name": "Model Beta",
            "slug": "model-beta",
            "isCurrent": True,
            "pricePer1kImages": 30,
            "creator": {"name": "CreatorB"},
            "family": {"name": "Beta"},
            "elos": [
                {"elo": 1250.0, "winRate": 0.65, "appearances": 800, "wins": 520, "tag": None},
            ],
        },
        {
            "name": "Model Gamma",
            "slug": "model-gamma",
            "isCurrent": False,
            "pricePer1kImages": None,
            "creator": {"name": "CreatorC"},
            "family": {"name": "Gamma"},
            "elos": [
                {"elo": 1100.0, "winRate": 0.50, "appearances": 500, "wins": 250, "tag": None},
            ],
        },
    ]
}

SAMPLE_VIDEO_MODELS = {
    "models": [
        {
            "name": "VideoModel X",
            "slug": "videomodel-x",
            "isCurrent": True,
            "pricePerMinute": 10.0,
            "creator": {"name": "VidCorp"},
            "elos": [
                {"elo": 1280.0, "winRate": 0.60, "appearances": 500, "wins": 300, "tag": None},
                {"elo": 1320.0, "winRate": 0.65, "appearances": 100, "wins": 65,
                 "tag": {"label": "Fantasy", "slug": "fantasy"}},
            ],
        },
    ]
}

SAMPLE_EMPTY = {"models": []}

SAMPLE_NO_ELO = {
    "models": [
        {
            "name": "NoElo Model",
            "slug": "no-elo",
            "isCurrent": True,
            "creator": {"name": "Nobody"},
            "elos": [],
        },
    ]
}


class TestExtractOverallElo(unittest.TestCase):
    def test_extracts_untagged_elo(self):
        model = SAMPLE_IMAGE_MODELS["models"][0]
        self.assertAlmostEqual(_extract_overall_elo(model), 1300.5)

    def test_fallback_to_first_entry(self):
        model = {"elos": [{"elo": 1200.0, "tag": {"label": "Something"}}]}
        self.assertAlmostEqual(_extract_overall_elo(model), 1200.0)

    def test_empty_elos_returns_none(self):
        self.assertIsNone(_extract_overall_elo({"elos": []}))

    def test_missing_elos_returns_none(self):
        self.assertIsNone(_extract_overall_elo({}))


class TestExtractSpecializations(unittest.TestCase):
    def test_extracts_tagged_categories(self):
        model = SAMPLE_IMAGE_MODELS["models"][0]
        specs = _extract_specializations(model)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["category"], "Photorealistic")

    def test_no_specializations(self):
        model = SAMPLE_IMAGE_MODELS["models"][1]
        specs = _extract_specializations(model)
        self.assertEqual(specs, [])

    def test_top_n_limit(self):
        model = {
            "elos": [
                {"elo": 1000, "winRate": 0.5, "tag": None},
                {"elo": 1300, "winRate": 0.7, "tag": {"label": "A"}},
                {"elo": 1200, "winRate": 0.6, "tag": {"label": "B"}},
                {"elo": 1100, "winRate": 0.5, "tag": {"label": "C"}},
                {"elo": 1400, "winRate": 0.8, "tag": {"label": "D"}},
            ]
        }
        specs = _extract_specializations(model, top_n=2)
        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0]["category"], "D")
        self.assertEqual(specs[1]["category"], "A")


class TestBestModelsTool(unittest.TestCase):
    def setUp(self):
        self.tool = BestModelsTool()

    def test_schema(self):
        schema = self.tool.to_openai_schema()
        self.assertEqual(schema["function"]["name"], "best_models")
        self.assertIn("category", schema["function"]["parameters"]["properties"])

    def test_invalid_category(self):
        result = self.tool.execute({"category": "text-to-smell"})
        self.assertFalse(result["ok"])
        self.assertIn("valid_categories", result)

    @patch("falgen.tools.leaderboard.httpx.get")
    def test_text_to_image_ranking(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_IMAGE_MODELS
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = self.tool.execute({"category": "text-to-image", "top_n": 10})

        self.assertTrue(result["ok"])
        self.assertEqual(result["category"], "text-to-image")
        self.assertEqual(len(result["models"]), 3)
        # Sorted by ELO descending
        self.assertEqual(result["models"][0]["name"], "Model Alpha")
        self.assertEqual(result["models"][0]["rank"], 1)
        self.assertAlmostEqual(result["models"][0]["elo"], 1300.5)
        self.assertEqual(result["models"][1]["name"], "Model Beta")
        self.assertEqual(result["models"][2]["name"], "Model Gamma")

    @patch("falgen.tools.leaderboard.httpx.get")
    def test_top_n_limits_results(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_IMAGE_MODELS
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = self.tool.execute({"category": "text-to-image", "top_n": 2})
        self.assertEqual(len(result["models"]), 2)

    @patch("falgen.tools.leaderboard.httpx.get")
    def test_top_n_capped_at_20(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_IMAGE_MODELS
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = self.tool.execute({"category": "text-to-image", "top_n": 100})
        # Should be capped, not 100
        self.assertLessEqual(len(result["models"]), 20)

    @patch("falgen.tools.leaderboard.httpx.get")
    def test_video_models_price_unit(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_VIDEO_MODELS
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = self.tool.execute({"category": "text-to-video"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["models"][0]["price_unit"], "per minute")

    @patch("falgen.tools.leaderboard.httpx.get")
    def test_empty_models_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_EMPTY
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = self.tool.execute({"category": "text-to-image"})
        self.assertFalse(result["ok"])
        self.assertIn("No models", result["error"])

    @patch("falgen.tools.leaderboard.httpx.get")
    def test_models_with_no_elo_skipped(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_NO_ELO
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = self.tool.execute({"category": "text-to-image"})
        # Model has empty elos, _extract_overall_elo returns None, so it's skipped
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["models"]), 0)

    @patch("falgen.tools.leaderboard.httpx.get")
    def test_network_error(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")

        result = self.tool.execute({"category": "text-to-image"})
        self.assertFalse(result["ok"])
        self.assertIn("Failed to fetch", result["error"])

    @patch("falgen.tools.leaderboard.httpx.get")
    def test_win_rate_percentage(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_IMAGE_MODELS
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = self.tool.execute({"category": "text-to-image"})
        # winRate 0.75 should become 75.0
        self.assertAlmostEqual(result["models"][0]["win_rate"], 75.0)

    @patch("falgen.tools.leaderboard.httpx.get")
    def test_specializations_included(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_IMAGE_MODELS
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = self.tool.execute({"category": "text-to-image"})
        alpha = result["models"][0]
        self.assertIn("best_at", alpha)
        self.assertEqual(alpha["best_at"][0]["category"], "Photorealistic")

    @patch("falgen.tools.leaderboard.httpx.get")
    def test_null_price_omitted(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_IMAGE_MODELS
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = self.tool.execute({"category": "text-to-image"})
        gamma = result["models"][2]  # pricePer1kImages is None
        self.assertNotIn("price", gamma)

    def test_tool_discovery(self):
        from falgen.tools import discover_tools
        registry = discover_tools()
        tool = registry.get("best_models")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "best_models")


if __name__ == "__main__":
    unittest.main()
