"""Context window management — summarize older messages when approaching limits."""

import json

# Approximate context limits per model family
CONTEXT_LIMITS = {
    "anthropic/claude": 200000,
    "openai/gpt": 128000,
    "google/gemini": 1000000,
}
DEFAULT_LIMIT = 128000

# Summarize when we hit this fraction of the limit
SUMMARIZE_THRESHOLD = 0.75

# Keep this many recent messages unsummarized
KEEP_RECENT = 10

_SUMMARY_MARKER = "[Summary of earlier conversation]"

_SUMMARIZE_PROMPT = """\
Summarize the conversation above into a concise context block. Include:
- Key facts and user preferences discovered
- Models used and their results (include output URLs)
- Any errors encountered and how they were resolved
- The user's creative direction and style preferences

Be concise. This summary replaces the older messages to save context space.
Output only the summary, no preamble."""


def estimate_tokens(messages: list[dict]) -> int:
    """Rough token estimate: ~3.5 chars per token for mixed content."""
    total_chars = 0
    for msg in messages:
        content = msg.get("content") or ""
        total_chars += len(content)
        if msg.get("tool_calls"):
            total_chars += len(json.dumps(msg["tool_calls"], default=str))
    return int(total_chars / 3.5)


def get_context_limit(model: str) -> int:
    """Get approximate context limit for a model."""
    for prefix, limit in CONTEXT_LIMITS.items():
        if model.startswith(prefix):
            return limit
    return DEFAULT_LIMIT


def needs_summarization(messages: list[dict], model: str) -> bool:
    """Check if messages are approaching the context limit."""
    limit = get_context_limit(model)
    tokens = estimate_tokens(messages)
    return tokens > limit * SUMMARIZE_THRESHOLD


def summarize_messages(messages: list[dict], provider, model: str) -> list[dict]:
    """Summarize older messages to fit within context limits.

    Returns a new message list with older messages replaced by a summary.
    Preserves: system prompt (first), recent messages (last KEEP_RECENT).
    """
    if len(messages) <= KEEP_RECENT + 2:
        return messages  # too few to summarize

    system_prompt = messages[0]  # always keep
    old_messages = messages[1:-KEEP_RECENT]
    recent_messages = messages[-KEEP_RECENT:]

    if not old_messages:
        return messages

    # Build summarization request
    summary_messages = [
        system_prompt,
        *old_messages,
        {"role": "user", "content": _SUMMARIZE_PROMPT},
    ]

    # Call LLM for summarization (non-streaming, collect full response)
    summary_text = ""
    for event_type, data in provider.stream_chat(model, summary_messages, []):
        if event_type == "content":
            summary_text += data
        elif event_type == "error":
            # If summarization fails, just truncate old messages
            return [system_prompt] + recent_messages

    if not summary_text:
        return [system_prompt] + recent_messages

    summary_msg = {
        "role": "assistant",
        "content": f"{_SUMMARY_MARKER}\n\n{summary_text}",
    }

    return [system_prompt, summary_msg] + recent_messages
