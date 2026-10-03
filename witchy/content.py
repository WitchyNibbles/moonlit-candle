"""Hand-written content: spinner verbs and tips, the output style, and the greeting's texts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"
SPINNER = "spinner.json"
OUTPUT_STYLE = "output-style.md"
RITUAL = "ritual.json"


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
