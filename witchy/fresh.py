"""install --fresh: the apt packages a new WSL box lacks, and fish as the login shell (spec 15.1, D15).

It runs before validation and the lock, asks before each step, and runs sudo with the terminal attached so sudo
can ask for the password.
"""
from __future__ import annotations

import getpass
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

PACKAGES = ("fish", "curl", "eza")
OPTIONAL = ("eza",)  # ll and lt fall back to ls without it
NO_TERMINAL = "--fresh needs a terminal to ask before using sudo"


def login_shell(ctx: Any) -> str | None:
    """The login shell `getent passwd` names for the user, or None when it cannot be read."""
    user = ctx.env.get("USER") or getpass.getuser()
    try:
        done = ctx.run(["getent", "passwd", user], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    fields = done.stdout.strip().split(":")
    return fields[6] if done.returncode == 0 and len(fields) >= 7 else None


def _attached(ctx: Any, command: list[str]) -> int:
    """Run with the terminal attached (sudo asks for the password there); the exit code, 127 when it cannot start."""
    try:
        return ctx.run(command).returncode
    except OSError:
        return 127


def _yes(ask: Callable[[str], str], question: str) -> bool:
    try:
        return ask(question).strip().lower() in ("y", "yes")
    except EOFError:
        return False


def prepare(ctx: Any, ask: Callable[[str], str] = input, interactive: bool | None = None) -> int | None:
    """Install what is missing and offer chsh. None means go on with the install; a number is the exit code."""
    path = ctx.env.get("PATH")
    missing = [package for package in PACKAGES if shutil.which(package, path=path) is None]
    shell = login_shell(ctx)
    offer_shell = shell is None or Path(shell).name != "fish"
    install_question = f"sudo apt install {' '.join(missing)}? [y/N] "
    if ctx.dry_run:
        if missing:
            ctx.say(f"fresh: would ask: {install_question.strip()}")
        if offer_shell:
            ctx.say("fresh: would ask: make fish your login shell (chsh -s <fish>)? [y/N]")
        return None
    if not missing and not offer_shell:
        return None
    if not (sys.stdin.isatty() if interactive is None else interactive):
        ctx.say(NO_TERMINAL)
        return 1
    if missing:
        if not _yes(ask, install_question):
            ctx.say("fresh: nothing was installed.")
            return 1
        needed = [package for package in missing if package not in OPTIONAL]
        steps = [["sudo", "apt-get", "update"]] + ([["sudo", "apt-get", "install", "-y", *needed]] if needed else [])
        for command in steps:
            code = _attached(ctx, command)
            if code != 0:
                ctx.say(f"fresh: {' '.join(command)} failed (exit {code}); nothing else ran.")
                return 1
        for package in (package for package in missing if package in OPTIONAL):
            code = _attached(ctx, ["sudo", "apt-get", "install", "-y", package])
            if code != 0:
                ctx.say(f"fresh: {package} could not be installed (exit {code}); ll and lt use ls.")
    fish = shutil.which("fish", path=path)
    if offer_shell and fish and _yes(ask, f"make fish your login shell (chsh -s {fish})? [y/N] "):
        code = _attached(ctx, ["chsh", "-s", fish])
        if code != 0:
            ctx.say(f"fresh: chsh failed (exit {code}); your login shell stays as it was.")
    return None
