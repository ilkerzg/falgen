"""falgen - AI media generation from the terminal."""

__version__ = "0.2.0"

import argparse
import sys

from .config import DEFAULT_MODEL


def main():
    """Entry point for the `falgen` command."""
    parser = argparse.ArgumentParser(description="falgen — AI creative engine powered by fal.ai")
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
