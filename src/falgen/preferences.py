"""User preferences — persistent default models per category."""

import json
from pathlib import Path

KNOWN_CATEGORIES = [
    "text-to-image",
    "image-to-image",
    "text-to-video",
    "image-to-video",
    "text-to-audio",
    "text-to-speech",
]

_PREFS_PATH = Path.home() / ".config" / "falgen" / "preferences.json"


class Preferences:
    """Read/write default model preferences to ~/.config/falgen/preferences.json."""

    def __init__(self) -> None:
        self._data: dict = self._load()

    def _load(self) -> dict:
        if _PREFS_PATH.exists():
            try:
                return json.loads(_PREFS_PATH.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save(self) -> None:
        _PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PREFS_PATH.write_text(json.dumps(self._data, indent=2))

    def get_defaults(self) -> dict:
        """Return dict of category → endpoint_id for all set defaults."""
        return dict(self._data.get("defaults", {}))

    def get_default(self, category: str) -> str | None:
        return self._data.get("defaults", {}).get(category)

    def set_default(self, category: str, endpoint_id: str) -> None:
        if "defaults" not in self._data:
            self._data["defaults"] = {}
        self._data["defaults"][category] = endpoint_id
        self._save()

    def format_for_system_prompt(self) -> str:
        """Format current defaults as a section for the system prompt."""
        defaults = self.get_defaults()
        if not defaults:
            return ""
        lines = ["User's default models (use these when no specific model is requested):"]
        for cat, ep in defaults.items():
            lines.append(f"  - {cat}: {ep}")
        return "\n".join(lines) + "\n"
