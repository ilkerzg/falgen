"""model_info tool — direct API call."""

from .base import Tool


def _resolve_refs(obj, definitions=None):
    """Recursively resolve $ref in JSON Schema so Gemini doesn't choke on them."""
    if definitions is None:
        definitions = {}

    if isinstance(obj, dict):
        for key in ("definitions", "$defs", "components"):
            if key in obj and isinstance(obj[key], dict):
                defs = obj[key]
                if key == "components" and "schemas" in defs:
                    defs = defs["schemas"]
                definitions.update(defs)

        if "$ref" in obj:
            ref_path = obj["$ref"]
            ref_name = ref_path.rsplit("/", 1)[-1]
            if ref_name in definitions:
                resolved = dict(definitions[ref_name])
                for k, v in obj.items():
                    if k != "$ref":
                        resolved[k] = v
                return _resolve_refs(resolved, definitions)
            else:
                result = {"type": "object", "description": f"(schema: {ref_name})"}
                for k, v in obj.items():
                    if k != "$ref":
                        result[k] = v
                return result

        return {k: _resolve_refs(v, definitions) for k, v in obj.items()
                if k not in ("definitions", "$defs")}

    if isinstance(obj, list):
        return [_resolve_refs(item, definitions) for item in obj]

    return obj


class ModelInfoTool(Tool):
    name = "model_info"
    description = "Get detailed information about a specific model, including its input parameters (with types, defaults, constraints) and output schema."
    parameters = {
        "properties": {
            "endpoint_id": {
                "type": "string",
                "description": "The model endpoint ID (e.g. 'fal-ai/flux/dev', 'fal-ai/kling-video/v2.5/standard/text-to-video')",
            },
        },
        "required": ["endpoint_id"],
    }

    def execute(self, args: dict) -> dict:
        from ..auth import api_get, get_auth_headers

        headers = get_auth_headers()
        endpoint_id = args["endpoint_id"]

        try:
            data = api_get(
                "/models",
                params={"endpoint_id": endpoint_id, "expand": "openapi-3.0"},
                headers=headers,
                timeout=15,
            )
        except Exception as e:
            return {"ok": False, "error": f"Failed to get model info: {e}"}

        # API may return a list or a single object
        if isinstance(data, list):
            if not data:
                return {"ok": False, "error": f"Model not found: {endpoint_id}"}
            data = data[0]
        elif isinstance(data, dict):
            items = data.get("models", data.get("items", data.get("data", [])))
            if isinstance(items, list):
                if not items:
                    return {"ok": False, "error": f"Model not found: {endpoint_id}"}
                data = items[0]

        result = {"ok": True, "endpoint_id": endpoint_id}

        # Extract fields from metadata if present
        meta = data.get("metadata", {})
        if meta:
            if meta.get("display_name"):
                result["name"] = meta["display_name"]
            if meta.get("description"):
                result["description"] = meta["description"]
            if meta.get("category"):
                result["category"] = meta["category"]

        # Extract useful fields from top level
        for key in ("name", "description", "category", "input_schema", "output_schema", "openapi"):
            if key in data and key not in result:
                result[key] = data[key]

        # Resolve $ref in schemas
        for key in ("input_schema", "output_schema"):
            if key in result and isinstance(result[key], dict):
                result[key] = _resolve_refs(result[key])

        # Try to extract input/output schema from openapi spec
        if "openapi" in result and isinstance(result["openapi"], dict):
            openapi = result["openapi"]
            paths = openapi.get("paths", {})
            components = openapi.get("components", {}).get("schemas", {})

            # Find input schema from POST body
            for path_data in paths.values():
                post = path_data.get("post", {})
                req_body = post.get("requestBody", {})
                content = req_body.get("content", {})
                json_schema = content.get("application/json", {}).get("schema", {})
                if json_schema and "input_schema" not in result:
                    resolved = _resolve_refs(json_schema, dict(components))
                    result["input_schema"] = resolved

                # Find output schema from 200 response
                responses = post.get("responses", {})
                resp_200 = responses.get("200", {})
                resp_content = resp_200.get("content", {})
                resp_schema = resp_content.get("application/json", {}).get("schema", {})
                if resp_schema and "output_schema" not in result:
                    resolved = _resolve_refs(resp_schema, dict(components))
                    result["output_schema"] = resolved

            del result["openapi"]

        # Remove components/definitions if present
        for key in ("components", "definitions", "$defs"):
            result.pop(key, None)

        return result
