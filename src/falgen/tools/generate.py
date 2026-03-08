"""generate tool — uses queue API directly for live progress."""

import json as json_mod
import time

import httpx

from .base import Tool

QUEUE_BASE = "https://queue.fal.run"


def _build_urls(endpoint_id, request_id):
    parts = endpoint_id.split("/")
    base_app = "/".join(parts[:2]) if len(parts) >= 2 else endpoint_id
    base = f"{QUEUE_BASE}/{base_app}/requests/{request_id}"
    return {
        "status_url": f"{base}/status",
        "response_url": base,
        "cancel_url": f"{base}/cancel",
    }


class GenerateTool(Tool):
    name = "generate"
    description = "Run a model with the given input parameters. Submits the job, waits for completion, and returns the result including output URLs."
    parameters = {
        "properties": {
            "endpoint_id": {
                "type": "string",
                "description": "Model endpoint ID (e.g. 'fal-ai/flux/dev')",
            },
            "input": {
                "type": "object",
                "description": 'Input parameters for the model (e.g. {"prompt": "a cat", "image_size": "landscape_16_9"})',
            },
            "background": {
                "type": "boolean",
                "description": "If true, submit job and return immediately while it runs in background. Use when the user wants to continue chatting during generation.",
                "default": False,
            },
        },
        "required": ["endpoint_id", "input"],
    }

    def execute(self, args: dict, on_progress=None) -> dict:
        endpoint_id = args["endpoint_id"]
        input_data = args.get("input", {})

        # LLMs often put model parameters at the top level instead of inside "input".
        if not input_data:
            known_meta = {"endpoint_id", "input"}
            extra = {k: v for k, v in args.items() if k not in known_meta}
            if extra:
                input_data = extra

        from ..auth import get_auth_headers
        headers = get_auth_headers()
        if not headers:
            return {"ok": False, "error": "Not authenticated"}

        if on_progress:
            on_progress({"state": "SUBMITTING", "endpoint_id": endpoint_id})

        start_time = time.monotonic()

        # Submit
        try:
            url = f"{QUEUE_BASE}/{endpoint_id}"
            resp = httpx.post(url, json=input_data, headers=headers, timeout=30)
            if resp.status_code == 422:
                try:
                    detail = resp.json()
                except Exception:
                    detail = resp.text[:500]
                return {
                    "ok": False,
                    "error": f"422 Validation Error: {detail}",
                    "hint": "Call model_info to check correct parameter names, types, and valid values, then retry.",
                }
            resp.raise_for_status()
            submit_data = resp.json()
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text[:500]
            return {"ok": False, "error": f"HTTP {e.response.status_code}: {detail}"}
        except Exception as e:
            return {"ok": False, "error": f"Submit failed: {e}"}

        request_id = submit_data["request_id"]
        urls = _build_urls(endpoint_id, request_id)

        # Background mode: submit and return immediately
        if args.get("background", False):
            return {
                "ok": True,
                "background": True,
                "request_id": request_id,
                "endpoint_id": endpoint_id,
                "message": f"Generation submitted in background. Task ID: {request_id[:8]}",
                "_task_data": {
                    "endpoint_id": endpoint_id,
                    "request_id": request_id,
                    "urls": urls,
                    "headers": dict(headers),
                },
            }

        status_url = submit_data.get("status_url") or urls["status_url"]
        response_url = submit_data.get("response_url") or urls["response_url"]

        # Poll with progress
        poll_interval = 0.5
        try:
            while True:
                try:
                    status_resp = httpx.get(
                        status_url, params={"logs": 1}, headers=headers, timeout=15
                    )
                    status_resp.raise_for_status()
                    status = status_resp.json()
                except Exception:
                    time.sleep(poll_interval)
                    continue

                state = status.get("status", "UNKNOWN")
                elapsed = time.monotonic() - start_time

                if on_progress:
                    progress = {
                        "state": state,
                        "elapsed": elapsed,
                        "endpoint_id": endpoint_id,
                        "request_id": request_id,
                    }
                    if state == "IN_QUEUE":
                        progress["position"] = status.get("queue_position", "?")
                    elif state == "IN_PROGRESS":
                        progress["logs"] = [
                            log.get("message", "") for log in status.get("logs", [])
                        ]
                    on_progress(progress)

                if state == "COMPLETED":
                    break

                if status.get("error"):
                    error_detail = status.get("error")
                    if isinstance(error_detail, dict):
                        error_msg = json_mod.dumps(error_detail, default=str)[:500]
                    else:
                        error_msg = str(error_detail)[:500]
                    return {
                        "ok": False,
                        "error": f"Execution failed: {error_msg}",
                        "hint": "Check model_info for valid parameters and retry with corrected input.",
                    }

                time.sleep(poll_interval)
                poll_interval = min(poll_interval * 1.2, 2.0)

        except KeyboardInterrupt:
            try:
                cancel_url = submit_data.get("cancel_url") or urls["cancel_url"]
                httpx.put(cancel_url, headers=headers, timeout=15)
            except Exception:
                pass
            return {"ok": False, "error": "Cancelled by user"}

        # Fetch result
        try:
            result_resp = httpx.get(response_url, headers=headers, timeout=60)
            if result_resp.status_code == 422:
                try:
                    detail = result_resp.json()
                except Exception:
                    detail = result_resp.text[:500]
                return {
                    "ok": False,
                    "error": f"Result fetch 422: {detail}",
                    "hint": "The input parameters were likely invalid. Call model_info to check correct params and retry.",
                }
            result_resp.raise_for_status()
            result = result_resp.json()
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text[:500]
            return {"ok": False, "error": f"Result fetch HTTP {e.response.status_code}: {detail}"}
        except Exception as e:
            return {"ok": False, "error": f"Failed to fetch result: {e}"}

        elapsed = time.monotonic() - start_time
        if on_progress:
            on_progress({"state": "COMPLETED", "elapsed": elapsed, "endpoint_id": endpoint_id})

        return {
            "ok": True,
            "request_id": request_id,
            "endpoint_id": endpoint_id,
            "elapsed_seconds": round(elapsed, 1),
            "result": result,
        }
