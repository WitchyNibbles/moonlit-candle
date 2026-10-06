"""Other prompt owners in config.fish and conf.d: found, and disabled line by line (spec 5.2).

Files are read and written as bytes and split on ``\\n`` only, so line endings and bytes that are not UTF-8 stay
exactly as they were; disabling a line puts ``# witchy-disabled: `` in front of it, and enabling takes it away.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .components.base import Change

PREFIX = b"# witchy-disabled: "
STARSHIP = re.compile(r"\bstarship\s+init\s+fish\b")
OH_MY_POSH = re.compile(r"\boh-my-posh\b.*(?:\binit\s+fish\b|--shell\s+fish\b)")
SET = re.compile(r"\bset\s+((?:-[-\w]+\s+)+)(tide_\w+)")
FUNCTION = re.compile(r"^\s*function\s+fish_prompt(?:\s|;|$)")
NOT_A_SET = set("qenS")  # set -q, -e, -n, -S read or erase; they never give a value
NOT_A_SET_LONG = {"--query", "--erase", "--names", "--show"}


@dataclass(frozen=True)
class Line:
    """An active line that makes something other than Tide own the prompt."""

    path: Path
    number: int  # from 1
    what: str  # "starship init", "oh-my-posh init" or "set -g tide_…"


@dataclass
class Scan:
    lines: list[Line] = field(default_factory=list)
    # Why the takeover cannot go ahead (a fish_prompt function, a continued line, a symlink); nothing is changed.
    blockers: list[str] = field(default_factory=list)
    changes: list[Change] = field(default_factory=list)  # each file with its owner lines disabled


def _global_set(line: str) -> str | None:
    for match in SET.finditer(line):
        flags = match.group(1).split()
        short = "".join(flag[1:] for flag in flags if not flag.startswith("--"))
        long = {flag for flag in flags if flag.startswith("--")}
        if NOT_A_SET & set(short) or NOT_A_SET_LONG & long:
            continue
        if "g" in short or "--global" in long:
            return f"set -g {match.group(2)}"
    return None


def owner(line: str) -> str | None:
    """What an active line does to the prompt, or None (a comment, already disabled, or unrelated)."""
    if line.lstrip().startswith("#"):
        return None
    if STARSHIP.search(line):
        return "starship init"
    if OH_MY_POSH.search(line):
        return "oh-my-posh init"
    return _global_set(line)


def config_files(folder: Path, skip: set[Path]) -> list[Path]:
    """config.fish, then each conf.d/*.fish by name, leaving out ``skip`` (witchy's own and fisher's files)."""
    conf_d = folder / "conf.d"
    found = [folder / "config.fish"] + (sorted(conf_d.glob("*.fish")) if conf_d.is_dir() else [])
    return [path for path in found if (path.is_file() or path.is_symlink()) and path not in skip]


def _numbers(numbers: list[int]) -> str:
    return f"line {numbers[0]}" if len(numbers) == 1 else "lines " + ", ".join(map(str, numbers))


def scan(folder: Path, skip: set[Path] = frozenset()) -> Scan:
    """Every other prompt owner in ``folder`` (fish's config folder), and the changes that disable them."""
    found = Scan()
    for path in config_files(folder, skip):
        name = path.relative_to(folder).as_posix()
        try:
            data = path.read_bytes()
        except OSError as exc:
            found.blockers.append(f"cannot read {name} ({exc.strerror or exc})")
            continue
        raw = data.split(b"\n")
        numbers = []
        for index, line in enumerate(raw):
            text = line.decode("utf-8", "surrogateescape").rstrip("\r")
            if FUNCTION.match(text):
                found.blockers.append(f"{name} defines fish_prompt at line {index + 1}; remove that function")
                continue
            what = owner(text)
            if what is None:
                continue
            continued = index > 0 and raw[index - 1].rstrip(b"\r").endswith(b"\\")
            if text.endswith("\\") or continued:
                found.blockers.append(f"{name} line {index + 1} is continued over several lines; "
                                      "disable it yourself")
                continue
            numbers.append(index + 1)
            found.lines.append(Line(path, index + 1, what))
        if numbers and path.is_symlink():
            # A file that lives elsewhere (a dotfiles repository) is never edited (spec D22).
            found.blockers.append(f"{name} is a symlink to {os.readlink(path)}; disable {_numbers(numbers)} there "
                                  "yourself")
        elif numbers:
            found.changes.append(Change(path, data, disable(data, numbers)))
    return found


def disable(data: bytes, numbers: list[int]) -> bytes:
    lines = data.split(b"\n")
    for number in numbers:
        lines[number - 1] = PREFIX + lines[number - 1]
    return b"\n".join(lines)


def enable(data: bytes) -> bytes:
    """Every line witchy disabled, back as it was."""
    return b"\n".join(line[len(PREFIX):] if line.startswith(PREFIX) else line for line in data.split(b"\n"))
