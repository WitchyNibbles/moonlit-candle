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
RITUAL_SOURCE = Path(__file__).resolve().parent / "ritual"
FISH_SOURCE = content.CONTENT_DIR / "fish"
TIDE_DEFAULTS = content.CONTENT_DIR / content.TIDE_DEFAULTS

THEME = "claude/themes/moonlit-candle.json"
OUTPUT_STYLE = "claude/output-styles/witchynibbles.md"
STATUSLINE = "claude/witchy/statusline.py"
TIPS = "claude/witchy/tips.json"
WT_SCHEME = "windows-terminal/moonlit-candle.scheme.json"


def dict_block(name: str, values: dict[str, str]) -> str:
    """``NAME = {...}``, one ``"key": "value",`` line per entry, as the generated blocks hold it."""
    lines = [f"{name} = {{", *(f"    {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)},"
                               for key, value in values.items()), "}"]
    return "\n".join(lines) + "\n"


def palette_block(colours: dict[str, str]) -> str:
    return dict_block("PALETTE", colours)


def with_blocks(source: Path, blocks: dict[str, dict[str, str]]) -> str:
    """``source`` with each ``# BEGIN NAME`` / ``# END NAME`` block rewritten; each must appear exactly once."""
    text = source.read_text(encoding="utf-8")
    for name, values in blocks.items():
        pattern = re.compile(rf"(# BEGIN {name}\n)(.*?)(# END {name}\n)", re.DOTALL)
        text, count = pattern.subn(lambda m: m.group(1) + dict_block(name, values) + m.group(3), text)
        if count != 1:
            raise ValueError(f"{source} must contain exactly one {name} block, found {count}")
    return text


def statusline_source(colours: dict[str, str] = palette.STATUSLINE, source: Path = STATUSLINE_SOURCE,
                      glyphs: dict[str, str] = palette.GLYPHS) -> str:
    """The status line script with its PALETTE and GLYPHS blocks rewritten."""
    return with_blocks(source, {"PALETTE": colours, "GLYPHS": glyphs})


def ritual_package(variant: str = palette.DEFAULT_VARIANT, content_dir: Path = content.CONTENT_DIR,
                   source: Path = RITUAL_SOURCE) -> dict[str, bytes]:
    """The greeting package as installed: its modules, palette.py from ``variant`` and the glyph table, and
    data.json from content/."""
    files = {}
    for module in sorted(source.glob("*.py")):
        text = (with_blocks(module, {"PALETTE": palette.VARIANTS[variant].ritual, "GLYPHS": palette.GLYPHS})
                if module.name == "palette.py" else module.read_text(encoding="utf-8"))
        files[module.name] = text.encode("utf-8")
    files["data.json"] = (content_dir / content.RITUAL).read_bytes()
    return files


# Each eza colour role and the EZA_COLORS codes it sets (eza's colour codes: di directories, ex executables,
# ln symlinks, sn/sb size number/unit, da date, ga/gm/gv/gt/gd git new/modified/renamed/typechange/deleted).
EZA_CODES = {
    "directory": ("di",),
    "executable": ("ex",),
    "symlink": ("ln",),
    "size": ("sn", "sb"),
    "date": ("da",),
    "git_new": ("ga",),
    "git_modified": ("gm",),
    "git_renamed": ("gv",),
    "git_typechange": ("gt",),
    "git_deleted": ("gd",),
}


def eza_colors(colours: dict[str, str]) -> str:
    """EZA_COLORS for ``colours``, in 24-bit colour: ``di=38;2;185;154;255:ex=…``."""
    parts = []
    for role, codes in EZA_CODES.items():
        red, green, blue = (int(colours[role][i:i + 2], 16) for i in (1, 3, 5))
        parts += [f"{code}=38;2;{red};{green};{blue}" for code in codes]
    return ":".join(parts)


def tide(variant: str = palette.DEFAULT_VARIANT,
         content_dir: Path = content.CONTENT_DIR) -> dict[str, str | tuple[str, ...]]:
    """Every Tide variable witchy sets: Tide 6.1.1's defaults with the variant's overrides on top (spec 6.1)."""
    return {**content.load_tide_defaults(content_dir), **palette.VARIANTS[variant].tide}


def fish_quote(text: str) -> str:
    """``text`` as one fish word: single quotes, with backslashes and single quotes escaped."""
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def fish_files(python: str, witchy_dir: Path, variant: str = palette.DEFAULT_VARIANT,
               source: Path = FISH_SOURCE) -> dict[str, bytes]:
    """The fish functions and conf.d snippet as installed, keyed by their path inside the fish config folder."""
    values = {"@PYTHON@": fish_quote(python), "@WITCHY_DIR@": fish_quote(str(witchy_dir)),
              "@EZA_COLORS@": fish_quote(eza_colors(palette.VARIANTS[variant].eza))}
    files = {}
    for path in sorted(source.rglob("*.fish")):
        text = path.read_text(encoding="utf-8")
        for placeholder, value in values.items():
            text = text.replace(placeholder, value)
        files[path.relative_to(source).as_posix()] = text.encode("utf-8")
    return files


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def render_outputs(content_dir: Path = content.CONTENT_DIR,
                   variant: str = palette.DEFAULT_VARIANT) -> dict[str, str]:
    colours = palette.VARIANTS[variant]
    spinner = content.load_spinner(content_dir)
    return {
        THEME: _json({"name": palette.THEME_NAME, "base": colours.claude_base, "overrides": colours.claude_overrides}),
        OUTPUT_STYLE: content.read_output_style(content_dir),
        STATUSLINE: statusline_source(colours.statusline),
        TIPS: _json({"tips": spinner["tips"]}),
        WT_SCHEME: _json(colours.wt_scheme),
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
