"""~/.cache/witchy/ritual.log: the last 20 errors of the greeting and the sky job, for doctor."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

NAME = "ritual.log"
MAX_LINES = 20


def append(path: Path, message: str, now: datetime) -> None:
    """Add one line; never raises, because the greeting must stay silent."""
    try:
        old = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        line = f"{now:%Y-%m-%dT%H:%M:%S} " + " ".join(message.split())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join([*old, line][-MAX_LINES:]) + "\n", encoding="utf-8")
    except (OSError, ValueError):
        pass


def last(path: Path) -> str | None:
    """The newest line, or None when there is no log."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return None
    return lines[-1] if lines else None
