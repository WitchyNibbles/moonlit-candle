"""The greeting: the full ritual, the one-line omen, or the sky job (spec 6) with or without the sky."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import textwrap
import time
from datetime import date, datetime
from pathlib import Path
from typing import Mapping, NoReturn, TextIO

from . import art, fetch, layout, log, moon, palette, sky, tarot, wheel

HERE = Path(__file__).resolve().parent
# The installed copy carries data.json; in the repository the texts are still in content/.
DATA_FILES = (HERE / "data.json", HERE.parent.parent / "content" / "ritual.json")
CACHE = Path(".cache/witchy")
STAMP = "last-ritual"
FULL_EVERY = 600  # seconds between two full rituals in auto mode
MIN_FULL_COLUMNS = 60
SIDE_BY_SIDE = 80
STACKED = 40
# (first hour after the greeting ends, greeting)
SALUTATIONS = ((4, "Good witching hour"), (12, "Good morning"), (18, "Good afternoon"), (24, "Good evening"))
LUNAR = {"new": ("🌑", "New moon"), "full": ("🌕", "Full moon"), "blue": ("🌕", "Blue moon")}
SEPARATOR = (" · ", "label", False)
ISO_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def load_data() -> dict:
    path = next((path for path in DATA_FILES if path.is_file()), DATA_FILES[0])
    return json.loads(path.read_text(encoding="utf-8"))


def salutation(hour: int) -> str:
    return next(text for end, text in SALUTATIONS if hour < end)


def _countdown(name: str, days: int) -> str:
    star = palette.GLYPHS["separator"]
    return f"{star} {name} tomorrow" if days == 1 else f"{star} {name} in {days} days"


def info_lines(now: datetime, data: dict, fetched: list[tuple[str, str]], width: int) -> list[layout.Line]:
    """The column beside the moon: salutation, sabbat, lunar events, phase, tarot, system."""
    day, tz = now.date(), now.tzinfo
    sabbat = wheel.upcoming(day, tz)
    on_sabbat = sabbat is not None and sabbat[1] == 0
    lines = [[(f"{salutation(now.hour)}, {fetch.clean(data['name'])}",
               sabbat[0].lower() if on_sabbat else "salutation", True)]]
    if sabbat:
        name, days = sabbat
        text = f"{palette.GLYPHS['candle']} {name} — {data['sabbats'][name]}" if days == 0 else _countdown(name, days)
        lines.append([(text, name.lower(), False)])
    for event in moon.lunar_events(day, tz):
        glyph, label = LUNAR[event]
        lines.append([(f"{glyph} {label} — {data['lunar'][event]}", "moon", False)])
    phase = moon.phase_bin(now)
    lines.append([(f"{palette.GLYPHS['separator']} {moon.NAMES[phase]}  {moon.illumination(now)}%", "moon", False)])
    card, reversed_ = tarot.card_of(day, data["tarot"])
    title = [(f"{palette.GLYPHS['dirty']} {tarot.NUMERALS[card['number']]} · {card['name']}", "tarot", False)]
    lines.append(title + ([(" (reversed)", "muted", False)] if reversed_ else []))
    meaning = card["reversed"] if reversed_ else card["upright"]
    lines += [[("  " + part, "muted", False)] for part in textwrap.wrap(meaning, max(10, width - 2))]
    lines += [[(label.ljust(fetch.LABEL_WIDTH), "label", False), (value, "value", False)] for label, value in fetched]
    return [layout.fit(line, width) for line in lines]


def omen_line(now: datetime, data: dict, width: int) -> layout.Line:
    """One line: phase, card of the day and, near a sabbat, the sabbat."""
    phase = moon.phase_bin(now)
    card, reversed_ = tarot.card_of(now.date(), data["tarot"])
    line = [(f"{moon.GLYPHS[phase]} {moon.NAMES[phase]} {moon.illumination(now)}%", "moon", False), SEPARATOR,
            (f"{palette.GLYPHS['dirty']} {card['name']}", "tarot", False)]
    if reversed_:
        line.append((" (reversed)", "muted", False))
    sabbat = wheel.upcoming(now.date(), now.tzinfo)
    if sabbat:
        name, days = sabbat
        candle = f"{palette.GLYPHS['candle']} {name}"
        line += [SEPARATOR, (candle if days == 0 else _countdown(name, days), name.lower(), False)]
    return layout.fit(line, width)


def art_lines(now: datetime) -> list[layout.Line]:
    rows = []
    for cells in art.picture(moon.age(now) / moon.SYNODIC_DAYS, now.date()):
        line: layout.Line = []
        for char, key in cells:
            if line and line[-1][1] == key:
                line[-1] = (line[-1][0] + char, key, False)
            else:
                line.append((char, key, False))
        rows.append(line)
    return rows


def full_ritual(now: datetime, data: dict, fetched: list[tuple[str, str]], columns: int) -> list[layout.Line]:
    if columns >= SIDE_BY_SIDE:
        info = info_lines(now, data, fetched, columns - art.WIDTH - layout.GAP)
        return layout.side_by_side(art_lines(now), info, art.WIDTH)
    info = info_lines(now, data, fetched, columns)
    return art_lines(now) + [[]] + info if columns >= STACKED else info


def _auto(stamp: Path, now: datetime, columns: int) -> str:
    try:
        recent = 0 <= now.timestamp() - stamp.stat().st_mtime < FULL_EVERY  # a future stamp is stale
    except OSError:
        recent = False
    return "full" if not recent and columns >= MIN_FULL_COLUMNS else "omen"


def _stamp(path: Path, now: datetime) -> None:
    """Remember when the full ritual last ran (the file's mtime), so auto mode shows the omen for a while."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        os.utime(path, (now.timestamp(), now.timestamp()))
    except OSError:
        pass


def iso_day(text: str) -> date:
    """``--date``: YYYY-MM-DD only (from 3.11, date.fromisoformat also takes 20261031 and 2026-W44-6)."""
    if ISO_DAY.fullmatch(text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(f"{text!r} is not a date in the form YYYY-MM-DD")


class _Parser(argparse.ArgumentParser):
    """Exits 2 with usage as usual, and also logs the error when stderr is not a terminal.

    fish_greeting sends stderr to /dev/null, so without the log a broken call would be invisible to doctor.
    """

    def __init__(self, log_path: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self.log_path = log_path

    def error(self, message: str) -> NoReturn:
        if not (sys.stderr and sys.stderr.isatty()):
            log.append(self.log_path, f"greeting: bad arguments: {message}", datetime.now())
        super().error(message)


def _arguments(argv: list[str] | None, log_path: Path) -> argparse.Namespace:
    parser = _Parser(log_path, prog="ritual", description="The Moonlit Candle greeting")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--full", action="store_true", help="always show the full ritual")
    mode.add_argument("--omen", action="store_true", help="show the one-line omen")
    mode.add_argument("--sky", action="store_true",
                      help="move the Windows Terminal sky to tonight's phase and write the caret cache")
    mode.add_argument("--caret", action="store_true", help="write the caret cache only")
    parser.add_argument("--debug", action="store_true", help="print the time each stage took")
    parser.add_argument("--date", type=iso_day, help="preview another day (YYYY-MM-DD)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, env: Mapping[str, str] | None = None, out: TextIO | None = None,
         now: datetime | None = None, home: Path | None = None, root: Path = Path("/"),
         columns: int | None = None) -> int:
    """Print the greeting. Any error prints nothing, is logged, and still exits 0."""
    env = os.environ if env is None else env
    out = sys.stdout if out is None else out
    home = Path.home() if home is None else home
    cache = home / CACHE
    args = _arguments(argv, cache / log.NAME)
    try:
        marks = [("start", time.perf_counter())]
        now = now or datetime.now().astimezone()
        if args.date and not (args.sky or args.caret):  # the sky job always works on the real now
            # the same wall time, with the local UTC offset of that day (it differs across a DST change)
            now = datetime.combine(args.date, now.time()).astimezone()
        if args.sky:
            return sky.run(home, now)
        if args.caret:
            return sky.run(home, now, move_sky=False)
        columns = columns or shutil.get_terminal_size((80, 24)).columns
        data = load_data()
        marks.append(("data", time.perf_counter()))
        if args.full or args.omen:
            mode = "full" if args.full else "omen"
        else:
            mode = _auto(cache / STAMP, now, columns)
        if mode == "full":
            fetched = fetch.lines(env, root)
            marks.append(("fetch", time.perf_counter()))
            lines = full_ritual(now, data, fetched, columns)
        else:
            lines = [omen_line(now, data, columns)]
        marks.append(("compose", time.perf_counter()))
        colours = None if env.get("NO_COLOR") else palette.PALETTE
        text = "".join(layout.render(line, colours) + "\n" for line in lines) + "\n"
        marks.append(("render", time.perf_counter()))
        if args.debug:
            stages = [f"{name} {(end - start) * 1000:.1f} ms" for (_, start), (name, end) in zip(marks, marks[1:])]
            text += "debug: " + " · ".join(stages) + f" · total {(marks[-1][1] - marks[0][1]) * 1000:.1f} ms\n"
        out.write(text)
        if mode == "full" and not args.date:  # a preview must not silence the real greeting
            _stamp(cache / STAMP, now)
    except Exception as exc:  # the greeting must never break a shell: log and stay silent
        log.append(cache / log.NAME, f"greeting: {exc!r}", datetime.now())
    return 0
