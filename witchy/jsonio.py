"""Careful JSON file handling: strict reads, style-preserving writes, dated backups.

Settings files belong to other programs (Claude Code, Windows Terminal), so a
rewrite keeps their indentation, escaping and line endings, never leaves a
half-written file behind, and a file that is not strictly JSON is never rewritten.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

_INDENT = re.compile(r"^([ \t]+)\S", re.MULTILINE)
# Windows Terminal puts an object or array value on its own line: `"actions": ` then `[` below it.
_OWN_LINE = re.compile(r'": \r?\n[ \t]*[\[{]')
_OPENS_LINE_END = re.compile(r'^([ \t]*)("(?:[^"\\]|\\.)*"): ([\[{])$', re.MULTILINE)


class StrictJsonError(ValueError):
    """Not plain JSON (comments, trailing commas, a BOM), so it must not be rewritten."""


def read_json(path: Path) -> tuple[Any, str]:
    """Parse ``path`` strictly; return the data and the exact text it came from."""
    try:
        text = path.read_bytes().decode("utf-8")
        return json.loads(text), text
    except ValueError as exc:
        raise StrictJsonError(f"{path}: {exc}") from exc


def detect_indent(text: str) -> str:
    match = _INDENT.search(text)
    return match.group(1) if match else "  "


def dumps_like(data: Any, like: str | None) -> str:
    """Serialise ``data`` in the style of ``like``; a brand-new file gets two spaces and UTF-8."""
    if like is None:
        return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    # Windows Terminal stores non-ASCII names as \uXXXX escapes; an ASCII-only file stays ASCII-only.
    text = json.dumps(data, indent=detect_indent(like), ensure_ascii=like.isascii())
    if _OWN_LINE.search(like):
        text = _OPENS_LINE_END.sub(r"\1\2: \n\1\3", text)
    newline = "\r\n" if "\r\n" in like else "\n"
    text = text.replace("\n", newline)
    return text + newline if like.endswith("\n") else text


def write_atomic_bytes(path: Path, data: bytes) -> None:
    """Replace ``path`` in one step: write a sibling temp file, then rename it over."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            try:
                shutil.copymode(path, tmp)
            except OSError:
                pass  # /mnt/c (drvfs) may refuse chmod; the content is what matters
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def backup(path: Path, stamp: str) -> Path:
    """Copy ``path`` to ``<name>.bak-witchy-<stamp>`` beside it and return the copy."""
    target = path.with_name(f"{path.name}.bak-witchy-{stamp}")
    counter = 1
    while target.exists():
        target = path.with_name(f"{path.name}.bak-witchy-{stamp}-{counter}")
        counter += 1
    shutil.copyfile(path, target)
    return target
