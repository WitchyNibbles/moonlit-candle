"""Other prompt owners in config.fish and conf.d: found, and disabled line by line (spec 5.2).

Files are read and written as bytes and split on ``\\n`` only, so line endings and bytes that are not UTF-8 stay
exactly as they were; disabling a line puts ``# witchy-disabled: `` in front of it, and enabling takes it away.
A command or string that goes on over several lines is caught by cheap checks (a trailing backslash or operator, a
block opened or closed) and, when a ``parses`` check is given (fish itself, ``fish --no-execute``), by asking whether
fish can still read the file with the lines disabled.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .components.base import Change

PREFIX = b"# witchy-disabled: "
STARSHIP = re.compile(r"\bstarship\s+init\s+fish\b")
OH_MY_POSH = re.compile(r"\boh-my-posh\b.*(?:\binit\s+fish\b|--shell\s+fish\b)")
# Functions the init lines define: a call left on once its init line is disabled fails at every shell start.
HELPERS = {"enable_transience": "starship", "disable_transience": "starship",
           "enable_poshtransientprompt": "oh-my-posh", "enable_poshtooltips": "oh-my-posh"}
HELPER = re.compile(r"(?:^|[;|&]|\b(?:and|or|not)\s)\s*(" + "|".join(HELPERS) + r")\s*(?:$|[;|&])")
SET = re.compile(r"\bset\s+((?:-[-\w]+\s+)+)(tide_\w+)")
FUNCTION = re.compile(r"^\s*function\s+fish_prompt(?:\s|;|$)")
NOT_A_SET = set("qenS")  # set -q, -e, -n, -S read or erase; they never give a value
NOT_A_SET_LONG = {"--query", "--erase", "--names", "--show"}
OPENERS = {"if", "while", "for", "function", "begin", "switch"}
MODIFIERS = {"and", "or", "not", "time"}
SEPARATORS = re.compile(r";|\|\||&&|\||&")


@dataclass(frozen=True)
class Line:
    """An active line that makes something other than Tide own the prompt."""

    path: Path
    number: int  # from 1
    what: str  # "starship init", "oh-my-posh init", "starship enable_transience" or "set -g tide_…"


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


def _code(text: str) -> str:
    """The part of a line that runs: no comment, and quoted strings emptied (``'a b'`` becomes ``''``)."""
    out = []
    quote = ""
    i = 0
    while i < len(text):
        char = text[i]
        if quote:
            if char == "\\" and i + 1 < len(text) and (quote == '"' or text[i + 1] in "\\'"):
                i += 2
                continue
            if char == quote:
                quote = ""
                out.append(char)
        elif char == "\\":
            out.append("_" if i + 1 < len(text) else char)
            i += 2
            continue
        elif char in "'\"":
            quote = char
            out.append(char)
        elif char == "#" and (i == 0 or text[i - 1].isspace() or text[i - 1] == ";"):
            break
        else:
            out.append(char)
        i += 1
    return "".join(out)


def _continues(code: str) -> bool:
    """Whether the next line belongs to this command (a trailing backslash, ``&&``, ``||`` or ``|``)."""
    return code.rstrip().endswith(("\\", "&&", "||", "|"))


def _crosses_block(code: str) -> bool:
    """Whether a line opens a block it does not close, or closes (or continues) one it did not open."""
    depth = 0
    for segment in SEPARATORS.split(code):
        words = segment.split()
        while words and words[0] in MODIFIERS:
            words.pop(0)
        word = words[0] if words else ""
        if word in OPENERS:
            depth += 1
        elif word == "end":
            depth -= 1
            if depth < 0:
                return True
        elif word in ("else", "case") and depth == 0:
            return True
    return depth != 0


def owner(line: str) -> str | None:
    """What an active line does to the prompt, or None (a comment, already disabled, or unrelated).

    A call to a function an init line defines counts too: disabling the init line would leave it failing."""
    code = _code(line)
    if STARSHIP.search(code):
        return "starship init"
    if OH_MY_POSH.search(code):
        return "oh-my-posh init"
    helper = HELPER.search(code)
    if helper:
        return f"{HELPERS[helper.group(1)]} {helper.group(1)}"
    return _global_set(code)


def _resolved(path: Path) -> Path:
    """``path`` with every symlink followed; a loop (RuntimeError before Python 3.13) leaves it as it is."""
    try:
        return path.resolve()
    except (OSError, RuntimeError):
        return path


def config_files(folder: Path, skip: set[Path]) -> list[Path]:
    """config.fish, then each conf.d/*.fish by name, leaving out ``skip`` (witchy's own and fisher's files).

    A symlink loop stays in the list: reading it fails, which scan reports as a file it cannot read."""
    conf_d = folder / "conf.d"
    found = [folder / "config.fish"] + (sorted(conf_d.glob("*.fish")) if conf_d.is_dir() else [])
    left = {_resolved(path) for path in skip}
    return [path for path in found if (path.is_file() or path.is_symlink()) and _resolved(path) not in left]


def _numbers(numbers: list[int]) -> str:
    return f"line {numbers[0]}" if len(numbers) == 1 else "lines " + ", ".join(map(str, numbers))


def _linked(folder: Path, path: Path) -> bool:
    """Whether the file, its conf.d folder or fish's config folder itself is a symlink."""
    return folder.is_symlink() or path.parent.is_symlink() or path.is_symlink()


def _unreadable(data: bytes, numbers: list[int], parses: Callable[[bytes], bool] | None) -> list[int]:
    """The lines whose disabling leaves a file fish cannot read (a ``(`` or a quote whose end is on another line).

    One check when the file reads fine; only a file fish read before is blamed on the disabled lines."""
    if parses is None or parses(disable(data, numbers)) or not parses(data):
        return []
    alone = [number for number in numbers if not parses(disable(data, [number]))]
    return alone or numbers


def scan(folder: Path, skip: set[Path] = frozenset(), parses: Callable[[bytes], bool] | None = None) -> Scan:
    """Every other prompt owner in ``folder`` (fish's config folder), and the changes that disable them.

    ``parses`` tells whether fish can read a file's bytes; each file with lines to disable is checked with them
    disabled, and a line that makes it unreadable is a blocker."""
    found = Scan()
    for path in config_files(folder, skip):
        name = path.relative_to(folder).as_posix()
        try:
            data = path.read_bytes()
        except OSError as exc:
            found.blockers.append(f"cannot read {name} ({exc.strerror or exc})")
            continue
        texts = [line.decode("utf-8", "surrogateescape").rstrip("\r") for line in data.split(b"\n")]
        codes = [_code(text) for text in texts]
        numbers = []
        for index, text in enumerate(texts):
            if FUNCTION.match(text):
                found.blockers.append(f"{name} defines fish_prompt at line {index + 1}; remove that function")
                continue
            what = owner(text)
            if what is None:
                continue
            if _continues(codes[index]) or (index > 0 and _continues(codes[index - 1])):
                found.blockers.append(f"{name} line {index + 1} is continued over several lines; "
                                      "disable it yourself")
                continue
            if _crosses_block(codes[index]):
                found.blockers.append(f"{name} line {index + 1} opens or closes a block; disable it yourself")
                continue
            numbers.append(index + 1)
            found.lines.append(Line(path, index + 1, what))
        if numbers and _linked(folder, path):
            # A file that lives elsewhere (a dotfiles repository) is never edited (spec D22).
            found.blockers.append(f"{name} is a symlink to {path.resolve()}; disable {_numbers(numbers)} there "
                                  "yourself")
        elif numbers:
            broken = _unreadable(data, numbers, parses)
            for number in broken:
                found.blockers.append(f"{name} line {number} is part of a command or string over several lines "
                                      "(fish could not read the file with it disabled); disable it yourself")
            found.lines = [line for line in found.lines if line.path != path or line.number not in broken]
            numbers = [number for number in numbers if number not in broken]
            if numbers:
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
