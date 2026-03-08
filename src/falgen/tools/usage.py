"""check_usage tool — direct API call."""

from .base import Tool


class CheckUsageTool(Tool):
    name = "check_usage"
    description = "View usage and cost data. Can show summary by endpoint or time series. Useful for checking how much has been spent."
    parameters = {
        "properties": {
            "start": {
                "type": "string",
                "description": "Start date in ISO8601 format (e.g. '2025-01-01')",
            },
            "end": {
                "type": "string",
                "description": "End date in ISO8601 format",
            },
            "summary": {
                "type": "boolean",
                "description": "If true, return summary grouped by endpoint instead of time series",
                "default": True,
            },
            "endpoint_id": {
                "type": "string",
                "description": "Filter usage to a specific endpoint ID",
            },
        },
    }

    def execute(self, args: dict) -> dict:
        from ..auth import api_get, get_auth_headers

        headers = get_auth_headers()
        if not headers:
            return {"ok": False, "error": "Not authenticated"}

        params = {}
        expand = []
        if args.get("summary", True):
            expand.append("summary")
        if expand:
            params["expand"] = expand
        if args.get("start"):
            params["start"] = args["start"]
        if args.get("end"):
            params["end"] = args["end"]
        if args.get("endpoint_id"):
            params["endpoint_id"] = args["endpoint_id"]

        try:
            data = api_get("/models/usage", params=params, headers=headers, timeout=15)
        except Exception as e:
            return {"ok": False, "error": f"Failed to get usage: {e}"}

        return {"ok": True, **data}
