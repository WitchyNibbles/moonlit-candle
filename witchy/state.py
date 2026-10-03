"""state.json: what witchy installed, and what every setting held before."""
from __future__ import annotations

import json
from pathlib import Path

from . import jsonio, palette
from .errors import Abort

VERSION = 2


def empty(variant: str) -> dict:
    return {"version": VERSION, "variant": variant, "last_install": None, "components": {}}


def migrate(v1: dict) -> dict:
    """Turn a version 1 state (written before components existed) into version 2, keeping every record."""
    components = {"claude": {"files": v1["files"], "settings": v1["claude_settings"]}}
    if v1.get("windows_terminal"):
        components["windows-terminal"] = v1["windows_terminal"]
    return {"version": VERSION, "variant": palette.DEFAULT_VARIANT, "last_install": None, "components": components}


def load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data, _ = jsonio.read_json(path)
    except jsonio.StrictJsonError as exc:
        raise Abort(f"{exc}\nThe state file is damaged; fix or remove {path} by hand.") from exc
    version = data.get("version") if isinstance(data, dict) else None
    if version == 1:
        return migrate(data)
    if version == VERSION:
        return data
    raise Abort(f"{path} has an unknown format; fix or remove it by hand.")


def save(path: Path, data: dict) -> None:
    # A fish value byte that is not UTF-8 is held as a lone surrogate; it is written as a \udcXX escape,
    # which json reads back as the same surrogate.
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    jsonio.write_atomic_bytes(path, text.encode("utf-8", "backslashreplace"))
