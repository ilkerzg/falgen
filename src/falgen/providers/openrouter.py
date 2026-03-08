"""OpenRouter streaming provider."""

import json as json_mod
import os
import time
from typing import Iterator

import httpx

from ..config import OPENROUTER_BASE
from . import ProviderBase

_MAX_RETRIES = 2
_CACHE_DIR = os.path.expanduser("~/.cache/falgen")


def _dump_error(body: str, request_body: dict) -> None:
    """Write request + error to disk for debugging."""
    os.makedirs(_CACHE_DIR, exist_ok=True)
    error_path = os.path.join(_CACHE_DIR, "last_error.json")
    debug_msgs = []
    for m in request_body.get("messages", []):
        dm = dict(m)
        if isinstance(dm.get("content"), str) and len(dm["content"]) > 500:
            dm["content"] = dm["content"][:500] + f"... [truncated, total {len(m['content'])} chars]"
        debug_msgs.append(dm)
    with open(error_path, "w") as f:
        json_mod.dump({
            "model": request_body.get("model"),
            "messages": debug_msgs,
            "tools_count": len(request_body.get("tools", [])),
            "error_body": body[:2000],
        }, f, indent=2, default=str)


class OpenRouterProvider(ProviderBase):
    def get_auth_key(self) -> str:
        from ..auth import get_auth_headers
        headers = get_auth_headers()
        return headers.get("Authorization", "")

    def stream_chat(self, model: str, messages: list, tools: list) -> Iterator[tuple]:
        """Generator that yields (type, data) tuples from streaming API response."""
        url = f"{OPENROUTER_BASE}/chat/completions"
        fal_key = self.get_auth_key()
        headers = {"Authorization": fal_key, "Content-Type": "application/json"}

        # Sanitize messages: ensure no None content (Gemini rejects it)
        clean_messages = []
        for m in messages:
            cm = dict(m)
            if cm.get("content") is None:
                cm["content"] = ""
            clean_messages.append(cm)

        body = {"model": model, "messages": clean_messages, "tools": tools, "stream": True}

        collected_content = ""
        tool_calls_map = {}

        for attempt in range(_MAX_RETRIES + 1):
            try:
                with httpx.stream(
                    "POST", url, json=body, headers=headers, timeout=httpx.Timeout(120.0, connect=10.0)
                ) as resp:
                    if resp.status_code >= 500 and attempt < _MAX_RETRIES:
                        resp.read()
                        time.sleep(1 * (attempt + 1))
                        continue

                    if resp.status_code != 200:
                        error_body = resp.read().decode()
                        _dump_error(error_body, body)
                        try:
                            err = json_mod.loads(error_body)
                            error_obj = err.get("error", {})
                            if isinstance(error_obj, dict):
                                error_msg = error_obj.get("message", error_body[:500])
                            else:
                                error_msg = str(error_obj)[:500]
                        except Exception:
                            error_msg = error_body[:500]
                        yield ("error", f"API error ({resp.status_code}): {error_msg}")
                        return

                    for line in resp.iter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break

                        try:
                            chunk = json_mod.loads(data_str)
                        except json_mod.JSONDecodeError:
                            continue

                        choices = chunk.get("choices", [])
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})

                        if delta.get("content"):
                            collected_content += delta["content"]
                            yield ("content", delta["content"])

                        if delta.get("tool_calls"):
                            for tc in delta["tool_calls"]:
                                idx = tc.get("index", 0)
                                if idx not in tool_calls_map:
                                    tool_calls_map[idx] = {
                                        "id": tc.get("id", ""),
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    }
                                if tc.get("id"):
                                    tool_calls_map[idx]["id"] = tc["id"]
                                fn = tc.get("function", {})
                                if fn.get("name"):
                                    tool_calls_map[idx]["function"]["name"] = fn["name"]
                                if fn.get("arguments"):
                                    tool_calls_map[idx]["function"]["arguments"] += fn["arguments"]

                # Successful stream — break out of retry loop
                break

            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                if attempt < _MAX_RETRIES:
                    time.sleep(1 * (attempt + 1))
                    continue
                error_label = "Connection error" if isinstance(e, httpx.ConnectError) else "Request timed out"
                yield ("error", f"{error_label} after {_MAX_RETRIES + 1} attempts: {e}")
                return

        # Build final message
        tool_calls_list = [tool_calls_map[i] for i in sorted(tool_calls_map)] if tool_calls_map else None
        msg = {"role": "assistant"}
        if collected_content:
            msg["content"] = collected_content
        else:
            msg["content"] = ""
        if tool_calls_list:
            msg["tool_calls"] = tool_calls_list
            yield ("tool_calls", tool_calls_list)

        yield ("done", msg)
