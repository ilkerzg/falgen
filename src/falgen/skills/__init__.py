"""Skill knowledge bases for falgen — loaded on demand by the AI.

Skills are markdown files containing domain knowledge that the LLM can
reference when generating media.
"""

import os
import re
import sys

# PyInstaller frozen binary support: look in _MEIPASS first
if getattr(sys, "_MEIPASS", None):
    SKILLS_DIR = os.path.join(sys._MEIPASS, "skills")
else:
    SKILLS_DIR = os.path.dirname(__file__)

# Skill registry: name → (filename, short description, trigger keywords)
SKILL_CATALOG = {
    "cinematography": (
        "cinematography.md",
        "Hollywood directing techniques, camera movements, lighting, composition, lens choices, color grading",
        ["cinema", "film", "movie", "director", "camera", "lighting", "shot", "lens", "composition", "color grade"],
    ),
    "video_prompting": (
        "video_prompting.md",
        "AI video generation prompt engineering — model-specific tips, motion keywords, artifact prevention",
        ["video", "animate", "motion", "clip", "wan", "kling", "veo", "sora", "luma", "minimax", "hunyuan", "seedance", "ltx", "hailuo"],
    ),
    "image_prompting": (
        "image_prompting.md",
        "AI image generation prompt engineering — style keywords, quality boosters, model-specific tips",
        ["image", "photo", "picture", "illustration", "render", "flux", "sdxl", "midjourney", "dall-e", "portrait", "landscape"],
    ),
    "commercial": (
        "commercial.md",
        "Advertising and commercial production — product shots, brand videos, social media formats",
        ["product", "ad", "commercial", "brand", "marketing", "social media", "instagram", "tiktok", "advertisement"],
    ),
    "audio_prompting": (
        "audio_prompting.md",
        "AI audio/music generation — genre, mood, instruments, sound effects, voice generation",
        ["audio", "music", "sound", "voice", "speech", "song", "soundtrack", "sfx", "tts"],
    ),
    "workflow_utils": (
        "workflow_utils.md",
        "fal.ai workflow utilities — image/video/audio processing, compositing, format conversion",
        ["workflow", "merge", "split", "overlay", "subtitle", "resize", "crop", "mask", "composite", "convert", "gif", "audio extract"],
    ),
    "character_design": (
        "character_design.md",
        "Character creation & consistency — anchor descriptions, multi-view sheets, expressions, costumes, LoRA training, IP-Adapter",
        ["character", "person", "face", "consistent", "identity", "costume", "outfit", "expression", "pose", "character sheet", "turnaround"],
    ),
    "storytelling": (
        "storytelling.md",
        "Multi-shot narrative video production — storyboarding, scene structure, pacing, transitions, shot sequences",
        ["story", "narrative", "storyboard", "scene", "sequence", "multi-shot", "transition", "pacing", "plot", "script"],
    ),
    "social_media": (
        "social_media.md",
        "Platform-optimized content creation — TikTok, Reels, Shorts, hooks, trends, viral formats, engagement",
        ["tiktok", "reels", "shorts", "viral", "hook", "trend", "engagement", "social", "influencer", "content creator"],
    ),
    "motion_design": (
        "motion_design.md",
        "Motion graphics & animation — kinetic typography, logo reveals, transitions, particle effects, UI animation",
        ["motion graphics", "typography", "kinetic", "logo reveal", "transition", "particle", "animation", "title", "lower third", "intro"],
    ),
    "world_building": (
        "world_building.md",
        "Environment & world design — architecture, interior design, landscapes, fantasy/sci-fi worlds, atmosphere",
        ["environment", "world", "architecture", "interior", "landscape", "city", "fantasy world", "sci-fi", "building", "room", "space"],
    ),
    "brand_identity": (
        "brand_identity.md",
        "Visual brand identity — logo design, color systems, typography, brand guidelines, visual consistency",
        ["logo", "brand", "identity", "typography", "color palette", "brand guide", "visual identity", "corporate", "design system"],
    ),
}


_skill_cache: dict[str, str] = {}


def load_skill(name: str) -> str | None:
    """Load a skill's markdown content by name."""
    if name in _skill_cache:
        return _skill_cache[name]
    if name not in SKILL_CATALOG:
        return None
    filename = SKILL_CATALOG[name][0]
    path = os.path.join(SKILLS_DIR, filename)
    if not os.path.isfile(path):
        return None
    with open(path, "r") as f:
        content = f.read()
    _skill_cache[name] = content
    return content


def _slugify(header_text: str) -> str:
    text = header_text.strip().lstrip("#").strip()
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", "_", text.strip())
    return text.strip("_")


def _parse_sections(content: str, level: str = "##") -> list[tuple[str, str, str, int]]:
    prefix = level + " "
    lines = content.split("\n")
    sections = []
    current_header = None
    current_slug = None
    current_lines: list[str] = []

    for line in lines:
        if line.startswith(prefix) and not line.startswith(prefix + "#"):
            if current_header is not None:
                body = "\n".join(current_lines)
                sections.append((current_slug, current_header, body, len(current_lines)))
            current_header = line
            current_slug = _slugify(line)
            current_lines = [line]
        elif current_header is not None:
            current_lines.append(line)

    if current_header is not None:
        body = "\n".join(current_lines)
        sections.append((current_slug, current_header, body, len(current_lines)))

    return sections


_LARGE_SECTION_THRESHOLD = 5000


def load_skill_toc(name: str) -> str | None:
    content = load_skill(name)
    if content is None:
        return None

    lines = content.split("\n")

    title = ""
    intro_lines = []
    for line in lines:
        if line.startswith("# ") and not line.startswith("## ") and not title:
            title = line
        elif line.startswith("## "):
            break
        elif title:
            intro_lines.append(line)

    intro = "\n".join(intro_lines).strip()
    sections = _parse_sections(content)

    quick_ref = ""
    for slug, header, body, _ in sections:
        if slug == "quick_reference":
            quick_ref = body
            break

    parts = [title]
    if intro:
        parts.append(intro)
    parts.append("")

    if quick_ref:
        parts.append(quick_ref)
        parts.append("")

    parts.append("## Available Sections")
    for slug, header, _, line_count in sections:
        if slug == "quick_reference":
            continue
        header_text = header.lstrip("#").strip()
        parts.append(f"- **{slug}** — {header_text} ({line_count} lines)")

    parts.append("")
    parts.append(f'Call get_skill("{name}", section="<key>") to load a specific section.')

    return "\n".join(parts)


def _find_section(sections: list, key: str) -> tuple[str, str, str, int] | None:
    for entry in sections:
        if entry[0] == key:
            return entry
    for entry in sections:
        tokens = entry[0].split("_")
        if any(t.startswith(key) for t in tokens):
            return entry
    return None


def _build_section_toc(name: str, h2_slug: str, h2_header: str, h3_sections: list) -> str:
    parts = [h2_header.strip()]
    parts.append("")
    parts.append(f"This section has {len(h3_sections)} subsections. Load one at a time:")
    parts.append("")
    for slug, header, _, line_count in h3_sections:
        header_text = header.lstrip("#").strip()
        parts.append(f"- **{slug}** — {header_text} ({line_count} lines)")
    parts.append("")
    parts.append(f'Call get_skill("{name}", section="{h3_sections[0][0]}") to load a subsection.')
    return "\n".join(parts)


def load_skill_section(name: str, section_key: str) -> str | None:
    content = load_skill(name)
    if content is None:
        return None

    h2_sections = _parse_sections(content, level="##")
    key = section_key.lower().strip()

    for h2_slug, h2_header, h2_body, _ in h2_sections:
        h3_sections = _parse_sections(h2_body, level="###")
        if h3_sections:
            match = _find_section(h3_sections, key)
            if match:
                return match[2]

    h2_match = _find_section(h2_sections, key)
    if h2_match:
        h2_slug, h2_header, h2_body, _ = h2_match
        if len(h2_body) < _LARGE_SECTION_THRESHOLD:
            return h2_body
        h3_sections = _parse_sections(h2_body, level="###")
        if h3_sections:
            return _build_section_toc(name, h2_slug, h2_header, h3_sections)
        return h2_body

    available = []
    for h2_slug, _, h2_body, _ in h2_sections:
        available.append(h2_slug)
        for h3_slug, _, _, _ in _parse_sections(h2_body, level="###"):
            available.append(f"  {h3_slug}")
    return f"Section '{section_key}' not found. Available sections:\n" + "\n".join(available)


def find_relevant_skills(query: str) -> list[str]:
    query_lower = query.lower()
    matches = []
    for name, (_, _, keywords) in SKILL_CATALOG.items():
        if any(kw in query_lower for kw in keywords):
            matches.append(name)
    return matches


def list_skills() -> list[dict]:
    result = []
    for name, (filename, description, _) in SKILL_CATALOG.items():
        path = os.path.join(SKILLS_DIR, filename)
        result.append({
            "name": name,
            "description": description,
            "available": os.path.isfile(path),
        })
    return result
