"""Turn palette.py and content/ into the files install copies into place."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import content, palette, validate

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
STATUSLINE_SOURCE = Path(__file__).resolve().parent / "statusline.py"
PALETTE_BLOCK = re.compile(r"(# BEGIN PALETTE\n)(.*?)(# END PALETTE\n)", re.DOTALL)

THEME = "claude/themes/moonlit-candle.json"
OUTPUT_STYLE = "claude/output-styles/witchynibbles.md"
STATUSLINE = "claude/witchy/statusline.py"
TIPS = "claude/witchy/tips.json"
WT_SCHEME = "windows-terminal/moonlit-candle.scheme.json"


def palette_block(colours: dict[str, str]) -> str:
    lines = ["PALETTE = {", *(f'    "{key}": "{value}",' for key, value in colours.items()), "}"]
    return "\n".join(lines) + "\n"


def statusline_source(colours: dict[str, str] = palette.STATUSLINE, source: Path = STATUSLINE_SOURCE) -> str:
    """The status line script with its PALETTE block rewritten from ``colours``."""
    text = source.read_text(encoding="utf-8")
    rewritten, count = PALETTE_BLOCK.subn(lambda m: m.group(1) + palette_block(colours) + m.group(3), text)
    if count != 1:
        raise ValueError(f"{source} must contain exactly one PALETTE block, found {count}")
    return rewritten


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def render_outputs(content_dir: Path = content.CONTENT_DIR) -> dict[str, str]:
    spinner = content.load_spinner(content_dir)
    return {
        THEME: _json({"name": palette.THEME_NAME, "base": "dark", "overrides": palette.CLAUDE_OVERRIDES}),
        OUTPUT_STYLE: content.read_output_style(content_dir),
        STATUSLINE: statusline_source(),
        TIPS: _json({"tips": spinner["tips"]}),
        WT_SCHEME: _json(palette.WT_SCHEME),
    }


def write_dist(outputs: dict[str, str], dist: Path | None = None) -> None:
    root = dist or DIST
    for rel, text in outputs.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def build(dist: Path | None = None, content_dir: Path = content.CONTENT_DIR) -> list[validate.Failure]:
    """Validate, then write dist/. Nothing is written when any rule fails."""
    failures = validate.validate_all(content_dir)
    if not failures:
        write_dist(render_outputs(content_dir), dist)
    return failures
