"""request_history tool — direct API call."""

from .base import Tool


class RequestHistoryTool(Tool):
    name = "request_history"
    description = "List past requests for a specific endpoint. Shows request IDs, status codes, durations, and timestamps. Can filter by request_id and include full payloads (input/output)."
    parameters = {
        "properties": {
            "endpoint_id": {
                "type": "string",
                "description": "Endpoint ID to list requests for",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of requests to return (default: 10)",
            },
            "request_id": {
                "type": "string",
                "description": "Filter to a specific request ID (UUID) to get its details",
            },
            "payloads": {
                "type": "boolean",
                "description": "If true, include full input/output payloads for each request",
            },
        },
        "required": ["endpoint_id"],
    }

    def execute(self, args: dict) -> dict:
        from ..auth import api_get, get_auth_headers

        headers = get_auth_headers()
        if not headers:
            return {"ok": False, "error": "Not authenticated"}

        params = {"endpoint_id": args["endpoint_id"]}
        if args.get("limit"):
            params["limit"] = args["limit"]
        if args.get("request_id"):
            params["request_id"] = args["request_id"]
        if args.get("payloads"):
            params["expand"] = "payload"

        try:
            data = api_get("/models/requests/by-endpoint", params=params, headers=headers, timeout=15)
        except Exception as e:
            return {"ok": False, "error": f"Failed to fetch history: {e}"}

        return {"ok": True, **data}
