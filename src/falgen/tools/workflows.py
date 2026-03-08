"""list_workflows tool — direct API call."""

from .base import Tool


class ListWorkflowsTool(Tool):
    name = "list_workflows"
    description = "List saved workflows. Optionally filter by search query."
    parameters = {
        "properties": {
            "search": {
                "type": "string",
                "description": "Optional search query to filter workflows",
            },
        },
    }

    def execute(self, args: dict) -> dict:
        from ..auth import api_get, get_auth_headers

        headers = get_auth_headers()
        if not headers:
            return {"ok": False, "error": "Not authenticated"}

        params = {}
        if args.get("search"):
            params["search"] = args["search"]

        try:
            data = api_get("/workflows", params=params, headers=headers, timeout=15)
        except Exception as e:
            return {"ok": False, "error": f"Failed to list workflows: {e}"}

        return {"ok": True, **data}
