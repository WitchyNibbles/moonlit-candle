"""~/.cache/witchy/caret: the prompt caret's colour on a sabbat and its eve (prompt takeover spec 15.3).

The sky job writes two lines, today's and tomorrow's: "<YYYY-MM-DD> <HEX> <sabbat>" when that day or the next
is a sabbat, else "<YYYY-MM-DD>". conf.d/witchy.fish reads the line for today with fish's read and sets a
global tide_character_color; tomorrow's line lets the first shell of a day show the right caret before the job
has run. doctor reads the file too.
"""
from __future__ import annotations

import os
import re
import tempfile
from datetime import date, timedelta, tzinfo
from pathlib import Path

from . import palette, wheel

NAME = "caret"
EVE_DAYS = 1  # the day before a sabbat wears its colour too
LINE = re.compile(r"(\d{4}-\d\d-\d\d)(?: ([0-9A-F]{6}) ([a-z]+))?")


def colour(day: date, tz: tzinfo | None) -> tuple[str, str] | None:
    """The sabbat on ``day`` or the day after, and its colour as Tide writes it (no "#"); None for gold."""
    found = wheel.upcoming(day, tz)
    if found is None or found[1] > EVE_DAYS:
        return None
    name = found[0].lower()
    return name, palette.PALETTE[name].lstrip("#").upper()


def line(day: date, tz: tzinfo | None) -> str:
    found = colour(day, tz)
    return day.isoformat() if found is None else f"{day.isoformat()} {found[1]} {found[0]}"


def text(day: date, tz: tzinfo | None) -> str:
    """The whole file: the line for ``day`` and the line for the day after."""
    return "".join(line(day + timedelta(days=offset), tz) + "\n" for offset in (0, 1))


def write(path: Path, day: date, tz: tzinfo | None) -> None:
    """Replace the file whole, so a shell never reads half of it. Raises OSError."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text(day, tz))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read(path: Path) -> dict[str, tuple[str, str] | None]:
    """Each well-formed line's date and its (sabbat, colour), or None for gold. Raises OSError without a file."""
    found = {}
    for entry in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LINE.fullmatch(entry)
        if match:
            found[match.group(1)] = (match.group(3), match.group(2)) if match.group(2) else None
    return found
