"""Standalone authentication for falgen.

Supports:
  1. FAL_KEY environment variable
  2. Cached API key at ~/.cache/falgen/api_key

No dependency on fal SDK.
"""

import os

import httpx

FAL_API_BASE = "https://api.fal.ai/v1"

_CACHE_DIR = os.path.expanduser("~/.cache/falgen")
_CACHED_KEY_FILE = os.path.join(_CACHE_DIR, "api_key")


def _read_cached_key() -> str | None:
    """Read cached API key from disk."""
    try:
        with open(_CACHED_KEY_FILE) as f:
            key = f.read().strip()
            if key:
                return key
    except FileNotFoundError:
        pass
    return None


def save_key(key: str) -> None:
    """Save API key to cache."""
    os.makedirs(_CACHE_DIR, exist_ok=True)
    with open(_CACHED_KEY_FILE, "w") as f:
        f.write(key.strip())
    os.chmod(_CACHED_KEY_FILE, 0o600)


def get_auth_headers() -> dict[str, str]:
    """Get auth headers. Checks FAL_KEY env var, then cached key."""
    headers: dict[str, str] = {}

    # 1. FAL_KEY env var
    fal_key = os.environ.get("FAL_KEY", "").strip()
    if fal_key:
        if ":" in fal_key:
            headers["Authorization"] = f"Key {fal_key}"
        else:
            headers["Authorization"] = f"Key {fal_key}"
        return headers

    # 2. Cached key
    cached = _read_cached_key()
    if cached:
        if ":" in cached:
            headers["Authorization"] = f"Key {cached}"
        else:
            headers["Authorization"] = f"Key {cached}"
        return headers

    return headers


def api_get(path: str, params=None, headers=None, timeout: int = 15):
    """Make a GET request to the fal API."""
    url = f"{FAL_API_BASE}{path}"
    resp = httpx.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def api_delete(path: str, headers=None, timeout: int = 15):
    """Make a DELETE request to the fal API."""
    url = f"{FAL_API_BASE}{path}"
    resp = httpx.delete(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, json_data=None, headers=None, timeout: int = 15):
    """Make a POST request to the fal API."""
    url = f"{FAL_API_BASE}{path}"
    resp = httpx.post(url, json=json_data, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


FAL_CDN_UPLOAD_URL = "https://v3.fal.media/files/upload"


def upload_file(data: bytes, content_type: str = "image/png", filename: str = "image.png") -> str:
    """Upload file bytes to fal CDN and return the access URL."""
    headers = get_auth_headers()
    if not headers:
        raise RuntimeError("Not authenticated — run /login first")

    headers["Content-Type"] = content_type
    headers["X-Fal-File-Name"] = filename

    resp = httpx.post(FAL_CDN_UPLOAD_URL, content=data, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()["access_url"]
