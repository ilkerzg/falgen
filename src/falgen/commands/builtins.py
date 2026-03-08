"""Built-in slash commands: /help /clear /quit /model /theme /history /default /login."""

from textual.widgets import Markdown, Static

from ..config import LLM_MODELS, THEMES
from ..preferences import KNOWN_CATEGORIES
from .base import SlashCommand


class HelpCommand(SlashCommand):
    name = "/help"
    description = "Show help"

    def execute(self, app, arg: str) -> None:
        commands = app.command_registry.all_unique()
        help_md = "### Commands\n\n"
        help_md += "| Command | Description |\n|---|---|\n"
        for cmd in commands:
            cmd_str = f"`{cmd.name}"
            if cmd.args_hint:
                cmd_str += f" {cmd.args_hint}"
            cmd_str += "`"
            help_md += f"| {cmd_str} | {cmd.description} |\n"
        help_md += f"\n### Themes\n\nAvailable: {', '.join(f'`{k}`' for k in THEMES)}\n"
        container = app.query_one("#messages")
        container.mount(Markdown(help_md))
        container.scroll_end(animate=False)


class ClearCommand(SlashCommand):
    name = "/clear"
    description = "Clear conversation"

    def execute(self, app, arg: str) -> None:
        app.action_clear_chat()


class QuitCommand(SlashCommand):
    name = "/quit"
    aliases = ["/exit", "/q"]
    description = "Exit"

    def execute(self, app, arg: str) -> None:
        app.exit(0)


class ModelCommand(SlashCommand):
    name = "/model"
    args_hint = "[name]"
    description = "Switch LLM model"

    def _persist_model(self, app, model: str) -> None:
        if app._session_id and app._session_store:
            app._session_store.update_model(app._session_id, model)

    def execute(self, app, arg: str) -> None:
        container = app.query_one("#messages")
        if arg:
            app.model = arg
            self._persist_model(app, arg)
            app._update_status("Model changed")
            container.mount(Static(f"[dim]Model changed to:[/dim] [bold]{app.model}[/bold]"))
            container.scroll_end(animate=False)
            return

        # Show choice picker with available models
        from ..widgets import ChoiceMenu

        def on_select(model: str):
            app.model = model
            self._persist_model(app, model)
            app._update_status("Model changed")
            container.mount(Static(f"[dim]Model changed to:[/dim] [bold]{model}[/bold]"))
            container.scroll_end(animate=False)

        choice_menu = app.query_one(ChoiceMenu)
        choice_menu.show_question("Select LLM model:", LLM_MODELS, on_select)


class ThemeCommand(SlashCommand):
    name = "/theme"
    args_hint = "[name]"
    description = "Switch theme"

    def execute(self, app, arg: str) -> None:
        container = app.query_one("#messages")
        if arg and arg in THEMES:
            app._theme_key = arg
            app._update_status(f"Theme: {THEMES[arg]['name']}")
            for widget in app.query("*"):
                widget.refresh()
            info_w = Static(f"[dim]Theme changed to:[/dim] [bold]{THEMES[arg]['name']}[/bold]")
            container.mount(info_w)
        elif arg:
            names = ", ".join(f"[bold]{k}[/bold]" for k in THEMES)
            info_w = Static(f"[yellow]Unknown theme: {arg}[/yellow]\nAvailable: {names}")
            container.mount(info_w)
        else:
            names = ", ".join(
                (f"[bold cyan]{k}[/bold cyan]" if k == app._theme_key else f"[bold]{k}[/bold]")
                for k in THEMES
            )
            info_w = Static(f"[dim]Available themes:[/dim] {names}")
            container.mount(info_w)
        container.scroll_end(animate=False)


class HistoryCommand(SlashCommand):
    name = "/history"
    args_hint = "<endpoint>"
    description = "Browse request history"

    def execute(self, app, arg: str) -> None:
        if not arg:
            container = app.query_one("#messages")
            container.mount(Static("[yellow]Usage: /history <endpoint>  (e.g. /history fal-ai/flux/dev)[/yellow]"))
            container.scroll_end(animate=False)
            return
        app._browse_history(arg)


class DefaultCommand(SlashCommand):
    name = "/default"
    args_hint = "[category [endpoint]]"
    description = "Set default models"

    def execute(self, app, arg: str) -> None:
        container = app.query_one("#messages")
        prefs = app._preferences

        parts = arg.split(None, 1) if arg else []

        if not parts:
            # Show all defaults
            defaults = prefs.get_defaults()
            if not defaults:
                lines = "[dim]No default models set.[/dim]\n"
                lines += f"[dim]Categories: {', '.join(KNOWN_CATEGORIES)}[/dim]\n"
                lines += "[dim]Usage: /default <category> <endpoint>[/dim]"
                container.mount(Static(lines))
            else:
                lines_parts = []
                for cat, ep in defaults.items():
                    lines_parts.append(f"[bold]{cat}[/bold]  →  {ep}")
                container.mount(Static("\n".join(lines_parts)))
            container.scroll_end(animate=False)
            return

        category = parts[0].lower()
        if category not in KNOWN_CATEGORIES:
            container.mount(Static(
                f"[yellow]Unknown category: {category}[/yellow]\n"
                f"[dim]Available: {', '.join(KNOWN_CATEGORIES)}[/dim]"
            ))
            container.scroll_end(animate=False)
            return

        if len(parts) < 2:
            # Show one default
            current = prefs.get_default(category)
            if current:
                container.mount(Static(f"[bold]{category}[/bold]  →  {current}"))
            else:
                container.mount(Static(f"[dim]No default set for {category}[/dim]"))
            container.scroll_end(animate=False)
            return

        endpoint = parts[1].strip()
        prefs.set_default(category, endpoint)

        # Rebuild system prompt with new defaults
        from ..config import build_system_prompt
        app.messages[0] = {"role": "system", "content": build_system_prompt(prefs)}

        container.mount(Static(f"[bold]{category}[/bold]  →  {endpoint}  [dim](saved)[/dim]"))
        container.scroll_end(animate=False)


class ResumeCommand(SlashCommand):
    name = "/resume"
    description = "Resume previous session"

    def execute(self, app, arg: str) -> None:
        from ..widgets import ChoiceMenu

        container = app.query_one("#messages")

        if arg:
            app._resume_session(arg)
            return

        app._ensure_session_store()
        sessions = app._session_store.list_sessions(limit=20)
        if not sessions:
            container.mount(Static("[dim]No previous sessions found.[/dim]"))
            container.scroll_end(animate=False)
            return

        options = []
        session_map = {}
        for s in sessions:
            if s["id"] == app._session_id:
                continue
            title = s["title"] or "(untitled)"
            date = s["updated_at"][:16].replace("T", " ")
            label = f"{title}  ({s['model']})  {date}"
            options.append(label)
            session_map[label] = s["id"]

        if not options:
            container.mount(Static("[dim]No other sessions to resume.[/dim]"))
            container.scroll_end(animate=False)
            return

        def on_select(answer):
            sid = session_map.get(answer)
            if sid:
                app._resume_session(sid)

        choice_menu = app.query_one(ChoiceMenu)
        choice_menu.show_question("Resume session:", options, on_select)


class CompactCommand(SlashCommand):
    name = "/compact"
    description = "Toggle compact mode"

    def execute(self, app, arg: str) -> None:
        app._compact_mode = not app._compact_mode
        state = "on" if app._compact_mode else "off"
        container = app.query_one("#messages")
        container.mount(Static(f"[dim]Compact mode:[/dim] [bold]{state}[/bold]"))
        container.scroll_end(animate=False)
        app._update_status()


class LoginCommand(SlashCommand):
    name = "/login"
    args_hint = "[key]"
    description = "Set API key"

    def execute(self, app, arg: str) -> None:
        container = app.query_one("#messages")

        if arg:
            # Direct key input
            from ..auth import save_key
            save_key(arg)
            # Re-read to update provider
            from ..auth import get_auth_headers
            headers = get_auth_headers()
            app.fal_key = headers.get("Authorization", "")
            container.mount(Static("[dim]API key saved.[/dim]"))
            container.scroll_end(animate=False)
            return

        # Prompt via choice menu
        container.mount(Static(
            "[dim]Get your API key from[/dim] [bold]https://fal.ai/dashboard/keys[/bold]\n"
            "[dim]Then paste it here: /login YOUR_KEY[/dim]"
        ))
        container.scroll_end(animate=False)
