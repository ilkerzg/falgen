"""Textual widgets for fal-dev chat — OpenCode-inspired design.

Key design language (from OpenCode):
- Messages use LEFT THICK BORDER only (no box)
- User = secondary color (purple), Assistant = primary (blue), Tool = muted (grey)
- Minimal chrome, clean spacing, theme-aware everything
"""

import os
import re
import shutil
import subprocess
import tempfile

from textual import work
from textual.reactive import reactive
from textual.widgets import Input, Markdown, Static

from .config import (
    DEFAULT_THEME,
    HELP_COMMANDS,
    LOGO_GEN,
    LOGO_MEDIA,
    THEMES,
)


def _get_theme(app) -> dict:
    key = getattr(app, "_theme_key", DEFAULT_THEME)
    return THEMES.get(key, THEMES[DEFAULT_THEME])


# ── Thick left-border character ──────────────────────────────────
# Thick left border rendered as a full-height Unicode block
THICK_BAR = "\u2503"  # ┃


class UserMessage(Static):
    """User message with left thick border in secondary (purple) color."""

    DEFAULT_CSS = """
    UserMessage {
        margin: 1 0 0 0;
        padding: 0 1 0 0;
    }
    """

    def __init__(self, text: str) -> None:
        super().__init__()
        self._text = text

    def render(self):
        from rich.text import Text as RichText

        t = _get_theme(self.app)
        rt = RichText()
        lines = self._text.split("\n")
        for i, line in enumerate(lines):
            if i > 0:
                rt.append("\n")
            rt.append(f" {THICK_BAR} ", style=f"bold {t['secondary']}")
            rt.append(line, style=t["text"])
        return rt


class AssistantMarkdown(Markdown):
    """Markdown widget for assistant responses with left border styling."""

    DEFAULT_CSS = """
    AssistantMarkdown {
        margin: 0 0 0 0;
        padding: 0 1 0 3;
        border-left: thick $accent;
    }
    """


class ToolCallStatus(Static):
    """Tool call indicator with left thick border in muted color.

    Supports live progress updates for long-running tools (generate).
    """

    DEFAULT_CSS = """
    ToolCallStatus {
        margin: 0 0 0 0;
        padding: 0 1 0 0;
    }
    """

    def __init__(self, tool_name: str, args_preview: str, status: str = "running") -> None:
        self._tool_name = tool_name
        self._args_preview = args_preview
        self._status = status
        self._progress_line = ""
        super().__init__()

    def render(self):
        from rich.text import Text as RichText

        t = _get_theme(self.app)
        rt = RichText()
        rt.append(f" {THICK_BAR} ", style=f"{t['text_muted']}")

        if self._status == "running":
            rt.append("\u25cb ", style=f"{t['warning']}")
        elif self._status == "done":
            rt.append("\u25cf ", style=f"{t['success']}")
        elif self._status == "error":
            rt.append("\u25cf ", style=f"{t['error']}")

        rt.append(self._tool_name, style=f"bold {t['text']}")
        if self._args_preview:
            rt.append(f"  {self._args_preview}", style=f"{t['text_muted']}")

        # Progress line (queue position, elapsed, etc.)
        if self._progress_line:
            rt.append(f"  {self._progress_line}", style=f"italic {t['accent']}")

        return rt

    def set_progress(self, text: str):
        self._progress_line = text
        self.refresh()

    def set_done(self, elapsed: float = 0):
        self._status = "done"
        if elapsed > 0:
            self._progress_line = f"{elapsed:.1f}s"
        else:
            self._progress_line = ""
        self.refresh()

    def set_error(self):
        self._status = "error"
        self._progress_line = ""
        self.refresh()


class WelcomeBanner(Static):
    """Welcome banner — OpenCode style: centered two-tone logo + command table."""

    DEFAULT_CSS = """
    WelcomeBanner {
        margin: 4 1 1 1;
        padding: 1 2;
    }
    """

    def __init__(self, model: str) -> None:
        self._model = model
        super().__init__()

    def render(self):
        from rich.text import Text as RichText

        t = _get_theme(self.app)
        rt = RichText()

        try:
            term_w = self.app.size.width - 6  # account for padding/margin
        except Exception:
            term_w = 80

        # ── Logo: GEN (bright) + SH (muted) ──
        logo_w = len(LOGO_GEN[0]) + len(LOGO_MEDIA[0])
        logo_pad = max(0, (term_w - logo_w) // 2)
        pad = " " * logo_pad

        for gen_line, media_line in zip(LOGO_GEN, LOGO_MEDIA):
            rt.append(pad)
            rt.append(gen_line, style=f"bold {t['text']}")
            rt.append(media_line, style=f"{t['text_muted']}")
            rt.append("\n")

        # "powered by fal.ai" right-aligned under logo
        powered = "powered by fal.ai"
        powered_pad = max(0, logo_pad + logo_w - len(powered))
        rt.append(" " * powered_pad)
        rt.append(powered, style=f"{t['text_muted']}")
        rt.append("\n\n")

        # ── Command table ──
        col_cmd = max(len(c[0]) for c in HELP_COMMANDS) + 2
        col_desc = max(len(c[1]) for c in HELP_COMMANDS) + 2
        table_w = col_cmd + col_desc + 10  # keybind column
        table_pad = " " * max(0, (term_w - table_w) // 2)

        for cmd, desc, key in HELP_COMMANDS:
            rt.append(table_pad)
            rt.append(cmd.ljust(col_cmd), style=f"bold {t['primary']}")
            rt.append(desc.ljust(col_desc), style=f"{t['text_muted']}")
            if key:
                rt.append(key, style=f"{t['text_muted']}")
            rt.append("\n")

        # ── Model info ──
        rt.append("\n")
        model_line = f"model  {self._model}"
        model_pad = " " * max(0, (term_w - len(model_line)) // 2)
        rt.append(model_pad)
        rt.append("model  ", style=f"{t['text_muted']}")
        rt.append(self._model, style=f"bold {t['text']}")
        rt.append("\n")

        return rt


class ChatInput(Input):
    """Chat input — clean border, focus-aware color, multi-line paste support."""

    DEFAULT_CSS = """
    ChatInput {
        dock: bottom;
        margin: 1 1 1 1;
        border: round $accent-darken-3;
        background: $surface;
        padding: 0 1;
    }
    ChatInput:focus {
        border: round $accent;
    }
    """

    # Matches escape sequences and control chars that leak from terminal responses
    _GARBAGE_RE = re.compile(
        r'\x1b\][^\x07\x1b]{0,80}(?:\x07|\x1b\\?)?'  # OSC (possibly incomplete)
        r'|\x1b\[[\x20-\x3f]*[\x40-\x7e]'  # CSI
        r'|\^\[[\x20-\x3f]*[\x40-\x7e]'  # caret-notation CSI (e.g. ^[6;14;7t)
        r'|\x1b[^\[\]]{0,2}'  # other ESC sequences
        r'|\x1b'  # lone ESC
        r'|[\x00-\x08\x0e-\x1f\x7f]'  # control chars (keep \t \n \r)
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pasted_text: str | None = None
        self._preview_value: str | None = None
        self._pasted_image: bytes | None = None
        self._pasted_image_mime: str | None = None
        self._multiline_buffer: list[str] = []

    def add_line(self) -> None:
        """Add current input as a new line in multi-line buffer (Shift+Enter)."""
        current = self.value
        self._multiline_buffer.append(current)
        count = len(self._multiline_buffer)
        first = self._multiline_buffer[0][:40]
        if len(self._multiline_buffer[0]) > 40:
            first += "..."
        self.value = f"{first}  (+{count} lines, Shift+Enter for more)"
        self._preview_value = self.value
        self.cursor_position = 0  # place cursor at start for new line content

    def get_effective_value(self) -> str:
        """Return full text including multi-line buffer."""
        if self._multiline_buffer:
            # Current value may be the preview or new typed text
            current = self.value
            if current == self._preview_value:
                # User didn't type anything new — just submit buffer
                result = "\n".join(self._multiline_buffer)
            else:
                # User typed more after Shift+Enter
                self._multiline_buffer.append(current)
                result = "\n".join(self._multiline_buffer)
            self._multiline_buffer = []
            self._preview_value = None
            return result.strip()

        if self._pasted_text is not None and self._preview_value is not None:
            if self.value == self._preview_value:
                return self._pasted_text
            if self.value.startswith(self._preview_value):
                appended = self.value[len(self._preview_value):]
                return self._pasted_text + "\n" + appended.strip()
        self._pasted_text = None
        self._preview_value = None
        return self.value.strip()

    def insert_text_at_cursor(self, text: str) -> None:
        """Only allow printable characters into the input.

        Terminal escape-sequence responses arrive as key events with
        control characters (\x1b, \x07, etc.) mixed with normal chars.
        Drop anything that isn't a regular printable character.
        """
        filtered = "".join(c for c in text if c >= " " and c != "\x7f")
        if filtered:
            super().insert_text_at_cursor(filtered)

    def validate_value(self, value: str) -> str:
        """Strip escape sequences / control chars before value is set.

        Called by Textual's reactive system before the value is stored,
        preventing terminal response garbage from ever appearing.
        """
        return self._GARBAGE_RE.sub("", value)

    # 100KB max for pasted text
    _MAX_PASTE_SIZE = 100 * 1024

    def _on_paste(self, event) -> None:
        """Intercept paste: handle multi-line and very long single-line pastes."""
        text = event.text

        # Short single-line paste — let Input handle it normally
        if len(text.splitlines()) <= 1 and len(text) <= 500:
            return

        # Everything else: intercept and show preview
        event.prevent_default()

        full_text = text.strip()

        # Truncate very large pastes
        if len(full_text) > self._MAX_PASTE_SIZE:
            full_text = full_text[:self._MAX_PASTE_SIZE]
            truncated = True
        else:
            truncated = False

        lines = full_text.splitlines()
        self._pasted_text = full_text

        first_line = lines[0][:60].rstrip()
        if len(lines[0]) > 60:
            first_line += "..."

        if len(lines) > 1:
            extra = len(lines) - 1
            preview = f"{first_line}  (+{extra} lines)"
        else:
            size_kb = len(full_text) / 1024
            preview = f"{first_line}  ({size_kb:.0f}KB)"

        if truncated:
            preview += "  [truncated to 100KB]"
        self._preview_value = preview
        self.value = preview
        self.cursor_position = len(self.value)

    # 20MB max for pasted images
    _MAX_IMAGE_SIZE = 20 * 1024 * 1024

    def set_pasted_image(self, data: bytes, mime: str) -> bool:
        """Store pasted image data for upload on submit. Returns False if too large."""
        if len(data) > self._MAX_IMAGE_SIZE:
            size_mb = len(data) / (1024 * 1024)
            self.value = f"[image too large: {size_mb:.1f}MB, max 20MB]"
            self.cursor_position = len(self.value)
            return False
        self._pasted_image = data
        self._pasted_image_mime = mime
        size_kb = len(data) / 1024
        if size_kb >= 1024:
            size_str = f"{size_kb / 1024:.1f}MB"
        else:
            size_str = f"{size_kb:.0f}KB"
        self._preview_value = f"[image: {size_str}]"
        self.value = self._preview_value
        self.cursor_position = len(self.value)
        return True

    def has_pasted_image(self) -> bool:
        return self._pasted_image is not None

    def take_pasted_image(self) -> tuple[bytes, str] | None:
        """Return and clear pasted image data."""
        if self._pasted_image is None:
            return None
        result = (self._pasted_image, self._pasted_image_mime or "image/png")
        self._pasted_image = None
        self._pasted_image_mime = None
        return result

    def clear(self) -> None:
        self._pasted_text = None
        self._preview_value = None
        self._pasted_image = None
        self._pasted_image_mime = None
        self._multiline_buffer = []
        self.value = ""


class SlashMenu(Static):
    """Autocomplete dropdown for slash commands."""

    DEFAULT_CSS = """
    SlashMenu {
        layer: overlay;
        dock: bottom;
        margin: 0 1 4 1;
        max-height: 14;
        overflow-y: auto;
        background: $surface;
        border: round $accent-darken-2;
        padding: 0 1;
        display: none;
    }
    """

    selected_index = reactive(0)

    def __init__(self) -> None:
        super().__init__()
        self._items: list[tuple[str, str, str]] = []

    def set_commands(self, commands):
        self._all_commands = [
            (cmd.name, cmd.args_hint, cmd.description)
            for cmd in commands
        ]

    def filter(self, text: str) -> None:
        query = text.lower()
        self._items = [c for c in self._all_commands if c[0].startswith(query)]
        self.selected_index = 0
        if self._items:
            self.display = True
            self.refresh()
        else:
            self.display = False

    def hide(self) -> None:
        self.display = False

    def move_selection(self, delta: int) -> None:
        if not self._items:
            return
        self.selected_index = max(0, min(len(self._items) - 1, self.selected_index + delta))
        self.refresh()

    def get_selected(self) -> str | None:
        if not self._items:
            return None
        cmd, args, _desc = self._items[self.selected_index]
        return f"{cmd} {args}".rstrip() if args else cmd

    def get_selected_parts(self) -> tuple[str, str] | None:
        """Return (command_name, args_hint) or None."""
        if not self._items:
            return None
        cmd, args, _desc = self._items[self.selected_index]
        return (cmd, args)

    def render(self):
        from rich.text import Text as RichText

        t = _get_theme(self.app)
        rt = RichText()
        for i, (cmd, args, desc) in enumerate(self._items):
            if i > 0:
                rt.append("\n")
            if i == self.selected_index:
                rt.append(f" {cmd}", style=f"bold {t['primary']}")
                if args:
                    rt.append(f" {args}", style=f"{t['text_muted']}")
                rt.append(f"  {desc}", style=f"italic {t['text']}")
            else:
                rt.append(f" {cmd}", style=f"bold {t['text']}")
                if args:
                    rt.append(f" {args}", style="dim")
                rt.append(f"  {desc}", style=f"{t['text_muted']}")
        return rt


# ── ASCII skeleton with shine sweep ──────────────────────────────

_SKEL_W = 36
_SKEL_H = 10
_SHINE_WIDTH = 4

# The base ASCII "image frame"
_SKEL_ART = [
    "╔══════════════════════════════════╗",
    "║                                  ║",
    "║        ┌──────────────┐          ║",
    "║        │   ▓▓    ▓▓   │          ║",
    "║        │  ▓▓▓▓▓▓▓▓▓▓  │          ║",
    "║        │   ▓▓▓▓▓▓▓▓   │          ║",
    "║        │    ▓▓▓▓▓▓    │          ║",
    "║        └──────────────┘          ║",
    "║                                  ║",
    "╚══════════════════════════════════╝",
]

# Characters that glow during shine pass: dim → mid → bright → mid → dim
_SHINE_CHARS = " .:`"


class MediaPreview(Static):
    """Media preview widget: skeleton loading → chafa render → click to open.

    Supports image, video, and audio media types.

    Posts ActionRequested message on click for parent to handle.
    - image: chafa render directly
    - video: ffmpeg extract first frame → chafa render thumbnail
    - audio: ffmpeg generate waveform PNG → chafa render

    Usage:
        w = MediaPreview(url="https://...", label="fal-ai/flux/dev", media_type="image")
        container.mount(w)
        # call w.load_from_url() from a background thread
    """

    from textual.message import Message as _Message

    class ActionRequested(_Message):
        """Posted when user clicks the preview to request actions."""
        def __init__(self, preview: "MediaPreview") -> None:
            self.preview = preview
            super().__init__()

    DEFAULT_CSS = """
    MediaPreview {
        margin: 1 0 1 3;
        padding: 0 1;
        min-height: 3;
    }
    """

    _frame_index = reactive(0)

    def __init__(self, url: str, label: str = "", media_type: str = "image") -> None:
        super().__init__()
        self._url = url
        self._label = label
        self._media_type = media_type  # "image", "video", "audio"
        self._chafa_output: str | None = None
        self._local_path: str | None = None
        self._loading = True
        self._error: str | None = None
        self._duration: float | None = None
        self._temp_files: set[str] = set()

    def on_mount(self) -> None:
        if self._loading:
            self._animate_skeleton()

    @work()
    async def _animate_skeleton(self) -> None:
        import asyncio
        total_sweep = _SKEL_W + _SHINE_WIDTH * 2
        while self._loading:
            self._frame_index = (self._frame_index + 1) % total_sweep
            await asyncio.sleep(0.07)

    def render(self):
        from rich.text import Text as RichText

        t = _get_theme(self.app)
        rt = RichText()

        if self._error:
            rt.append(f"  {self._media_type} error: {self._error}", style=f"{t['error']}")
            return rt

        if self._loading:
            # ASCII art with shine sweep
            shine_pos = self._frame_index - _SHINE_WIDTH
            for row in _SKEL_ART:
                rt.append("  ")
                for col, ch in enumerate(row):
                    dist = col - shine_pos
                    if 0 <= dist < _SHINE_WIDTH:
                        brightness = 1.0 - (dist / _SHINE_WIDTH)
                        if brightness > 0.7:
                            rt.append(ch, style=f"bold {t['text']}")
                        elif brightness > 0.3:
                            rt.append(ch, style=f"{t['primary']}")
                        else:
                            rt.append(ch, style=f"{t['text_muted']}")
                    else:
                        rt.append(ch, style=f"{t['border_dim']}")
                rt.append("\n")
            rt.append("  generating...", style=f"italic {t['text_muted']}")
            return rt

        # Loaded — show chafa output (contains ANSI escape codes)
        if self._chafa_output:
            from rich.text import Text as AnsiText
            ansi_rendered = AnsiText.from_ansi(self._chafa_output)
            rt.append_text(ansi_rendered)

        # Footer varies by media type
        rt.append("\n  ")
        if self._media_type == "video" and self._duration is not None:
            rt.append(f"[>] {self._duration:.1f}s  ", style=f"bold {t['accent']}")
        elif self._media_type == "audio" and self._duration is not None:
            rt.append(f"[~] {self._duration:.1f}s  ", style=f"bold {t['accent']}")

        rt.append(f"{self._label}", style=f"bold {t['text_muted']}")
        rt.append(f"  {self._url}", style=f"underline {t['primary']}")
        rt.append("  [click to open]", style=f"italic {t['text_muted']}")

        return rt

    def on_click(self) -> None:
        """Show action menu on click."""
        from textual import events
        self.post_message(self.ActionRequested(self))

    def open_media(self) -> None:
        """Open media in system viewer/player."""
        path = self._local_path or self._url
        if path:
            import platform
            if platform.system() == "Darwin":
                subprocess.Popen(["open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif platform.system() == "Linux":
                subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def copy_url(self) -> bool:
        """Copy media URL to clipboard. Returns True on success."""
        if not self._url:
            return False
        import platform
        try:
            if platform.system() == "Darwin":
                subprocess.run(["pbcopy"], input=self._url.encode(), check=True, timeout=3)
            elif platform.system() == "Linux":
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=self._url.encode(), check=True, timeout=3,
                )
            else:
                return False
            return True
        except (FileNotFoundError, subprocess.SubprocessError):
            return False

    def save_locally(self) -> str | None:
        """Download media to ~/Downloads/. Returns saved path or None."""
        if not self._url:
            return None
        import httpx
        downloads = os.path.expanduser("~/Downloads")
        os.makedirs(downloads, exist_ok=True)

        # Determine filename from URL
        url_path = self._url.split("?")[0]
        basename = os.path.basename(url_path)
        if not basename or "." not in basename:
            ext = ".png" if self._media_type == "image" else ".mp4" if self._media_type == "video" else ".mp3"
            from datetime import datetime
            basename = f"falgen_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"

        save_path = os.path.join(downloads, basename)
        try:
            resp = httpx.get(self._url, timeout=60, follow_redirects=True)
            resp.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(resp.content)
            return save_path
        except Exception:
            return None

    def _probe_duration(self, file_path: str) -> float | None:
        """Get media duration in seconds using ffprobe."""
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return None
        try:
            result = subprocess.run(
                [ffprobe, "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", file_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception:
            pass
        return None

    def _extract_video_thumbnail(self, video_path: str) -> str | None:
        """Extract first frame from video using ffmpeg. Returns thumbnail path or None."""
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return None
        thumb_path = video_path + ".thumb.png"
        try:
            result = subprocess.run(
                [ffmpeg, "-y", "-i", video_path, "-vframes", "1",
                 "-f", "image2", thumb_path],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and os.path.exists(thumb_path):
                return thumb_path
        except Exception:
            pass
        return None

    def _generate_waveform(self, audio_path: str) -> str | None:
        """Generate waveform PNG from audio using ffmpeg. Returns waveform path or None."""
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return None
        wave_path = audio_path + ".wave.png"
        try:
            result = subprocess.run(
                [ffmpeg, "-y", "-i", audio_path,
                 "-filter_complex", "showwavespic=s=640x240:colors=#4a9eff",
                 "-frames:v", "1", wave_path],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and os.path.exists(wave_path):
                return wave_path
        except Exception:
            pass
        return None

    def _render_chafa(self, image_path: str) -> str | None:
        """Render image with chafa in an isolated PTY.

        Chafa sends terminal query escape sequences (background color, device
        attributes, window size) in its output.  When those reach the real
        terminal, the terminal responds with sequences that leak into our
        Input widget as garbage text.

        Running chafa with stdout connected to a *separate* PTY means:
        - chafa sees ``isatty()=True`` → outputs full 256-color ANSI
        - queries go into the PTY, **not** the real terminal
        - we read the master end and sanitize before storing
        """
        chafa = shutil.which("chafa")
        if not chafa:
            return None

        cmd = [
            chafa, "--size", "60x20", "--animate=off",
            "--format=symbols", "--color-space=din99d",
            "--passthrough=none",
            image_path,
        ]

        # ── Try PTY-isolated execution ──────────────────────────────
        try:
            import pty as pty_mod
            import select as select_mod

            master_fd, slave_fd = pty_mod.openpty()

            # Tell the PTY slave a reasonable size so chafa formats correctly
            try:
                import fcntl, struct, termios
                winsize = struct.pack("HHHH", 25, 80, 0, 0)
                fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)
            except Exception:
                pass

            proc = subprocess.Popen(
                cmd,
                stdout=slave_fd,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                close_fds=True,
                env={**os.environ, "TERM": "xterm-256color"},
            )
            os.close(slave_fd)

            chunks: list[bytes] = []
            while True:
                ready, _, _ = select_mod.select([master_fd], [], [], 10.0)
                if not ready:
                    break
                try:
                    data = os.read(master_fd, 16384)
                    if not data:
                        break
                    chunks.append(data)
                except OSError:
                    break

            os.close(master_fd)
            proc.wait(timeout=5)

            if proc.returncode == 0 and chunks:
                raw = b"".join(chunks).decode("utf-8", errors="replace")
                return self._sanitize_ansi(raw.rstrip("\n"))
        except Exception:
            pass

        # ── Fallback: pipe mode (no color queries but may lack some color) ─
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10,
                stdin=subprocess.DEVNULL,
                env={**os.environ, "TERM": "xterm-256color"},
            )
            if result.returncode == 0:
                return self._sanitize_ansi(result.stdout.rstrip("\n"))
        except Exception:
            pass

        return None

    @staticmethod
    def _sanitize_ansi(raw: str) -> str:
        """Whitelist: keep ONLY SGR sequences (\\x1b[...m) and printable text.

        Strips ALL other escape sequences (OSC, CSI queries, DCS, etc.)
        to prevent terminal query responses from leaking into input.
        """
        import re

        sgr_re = re.compile(r'(\x1b\[[0-9;]*m)')
        parts = sgr_re.split(raw)
        cleaned = []
        for part in parts:
            if sgr_re.fullmatch(part):
                cleaned.append(part)  # SGR — keep
            else:
                # Strip well-formed sequences first, then any remaining ESC
                part = re.sub(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)', '', part)  # OSC
                part = re.sub(r'\x1b[^\x1b]{0,40}?[a-zA-Z~\\@`]', '', part)
                part = re.sub(r'\x1b.?', '', part)  # lone ESC
                part = re.sub(r'[\x00-\x08\x0e-\x1f\x7f]', '', part)  # control chars
                cleaned.append(part)
        return ''.join(cleaned)

    def _load_image(self, resp_content: bytes, content_type: str) -> None:
        """Handle image media type."""
        suffix = ".png"
        if "jpeg" in content_type or "jpg" in self._url:
            suffix = ".jpg"
        elif "webp" in content_type:
            suffix = ".webp"

        if shutil.which("chafa") is None:
            self._error = "chafa not installed (brew install chafa)"
            return

        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False, prefix="fal_chat_")
        tmp.write(resp_content)
        tmp.close()
        self._local_path = tmp.name
        self._temp_files.add(tmp.name)

        chafa_out = self._render_chafa(self._local_path)
        if chafa_out is None:
            self._error = "chafa render failed"
            return
        self._chafa_output = chafa_out

    def _load_video(self, resp_content: bytes, content_type: str) -> None:
        """Handle video media type."""
        ext_map = {
            "mp4": ".mp4", "webm": ".webm", "quicktime": ".mov",
            "x-msvideo": ".avi", "x-matroska": ".mkv",
        }
        suffix = ".mp4"
        for key, ext in ext_map.items():
            if key in content_type or self._url.lower().split("?")[0].endswith(ext):
                suffix = ext
                break

        if shutil.which("ffmpeg") is None:
            self._error = "install ffmpeg for video preview"
            return
        if shutil.which("chafa") is None:
            self._error = "chafa not installed (brew install chafa)"
            return

        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False, prefix="fal_chat_")
        tmp.write(resp_content)
        tmp.close()
        self._local_path = tmp.name
        self._temp_files.add(tmp.name)

        self._duration = self._probe_duration(self._local_path)

        thumb_path = self._extract_video_thumbnail(self._local_path)
        if not thumb_path:
            self._error = "ffmpeg failed to extract thumbnail"
            return

        chafa_out = self._render_chafa(thumb_path)
        if chafa_out is None:
            self._error = "chafa render failed"
            return
        self._chafa_output = chafa_out
        # Clean up thumbnail temp file
        try:
            os.unlink(thumb_path)
        except OSError:
            pass

    def _load_audio(self, resp_content: bytes, content_type: str) -> None:
        """Handle audio media type."""
        ext_map = {
            "mpeg": ".mp3", "wav": ".wav", "ogg": ".ogg",
            "flac": ".flac", "aac": ".aac", "mp4": ".m4a",
        }
        suffix = ".mp3"
        for key, ext in ext_map.items():
            if key in content_type or self._url.lower().split("?")[0].endswith(ext):
                suffix = ext
                break

        if shutil.which("ffmpeg") is None:
            self._error = "install ffmpeg for audio preview"
            return
        if shutil.which("chafa") is None:
            self._error = "chafa not installed (brew install chafa)"
            return

        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False, prefix="fal_chat_")
        tmp.write(resp_content)
        tmp.close()
        self._local_path = tmp.name
        self._temp_files.add(tmp.name)

        self._duration = self._probe_duration(self._local_path)

        wave_path = self._generate_waveform(self._local_path)
        if not wave_path:
            self._error = "ffmpeg failed to generate waveform"
            return

        chafa_out = self._render_chafa(wave_path)
        if chafa_out is None:
            self._error = "chafa render failed"
            return
        self._chafa_output = chafa_out
        # Clean up waveform temp file
        try:
            os.unlink(wave_path)
        except OSError:
            pass

    def load_from_url(self) -> None:
        """Download media and render preview. Call from a background thread."""
        import httpx

        try:
            resp = httpx.get(self._url, timeout=60, follow_redirects=True)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")

            if self._media_type == "video":
                self._load_video(resp.content, content_type)
            elif self._media_type == "audio":
                self._load_audio(resp.content, content_type)
            else:
                self._load_image(resp.content, content_type)

        except Exception as e:
            self._error = str(e)[:100]

        self._loading = False
        self.refresh()

    def on_unmount(self) -> None:
        """Clean up temp files when widget is removed."""
        for path in self._temp_files:
            try:
                os.unlink(path)
            except OSError:
                pass


class AskUserWidget(Static):
    """Inline widget showing an ask_user question and (after answered) the answer."""

    DEFAULT_CSS = """
    AskUserWidget {
        margin: 1 0 0 0;
        padding: 0 1 0 0;
    }
    """

    def __init__(self, question: str) -> None:
        super().__init__()
        self._question = question
        self._answer: str | None = None

    def set_answer(self, answer: str) -> None:
        self._answer = answer
        self.refresh()

    def render(self):
        from rich.text import Text as RichText

        t = _get_theme(self.app)
        rt = RichText()
        rt.append(f" {THICK_BAR} ", style=f"bold {t['accent']}")
        rt.append("? ", style=f"bold {t['accent']}")
        rt.append(self._question, style=f"{t['text']}")
        if self._answer is not None:
            rt.append(f"\n {THICK_BAR} ", style=f"bold {t['accent']}")
            rt.append(f"→ {self._answer}", style=f"bold {t['primary']}")
        return rt


class ChoiceMenu(Static):
    """Overlay menu for ask_user — shows question + numbered options + Other.

    Features:
    - Fuzzy filter: type to narrow options
    - Scroll indicator: shows position when list is long
    - Cancel callback: escape properly unblocks waiting threads
    """

    DEFAULT_CSS = """
    ChoiceMenu {
        layer: overlay;
        dock: bottom;
        margin: 0 1 4 1;
        max-height: 16;
        overflow-y: auto;
        background: $surface;
        border: round $accent;
        padding: 1 2;
        display: none;
    }
    """

    selected_index = reactive(0)

    # Max visible options before showing scroll indicator
    _MAX_VISIBLE = 10

    def __init__(self) -> None:
        super().__init__()
        self._question = ""
        self._options: list[str] = []
        self._filtered: list[int] = []  # indices into _options
        self._filter_text = ""
        self._on_select = None
        self._on_cancel = None
        self._custom_mode = False
        self._custom_text = ""

    def show_question(self, question: str, options: list[str], on_select, on_cancel=None) -> None:
        self._question = question
        self._options = list(options)
        self._on_select = on_select
        self._on_cancel = on_cancel
        self._custom_mode = False
        self._custom_text = ""
        self._filter_text = ""
        self._filtered = list(range(len(self._options)))
        self.selected_index = 0
        self.display = True
        self.refresh()

    def hide(self) -> None:
        self.display = False
        self._on_select = None
        self._on_cancel = None

    def cancel(self) -> None:
        """Cancel the menu and notify any waiting thread."""
        callback = self._on_cancel
        self.hide()
        if callback:
            callback()

    @property
    def is_visible(self) -> bool:
        return self.display

    @property
    def in_custom_mode(self) -> bool:
        return self._custom_mode

    def _total_items(self) -> int:
        """Filtered options + 'Other...' entry."""
        return len(self._filtered) + 1

    def _apply_filter(self) -> None:
        """Filter options by fuzzy matching the filter text."""
        if not self._filter_text:
            self._filtered = list(range(len(self._options)))
        else:
            query = self._filter_text.lower()
            self._filtered = [
                i for i, opt in enumerate(self._options)
                if _fuzzy_match(query, opt.lower())
            ]
        self.selected_index = 0
        self.refresh()

    def handle_filter_key(self, key: str, character: str | None) -> None:
        """Handle typing for fuzzy filter mode."""
        if key == "backspace":
            if self._filter_text:
                self._filter_text = self._filter_text[:-1]
                self._apply_filter()
        elif character and len(character) == 1 and character.isprintable():
            self._filter_text += character
            self._apply_filter()

    def move_selection(self, delta: int) -> None:
        if self._custom_mode:
            return
        total = self._total_items()
        self.selected_index = max(0, min(total - 1, self.selected_index + delta))
        self.refresh()

    def confirm_selection(self) -> None:
        if self._custom_mode:
            if self._custom_text.strip():
                answer = self._custom_text.strip()
                callback = self._on_select
                self.hide()
                if callback:
                    callback(answer)
            return

        if self.selected_index < len(self._filtered):
            original_idx = self._filtered[self.selected_index]
            answer = self._options[original_idx]
            callback = self._on_select
            self.hide()
            if callback:
                callback(answer)
        else:
            # "Other..." selected — enter custom text mode
            self._custom_mode = True
            self._custom_text = ""
            self.refresh()

    def handle_custom_key(self, key: str, character: str | None) -> None:
        """Handle keystrokes in custom text mode."""
        if key == "escape":
            self._custom_mode = False
            self.refresh()
        elif key == "backspace":
            self._custom_text = self._custom_text[:-1]
            self.refresh()
        elif character and len(character) == 1 and character.isprintable():
            self._custom_text += character
            self.refresh()

    def _scroll_window(self) -> tuple[int, int]:
        """Calculate visible window [start, end) for scroll."""
        total = len(self._filtered)
        if total <= self._MAX_VISIBLE:
            return 0, total
        half = self._MAX_VISIBLE // 2
        start = max(0, self.selected_index - half)
        end = start + self._MAX_VISIBLE
        if end > total:
            end = total
            start = max(0, end - self._MAX_VISIBLE)
        return start, end

    def render(self):
        from rich.text import Text as RichText

        t = _get_theme(self.app)
        rt = RichText()

        # Question
        rt.append("? ", style=f"bold {t['accent']}")
        rt.append(self._question, style=f"bold {t['text']}")

        # Filter indicator
        if self._filter_text and not self._custom_mode:
            rt.append(f"  /{self._filter_text}", style=f"italic {t['primary']}")

        rt.append("\n")

        if self._custom_mode:
            rt.append("\n")
            rt.append("  Type your answer: ", style=f"{t['text_muted']}")
            rt.append(self._custom_text, style=f"bold {t['text']}")
            rt.append("▎", style=f"blink {t['primary']}")
            rt.append("\n")
            rt.append("  Enter to confirm, Escape to go back", style=f"italic {t['text_muted']}")
        else:
            total_filtered = len(self._filtered)

            if total_filtered == 0 and self._filter_text:
                rt.append("\n")
                rt.append("  No matches", style=f"italic {t['text_muted']}")
            else:
                start, end = self._scroll_window()

                # Scroll up indicator
                if start > 0:
                    rt.append("\n")
                    rt.append(f"    ... {start} more above", style=f"italic {t['text_muted']}")

                for vi, fi in enumerate(range(start, end)):
                    original_idx = self._filtered[fi]
                    option = self._options[original_idx]
                    rt.append("\n")
                    if fi == self.selected_index:
                        rt.append(f"  ▶ {option}", style=f"bold {t['primary']}")
                    else:
                        rt.append(f"    {option}", style=f"{t['text']}")

                # Scroll down indicator
                remaining = total_filtered - end
                if remaining > 0:
                    rt.append("\n")
                    rt.append(f"    ... {remaining} more below", style=f"italic {t['text_muted']}")

            # "Other..." entry
            rt.append("\n")
            other_idx = total_filtered
            if self.selected_index == other_idx:
                rt.append("  ▶ Other...", style=f"bold italic {t['primary']}")
            else:
                rt.append("    Other...", style=f"italic {t['text_muted']}")

            # Footer hints
            rt.append("\n")
            pos = f"{self.selected_index + 1}/{self._total_items()}"
            rt.append(f"  ↑↓ navigate  Enter select  Esc cancel  Type to filter  {pos}",
                      style=f"italic {t['text_muted']}")

        return rt


def _fuzzy_match(query: str, text: str) -> bool:
    """Simple fuzzy match — all query chars must appear in order in text."""
    qi = 0
    for ch in text:
        if qi < len(query) and ch == query[qi]:
            qi += 1
    return qi == len(query)


# Backward compat alias
ImagePreview = MediaPreview
