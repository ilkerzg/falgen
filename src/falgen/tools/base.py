"""Base class for chat tools."""

from abc import ABC, abstractmethod


class Tool(ABC):
    """Abstract base for an AI-callable tool."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """OpenAI-style parameters schema (properties, required, etc.)."""
        ...

    @abstractmethod
    def execute(self, args: dict) -> dict:
        """Execute the tool and return a result dict."""
        ...

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", **self.parameters},
            },
        }
