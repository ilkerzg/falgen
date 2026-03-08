"""best_models tool — quality rankings from Artificial Analysis arena."""

import httpx

from .base import Tool

# Public arena preference endpoints (no auth required)
_ENDPOINTS = {
    "text-to-image": "https://artificialanalysis.ai/api/text-to-image/arena/preferences?supports_image_input=false",
    "image-editing": "https://artificialanalysis.ai/api/text-to-image/arena/preferences?supports_image_input=true",
    "text-to-video": "https://artificialanalysis.ai/api/text-to-video/arena/preferences?supports-image-input=false",
    "image-to-video": "https://artificialanalysis.ai/api/text-to-video/arena/preferences?supports-image-input=true",
    "text-to-speech": "https://artificialanalysis.ai/api/text-to-speech/arena/preferences",
}

_VALID_CATEGORIES = list(_ENDPOINTS.keys())


def _get_tag_label(elo_entry: dict) -> str | None:
    """Extract the tag/category label from an ELO entry."""
    tag = elo_entry.get("tag") or elo_entry.get("category")
    if tag is None:
        return None
    if isinstance(tag, dict):
        return tag.get("label") or tag.get("slug")
    return str(tag) if tag else None


def _extract_elo_for_style(model: dict, style: str) -> float | None:
    """Extract ELO for a specific style/tag. Fuzzy matches the style query."""
    style_lower = style.lower()
    best_match = None
    best_elo = None

    for elo_entry in model.get("elos", []):
        label = _get_tag_label(elo_entry)
        if label is None:
            continue
        label_lower = label.lower()
        # Exact match or substring match
        if style_lower in label_lower or label_lower in style_lower:
            elo = elo_entry.get("elo")
            if elo is not None and (best_elo is None or elo > best_elo):
                best_elo = elo
                best_match = label
    return best_elo


def _extract_overall_elo(model: dict) -> float | None:
    """Extract the overall (untagged) ELO from model's elos array."""
    for elo_entry in model.get("elos", []):
        tag = elo_entry.get("tag") or elo_entry.get("category") or elo_entry.get("accent")
        if tag is None:
            return elo_entry.get("elo")
    if model.get("elos"):
        return model["elos"][0].get("elo")
    return None


def _extract_win_rate(model: dict, style: str | None = None) -> float | None:
    """Extract win rate for a style or overall."""
    if style:
        style_lower = style.lower()
        for elo_entry in model.get("elos", []):
            label = _get_tag_label(elo_entry)
            if label and style_lower in label.lower():
                return elo_entry.get("winRate")
    # Fallback to overall
    for elo_entry in model.get("elos", []):
        tag = elo_entry.get("tag") or elo_entry.get("category")
        if tag is None:
            return elo_entry.get("winRate")
    return None


def _extract_specializations(model: dict, top_n: int = 3) -> list[dict]:
    """Extract top specialized ELO categories (non-overall)."""
    specs = []
    for elo_entry in model.get("elos", []):
        label = _get_tag_label(elo_entry)
        if label is None:
            continue
        specs.append({
            "category": label,
            "elo": round(elo_entry.get("elo", 0), 1),
            "win_rate": round(elo_entry.get("winRate", 0) * 100, 1),
        })
    specs.sort(key=lambda x: x["elo"], reverse=True)
    return specs[:top_n]


def _collect_all_styles(raw_models: list[dict]) -> list[str]:
    """Collect all unique style/tag labels from models."""
    styles = set()
    for m in raw_models:
        for elo_entry in m.get("elos", []):
            label = _get_tag_label(elo_entry)
            if label:
                styles.add(label)
    return sorted(styles)


class BestModelsTool(Tool):
    name = "best_models"
    description = (
        "Get quality-ranked AI models from Artificial Analysis arena leaderboard. "
        "Returns models sorted by ELO rating (crowd-sourced blind comparisons). "
        "Use this BEFORE choosing which model to run — it tells you which models "
        "produce the best results for each category. "
        "Categories: text-to-image, image-editing, text-to-video, image-to-video, text-to-speech. "
        "Use the 'style' parameter to rank by a specific style/subject instead of overall quality. "
        "Examples: style='portrait' for people/portraits, style='anime' for anime, "
        "style='photorealistic' for photos, style='fantasy' for fantasy art."
    )
    parameters = {
        "properties": {
            "category": {
                "type": "string",
                "enum": _VALID_CATEGORIES,
                "description": "Media generation category to get rankings for.",
            },
            "style": {
                "type": "string",
                "description": (
                    "Optional style/subject to rank by instead of overall quality. "
                    "Fuzzy matched against available tags. Examples: portrait, anime, "
                    "photorealistic, fantasy, cartoon, text, landscape, action, etc. "
                    "If the style doesn't match any tag, falls back to overall ranking "
                    "and returns available_styles so you can try again."
                ),
            },
            "top_n": {
                "type": "integer",
                "description": "Number of top models to return (default 5, max 20).",
                "default": 5,
            },
        },
        "required": ["category"],
    }

    def execute(self, args: dict) -> dict:
        category = args.get("category", "")
        if category not in _ENDPOINTS:
            return {
                "ok": False,
                "error": f"Unknown category: {category}",
                "valid_categories": _VALID_CATEGORIES,
            }

        top_n = min(args.get("top_n", 5), 20)
        style = args.get("style", "").strip() or None
        url = _ENDPOINTS[category]

        try:
            resp = httpx.get(url, timeout=15, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return {"ok": False, "error": f"Failed to fetch leaderboard: {e}"}

        raw_models = data.get("models", [])
        if not raw_models:
            return {"ok": False, "error": "No models found in response"}

        # Check if style matches any tags
        using_style = False
        if style:
            # Check if any model has this style tag
            style_lower = style.lower()
            has_match = any(
                any(
                    (label := _get_tag_label(e)) and style_lower in label.lower()
                    for e in m.get("elos", [])
                )
                for m in raw_models
            )
            if has_match:
                using_style = True
            else:
                # No match — return available styles
                available = _collect_all_styles(raw_models)
                return {
                    "ok": True,
                    "category": category,
                    "style_not_found": style,
                    "available_styles": available,
                    "hint": "Try one of the available_styles listed above.",
                }

        # Build ranked list
        ranked = []
        for m in raw_models:
            if using_style:
                elo = _extract_elo_for_style(m, style)
                if elo is None:
                    continue  # model doesn't have this style
            else:
                elo = _extract_overall_elo(m)
                if elo is None:
                    continue

            creator = m.get("creator", {})
            price_key = (
                "pricePer1kImages" if "pricePer1kImages" in m
                else "pricePerMinute" if "pricePerMinute" in m
                else "pricePer1MCharacters" if "pricePer1MCharacters" in m
                else None
            )

            entry = {
                "name": m.get("name", ""),
                "creator": creator.get("name", ""),
                "elo": round(elo, 1),
                "is_current": m.get("isCurrent", False),
            }

            # Win rate
            win_rate = _extract_win_rate(m, style if using_style else None)
            if win_rate is not None:
                entry["win_rate"] = round(win_rate * 100, 1)

            if price_key and m.get(price_key) is not None:
                entry["price"] = m[price_key]
                entry["price_unit"] = {
                    "pricePer1kImages": "per 1k images",
                    "pricePerMinute": "per minute",
                    "pricePer1MCharacters": "per 1M characters",
                }.get(price_key, "")

            # Top specializations (only when not filtering by style)
            if not using_style:
                specs = _extract_specializations(m)
                if specs:
                    entry["best_at"] = specs

            ranked.append(entry)

        # Sort by ELO descending
        ranked.sort(key=lambda x: x["elo"], reverse=True)
        ranked = ranked[:top_n]

        for i, entry in enumerate(ranked, 1):
            entry["rank"] = i

        result = {
            "ok": True,
            "category": category,
            "source": "Artificial Analysis Arena (crowd-sourced blind comparisons)",
            "models": ranked,
            "total_evaluated": len(raw_models),
            "note": "Use search_models to find the fal.ai endpoint for any model listed here, then generate.",
        }
        if using_style:
            result["ranked_by_style"] = style
        return result
