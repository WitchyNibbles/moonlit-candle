"""The pieces witchy installs, in the order they are installed."""
from __future__ import annotations

from .claude import ClaudeComponent
from .fish import FishComponent
from .font import FontComponent
from .windows_terminal import WindowsTerminalComponent


def all_components() -> list:
    return [ClaudeComponent(), FontComponent(), WindowsTerminalComponent(), FishComponent()]


NAMES: tuple[str, ...] = tuple(component.name for component in all_components())
