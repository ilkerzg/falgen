"""get_pricing tool — direct API call."""

from .base import Tool


class GetPricingTool(Tool):
    name = "get_pricing"
    description = "Get pricing information for one or more models. Shows unit price, unit type, and currency."
    parameters = {
        "properties": {
            "endpoint_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of endpoint IDs to get pricing for",
            },
        },
        "required": ["endpoint_ids"],
    }

    def execute(self, args: dict) -> dict:
        from ..auth import api_get, get_auth_headers

        headers = get_auth_headers()
        if not headers:
            return {"ok": False, "error": "Not authenticated"}

        endpoint_ids = args.get("endpoint_ids", [])
        results = []
        for ep_id in endpoint_ids:
            try:
                data = api_get(
                    "/models/pricing",
                    params={"endpoint_id": ep_id},
                    headers=headers,
                    timeout=15,
                )
                results.append({"endpoint_id": ep_id, **data})
            except Exception as e:
                results.append({"endpoint_id": ep_id, "error": str(e)})

        return {"ok": True, "pricing": results}
