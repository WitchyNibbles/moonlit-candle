"""Moonlit Candle status line: model, a moon for context, windows left, and git.

Claude Code pipes one JSON payload per render and shows the line printed here.
This file is copied on its own to ~/.claude/witchy/, so it imports nothing from
the witchy package; build.py rewrites the PALETTE block from palette.py. Like
the archon status line it replaces, it is a sensor, never a gate: a missing or
malformed field reads as a dash, and the script always exits 0.
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
from typing import Any, Optional, TextIO

MAX_INPUT_BYTES = 1_048_576
DASH = "--"
CANDLE = "🕯️"
SCROLL = "📜"
BRANCH = "⎇"
DIRTY = "✦"
SEPARATOR = "⋆"
# Inclusive upper bound of the rounded context percentage, and the moon shown up to it.
MOONS = ((12, "🌑"), (37, "🌒"), (62, "🌓"), (87, "🌔"), (100, "🌕"))
BRANCH_MAX = 28
GIT_TIMEOUT = 1

# BEGIN PALETTE
PALETTE = {
    "model": "#FFD477",
    "muted": "#A99AB9",
    "divider": "#503762",
    "repo": "#B99AFF",
    "branch": "#77D9FF",
    "dirty": "#FF67B7",
    "context_low": "#FFD477",
    "context_mid": "#FF67B7",
    "context_high": "#FF6B9F",
    "left_high": "#FFD477",
    "left_mid": "#B99AFF",
    "left_low": "#FF67B7",
}
# END PALETTE

RESET = "\x1b[0m"
BOLD = "\x1b[1m"


def _paint(text: str, key: str, *, bold: bool = False) -> str:
    colour = PALETTE[key]
    red, green, blue = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return f"{BOLD if bold else ''}\x1b[38;2;{red};{green};{blue}m{text}{RESET}"


def _get(payload: Any, *path: str) -> Any:
    for name in path:
        if not isinstance(payload, dict):
            return None
        payload = payload.get(name)
    return payload


def _percent(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return min(100.0, max(0.0, float(value)))


def moon(used: Optional[float]) -> str:
    """The moon for a context percentage; a new moon while nothing is known."""
    if used is None:
        return MOONS[0][1]
    rounded = round(used)
    for limit, glyph in MOONS:
        if rounded <= limit:
            return glyph
    return MOONS[-1][1]


def _model(payload: Any) -> str:
    name = _get(payload, "model", "display_name")
    name = re.sub(r"\s*\(.*\)\s*$", "", name).strip() if isinstance(name, str) else ""
    level = _get(payload, "effort", "level")
    effort = _paint(f"·{level}", "muted") if isinstance(level, str) and level else ""
    return _paint(f"{CANDLE} {name or DASH}", "model", bold=True) + effort


def _context(payload: Any) -> str:
    used = _percent(_get(payload, "context_window", "used_percentage"))
    if used is None:
        return f"{moon(None)} {_paint(DASH, 'muted')}"
    rounded = round(used)
    key = "context_low" if rounded < 50 else "context_mid" if rounded < 80 else "context_high"
    return f"{moon(used)} {_paint(f'{rounded}%', key, bold=rounded >= 80)}"


def _left(payload: Any, window: str, label: str) -> str:
    used = _percent(_get(payload, "rate_limits", window, "used_percentage"))
    tag = _paint(label, "muted")
    if used is None:
        return f"{tag} {_paint(DASH, 'muted')}"
    left = round(100 - used)
    key = "left_high" if left > 50 else "left_mid" if left > 20 else "left_low"
    return f"{tag} {_paint(f'{left}%', key, bold=left <= 20)}"


def _git(cwd: str, *args: str) -> Optional[str]:
    try:
        done = subprocess.run(
            ["git", *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            timeout=GIT_TIMEOUT, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return done.stdout if done.returncode == 0 else None


def _repo(payload: Any) -> Optional[str]:
    cwd = _get(payload, "workspace", "current_dir")
    if not isinstance(cwd, str) or not cwd:
        cwd = _get(payload, "cwd")
    if not isinstance(cwd, str) or not os.path.isdir(cwd):
        return None
    top = (_git(cwd, "rev-parse", "--show-toplevel") or "").strip()
    if not top:
        return None
    # Any git call failing hides the whole segment: a guessed branch or a tree
    # wrongly shown as clean is worse than no segment. An empty branch name with
    # a zero exit status is not a failure, it is a detached HEAD.
    branch = _git(cwd, "branch", "--show-current")
    if branch is None:
        return None
    branch = branch.strip()
    if not branch:
        branch = (_git(cwd, "rev-parse", "--short", "HEAD") or "").strip()
        if not branch:
            return None
    if len(branch) > BRANCH_MAX:
        branch = branch[:BRANCH_MAX - 1] + "…"
    status = _git(cwd, "status", "--porcelain")
    if status is None:
        return None
    dirty = sum(1 for line in status.splitlines() if line.strip())
    segment = _paint(f"{SCROLL} {os.path.basename(top)}", "repo") + " " + _paint(f"{BRANCH} {branch}", "branch")
    return segment + (_paint(f"{DIRTY}{dirty}", "dirty") if dirty else "")


def render(payload: Any) -> str:
    """One status line for one payload; never raises on a malformed one."""
    parts = [_model(payload), _context(payload), _left(payload, "five_hour", "5h"), _left(payload, "seven_day", "7d")]
    repo = _repo(payload)
    if repo:
        parts.append(repo)
    return " " + _paint(f" {SEPARATOR} ", "divider").join(parts) + " "


def _utf8(stream: Optional[TextIO]) -> Optional[TextIO]:
    """Best-effort UTF-8 for a standard stream; Claude Code may launch us under a C locale."""
    if stream is not None:
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass
    return stream


def _discard_stdout() -> None:
    """Point fd 1 at /dev/null so the flush at interpreter exit cannot turn a broken pipe into exit status 120."""
    try:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    except (AttributeError, OSError, ValueError):
        pass


def main(stdin: Optional[TextIO] = None, stdout: Optional[TextIO] = None) -> int:
    """Render stdin's payload. Always exit 0: a blank status line tells nobody anything."""
    if stdin is None:
        stdin = _utf8(sys.stdin)  # None when the parent closed fd 0
    if stdout is None:
        stdout = _utf8(sys.stdout)
    payload = None
    if stdin is not None:
        try:
            payload = json.loads(stdin.read(MAX_INPUT_BYTES))
        except (ValueError, OSError, RecursionError):
            pass
    try:
        line = render(payload)
    except Exception:  # a status line must never take the prompt down with it
        line = f" {DASH} "
    if stdout is not None:
        try:
            stdout.write(line + "\n")
            stdout.flush()
        except OSError:  # the reader went away (broken pipe); nobody is left to tell
            if stdout is sys.stdout:
                _discard_stdout()
    return 0


if __name__ == "__main__":
    sys.exit(main())
