"""The pieces witchy installs, in the order they are installed."""
from __future__ import annotations

from .claude import ClaudeComponent
from .windows_terminal import WindowsTerminalComponent


def all_components() -> list:
    return [ClaudeComponent(), WindowsTerminalComponent()]


NAMES: tuple[str, ...] = tuple(component.name for component in all_components())
