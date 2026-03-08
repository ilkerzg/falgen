"""search_models tool — direct API call."""

from .base import Tool


class SearchModelsTool(Tool):
    name = "search_models"
    description = "Search for AI models on the fal platform. Returns a list of matching models with endpoint IDs, names, categories, and descriptions."
    parameters = {
        "properties": {
            "query": {
                "type": "string",
                "description": "Free-text search query (e.g. 'text to image', 'video generation', 'flux')",
            },
            "category": {
                "type": "string",
                "description": "Filter by category (e.g. text-to-image, image-to-video, text-to-video, image-to-image)",
            },
            "sort": {
                "type": "string",
                "enum": ["newest", "oldest", "updated", "name"],
                "description": "Sort order for results",
            },
        },
    }

    def execute(self, args: dict) -> dict:
        from ..auth import api_get, get_auth_headers

        headers = get_auth_headers()

        params = {"limit": 15}
        if args.get("query"):
            params["q"] = args["query"]
        if args.get("category"):
            params["category"] = args["category"]

        try:
            data = api_get("/models", params=params, headers=headers, timeout=15)
        except Exception as e:
            return {"ok": False, "error": f"Search failed: {e}"}

        items = data if isinstance(data, list) else data.get("models", data.get("items", data.get("data", [])))
        results = []
        for item in items[:15]:
            meta = item.get("metadata", {})
            results.append({
                "endpoint_id": item.get("endpoint_id", item.get("id", "")),
                "name": meta.get("display_name", item.get("name", "")),
                "category": meta.get("category", item.get("category", "")),
                "description": (meta.get("description", item.get("description", "")) or "")[:200],
            })

        # Sort locally if requested
        sort_key = args.get("sort")
        if sort_key == "name":
            results.sort(key=lambda x: x["name"].lower())
        elif sort_key == "newest":
            results.reverse()

        return {"ok": True, "models": results, "count": len(results)}
