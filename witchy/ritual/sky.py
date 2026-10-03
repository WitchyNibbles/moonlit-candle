"""The sky job: point the Windows Terminal profile's backgroundImage at tonight's phase image (spec 4.5).

It edits the one value in place, so Windows Terminal's own formatting survives, and it shares
~/.cache/witchy/wt.lock with the installer.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from . import log, moon

CONFIG = Path(".claude/witchy/ritual-config.json")
CACHE = Path(".cache/witchy")
LOCK = "wt.lock"  # the same file as windows_terminal.WT_LOCK in the installer
STAMP = "sky-bin"
FAIL = "sky-fail"

LOCK_TIMEOUT = 10.0
KEY = "backgroundImage"


class SkyError(Exception):
    """The job left settings.json alone; the message says why."""


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    """Hold ``path`` like the installer's file_lock does, waiting up to LOCK_TIMEOUT seconds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as handle:
        deadline = time.monotonic() + LOCK_TIMEOUT
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SkyError(f"{path} is held by another process") from None
                time.sleep(0.1)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _write_atomic(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _profile(data: object, guid: str) -> dict | None:
    profiles = data.get("profiles") if isinstance(data, dict) else None
    listed = profiles.get("list") if isinstance(profiles, dict) else profiles
    for profile in listed if isinstance(listed, list) else []:
        if isinstance(profile, dict) and str(profile.get("guid", "")).lower() == guid.lower():
            return profile
    return None


def update(config: dict, lock: Path, target: int) -> bool:
    """Set the profile's backgroundImage to sky image ``target``; False when it already shows it."""
    settings, guid, sky = Path(config["settings"]), config["profile_guid"], config["sky"]
    with _locked(lock):
        raw = settings.read_bytes()
        try:
            text = raw.decode("utf-8")
            data = json.loads(text)
        except ValueError as exc:
            raise SkyError(f"{settings} is not plain JSON ({exc})") from exc
        profile = _profile(data, guid)
        if profile is None:
            raise SkyError(f"profile {guid} not found in {settings}")
        current = profile.get(KEY)
        if current not in sky:
            raise SkyError(f"{KEY} was changed by hand ({current!r}); leaving it")
        wanted = sky[target]
        if current == wanted:
            return False
        matches = list(re.finditer(rf'("{KEY}"\s*:\s*){re.escape(json.dumps(current))}', text))
        if len(matches) != 1:
            raise SkyError(f"{KEY} {current!r} appears {len(matches)} times in {settings}")
        match = matches[0]
        new_text = text[:match.start()] + match.group(1) + json.dumps(wanted) + text[match.end():]
        profile[KEY] = wanted
        if json.loads(new_text) != data:
            raise SkyError(f"rewriting {KEY} would change more than that value")
        if settings.read_bytes() != raw:
            raise SkyError(f"{settings} changed while the sky job ran")
        _write_atomic(settings, new_text.encode("utf-8"))
        return True


def run(home: Path, now: datetime) -> int:
    """Move the sky to ``now``'s phase. Failures are logged and retried at most once a day; always exits 0."""
    cache = home / CACHE
    today = now.date().isoformat()
    fail = cache / FAIL
    try:
        if fail.read_text(encoding="utf-8").strip() == today:
            return 0
    except OSError:
        pass
    try:
        config = json.loads((home / CONFIG).read_text(encoding="utf-8"))
        target = moon.phase_bin(now)
        update(config, cache / LOCK, target)
        (cache / STAMP).write_text(f"{target}\n", encoding="utf-8")
    except Exception as exc:  # the job runs in the background: it must never surface a traceback
        try:
            cache.mkdir(parents=True, exist_ok=True)
            fail.write_text(today + "\n", encoding="utf-8")
        except OSError:
            pass
        log.append(cache / log.NAME, f"sky: {exc}", now)
    return 0
