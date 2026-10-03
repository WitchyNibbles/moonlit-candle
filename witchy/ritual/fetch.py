"""A short system fetch from /etc and /proc; anything missing shows as --."""
from __future__ import annotations

import os
import unicodedata
from pathlib import Path
from typing import Callable, Mapping

DASH = "--"
LABEL_WIDTH = 8


def clean(text: str) -> str:
    """``text`` without control characters, so nothing it holds can move the cursor or change colours."""
    return "".join(ch for ch in text if not unicodedata.category(ch).startswith("C")).strip()


def _os_name(root: Path) -> str:
    for line in (root / "etc" / "os-release").read_text(encoding="utf-8", errors="replace").splitlines():
        key, _, value = line.partition("=")
        if key == "PRETTY_NAME":
            return value.strip().strip('"')
    raise ValueError("no PRETTY_NAME")


def _uptime(root: Path) -> str:
    minutes = int(float((root / "proc" / "uptime").read_text(encoding="ascii").split()[0]) // 60)
    days, rest = divmod(minutes, 24 * 60)
    hours, minutes = divmod(rest, 60)
    if days:
        return f"{days}d {hours}h"
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def _memory(root: Path) -> str:
    fields = {}
    for line in (root / "proc" / "meminfo").read_text(encoding="ascii").splitlines():
        key, _, value = line.partition(":")
        fields[key] = int(value.split()[0])  # kB
    total, available = fields["MemTotal"], fields["MemAvailable"]
    return f"{(total - available) / 2 ** 20:.1f} / {total / 2 ** 20:.1f} GiB"


def _shell(env: Mapping[str, str]) -> str:
    return f"fish {env['FISH_VERSION']}"


def lines(env: Mapping[str, str], root: Path = Path("/"),
          release: Callable[[], str] = lambda: os.uname().release) -> list[tuple[str, str]]:
    """(label, value) pairs; a value that cannot be read is --."""
    readers = (("os", lambda: _os_name(root)), ("kernel", release), ("uptime", lambda: _uptime(root)),
               ("memory", lambda: _memory(root)), ("shell", lambda: _shell(env)))
    result = []
    for label, reader in readers:
        try:
            value = clean(reader()) or DASH
        except (OSError, ValueError, KeyError, IndexError):
            value = DASH
        result.append((label, value))
    return result
