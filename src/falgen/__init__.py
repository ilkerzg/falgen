"""falgen - AI media generation from the terminal."""

__version__ = "0.1.1"

import argparse
import subprocess
import sys

from .config import DEFAULT_MODEL


def _update():
    """Update falgen to the latest version."""
    print(f"Current version: {__version__}")
    print("Updating...")
    try:
        # Detect how falgen was installed and update accordingly
        import importlib.metadata
        installer = ""
        try:
            dist = importlib.metadata.distribution("falgen")
            installer_data = dist.read_text("INSTALLER") or ""
            installer = installer_data.strip()
        except Exception:
            pass

        # Try pipx first, then uv, then pip
        if subprocess.run(["pipx", "list"], capture_output=True).returncode == 0:
            result = subprocess.run(
                ["pipx", "upgrade", "falgen"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                print(result.stdout.strip() or "Updated via pipx.")
                return
            # If not installed via pipx, try reinstall
            if "not installed" in result.stderr.lower():
                pass
            else:
                print(result.stdout.strip())
                return

        if subprocess.run(["uv", "--version"], capture_output=True).returncode == 0:
            result = subprocess.run(
                ["uv", "tool", "install", "falgen", "--upgrade"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                print(result.stdout.strip() or "Updated via uv.")
                return

        # Fallback to pip
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "falgen"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print("Updated via pip.")
        else:
            print(f"Update failed: {result.stderr.strip()}")
    except Exception as e:
        print(f"Update failed: {e}")
        print("Try manually: pip install --upgrade falgen")


def main():
    """Entry point for the `falgen` command."""
    # Handle `falgen update` before argparse
    if len(sys.argv) == 2 and sys.argv[1] == "update":
        _update()
        return

    parser = argparse.ArgumentParser(description="falgen - AI creative engine powered by fal.ai")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"LLM model (default: {DEFAULT_MODEL})")
    parser.add_argument("-s", "--session", default=None, help="Resume session by ID, or 'last'")
    parser.add_argument("-v", "--version", action="version", version=f"falgen {__version__}")
    args = parser.parse_args()

    from .providers import get_provider

    provider = get_provider()
    fal_key = provider.get_auth_key()

    from .app import FalChatApp

    app = FalChatApp(model=args.model, fal_key=fal_key, session_id=args.session)
    app.run()
