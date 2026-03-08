"""Provider abstraction for LLM streaming."""

from abc import ABC, abstractmethod
from typing import Iterator


class ProviderBase(ABC):
    @abstractmethod
    def get_auth_key(self) -> str:
        ...

    @abstractmethod
    def stream_chat(self, model: str, messages: list, tools: list) -> Iterator[tuple]:
        """Yield (type, data) tuples: ("content", str), ("tool_calls", list), ("error", str), ("done", dict)."""
        ...


def get_provider(name: str = "openrouter") -> ProviderBase:
    if name == "openrouter":
        from .openrouter import OpenRouterProvider
        return OpenRouterProvider()
    raise ValueError(f"Unknown provider: {name}")
