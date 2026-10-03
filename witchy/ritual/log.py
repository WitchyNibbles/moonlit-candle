"""~/.cache/witchy/ritual.log: the last 20 errors of the greeting and the sky job, for doctor."""
from __future__ import annotations

import fcntl
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import TextIO

NAME = "ritual.log"
MAX_LINES = 20
MAX_CHARS = 300  # per message; an exception's repr can hold the whole greeting
LOCK_TIMEOUT = 1.0  # seconds; past it the line is dropped, so a stuck writer never holds up a shell


def _lock(handle: TextIO) -> bool:
    """Take an exclusive lock on ``handle`` within LOCK_TIMEOUT; False when another writer still holds it."""
    deadline = time.monotonic() + LOCK_TIMEOUT
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.01)


def append(path: Path, message: str, now: datetime) -> None:
    """Add one line; never raises, because the greeting must stay silent.

    The greeting and the sky job may log at once: writers take ``ritual.log.lock`` in turn (a lock on the log
    itself would not hold across the replace) and swap in a whole new file, so a reader never sees half of one.
    """
    try:
        line = f"{now:%Y-%m-%dT%H:%M:%S} " + " ".join(message.split())[:MAX_CHARS]
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path.with_name(path.name + ".lock"), "a") as lock:
            if not _lock(lock):
                return
            old = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
            fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write("\n".join([*old, line][-MAX_LINES:]) + "\n")
                os.replace(tmp, path)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
    except (OSError, ValueError):
        pass


def last(path: Path) -> str | None:
    """The newest line, or None when there is no log."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return None
    return lines[-1] if lines else None
