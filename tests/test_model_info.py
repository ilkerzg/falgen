"""Tests for model_info tool and JSON Schema $ref resolution."""

import unittest
from unittest.mock import patch, MagicMock

from falgen.tools.info import ModelInfoTool, _resolve_refs


class TestResolveRefs(unittest.TestCase):
    def test_simple_ref(self):
        schema = {
            "definitions": {"Size": {"type": "string", "enum": ["small", "large"]}},
            "properties": {
                "size": {"$ref": "#/definitions/Size"},
            },
        }
        resolved = _resolve_refs(schema)
        self.assertEqual(resolved["properties"]["size"]["type"], "string")
        self.assertEqual(resolved["properties"]["size"]["enum"], ["small", "large"])

    def test_nested_ref(self):
        schema = {
            "definitions": {
                "Inner": {"type": "integer"},
                "Outer": {"type": "object", "properties": {"val": {"$ref": "#/definitions/Inner"}}},
            },
            "properties": {"data": {"$ref": "#/definitions/Outer"}},
        }
        resolved = _resolve_refs(schema)
        self.assertEqual(resolved["properties"]["data"]["properties"]["val"]["type"], "integer")

    def test_missing_ref(self):
        schema = {"properties": {"x": {"$ref": "#/definitions/Missing"}}}
        resolved = _resolve_refs(schema)
        self.assertEqual(resolved["properties"]["x"]["type"], "object")

    def test_no_refs(self):
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        resolved = _resolve_refs(schema)
        self.assertEqual(resolved, schema)

    def test_list_items(self):
        schema = {
            "definitions": {"Item": {"type": "string"}},
            "items": [{"$ref": "#/definitions/Item"}, {"type": "number"}],
        }
        resolved = _resolve_refs(schema)
        self.assertEqual(resolved["items"][0]["type"], "string")
        self.assertEqual(resolved["items"][1]["type"], "number")

    def test_ref_with_extra_fields(self):
        schema = {
            "definitions": {"Base": {"type": "string"}},
            "properties": {"x": {"$ref": "#/definitions/Base", "description": "custom"}},
        }
        resolved = _resolve_refs(schema)
        self.assertEqual(resolved["properties"]["x"]["type"], "string")
        self.assertEqual(resolved["properties"]["x"]["description"], "custom")

    def test_definitions_stripped(self):
        schema = {"definitions": {"A": {"type": "string"}}, "type": "object"}
        resolved = _resolve_refs(schema)
        self.assertNotIn("definitions", resolved)
        self.assertNotIn("$defs", resolved)


class TestModelInfoTool(unittest.TestCase):
    def setUp(self):
        self.tool = ModelInfoTool()

    def test_schema(self):
        schema = self.tool.to_openai_schema()
        self.assertEqual(schema["function"]["name"], "model_info")
        self.assertIn("endpoint_id", schema["function"]["parameters"]["properties"])

    @patch("falgen.auth.api_get")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key x"})
    def test_successful_model_info(self, mock_auth, mock_api):
        mock_api.return_value = {
            "models": [{
                "endpoint_id": "fal-ai/flux/dev",
                "metadata": {
                    "display_name": "FLUX Dev",
                    "description": "Fast image gen",
                    "category": "text-to-image",
                },
                "input_schema": {
                    "type": "object",
                    "properties": {"prompt": {"type": "string"}},
                },
            }]
        }

        result = self.tool.execute({"endpoint_id": "fal-ai/flux/dev"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["name"], "FLUX Dev")
        self.assertIn("input_schema", result)

    @patch("falgen.auth.api_get")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key x"})
    def test_model_not_found(self, mock_auth, mock_api):
        mock_api.return_value = {"models": []}

        result = self.tool.execute({"endpoint_id": "fal-ai/nonexistent"})
        self.assertFalse(result["ok"])
        self.assertIn("not found", result["error"])

    @patch("falgen.auth.api_get")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key x"})
    def test_api_error(self, mock_auth, mock_api):
        mock_api.side_effect = Exception("timeout")

        result = self.tool.execute({"endpoint_id": "fal-ai/flux/dev"})
        self.assertFalse(result["ok"])
        self.assertIn("Failed", result["error"])

    @patch("falgen.auth.api_get")
    @patch("falgen.auth.get_auth_headers", return_value={"Authorization": "Key x"})
    def test_openapi_schema_extraction(self, mock_auth, mock_api):
        mock_api.return_value = {
            "models": [{
                "endpoint_id": "fal-ai/flux/dev",
                "metadata": {},
                "openapi": {
                    "paths": {
                        "/": {
                            "post": {
                                "requestBody": {
                                    "content": {
                                        "application/json": {
                                            "schema": {
                                                "type": "object",
                                                "properties": {"prompt": {"type": "string"}},
                                            }
                                        }
                                    }
                                },
                                "responses": {
                                    "200": {
                                        "content": {
                                            "application/json": {
                                                "schema": {"type": "object", "properties": {"url": {"type": "string"}}}
                                            }
                                        }
                                    }
                                },
                            }
                        }
                    },
                    "components": {"schemas": {}},
                },
            }]
        }

        result = self.tool.execute({"endpoint_id": "fal-ai/flux/dev"})
        self.assertTrue(result["ok"])
        self.assertIn("input_schema", result)
        self.assertIn("output_schema", result)
        self.assertNotIn("openapi", result)  # should be removed


if __name__ == "__main__":
    unittest.main()
