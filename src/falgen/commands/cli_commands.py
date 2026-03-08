"""Slash commands that delegate to the LLM with tool calls against fal API."""

from .base import SlashCommand


def _llm_command(app, display: str, prompt: str) -> None:
    """Inject a prompt into the conversation so the LLM executes it with tools."""
    from ..widgets import UserMessage

    container = app.query_one("#messages")
    container.mount(UserMessage(display))
    container.scroll_end(animate=False)

    msg = {"role": "user", "content": prompt}
    app.messages.append(msg)
    app._save_message(msg)
    app._generate_response()


class SearchCommand(SlashCommand):
    name = "/search"
    args_hint = "[query]"
    description = "Search models"

    def execute(self, app, arg: str) -> None:
        if arg:
            prompt = f"Search for models matching \"{arg}\". Use the search_models tool."
        else:
            prompt = "Show me popular and recently updated models. Use the search_models tool."
        _llm_command(app, f"/search {arg}" if arg else "/search", prompt)


class InfoCommand(SlashCommand):
    name = "/info"
    args_hint = "<endpoint>"
    description = "Model details + params"

    def execute(self, app, arg: str) -> None:
        if not arg:
            from textual.widgets import Static
            container = app.query_one("#messages")
            container.mount(Static("[yellow]Usage: /info <endpoint>[/yellow]"))
            container.scroll_end(animate=False)
            return
        prompt = f"Get detailed info about model {arg}. Use the model_info tool. Show the key parameters, required inputs, and valid values."
        _llm_command(app, f"/info {arg}", prompt)


class PriceCommand(SlashCommand):
    name = "/price"
    args_hint = "<endpoint>"
    description = "Check pricing"

    def execute(self, app, arg: str) -> None:
        if not arg:
            from textual.widgets import Static
            container = app.query_one("#messages")
            container.mount(Static("[yellow]Usage: /price <endpoint>[/yellow]"))
            container.scroll_end(animate=False)
            return
        prompt = f"Check pricing for {arg}. Use the get_pricing tool."
        _llm_command(app, f"/price {arg}", prompt)


class UsageCommand(SlashCommand):
    name = "/usage"
    args_hint = "[query]"
    description = "Usage & cost info"

    def execute(self, app, arg: str) -> None:
        if arg:
            prompt = f"Show me usage and cost information for {arg}. Use the check_usage tool."
        else:
            prompt = "Show me my recent usage and cost summary. Use the check_usage tool."
        _llm_command(app, f"/usage {arg}" if arg else "/usage", prompt)


class WorkflowsCommand(SlashCommand):
    name = "/workflows"
    args_hint = "[query]"
    description = "List workflows"

    def execute(self, app, arg: str) -> None:
        if arg:
            prompt = f"List my workflows matching \"{arg}\". Use the list_workflows tool."
        else:
            prompt = "List all my saved workflows. Use the list_workflows tool."
        _llm_command(app, f"/workflows {arg}" if arg else "/workflows", prompt)
