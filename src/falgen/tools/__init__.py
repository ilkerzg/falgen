"""Tool registry with explicit imports for PyInstaller compatibility."""

import inspect
import json as json_mod

# Explicit imports — pkgutil.iter_modules doesn't work in frozen binaries
from . import (
    ask_user,
    generate,
    history,
    info,
    leaderboard,
    pricing,
    search,
    skills,
    usage,
    workflows,
)
from .base import Tool

_TOOL_MODULES = [
    ask_user,
    generate,
    search,
    info,
    leaderboard,
    history,
    pricing,
    usage,
    workflows,
    skills,
]


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def execute(self, name: str, arguments, on_progress=None) -> str:
        """Execute a tool by name and return JSON string result."""
        tool = self._tools.get(name)
        if tool is None:
            return json_mod.dumps({"ok": False, "error": f"Unknown tool: {name}"})
        args = arguments if isinstance(arguments, dict) else json_mod.loads(arguments)
        # Pass on_progress if tool supports it (generate, ask_user)
        sig = inspect.signature(tool.execute)
        if "on_progress" in sig.parameters and on_progress:
            data = tool.execute(args, on_progress=on_progress)
        else:
            data = tool.execute(args)
        result = json_mod.dumps(data, default=str)
        # Truncate very large results to avoid API rejections
        max_len = 32000
        if len(result) > max_len:
            truncated = result[:max_len]
            result = json_mod.dumps({
                "ok": data.get("ok", True) if isinstance(data, dict) else True,
                "data_truncated": True,
                "partial": truncated,
                "note": f"Result truncated from {len(json_mod.dumps(data, default=str))} chars to {max_len}",
            })
        return result

    def openai_schemas(self) -> list[dict]:
        return [t.to_openai_schema() for t in self._tools.values()]


def discover_tools() -> ToolRegistry:
    """Register all tools from explicit module list."""
    registry = ToolRegistry()
    for mod in _TOOL_MODULES:
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if isinstance(attr, type) and issubclass(attr, Tool) and attr is not Tool:
                registry.register(attr())
    return registry
