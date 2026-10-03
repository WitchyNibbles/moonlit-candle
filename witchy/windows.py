"""The Windows side of WSL: environment variables, the user's profile folder, path conversion."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

MOUNT_ROOT = Path("/mnt")
_DRIVE_PATH = re.compile(r"^([A-Za-z]):\\(.*)$")


@dataclass(frozen=True)
class WindowsHome:
    """The current Windows user's profile folder, as Windows and as WSL see it."""

    windows: str
    wsl: Path


def echo(variable: str, run: Callable[..., Any] = subprocess.run) -> str | None:
    """The value of a Windows environment variable, or None."""
    try:
        # cwd=/mnt/c keeps cmd.exe from warning about a UNC working directory. cmd.exe answers in the OEM code
        # page, so a name like "José" is not valid UTF-8: replace instead of raising.
        done = run(["cmd.exe", "/c", f"echo %{variable}%"], capture_output=True, text=True, errors="replace",
                   timeout=5, cwd="/mnt/c")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    value = (done.stdout or "").strip()
    return value if done.returncode == 0 and value and "%" not in value else None


def to_wsl(path: str, mount_root: Path = MOUNT_ROOT) -> Path | None:
    """``C:\\Users\\x`` as ``/mnt/c/Users/x``; None for anything that is not a drive path."""
    match = _DRIVE_PATH.match(path.strip())
    if not match:
        return None
    parts = [part for part in match.group(2).split("\\") if part]
    return mount_root.joinpath(match.group(1).lower(), *parts)


def user_home(run: Callable[..., Any] = subprocess.run, mount_root: Path = MOUNT_ROOT) -> WindowsHome | None:
    """``%USERPROFILE%``. It is the real folder name, which ``%USERNAME%`` is not after an account rename."""
    value = echo("USERPROFILE", run)
    path = to_wsl(value, mount_root) if value else None
    if path is None or not path.is_dir():
        return None
    return WindowsHome(value.rstrip("\\"), path)
