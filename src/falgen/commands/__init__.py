"""Command registry with auto-discovery."""

import importlib
import inspect
import pkgutil

from .base import SlashCommand


class CommandRegistry:
    def __init__(self):
        self._commands: dict[str, SlashCommand] = {}

    def register(self, cmd: SlashCommand) -> None:
        self._commands[cmd.name] = cmd
        for alias in cmd.aliases:
            self._commands[alias] = cmd

    def get(self, name: str) -> SlashCommand | None:
        return self._commands.get(name)

    def all_unique(self) -> list[SlashCommand]:
        """Return unique commands (no alias duplicates), in insertion order."""
        seen = set()
        result = []
        for cmd in self._commands.values():
            if id(cmd) not in seen:
                seen.add(id(cmd))
                result.append(cmd)
        return result


def discover_commands() -> CommandRegistry:
    """Auto-import all command modules and collect registered commands."""
    registry = CommandRegistry()

    package = importlib.import_module(__package__)
    for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
        if modname == "base":
            continue
        mod = importlib.import_module(f"{__package__}.{modname}")
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if isinstance(attr, type) and issubclass(attr, SlashCommand) and attr is not SlashCommand and not inspect.isabstract(attr):
                registry.register(attr())

    return registry
