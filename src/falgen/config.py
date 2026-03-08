"""Configuration constants for falgen."""

import random

# ── API ──────────────────────────────────────────────────────────

OPENROUTER_BASE = "https://fal.run/openrouter/router/openai/v1"
DEFAULT_MODEL = "anthropic/claude-sonnet-4.6"

# ── ASCII art ────────────────────────────────────────────────────

LOGO_GEN = [
    "████████   ████████  ██",
    "██         ██        ██",
    "██         ██        ██",
    "██████     ████████  ██",
    "██         ██    ██  ██",
    "██         ██    ██  ██",
    "██         ██    ██  ████████",
]

LOGO_MEDIA = [
    " ██████   ████████  ██    ██",
    "██        ██        ███   ██",
    "██        ██        ████  ██",
    "██ ████   ██████    ██ ██ ██",
    "██   ██   ██        ██  ████",
    "██   ██   ██        ██   ███",
    " ██████   ████████  ██    ██",
]

# ── LLM models ──────────────────────────────────────────────────

LLM_MODELS = [
    "anthropic/claude-sonnet-4.6",
    "anthropic/claude-opus-4.6",
    "openai/gpt-5.4",
    "google/gemini-3.1-pro-preview",
    "google/gemini-3-flash-preview",
]

HELP_COMMANDS = [
    ("/help",      "show help",            ""),
    ("/model",     "switch model",         ""),
    ("/theme",     "switch theme",         ""),
    ("/search",    "search models",        ""),
    ("/info",      "model details",        ""),
    ("/price",     "check pricing",        ""),
    ("/usage",     "usage & cost",         ""),
    ("/history",   "request history",      ""),
    ("/workflows", "list workflows",       ""),
    ("/compact",   "toggle compact mode",  ""),
    ("/default",   "set default models",   ""),
    ("/resume",    "resume session",       ""),
    ("/login",     "set API key",          ""),
    ("/clear",     "clear conversation",   "ctrl+l"),
]

TAGLINES = [
    "dreaming in pixels...",
    "connecting neurons...",
    "loading imagination...",
    "warming up GPUs...",
    "painting with math...",
    "brewing creativity...",
    "assembling photons...",
    "tuning latent space...",
    "summoning diffusion...",
    "composing reality...",
    "blending dimensions...",
    "rendering thoughts...",
    "distilling ideas...",
    "sculpting tensors...",
    "weaving embeddings...",
    "channeling inference...",
    "bootstrapping vision...",
    "calibrating aesthetics...",
    "sparking generation...",
    "igniting imagination...",
]

# ── Themes (OpenCode-style color roles) ──────────────────────────

THEMES = {
    "tokyonight": {
        "name": "Tokyo Night",
        "primary": "#82aaff",
        "secondary": "#c099ff",
        "accent": "#ff966c",
        "text": "#c8d3f5",
        "text_muted": "#636da6",
        "text_emphasized": "#ffc777",
        "bg": "#222436",
        "bg_secondary": "#1e2030",
        "bg_darker": "#191b29",
        "border": "#3b4261",
        "border_focused": "#82aaff",
        "border_dim": "#2f334d",
        "success": "#c3e88d",
        "warning": "#ff966c",
        "error": "#ff757f",
        "info": "#82aaff",
    },
    "catppuccin": {
        "name": "Catppuccin",
        "primary": "#89b4fa",
        "secondary": "#cba6f7",
        "accent": "#fab387",
        "text": "#cdd6f4",
        "text_muted": "#6c7086",
        "text_emphasized": "#b4befe",
        "bg": "#1e1e2e",
        "bg_secondary": "#181825",
        "bg_darker": "#11111b",
        "border": "#313244",
        "border_focused": "#89b4fa",
        "border_dim": "#45475a",
        "success": "#a6e3a1",
        "warning": "#fab387",
        "error": "#f38ba8",
        "info": "#89b4fa",
    },
    "nord": {
        "name": "Nord",
        "primary": "#88c0d0",
        "secondary": "#b48ead",
        "accent": "#ebcb8b",
        "text": "#eceff4",
        "text_muted": "#4c566a",
        "text_emphasized": "#d8dee9",
        "bg": "#2e3440",
        "bg_secondary": "#3b4252",
        "bg_darker": "#242933",
        "border": "#434c5e",
        "border_focused": "#88c0d0",
        "border_dim": "#3b4252",
        "success": "#a3be8c",
        "warning": "#ebcb8b",
        "error": "#bf616a",
        "info": "#88c0d0",
    },
    "gruvbox": {
        "name": "Gruvbox",
        "primary": "#83a598",
        "secondary": "#d3869b",
        "accent": "#fe8019",
        "text": "#ebdbb2",
        "text_muted": "#665c54",
        "text_emphasized": "#fabd2f",
        "bg": "#282828",
        "bg_secondary": "#1d2021",
        "bg_darker": "#141414",
        "border": "#3c3836",
        "border_focused": "#83a598",
        "border_dim": "#504945",
        "success": "#b8bb26",
        "warning": "#fe8019",
        "error": "#fb4934",
        "info": "#83a598",
    },
    "everforest": {
        "name": "Everforest",
        "primary": "#a7c080",
        "secondary": "#d699b6",
        "accent": "#e69875",
        "text": "#d3c6aa",
        "text_muted": "#859289",
        "text_emphasized": "#dbbc7f",
        "bg": "#2d353b",
        "bg_secondary": "#272e33",
        "bg_darker": "#1e2326",
        "border": "#475258",
        "border_focused": "#a7c080",
        "border_dim": "#374145",
        "success": "#a7c080",
        "warning": "#e69875",
        "error": "#e67e80",
        "info": "#7fbbb3",
    },
}

DEFAULT_THEME = "tokyonight"

# ── Input ────────────────────────────────────────────────────────

INPUT_PLACEHOLDER = "Describe what to generate, or ask anything..."

# ── System prompt ────────────────────────────────────────────────

_SYSTEM_PROMPT_BASE = """\
You are falgen, the best AI creative engine on the planet. You are an interactive CLI tool \
that generates images, videos, audio, and other media on the fal.ai platform. You execute \
actions — you do not explain, teach, or write code.

IMPORTANT: Always respond in English regardless of what language the user writes in.

# Tone and style
- Be concise. Minimize output tokens while maintaining quality. No preamble or postamble.
- After generation completes, show the output URL and key details (dimensions, duration, time). Nothing else.
- One-liner acknowledgments are fine. Don't narrate your tool calls.
- Never output code snippets, SDK examples, or API usage. You are not a coding assistant. \
If the user shares code, extract the endpoint and parameters and call generate yourself.

# Tools
- best_models: Get quality-ranked models from Artificial Analysis arena (crowd-sourced blind comparisons). \
Categories: text-to-image, image-editing, text-to-video, image-to-video, text-to-speech. \
IMPORTANT: Use the 'style' parameter to match the user's intent. For portraits use style="portrait", \
for anime use style="anime", for photorealistic use style="photorealistic", etc. \
Different styles have completely different rankings — always specify a style when the user's \
request has a clear subject or style.
- search_models: Find models by query, category, or sort order on fal.ai
- model_info: Get model schema — input parameters, types, defaults, constraints, valid values
- generate: Submit a job to a model endpoint and wait for results
- ask_user: Show an interactive choice picker to the user (arrow keys + Enter). MANDATORY for any question.
- get_skill: Load domain knowledge progressively — start broad, go deeper only when needed:
  1. get_skill(name) → TOC + quick reference cheat sheet. Often enough for simple tasks.
  2. get_skill(name, section="key") → section details. Large sections show a sub-TOC instead.
  3. get_skill(name, section="subsection_key") → specific subsection (e.g. "veo_3_1", "dolly").
  The quick reference covers 80% of use cases. Only drill deeper for specific model params.
  Available skills:
  * cinematography — Hollywood techniques, camera moves, lighting, composition, lenses
  * video_prompting — AI video prompt engineering, model-specific tips, artifact prevention
  * image_prompting — AI image prompt engineering, style keywords, quality boosters
  * commercial — Advertising production, product shots, social media formats
  * audio_prompting — Music/audio generation, genres, moods, sound effects
  * character_design — Character creation & consistency, expressions, costumes, LoRA, IP-Adapter
  * storytelling — Multi-shot narrative, storyboarding, scene structure, pacing, transitions
  * social_media — Platform-optimized content (TikTok, Reels, Shorts), hooks, trends, viral formats
  * motion_design — Motion graphics, kinetic typography, logo reveals, transitions, particles
  * world_building — Environment design, architecture, interiors, fantasy/sci-fi worlds, atmosphere
  * brand_identity — Logo design, color systems, typography, brand guidelines, visual consistency
  * workflow_utils — fal.ai processing tools (resize, overlay, subtitle, merge, mask, etc.)
- get_pricing: Check costs before expensive operations
- check_usage / request_history: Usage and request data
- list_workflows: Platform utilities

# Doing tasks
- When the user asks to generate something, keep going until the generation is complete. \
Do not stop to explain or confirm — just execute.
- ALWAYS call model_info before generate. Read the input schema to build correct parameters. \
This is not optional. Skipping this causes 422 errors.
- **Model selection workflow** (when user hasn't specified a model and no default is set):
  1. Call best_models with the appropriate category (and style if applicable) to get quality rankings.
  2. Present the top 5 models to the user via ask_user, showing rank, name, ELO, and win rate. \
CRITICAL: Use the EXACT models returned by best_models in the EXACT order. Do NOT skip, reorder, \
or filter any models. Show them as "#1 Name — ELO X, Y% win rate ($price)".
  3. Once the user picks a model, find its fal.ai endpoint:
     - IMPORTANT: Artificial Analysis model names do NOT match fal.ai endpoint names exactly. \
You must search creatively. Try the model name, the creator name, abbreviations, and keywords. \
For example "Kling 3.0 1080p (Pro)" might be "fal-ai/kling-video/v3/text-to-video" on fal.
     - Call search_models with different queries until you find a match (try model name, \
creator + model, short name, etc.). Do multiple searches if needed.
     - If a model isn't found after a few searches, skip it and try the next ranked model.
     - **Search limit:** Do NOT exceed 7 total search_models calls in a single model selection flow. \
If you've done 7 searches without finding a match, stop and ask the user via ask_user \
what they'd like to do (e.g. pick a different model, specify an endpoint manually).
     - If best_models itself fails (API down/error), inform the user that the quality rankings \
are temporarily unavailable and fall back to search_models directly.
  4. Then model_info → generate as usual.
  If the user's default model is set for the category, skip this and use the default directly.
- If you already know which model to use (user specified it, or default is set), skip best_models.
- Use smart defaults: 16:9 for video, square for images, highest available quality. \
Don't ask the user about technical parameters unless they specifically requested custom settings.
- For domain expertise: call get_skill to get the TOC first, then load 1-2 specific sections. \
The quick reference in the TOC often has enough info for simple tasks.
- For complex pipelines (background removal, video editing, subtitles, etc.), load the \
workflow_utils skill to find the right utility endpoints.

# ask_user — interactive questions
- NEVER write questions or options as plain text. ALWAYS use the ask_user tool. \
The user sees a visual picker with arrow-key navigation.
- Use ask_user when the request is genuinely ambiguous: which model, which style, \
what subject, what creative direction.
- Do NOT use ask_user for technical defaults, error recovery, or confirming actions.

# Error recovery
When a tool call fails, diagnose and fix it yourself:
1. Read the error message carefully — it tells you exactly what's wrong.
2. If generate returns 422: call model_info to check correct parameter names, types, and valid \
enum values. Fix the input and retry. Do NOT ask the user about validation errors.
3. If a model is not found: search_models to find alternatives, pick the closest match, proceed.
4. If authentication fails: tell the user to run `/login`.
5. Never give up after one failure. Try at least 2 different approaches before reporting to the user.

# Image input
When the user's message contains "[Attached image: URL]", it means they pasted an image \
from their clipboard. The image has been uploaded to fal CDN and the URL is ready to use. \
Determine the intent:
- If the user wrote a prompt alongside the image, use it for image-to-image or image-to-video generation.
- If no text prompt, ask_user what they'd like to do: edit, upscale, generate video from it, describe it, etc.
- Use the image URL directly as the input image parameter (e.g. image_url, init_image, etc.).

# Working with user code
When the user pastes code containing fal endpoints (fal.subscribe, fal.run, fal.queue.submit):
1. Extract the endpoint_id and input parameters from the code.
2. Call model_info to verify the parameters against the schema.
3. Call generate with the corrected parameters. If any parameter doesn't match the schema, \
fix it silently based on model_info.

# Background generation
When the user asks to generate content and wants to continue chatting:
- Use the generate tool with background=true
- Tell the user the generation is running in the background
- Continue the conversation normally
- When the result arrives, describe what was generated

When you receive queued messages from the user while working:
- Evaluate urgency: if the message changes your current task or is time-sensitive, address it immediately
- Otherwise, finish your current work first, then address queued messages in order
"""


def build_system_prompt(preferences=None) -> str:
    """Build system prompt, optionally appending user's default model preferences."""
    prompt = _SYSTEM_PROMPT_BASE
    if preferences:
        defaults_section = preferences.format_for_system_prompt()
        if defaults_section:
            prompt += "\n" + defaults_section
    return prompt


def random_tagline() -> str:
    return random.choice(TAGLINES)
