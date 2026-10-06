"""~/.cache/witchy/install.log: what downloads and fisher printed during an install (spec 5.1, D20).

Each run starts with a header line. The log stays under 200 KB: the oldest runs go first, and a run that is
still too large alone keeps its end. Writing the log never fails an install.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from . import jsonio
from .components.base import Command, ComponentFailed, run_command, tilde

NAME = "install.log"
LIMIT = 200 * 1024
RUN = re.compile(r"^=== witchy install \S+ ===$", re.MULTILINE)
ESCAPE = re.compile(r"\x1b(?:\[[0-9;?]*[A-Za-z]|\([A-Z0-9])")  # the colours fisher prints


def path(ctx: Any) -> Path:
    return ctx.cache_dir / NAME


def shown(ctx: Any) -> str:
    """The log's path with ~ for HOME, as messages show it."""
    return tilde(ctx, path(ctx))


def plain(text: str) -> str:
    return ESCAPE.sub("", text)


def append(ctx: Any, text: str) -> None:
    target = path(ctx)
    try:
        old = target.read_bytes().decode("utf-8", "replace")
    except OSError:
        old = ""
    starts = [match.start() for match in RUN.finditer(old)]
    runs = [old[start:end] for start, end in zip(starts, starts[1:] + [len(old)])]
    header = f"=== witchy install {ctx.stamp} ===\n"
    if not runs or not runs[-1].startswith(header):
        runs.append(header)
    runs[-1] += text if text.endswith("\n") else text + "\n"
    while len(runs) > 1 and len("".join(runs).encode("utf-8")) > LIMIT:
        runs.pop(0)
    data = "".join(runs).encode("utf-8")
    if len(data) > LIMIT:
        data = data[-LIMIT:]
        data = data[data.find(b"\n") + 1:]
    try:
        jsonio.write_atomic_bytes(target, data)
    except OSError:
        pass  # the log only explains a failure; it never causes one


def run(ctx: Any, command: Command) -> subprocess.CompletedProcess:
    """Run ``command`` without checking its exit code, and log what it printed under its label."""
    try:
        done = run_command(ctx, command, check=False)
    except ComponentFailed as exc:
        append(ctx, f"--- {command.label}: {exc}")
        raise
    output = "".join(plain(text) for text in (done.stdout, done.stderr) if text)
    append(ctx, f"--- {command.label} (exit {done.returncode})\n{output}")
    return done


def _last(text: str | None) -> str:
    return next((line.strip() for line in reversed(plain(text or "").splitlines()) if line.strip()), "")


def failure(ctx: Any, label: str, done: subprocess.CompletedProcess) -> str:
    """``could not <label> (exit N): <its last error line> (details: ~/.cache/witchy/install.log)``."""
    last = _last(done.stderr) or _last(done.stdout)
    said = f": {last}" if last else ""
    return f"could not {label} (exit {done.returncode}){said} (details: {shown(ctx)})"
