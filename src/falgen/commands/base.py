"""Base class for slash commands."""

from abc import ABC, abstractmethod


class SlashCommand(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    def aliases(self) -> list[str]:
        return []

    @property
    def args_hint(self) -> str:
        return ""

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @abstractmethod
    def execute(self, app, arg: str) -> None:
        """Execute the command. `app` is FalChatApp, `arg` is everything after the command name."""
        ...
