"""falgen — OpenCode-inspired TUI for fal platform."""

import json as json_mod
import os
import re
import time
from datetime import datetime, timezone
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Input, Markdown, Static

from .commands import discover_commands
from .config import (
    DEFAULT_MODEL,
    DEFAULT_THEME,
    INPUT_PLACEHOLDER,
    THEMES,
    build_system_prompt,
    random_tagline,
)
from .preferences import Preferences
from .providers import get_provider
from .tasks import TaskManager
from .tools import discover_tools
from .widgets import (
    AskUserWidget,
    AssistantMarkdown,
    ChatInput,
    ChoiceMenu,
    MediaPreview,
    SlashMenu,
    ToolCallStatus,
    UserMessage,
    WelcomeBanner,
)

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
VIDEO_EXTENSIONS = (".mp4", ".webm", ".mov", ".avi", ".mkv")
AUDIO_EXTENSIONS = (".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a")
_ALL_MEDIA_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS + AUDIO_EXTENSIONS

_MIME_MAP = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp",
    ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
    ".avi": "video/x-msvideo", ".mkv": "video/x-matroska",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
    ".flac": "audio/flac", ".aac": "audio/aac", ".m4a": "audio/mp4",
}


def _detect_file_paths(text: str) -> list[tuple[str, str]]:
    """Find local media file paths in text. Returns [(original, expanded), ...]."""
    results = []
    for word in re.split(r'\s+', text):
        word = word.strip("\"'(),;")
        if not word:
            continue
        lower = word.lower()
        if any(lower.endswith(ext) for ext in _ALL_MEDIA_EXTENSIONS):
            expanded = os.path.expanduser(word)
            if os.path.isfile(expanded):
                results.append((word, expanded))
    return results


def _detect_media_type(url: str) -> str:
    """Detect media type from URL extension."""
    lower = url.lower().split("?")[0]
    if any(lower.endswith(ext) for ext in VIDEO_EXTENSIONS):
        return "video"
    if any(lower.endswith(ext) for ext in AUDIO_EXTENSIONS):
        return "audio"
    return "image"


def _extract_media_urls(result: dict) -> list[tuple[str, str]]:
    """Recursively extract media URLs from a generation result.

    Returns list of (url, media_type) tuples.
    """
    urls: list[tuple[str, str]] = []

    def _walk(obj):
        if isinstance(obj, str):
            if not obj.startswith(("http://", "https://")):
                return
            lower = obj.lower().split("?")[0]
            all_extensions = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS + AUDIO_EXTENSIONS
            if any(lower.endswith(ext) for ext in all_extensions):
                urls.append((obj, _detect_media_type(obj)))
            elif "fal.media" in obj or "fal-cdn" in obj:
                urls.append((obj, _detect_media_type(obj)))
        elif isinstance(obj, dict):
            for key in ("url", "image", "images", "output", "audio", "video"):
                if key in obj:
                    _walk(obj[key])
            for k, v in obj.items():
                if k not in ("url", "image", "images", "output", "audio", "video"):
                    _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(result)
    # Deduplicate preserving order
    seen = set()
    unique = []
    for entry in urls:
        if entry[0] not in seen:
            seen.add(entry[0])
            unique.append(entry)
    return unique


class FalChatApp(App):
    """Full-screen TUI chat for fal platform."""

    TITLE = "falgen"

    CSS = """
    Screen {
        background: $surface;
        layers: default overlay;
    }

    #messages {
        height: 1fr;
        overflow-y: auto;
        padding: 0 0;
        scrollbar-size: 1 1;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $panel;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear_chat", "Clear", priority=True),
        Binding("ctrl+v", "paste_image", "Paste image", show=False, priority=True),
        Binding("escape", "escape_key", "Escape", show=False),
        Binding("pageup", "scroll_up_page", "Scroll up", show=False),
        Binding("pagedown", "scroll_down_page", "Scroll down", show=False),
        Binding("shift+up", "scroll_up_line", "Scroll up", show=False, priority=True),
        Binding("shift+down", "scroll_down_line", "Scroll down", show=False, priority=True),
    ]

    model = reactive(DEFAULT_MODEL)

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        fal_key: str = "",
        session_id: str | None = None,
    ) -> None:
        super().__init__()
        self.model = model
        self.fal_key = fal_key
        self._preferences = Preferences()
        self.messages: list[dict] = [{"role": "system", "content": build_system_prompt(self._preferences)}]
        self._is_generating = False
        self._cancel_generation = False
        self._compact_mode = False
        self._needs_onboarding = False
        self._input_history: list[str] = []
        self._history_index = -1
        self._theme_key = DEFAULT_THEME
        self._pending_tools = 0
        self._session_titled = False
        self._queued_messages: list[str] = []
        self._task_manager = TaskManager()
        self._task_manager.set_completion_callback(self._on_task_complete)

        # Registries
        self.tool_registry = discover_tools()
        self.command_registry = discover_commands()
        self.provider = get_provider()

        # Session
        self._session_id = session_id
        self._session_store = None

        # Conversation log file
        log_dir = os.path.expanduser("~/.cache/falgen/logs")
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._log_path = os.path.join(log_dir, f"chat_{ts}.jsonl")
        self._log_file = open(self._log_path, "a")

    def _log(self, event_type: str, data: dict) -> None:
        """Append a log entry to the session log file."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            **data,
        }
        self._log_file.write(json_mod.dumps(entry, default=str) + "\n")
        self._log_file.flush()

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="messages")
        menu = SlashMenu()
        menu.set_commands(self.command_registry.all_unique())
        yield menu
        yield ChoiceMenu()
        yield ChatInput(placeholder=INPUT_PLACEHOLDER, id="chat-input")
        yield Static(id="status-bar")

    def on_mount(self) -> None:
        container = self.query_one("#messages")

        # Load session if resuming
        if self._session_id:
            self._ensure_session_store()
            if self._session_id == "last":
                self._session_id = self._session_store.get_last_session_id()
            if self._session_id:
                saved = self._session_store.load_messages(self._session_id)
                if saved:
                    self.messages = [{"role": "system", "content": build_system_prompt(self._preferences)}] + saved
                    for msg in saved:
                        if msg["role"] == "user" and msg.get("content"):
                            container.mount(UserMessage(msg["content"]))
                        elif msg["role"] == "assistant" and msg.get("content"):
                            container.mount(AssistantMarkdown(msg["content"]))

        # Auto-create session if we don't have one (persist every conversation)
        if not self._session_id:
            self._ensure_session_store()
            self._session_id = self._session_store.create_session(self.model)

        # Restore model from session if resuming
        if self._session_store and self._session_id:
            session_info = self._session_store.get_session(self._session_id)
            if session_info and session_info.get("model"):
                self.model = session_info["model"]
            if session_info and session_info.get("title"):
                self._session_titled = True

        container.mount(WelcomeBanner(self.model))
        self._update_status()

        input_widget = self.query_one("#chat-input", ChatInput)

        # First-run: no API key — show onboarding prompt
        if not self.fal_key:
            self._needs_onboarding = True
            container.mount(Static(
                "[bold]Welcome![/bold] To get started, you need a fal.ai API key.\n"
                "Get yours at [bold]https://fal.ai/dashboard/keys[/bold]\n\n"
                "[dim]Paste your API key below and press Enter:[/dim]"
            ))
            input_widget.placeholder = "Paste your fal.ai API key here..."
            container.scroll_end(animate=False)

        input_widget.focus()

    def _ensure_session_store(self):
        if self._session_store is None:
            from .session import SessionStore
            self._session_store = SessionStore()

    def _save_message(self, message: dict) -> None:
        if self._session_id is None:
            return
        self._ensure_session_store()
        self._session_store.save_message(self._session_id, message)

    def _resume_session(self, session_id: str) -> None:
        """Load and resume a previous session."""
        self._ensure_session_store()
        session_info = self._session_store.get_session(session_id)
        if not session_info:
            container = self.query_one("#messages")
            container.mount(Static(f"[red]Session not found: {session_id}[/red]"))
            container.scroll_end(animate=False)
            return

        saved = self._session_store.load_messages(session_id)
        self._session_id = session_id
        self._session_titled = bool(session_info.get("title"))

        # Restore model
        if session_info.get("model"):
            self.model = session_info["model"]

        # Rebuild messages
        self.messages = [{"role": "system", "content": build_system_prompt(self._preferences)}]
        if saved:
            self.messages.extend(saved)

        # Rebuild UI
        container = self.query_one("#messages")
        container.remove_children()
        container.mount(WelcomeBanner(self.model))

        for msg in saved:
            if msg["role"] == "user" and msg.get("content"):
                container.mount(UserMessage(msg["content"]))
            elif msg["role"] == "assistant" and msg.get("content"):
                container.mount(AssistantMarkdown(msg["content"]))

        title = session_info.get("title") or session_id
        container.mount(Static(f"[dim]Resumed session: {title}[/dim]"))
        container.scroll_end(animate=False)
        self._update_status()

    def _save_media(self, url: str, media_type: str, endpoint_id: str = "") -> None:
        if self._session_id is None:
            return
        self._ensure_session_store()
        try:
            self._session_store.save_media(self._session_id, url, media_type, endpoint_id)
        except Exception:
            pass

    # ── Status bar (OpenCode-style: mode | status | model) ───────

    def _update_status(self, extra: str = "") -> None:
        from rich.text import Text as RichText

        t = THEMES.get(self._theme_key, THEMES[DEFAULT_THEME])
        status = self.query_one("#status-bar")
        rt = RichText()

        rt.append(" falgen ", style=f"bold reverse {t['primary']}")
        rt.append("  ", style="")

        # Status — shows generating state or tool count
        if self._pending_tools > 0:
            rt.append(f"\u25cb {self._pending_tools} running  ", style=f"{t['warning']}")
        elif extra:
            rt.append(f"{extra}  ", style=f"italic {t['primary']}")

        # Background tasks
        active = self._task_manager.active_tasks()
        if active:
            rt.append(f"\u27f3 {len(active)} bg  ", style=f"{t['warning']}")

        # Compact mode indicator
        if self._compact_mode:
            rt.append("compact  ", style=f"italic {t['text_muted']}")

        # Model
        rt.append(self.model, style=f"{t['text_muted']}")

        # Keybinds (right)
        rt.append("   /help ", style=f"{t['text_muted']}")
        if self._is_generating:
            rt.append("Esc cancel", style=f"{t['warning']}")
        else:
            rt.append("Ctrl+C", style=f"{t['text_muted']}")

        status.update(rt)

    # ── Actions ──────────────────────────────────────────────────

    def action_quit(self) -> None:
        self._log("session_end", {"model": self.model})
        self._log_file.close()
        self.exit(0)

    def action_clear_chat(self) -> None:
        self.messages = [{"role": "system", "content": build_system_prompt(self._preferences)}]
        container = self.query_one("#messages")
        container.remove_children()
        container.mount(WelcomeBanner(self.model))
        self._update_status()

    def action_escape_key(self) -> None:
        """Escape: cancel generation if running, otherwise focus input."""
        if self._is_generating:
            self._cancel_generation = True
            self._update_status("Cancelling...")
        else:
            self.query_one("#chat-input").focus()

    def action_scroll_up_page(self) -> None:
        self.query_one("#messages").scroll_page_up(animate=False)

    def action_scroll_down_page(self) -> None:
        self.query_one("#messages").scroll_page_down(animate=False)

    def action_scroll_up_line(self) -> None:
        self.query_one("#messages").scroll_up(animate=False)

    def action_scroll_down_line(self) -> None:
        self.query_one("#messages").scroll_down(animate=False)

    def action_paste_image(self) -> None:
        """Try to read image from clipboard (macOS: pngpaste/osascript, Linux: xclip)."""
        import platform
        import subprocess

        input_widget = self.query_one("#chat-input", ChatInput)
        if not input_widget.has_focus:
            return

        system = platform.system()
        img_data = None

        try:
            if system == "Darwin":
                img_data = self._clipboard_image_macos()
            elif system == "Linux":
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
                    capture_output=True, timeout=5,
                )
                if result.returncode == 0 and len(result.stdout) > 100:
                    img_data = result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass

        if img_data and len(img_data) > 100:
            input_widget.set_pasted_image(img_data, "image/png")
        # else: no image in clipboard — normal text paste will handle it

    @staticmethod
    def _clipboard_image_macos() -> bytes | None:
        """Read image from macOS clipboard as PNG bytes."""
        import subprocess
        import tempfile

        # Method 1: pngpaste (brew install pngpaste) — most reliable
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            result = subprocess.run(
                ["pngpaste", tmp_path], capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                with open(tmp_path, "rb") as f:
                    data = f.read()
                if len(data) > 100:
                    return data
        except FileNotFoundError:
            pass
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        # Method 2: osascript fallback — write clipboard to temp file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        script = (
            'use framework "AppKit"\n'
            'set pb to current application\'s NSPasteboard\'s generalPasteboard()\n'
            'set imgData to pb\'s dataForType:(current application\'s NSPasteboardTypePNG)\n'
            'if imgData is missing value then error "no image"\n'
            f'set fp to "{tmp_path}"\n'
            'imgData\'s writeToFile:fp atomically:true\n'
        )
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                with open(tmp_path, "rb") as f:
                    data = f.read()
                if len(data) > 100:
                    return data
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return None

    # ── Input handling ───────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        menu = self.query_one(SlashMenu)
        text = event.value.strip()
        if text.startswith("/"):
            cmd_part = text.split()[0] if text.split() else text
            menu.filter(cmd_part)
        else:
            menu.hide()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        input_widget = self.query_one("#chat-input", ChatInput)
        user_text = input_widget.get_effective_value()

        # First-run onboarding: treat input as API key
        if self._needs_onboarding and user_text and not user_text.startswith("/"):
            from .auth import save_key, get_auth_headers
            save_key(user_text)
            headers = get_auth_headers()
            self.fal_key = headers.get("Authorization", "")
            input_widget.clear()
            container = self.query_one("#messages")
            if self.fal_key:
                self._needs_onboarding = False
                input_widget.placeholder = INPUT_PLACEHOLDER
                container.mount(Static("[bold green]API key saved! You're ready to generate.[/bold green]"))
            else:
                container.mount(Static("[bold red]Invalid key. Please try again.[/bold red]"))
            container.scroll_end(animate=False)
            return

        # Handle pasted image: upload to fal CDN and inject URL into message
        pasted_image = input_widget.take_pasted_image()
        image_url = None
        if pasted_image:
            img_data, img_mime = pasted_image
            # If user only pasted image with no text, provide default prompt context
            if not user_text or user_text.startswith("[image:"):
                user_text = ""
            self._upload_and_send(user_text, img_data, img_mime)
            input_widget.clear()
            return

        if not user_text:
            return

        self.query_one(SlashMenu).hide()
        input_widget.clear()

        if not self._input_history or self._input_history[-1] != user_text:
            self._input_history.append(user_text)
        self._history_index = -1

        if user_text.startswith("/"):
            self._handle_slash(user_text)
            return

        # Detect local file paths and upload them
        file_paths = _detect_file_paths(user_text)
        if file_paths:
            self._upload_files_and_send(user_text, file_paths)
            return

        container = self.query_one("#messages")
        await container.mount(UserMessage(user_text))
        container.scroll_end(animate=False)
        msg = {"role": "user", "content": user_text}
        self.messages.append(msg)
        self._save_message(msg)

        if self._is_generating:
            # Queue the message — AI will evaluate priority when it checks
            self._queued_messages.append(user_text)
            self._log("user_message", {"content": user_text, "queued": True})
            return

        self._log("user_message", {"content": user_text})

        # Auto-set session title from first user message
        if not self._session_titled and self._session_id and self._session_store:
            title = user_text[:60].strip()
            self._session_store.update_title(self._session_id, title)
            self._session_titled = True

        self._generate_response()

    def on_key(self, event) -> None:
        # ChoiceMenu takes priority when visible
        choice_menu = self.query_one(ChoiceMenu)
        if choice_menu.is_visible:
            if choice_menu.in_custom_mode:
                if event.key == "enter":
                    choice_menu.confirm_selection()
                else:
                    choice_menu.handle_custom_key(event.key, event.character)
                event.prevent_default()
                return
            if event.key == "up":
                choice_menu.move_selection(-1)
                event.prevent_default()
                return
            elif event.key == "down":
                choice_menu.move_selection(1)
                event.prevent_default()
                return
            elif event.key == "enter":
                choice_menu.confirm_selection()
                event.prevent_default()
                return
            elif event.key == "escape":
                choice_menu.cancel()
                event.prevent_default()
                return
            else:
                # Fuzzy filter: printable keys and backspace filter the list
                choice_menu.handle_filter_key(event.key, event.character)
            event.prevent_default()
            return

        input_widget = self.query_one("#chat-input", ChatInput)
        if not input_widget.has_focus:
            return

        # Shift+Enter: add line to multi-line buffer
        if event.key == "shift+enter":
            input_widget.add_line()
            input_widget.value = ""
            event.prevent_default()
            return

        menu = self.query_one(SlashMenu)
        if menu.display:
            if event.key == "up":
                menu.move_selection(-1)
                event.prevent_default()
                return
            elif event.key == "down":
                menu.move_selection(1)
                event.prevent_default()
                return
            elif event.key == "enter":
                parts = menu.get_selected_parts()
                if parts:
                    cmd, args_hint = parts
                    if args_hint:
                        # Command expects args — fill command name, let user type args
                        input_widget.value = cmd + " "
                        input_widget.cursor_position = len(input_widget.value)
                        menu.hide()
                    else:
                        # No args needed — fill and submit directly
                        input_widget.value = cmd
                        input_widget.cursor_position = len(input_widget.value)
                        menu.hide()
                        # Don't prevent default — let Input.Submitted fire
                        return
                event.prevent_default()
                return
            elif event.key == "tab":
                selected = menu.get_selected()
                if selected:
                    input_widget.value = selected
                    input_widget.cursor_position = len(input_widget.value)
                    menu.hide()
                event.prevent_default()
                return
            elif event.key == "escape":
                menu.hide()
                event.prevent_default()
                return

        if event.key == "up" and self._input_history:
            if self._history_index == -1:
                self._history_index = len(self._input_history) - 1
            elif self._history_index > 0:
                self._history_index -= 1
            else:
                return
            input_widget.value = self._input_history[self._history_index]
            input_widget.cursor_position = len(input_widget.value)
            event.prevent_default()
        elif event.key == "down" and self._history_index != -1:
            if self._history_index < len(self._input_history) - 1:
                self._history_index += 1
                input_widget.value = self._input_history[self._history_index]
            else:
                self._history_index = -1
                input_widget.value = ""
            input_widget.cursor_position = len(input_widget.value)
            event.prevent_default()

    # ── Image upload ────────────────────────────────────────────

    @work(thread=True)
    def _upload_and_send(self, user_text: str, img_data: bytes, img_mime: str) -> None:
        """Upload pasted image to fal CDN, then send as user message with image URL."""
        from .auth import upload_file

        ext = img_mime.split("/")[-1] if "/" in img_mime else "png"
        filename = f"pasted_image.{ext}"

        # Show uploading status
        display_text = f"{user_text}  (uploading image...)" if user_text else "(uploading image...)"
        msg_widget = self.call_from_thread(self._mount_user_message, display_text)

        try:
            url = upload_file(img_data, content_type=img_mime, filename=filename)
        except Exception as e:
            self.call_from_thread(
                self._mount_status, f"[red]Image upload failed: {e}[/red]"
            )
            return

        # Build the user message with image URL
        if user_text:
            content = f"{user_text}\n\n[Attached image: {url}]"
        else:
            content = f"[Attached image: {url}]\n\nWhat would you like to do with this image?"

        # Update display
        self.call_from_thread(self._update_message_widget, msg_widget, content.split("\n")[0])

        msg = {"role": "user", "content": content}
        self.messages.append(msg)
        self._save_message(msg)

        if self._is_generating:
            self._queued_messages.append(content)
            return

        # Auto-set session title
        if not self._session_titled and self._session_id and self._session_store:
            title = (user_text or "Image upload")[:60].strip()
            self._session_store.update_title(self._session_id, title)
            self._session_titled = True

        self._generate_response()

    @work(thread=True)
    def _upload_files_and_send(self, user_text: str, file_paths: list[tuple[str, str]]) -> None:
        """Upload local files to fal CDN and send message with URLs."""
        from .auth import upload_file

        display_text = f"{user_text}  (uploading {len(file_paths)} file{'s' if len(file_paths) > 1 else ''}...)"
        msg_widget = self.call_from_thread(self._mount_user_message, display_text)

        content = user_text
        for original, expanded in file_paths:
            try:
                ext = os.path.splitext(expanded)[1].lower()
                mime = _MIME_MAP.get(ext, "application/octet-stream")
                with open(expanded, "rb") as f:
                    data = f.read()
                url = upload_file(data, content_type=mime, filename=os.path.basename(expanded))
                content = content.replace(original, f"[Attached file: {url}]")
            except Exception as e:
                self.call_from_thread(
                    self._mount_status, f"[red]Failed to upload {original}: {e}[/red]"
                )
                content = content.replace(original, f"[upload failed: {original}]")

        self.call_from_thread(self._update_message_widget, msg_widget, content.split("\n")[0][:80])

        msg = {"role": "user", "content": content}
        self.messages.append(msg)
        self._save_message(msg)

        if self._is_generating:
            self._queued_messages.append(content)
            return

        if not self._session_titled and self._session_id and self._session_store:
            title = user_text[:60].strip()
            self._session_store.update_title(self._session_id, title)
            self._session_titled = True

        self._generate_response()

    def _mount_user_message(self, text: str):
        container = self.query_one("#messages")
        widget = UserMessage(text)
        container.mount(widget)
        container.scroll_end(animate=False)
        return widget

    def _mount_status(self, text: str) -> None:
        container = self.query_one("#messages")
        container.mount(Static(text))
        container.scroll_end(animate=False)

    def _update_message_widget(self, widget, text: str) -> None:
        try:
            widget.update(text)
        except Exception:
            pass

    # ── Command dispatch ─────────────────────────────────────────

    def _handle_slash(self, text: str) -> None:
        parts = text.split(maxsplit=1)
        cmd_name = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        command = self.command_registry.get(cmd_name)
        if command:
            command.execute(self, arg)
        else:
            container = self.query_one("#messages")
            container.mount(Static(f"[bold red]Unknown command: {cmd_name}[/bold red]"))
            container.scroll_end(animate=False)

    # ── LLM generation ───────────────────────────────────────────

    @work(thread=True)
    def _generate_response(self) -> None:
        self._is_generating = True
        self._cancel_generation = False
        self.call_from_thread(self._update_status, random_tagline())

        try:
            self._run_generation_loop()
        finally:
            self._is_generating = False
            self._cancel_generation = False
            self._pending_tools = 0
            self.call_from_thread(self._update_status)

    def _run_generation_loop(self) -> None:
        from .context import needs_summarization, summarize_messages

        tools_schema = self.tool_registry.openai_schemas()

        while True:
            # Context window management: summarize if approaching limit
            if needs_summarization(self.messages, self.model):
                self.call_from_thread(self._update_status, "summarizing context...")
                self.messages = summarize_messages(
                    self.messages, self.provider, self.model
                )
                self.call_from_thread(self._update_status, random_tagline())
            md_widget = self.call_from_thread(self._mount_assistant_md)
            stream = None
            assistant_msg = None
            has_tool_calls = False

            for event_type, data in self.provider.stream_chat(self.model, self.messages, tools_schema):
                if self._cancel_generation:
                    self.call_from_thread(self._show_cancelled)
                    return

                if event_type == "content":
                    if stream is None:
                        stream = self.call_from_thread(self._start_stream, md_widget)
                    self.call_from_thread(self._write_to_stream, stream, data)

                elif event_type == "tool_calls":
                    has_tool_calls = True

                elif event_type == "error":
                    self._log("llm_error", {"error": data})
                    self.call_from_thread(self._show_error, data)
                    return

                elif event_type == "done":
                    assistant_msg = data

            if stream is not None:
                self.call_from_thread(self._stop_stream, stream)

            if assistant_msg is None:
                return

            self.messages.append(assistant_msg)
            self._save_message(assistant_msg)
            self._log("assistant_message", {
                "content": assistant_msg.get("content", ""),
                "has_tool_calls": has_tool_calls,
                "model": self.model,
            })

            if not has_tool_calls:
                return

            # Execute tool calls with pending count in status bar
            tool_calls = assistant_msg["tool_calls"]
            self._pending_tools = len(tool_calls)
            self.call_from_thread(self._update_status)

            for tc in tool_calls:
                if self._cancel_generation:
                    self.call_from_thread(self._show_cancelled)
                    return

                fn_name = tc["function"]["name"]
                fn_args_str = tc["function"]["arguments"]

                try:
                    fn_args = json_mod.loads(fn_args_str)
                except json_mod.JSONDecodeError:
                    fn_args = {}

                args_preview = json_mod.dumps(fn_args, ensure_ascii=False)
                if len(args_preview) > 60:
                    args_preview = args_preview[:57] + "..."

                indicator = self.call_from_thread(self._mount_tool_indicator, fn_name, args_preview)

                # Skeleton preview mounted early for generate tools
                early_preview = [None]

                # Progress callback for live status updates + ask_user bridge
                def on_progress(info, _ind=indicator, _fn=fn_name):
                    # ask_user tool bridge
                    if info.get("type") == "ask_user":
                        self.call_from_thread(
                            self._show_ask_user,
                            info["question"],
                            info["options"],
                            info["event"],
                            info["result_holder"],
                        )
                        return

                    state = info.get("state", "")
                    elapsed = info.get("elapsed", 0)
                    ep = info.get("endpoint_id", "")
                    t_str = f"{elapsed:.1f}s" if elapsed else ""

                    if state == "SUBMITTING":
                        self.call_from_thread(_ind.set_progress, f"{ep}  submitting...")
                        # Mount skeleton preview immediately when generate starts
                        if _fn == "generate":
                            early_preview[0] = self.call_from_thread(
                                self._mount_media_preview_skeleton, ep
                            )
                    elif state == "IN_QUEUE":
                        pos = info.get("position", "?")
                        self.call_from_thread(_ind.set_progress, f"{ep}  queue #{pos}  {t_str}")
                    elif state == "IN_PROGRESS":
                        logs = info.get("logs", [])
                        last_log = logs[-1] if logs else ""
                        if last_log:
                            self.call_from_thread(_ind.set_progress, f"{ep}  {last_log}  {t_str}")
                        else:
                            self.call_from_thread(_ind.set_progress, f"{ep}  processing...  {t_str}")

                self._log("tool_call", {"tool": fn_name, "args": fn_args})
                _tool_start = time.monotonic()
                result = self.tool_registry.execute(fn_name, fn_args, on_progress=on_progress)
                _tool_elapsed = round(time.monotonic() - _tool_start, 2)

                # Log tool result (truncate for log readability)
                try:
                    _result_data = json_mod.loads(result)
                    _log_result = {k: v for k, v in _result_data.items() if k != "result"}
                    if "result" in _result_data:
                        _log_result["result_keys"] = list(_result_data["result"].keys()) if isinstance(_result_data["result"], dict) else type(_result_data["result"]).__name__
                except Exception:
                    _log_result = {"raw_length": len(result)}
                self._log("tool_result", {"tool": fn_name, "elapsed_s": _tool_elapsed, **_log_result})

                self._pending_tools -= 1
                self.call_from_thread(self._update_status)

                try:
                    result_data = json_mod.loads(result)
                    if result_data.get("ok", False):
                        elapsed = result_data.get("elapsed_seconds", 0)
                        self.call_from_thread(indicator.set_done, elapsed)
                    else:
                        self.call_from_thread(indicator.set_error)
                except Exception:
                    result_data = {}
                    self.call_from_thread(indicator.set_done)

                # Register background task if generate returned _task_data
                if fn_name == "generate" and isinstance(result_data, dict) and "_task_data" in result_data:
                    td = result_data["_task_data"]
                    bg_task = self._task_manager.submit(
                        td["endpoint_id"], td["request_id"], td["urls"], td["headers"]
                    )
                    bg_task.tool_call_id = tc["id"]
                    # Remove internal data from result sent to LLM
                    del result_data["_task_data"]
                    result = json_mod.dumps(result_data, default=str)

                # Warn user if result was truncated
                if "data_truncated" in result:
                    self.call_from_thread(indicator.set_progress, "Result was truncated (too large)")

                # Show media previews for generate results (skip for background tasks)
                # Load synchronously so LLM text waits until media is visible
                if fn_name == "generate":
                    try:
                        rd = json_mod.loads(result)
                        if rd.get("ok") and not rd.get("background"):
                            media_items = _extract_media_urls(rd.get("result", {}))
                            ep = rd.get("endpoint_id", fn_name)
                            # Persist media URLs in session
                            for media_url, media_type in media_items:
                                self._save_media(media_url, media_type, ep)
                            for i, (media_url, media_type) in enumerate(media_items):
                                if i == 0 and early_preview[0] is not None:
                                    # Reuse the skeleton mounted at SUBMITTING
                                    preview = early_preview[0]
                                    preview._url = media_url
                                    preview._label = ep
                                    preview._media_type = media_type
                                else:
                                    preview = self.call_from_thread(
                                        self._mount_media_preview, media_url, ep, media_type
                                    )
                                self._load_preview_with_input_guard(preview)
                            if not media_items and early_preview[0] is not None:
                                self.call_from_thread(early_preview[0].remove)
                        else:
                            if early_preview[0] is not None:
                                self.call_from_thread(early_preview[0].remove)
                    except Exception:
                        if early_preview[0] is not None:
                            self.call_from_thread(early_preview[0].remove)

                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                }
                self.messages.append(tool_msg)
                self._save_message(tool_msg)

            # After all tool calls: check message queue
            if self._queued_messages:
                queued = self._queued_messages.copy()
                self._queued_messages.clear()
                queue_text = "\n".join(f"[QUEUED MESSAGE]: {m}" for m in queued)
                priority_prompt = (
                    f"The user sent new messages while you were working:\n{queue_text}\n\n"
                    "Evaluate priority: if any message is urgent or changes your current task, "
                    "address it immediately. Otherwise, finish current work first then address them."
                )
                self.messages.append({"role": "user", "content": priority_prompt})

    # ── Ask user (choice picker) ────────────────────────────────

    def _show_ask_user(self, question: str, options: list[str], event, result_holder) -> None:
        """Show ChoiceMenu overlay and wire up the callback to unblock the tool thread."""
        container = self.query_one("#messages")
        ask_widget = AskUserWidget(question)
        container.mount(ask_widget)
        container.scroll_end(animate=False)

        input_widget = self.query_one("#chat-input", ChatInput)
        input_widget.disabled = True

        def on_select(answer: str) -> None:
            ask_widget.set_answer(answer)
            # Show the answer as a user message so it's visible in chat flow
            container.mount(UserMessage(answer))
            input_widget.disabled = False
            input_widget.focus()
            result_holder[0] = answer
            event.set()
            container.scroll_end(animate=False)

        def on_cancel() -> None:
            ask_widget.set_answer("(cancelled)")
            input_widget.disabled = False
            input_widget.focus()
            result_holder[0] = None
            event.set()
            container.scroll_end(animate=False)

        choice_menu = self.query_one(ChoiceMenu)
        choice_menu.show_question(question, options, on_select, on_cancel=on_cancel)

    # ── History browser ────────────────────────────────────────

    @work(thread=True)
    def _browse_history(self, endpoint_id: str) -> None:
        """Fetch request history from fal API and show interactive picker."""
        self.call_from_thread(self._update_status, "fetching history...")

        from .auth import api_get, get_auth_headers

        headers = get_auth_headers()
        if not headers:
            self.call_from_thread(
                self._show_error,
                "Not authenticated. Run `falgen` and use /login, or set FAL_KEY.",
            )
            self.call_from_thread(self._update_status)
            return

        try:
            data = api_get(
                "/models/requests/by-endpoint",
                params={"endpoint_id": endpoint_id, "limit": 20},
                headers=headers,
            )
        except Exception as e:
            self.call_from_thread(self._show_error, f"Failed to fetch history: {e}")
            self.call_from_thread(self._update_status)
            return

        items = data.get("items", [])
        if not items:
            self.call_from_thread(
                self._show_history_empty, endpoint_id
            )
            self.call_from_thread(self._update_status)
            return

        self.call_from_thread(self._show_history_picker, endpoint_id, items)
        self.call_from_thread(self._update_status)

    def _show_history_empty(self, endpoint_id: str) -> None:
        container = self.query_one("#messages")
        container.mount(Static(f"[dim]No requests found for {endpoint_id}[/dim]"))
        container.scroll_end(animate=False)

    def _show_history_picker(self, endpoint_id: str, items: list) -> None:
        """Show history items in ChoiceMenu for interactive browsing."""
        container = self.query_one("#messages")
        container.mount(Static(f"[dim]History for[/dim] [bold]{endpoint_id}[/bold] [dim]({len(items)} requests)[/dim]"))
        container.scroll_end(animate=False)

        # Build option labels
        options = []
        for item in items:
            rid = item.get("request_id", "?")[:8]
            status = item.get("status_code", "?")
            duration = item.get("duration")
            dur_str = f"{duration:.1f}s" if duration else "—"
            started = (item.get("started_at") or "")[:19].replace("T", " ")

            if isinstance(status, int) and 200 <= status < 300:
                label = f"{started}  {status} OK  {dur_str}  {rid}…"
            elif isinstance(status, int) and status >= 400:
                label = f"{started}  {status} ERR  {dur_str}  {rid}…"
            else:
                label = f"{started}  {status}  {dur_str}  {rid}…"
            options.append(label)

        def on_select(answer: str) -> None:
            # Find the matching item by label
            idx = next((i for i, o in enumerate(options) if o == answer), None)
            if idx is not None and idx < len(items):
                selected = items[idx]
                self._request_detail_via_llm(endpoint_id, selected)

        choice_menu = self.query_one(ChoiceMenu)
        choice_menu.show_question("Select a request to inspect:", options, on_select)

    def _request_detail_via_llm(self, endpoint_id: str, item: dict) -> None:
        """Ask LLM to show details for a specific request."""

        rid = item.get("request_id", "")
        status = item.get("status_code", "?")
        duration = item.get("duration", "?")
        started = item.get("started_at", "?")

        prompt = (
            f"Show me the full details for request {rid} on endpoint {endpoint_id}. "
            f"Status: {status}, Duration: {duration}s, Started: {started}. "
            f"Use the request_history tool with endpoint_id=\"{endpoint_id}\" and include the request_id filter. "
            f"Show the input parameters and output URLs if available."
        )

        container = self.query_one("#messages")
        container.mount(UserMessage(f"inspect {rid[:8]}…"))
        container.scroll_end(animate=False)

        msg = {"role": "user", "content": prompt}
        self.messages.append(msg)
        self._save_message(msg)
        self._generate_response()

    # ── Background task callbacks ────────────────────────────────

    def _on_task_complete(self, task):
        """Called from polling thread when a background task finishes."""
        self.call_from_thread(self._handle_task_complete, task)

    def _handle_task_complete(self, task):
        """Show completed task result and inject into conversation."""
        if task.state == "COMPLETED" and task.result:
            media_items = _extract_media_urls(task.result)
            for media_url, media_type in media_items:
                self._save_media(media_url, media_type, task.endpoint_id)
            container = self.query_one("#messages")
            for url, media_type in media_items:
                preview = MediaPreview(url=url, label=task.endpoint_id, media_type=media_type)
                container.mount(preview)
                self._load_media_preview(preview)

            # Inject tool result into messages for LLM context
            result_str = json_mod.dumps(
                {
                    "ok": True,
                    "result": task.result,
                    "endpoint_id": task.endpoint_id,
                    "elapsed_seconds": round(task.elapsed, 1),
                    "background": True,
                },
                default=str,
            )
            if task.tool_call_id:
                tool_msg = {"role": "tool", "tool_call_id": task.tool_call_id, "content": result_str}
                self.messages.append(tool_msg)
                self._save_message(tool_msg)

        elif task.state == "FAILED":
            self._show_error(f"Background task failed: {task.error}")
            if task.tool_call_id:
                error_str = json_mod.dumps(
                    {"ok": False, "error": task.error, "background": True}, default=str
                )
                tool_msg = {"role": "tool", "tool_call_id": task.tool_call_id, "content": error_str}
                self.messages.append(tool_msg)
                self._save_message(tool_msg)

        self._update_status()
        # If not currently generating, kick off a new LLM turn to process the result
        if not self._is_generating:
            self._generate_response()

    # ── Input garbage cleanup ────────────────────────────────────

    # Terminal response patterns: digits;digits followed by a letter,
    # DEC private responses [?digits, or OSC color responses ;rgb:
    _TERM_GARBAGE_RE = re.compile(
        r'(?:\^\[|\x1b\[|\[)(?:\??\d+;){0,8}\d*[a-zA-Z~]$'
        r'|(?:\^\[|\x1b\[|\[)\?\d+$'
        r'|;rgb:[0-9a-fA-F/]+$'
        r'|(?:\^\[|\x1b\[|\[)(?:\??\d+;){0,8}\d*$'
        r'|(?:\??\d+;){2,8}\d*[a-zA-Z~]$'
        r'|(?:\??\d+;){2,8}\d*$'
    )

    def _flush_input_garbage(self) -> None:
        """Strip terminal response garbage from the input.

        After chafa renders an image, Textual re-renders the widget which
        can trigger terminal size/capability queries.  The terminal responds
        with escape sequences whose *printable* parts (digits, semicolons,
        letters like ``t``, ``c``) leak into the focused Input widget.
        """
        input_widget = self.query_one("#chat-input", ChatInput)
        val = input_widget.value
        if not val:
            return

        cleaned = val
        while cleaned and self._TERM_GARBAGE_RE.search(cleaned):
            updated = self._TERM_GARBAGE_RE.sub("", cleaned)
            if updated == cleaned:
                break
            cleaned = updated

        if cleaned != val:
            input_widget.value = cleaned

    def _suspend_input_focus(self) -> bool:
        """Temporarily unfocus the input while terminal previews render."""
        input_widget = self.query_one("#chat-input", ChatInput)
        had_focus = input_widget.has_focus
        if had_focus:
            self.set_focus(None)
        return had_focus

    def _restore_input_focus(self, should_restore: bool) -> None:
        if not should_restore:
            return
        input_widget = self.query_one("#chat-input", ChatInput)
        if not input_widget.disabled:
            input_widget.focus()

    def _load_preview_with_input_guard(self, preview: MediaPreview) -> None:
        restore_focus = self.call_from_thread(self._suspend_input_focus)
        try:
            preview.load_from_url()
            time.sleep(0.25)
            self.call_from_thread(self._flush_input_garbage)
            self.call_from_thread(self._scroll_messages)
        finally:
            self.call_from_thread(self._restore_input_focus, restore_focus)

    # ── Widget helpers ───────────────────────────────────────────

    def _mount_assistant_md(self) -> AssistantMarkdown:
        container = self.query_one("#messages")
        md = AssistantMarkdown("")
        container.mount(md)
        container.scroll_end(animate=False)
        return md

    def _start_stream(self, md_widget: AssistantMarkdown):
        return Markdown.get_stream(md_widget)

    async def _write_to_stream(self, stream, text: str) -> None:
        await stream.write(text)
        self.query_one("#messages").scroll_end(animate=False)

    async def _stop_stream(self, stream) -> None:
        await stream.stop()

    def _mount_tool_indicator(self, fn_name: str, args_preview: str) -> ToolCallStatus:
        container = self.query_one("#messages")
        indicator = ToolCallStatus(fn_name, args_preview, "running")
        if self._compact_mode:
            indicator.display = False
        container.mount(indicator)
        container.scroll_end(animate=False)
        return indicator

    def _mount_media_preview_skeleton(self, label: str) -> MediaPreview:
        """Mount a MediaPreview with no URL — shows skeleton animation until loaded."""
        container = self.query_one("#messages")
        preview = MediaPreview(url="", label=label, media_type="image")
        container.mount(preview)
        container.scroll_end(animate=False)
        return preview

    def _mount_media_preview(self, url: str, label: str, media_type: str = "image") -> MediaPreview:
        container = self.query_one("#messages")
        preview = MediaPreview(url=url, label=label, media_type=media_type)
        container.mount(preview)
        container.scroll_end(animate=False)
        return preview

    @work(thread=True)
    def _load_media_preview(self, preview: MediaPreview) -> None:
        self._load_preview_with_input_guard(preview)

    def _scroll_messages(self) -> None:
        self.query_one("#messages").scroll_end(animate=False)

    def _show_error(self, msg: str) -> None:
        container = self.query_one("#messages")
        t = THEMES.get(self._theme_key, THEMES[DEFAULT_THEME])
        container.mount(Static(f"[bold {t['error']}]{msg}[/bold {t['error']}]"))
        container.scroll_end(animate=False)

    def on_media_preview_action_requested(self, event: MediaPreview.ActionRequested) -> None:
        """Show action menu when user clicks a media preview."""
        preview = event.preview
        options = ["Open in viewer", "Copy URL", "Save to ~/Downloads"]

        def on_select(answer: str) -> None:
            container = self.query_one("#messages")
            if answer == "Open in viewer":
                preview.open_media()
            elif answer == "Copy URL":
                if preview.copy_url():
                    container.mount(Static("[dim]URL copied to clipboard.[/dim]"))
                else:
                    container.mount(Static("[red]Failed to copy URL.[/red]"))
                container.scroll_end(animate=False)
            elif answer.startswith("Save"):
                container.mount(Static("[dim]Downloading...[/dim]"))
                container.scroll_end(animate=False)
                self._save_media_locally(preview)

        choice_menu = self.query_one(ChoiceMenu)
        choice_menu.show_question("Media action:", options, on_select)

    @work(thread=True)
    def _save_media_locally(self, preview: MediaPreview) -> None:
        path = preview.save_locally()
        if path:
            self.call_from_thread(
                self._mount_status, f"[dim]Saved to {path}[/dim]"
            )
        else:
            self.call_from_thread(
                self._mount_status, "[red]Download failed.[/red]"
            )

    def _show_cancelled(self) -> None:
        container = self.query_one("#messages")
        t = THEMES.get(self._theme_key, THEMES[DEFAULT_THEME])
        container.mount(Static(f"[{t['text_muted']}]Generation cancelled.[/{t['text_muted']}]"))
        container.scroll_end(animate=False)
