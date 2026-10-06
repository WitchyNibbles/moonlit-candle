"""Hand-written content: spinner verbs and tips, the output style, and the greeting's texts."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"
SPINNER = "spinner.json"
OUTPUT_STYLE = "output-style.md"
RITUAL = "ritual.json"
TIDE_DEFAULTS = "tide-6.1.1-defaults.json"  # written by scripts/tide_defaults.py (spec 6.1)
PINS = "pins.json"  # written by scripts/pins.py (spec 5.1, D21)
SHA256 = re.compile(r"[0-9a-f]{64}")


def load_spinner(content_dir: Path = CONTENT_DIR) -> dict[str, Any]:
    data = json.loads((content_dir / SPINNER).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{SPINNER} must hold a JSON object")
    return data


def load_ritual(content_dir: Path = CONTENT_DIR) -> dict[str, Any]:
    data = json.loads((content_dir / RITUAL).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{RITUAL} must hold a JSON object")
    return data


def load_tide_defaults(content_dir: Path = CONTENT_DIR) -> dict[str, str | tuple[str, ...]]:
    """Tide 6.1.1's own value for each of its variables, in palette.TIDE's shapes: one element as a string,
    any other count as a tuple."""
    data = json.loads((content_dir / TIDE_DEFAULTS).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(
            isinstance(name, str) and name and isinstance(values, list) and all(isinstance(v, str) for v in values)
            for name, values in data.items()):
        raise ValueError(f"{TIDE_DEFAULTS} must map each variable name to a list of strings")
    return {name: values[0] if len(values) == 1 else tuple(values) for name, values in data.items()}


def _hashes(files: Any) -> bool:
    return isinstance(files, dict) and bool(files) and all(SHA256.fullmatch(str(digest)) for digest in files.values())


def load_pins(content_dir: Path = CONTENT_DIR) -> dict[str, Any]:
    """The SHA-256 of fisher's bootstrap file and of every file each pinned plugin installs, by path below
    fisher's folder: ``{"bootstrap": {"url", "sha256"}, "plugins": {"owner/repo@ref": {path: sha256}}}``."""
    data = json.loads((content_dir / PINS).read_text(encoding="utf-8"))
    bootstrap = data.get("bootstrap") if isinstance(data, dict) else None
    plugins = data.get("plugins") if isinstance(data, dict) else None
    if not (isinstance(bootstrap, dict) and isinstance(bootstrap.get("url"), str)
            and SHA256.fullmatch(str(bootstrap.get("sha256"))) and isinstance(plugins, dict) and plugins
            and all(_hashes(files) for files in plugins.values())):
        raise ValueError(f"{PINS} must hold the bootstrap file's URL and SHA-256 and each plugin's file hashes")
    return data


def read_output_style(content_dir: Path = CONTENT_DIR) -> str:
    return (content_dir / OUTPUT_STYLE).read_text(encoding="utf-8")


def split_frontmatter(text: str) -> tuple[dict[str, str], str] | None:
    """Split the flat ``key: value`` frontmatter that output styles use from the body."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 3)
    if end == -1:
        return None
    fields = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            return None
        fields[key.strip()] = value.strip()
    return fields, text[end + 5:]
