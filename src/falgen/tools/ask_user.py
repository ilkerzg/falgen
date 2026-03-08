"""ask_user tool — lets the AI ask the user interactive questions with a choice picker."""

import threading

from .base import Tool


class AskUserTool(Tool):
    name = "ask_user"
    description = (
        "MANDATORY for asking questions. Shows an interactive picker UI with arrow-key navigation. "
        "NEVER write questions as text — ALWAYS use this tool instead. "
        "Use for: choosing between models, styles, resolutions, creative directions, or any clarification."
    )
    parameters = {
        "properties": {
            "question": {
                "type": "string",
                "description": "The question to ask the user",
            },
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of options for the user to choose from (2-6 options)",
            },
        },
        "required": ["question", "options"],
    }

    def execute(self, args: dict, on_progress=None) -> dict:
        question = args.get("question", "")
        options = args.get("options", [])

        if not question or not options:
            return {"ok": False, "error": "question and options are required"}

        if on_progress is None:
            return {"ok": False, "error": "ask_user requires UI context (on_progress callback)"}

        event = threading.Event()
        result_holder = [None]

        on_progress({
            "type": "ask_user",
            "question": question,
            "options": options,
            "event": event,
            "result_holder": result_holder,
        })

        # Block until the user picks an option (5 min timeout to prevent deadlock)
        if not event.wait(timeout=300):
            return {"ok": False, "error": "User did not respond within 5 minutes."}

        answer = result_holder[0]
        if answer is None:
            return {"ok": False, "error": "User cancelled the question"}

        return {"ok": True, "answer": answer}
