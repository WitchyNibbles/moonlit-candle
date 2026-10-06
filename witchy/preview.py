"""python3 -m witchy preview: the Tide prompt drawn from the palette, with neither fish nor Tide (spec 15.2).

A sketch. For its sample states it copies what Tide 6.1.1 does (fish_prompt's frame, _tide_2_line_prompt,
_tide_print_item, _tide_pwd and the moon, pwd, git, status, cmd_duration, jobs, time and character items);
nothing of Tide runs, and Tide's truncation of long paths is left out because no sample needs it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from . import build, palette
from .ritual import layout, moon

NORMAL = "\x1b[0m"
BOLD = "\x1b[1m"
DEFAULT_BG = "\x1b[49m"
ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
PWD_MARK = "@PWD@"  # Tide draws the items first and puts the path in last; the frame needs its width


@dataclass(frozen=True)
class Sample:
    """One prompt state. ``pwd`` is the path as Tide shows it (``~`` for HOME)."""

    name: str
    title: str
    pwd: str
    writable: bool = True
    branch: str | None = None
    dirty: int = 0
    untracked: int = 0
    status: int = 0
    duration_ms: int = 0
    jobs: int = 0


SAMPLES = (
    Sample("home", "home", "~"),
    Sample("git", "a project with changed and new files", "~/projects/witchyterm", branch="main", dirty=2,
           untracked=1),
    Sample("unwritable", "a folder you cannot write to", "/etc/ssl", writable=False),
    Sample("failed", "a command that failed with exit 2 after 4 s", "~/projects/witchyterm", branch="main",
           status=2, duration_ms=4321),
    Sample("jobs", "two jobs in the background", "~/projects", jobs=2),
)


def _rgb(colour: str) -> str:
    """``RRGGBB`` as the ``R;G;B`` of a 24-bit colour escape."""
    return ";".join(str(int(colour[i:i + 2], 16)) for i in (0, 2, 4))


def fg(colour: str) -> str:
    return f"\x1b[38;2;{_rgb(colour)}m"


def bg(colour: str) -> str:
    return f"\x1b[48;2;{_rgb(colour)}m"


def width(text: str) -> int:
    """Cells on screen, as `string length -V` counts them with fish_emoji_width 2."""
    return layout.cell_width(ESCAPE.sub("", text))


class Side:
    """One side of the prompt, item by item, the way _tide_print_item joins them."""

    def __init__(self, tide: Mapping[str, str], side: str) -> None:
        self.tide, self.side = tide, side
        self.text = ""
        self.previous: str | None = None
        self.add_prefix = True
        self.pad = " " if tide["tide_prompt_pad_items"] == "true" else ""

    def item(self, name: str, text: str, bg_colour: str | None = None, colour: str | None = None) -> None:
        tide, side = self.tide, self.side
        item_bg = bg_colour or tide[f"tide_{name}_bg_color"]
        if self.add_prefix:
            self.text += fg(item_bg) + DEFAULT_BG + tide[f"tide_{side}_prompt_prefix"]
            self.add_prefix = False
        elif item_bg == self.previous:
            separator = tide[f"tide_{side}_prompt_separator_same_color"]
            self.text += fg(tide["tide_prompt_color_separator_same_color"]) + separator
        elif side == "left":
            self.text += fg(self.previous) + bg(item_bg) + tide["tide_left_prompt_separator_diff_color"]
        else:
            self.text += fg(item_bg) + bg(self.previous) + tide["tide_right_prompt_separator_diff_color"]
        colour = colour or tide.get(f"tide_{name}_color")  # pwd has none: its text carries its own colours
        self.text += (fg(colour) if colour else "") + bg(item_bg) + self.pad + text + self.pad
        self.previous = item_bg

    def end(self) -> str:
        """The side's last cap; the side is done."""
        if not self.add_prefix:
            self.text += fg(self.previous) + DEFAULT_BG + self.tide[f"tide_{self.side}_prompt_suffix"]
            self.add_prefix = True
        return self.text


def pwd(tide: Mapping[str, str], sample: Sample) -> str:
    """_tide_pwd for a path short enough to need no truncation."""
    anchors = BOLD + fg(tide["tide_pwd_color_anchors"])
    dirs = NORMAL + bg(tide["tide_pwd_bg_color"]) + fg(tide["tide_pwd_color_dirs"])
    if sample.pwd == "~":
        return dirs + tide["tide_pwd_icon_home"] + " " + anchors + "~"
    parts = sample.pwd.split("/")
    icon = tide["tide_pwd_icon"] if sample.writable else tide["tide_pwd_icon_unwritable"]
    parts[0] = icon + " " + parts[0]
    parts[-1] = anchors + parts[-1] + dirs
    return dirs + "/".join(parts)


def git(tide: Mapping[str, str], sample: Sample) -> tuple[str, str]:
    """The git item's text and background."""
    branch = fg(tide["tide_git_color_branch"])
    text = branch + tide["tide_git_icon"] + " " + branch + sample.branch
    if sample.dirty:
        text += fg(tide["tide_git_color_dirty"]) + f" !{sample.dirty}"
    if sample.untracked:
        text += fg(tide["tide_git_color_untracked"]) + f" ?{sample.untracked}"
    unstable = sample.dirty or sample.untracked
    return text, tide["tide_git_bg_color_unstable"] if unstable else tide["tide_git_bg_color"]


def duration(milliseconds: int) -> str:
    """_tide_item_cmd_duration with tide_cmd_duration_decimals 0: whole seconds, then minutes and hours."""
    seconds = milliseconds // 1000
    hours, minutes, seconds = seconds // 3600, seconds // 60 % 60, seconds % 60
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    return f"{minutes}m {seconds}s" if minutes else f"{seconds}s"


def prompt(tide: Mapping[str, str], sample: Sample, now: datetime, columns: int) -> list[str]:
    """The two lines a new prompt shows in ``sample``'s state."""
    left = Side(tide, "left")
    left.item("moon", moon.GLYPHS[moon.phase_bin(now)])
    left.item("pwd", PWD_MARK)
    if sample.branch is not None:
        text, git_bg = git(tide, sample)
        left.item("git", text, bg_colour=git_bg)
    top_left = left.end()  # the newline item
    bottom_left = fg(tide["tide_character_color"] if sample.status == 0 else tide["tide_character_color_failure"])
    bottom_left += tide["tide_character_icon"]

    right = Side(tide, "right")
    # With the character item on the left, Tide shows a status only for a code other than 1 (the caret turns
    # rose-red for any failure).
    if sample.status not in (0, 1):
        right.item("status", f"{tide['tide_status_icon_failure']} {sample.status}",
                   bg_colour=tide["tide_status_bg_color_failure"], colour=tide["tide_status_color_failure"])
    if sample.duration_ms > int(tide["tide_cmd_duration_threshold"]):
        right.item("cmd_duration", f"{tide['tide_cmd_duration_icon']} {duration(sample.duration_ms)}")
    if sample.jobs:
        number = f" {sample.jobs}" if sample.jobs >= int(tide["tide_jobs_number_threshold"]) else ""
        right.item("jobs", tide["tide_jobs_icon"] + number)
    right.item("time", now.strftime(tide["tide_time_format"]))
    top_right = right.end()

    frame = fg(tide["tide_prompt_color_frame_and_connection"]) + DEFAULT_BG
    top_left = top_left.replace(PWD_MARK, pwd(tide, sample))
    fill = max(0, columns - 4 - width(top_left) - width(top_right))
    top = (frame + "╭─" + top_left + frame + tide["tide_prompt_icon_connection"] * fill + top_right + frame + "─╮"
           + NORMAL)
    bottom_right = frame + "─╯" + NORMAL
    bottom = frame + "╰─" + bottom_left + NORMAL + " "
    bottom += " " * max(0, columns - width(bottom) - width(bottom_right)) + bottom_right
    return [top, bottom]


def render(variant: str = palette.DEFAULT_VARIANT, now: datetime | None = None, columns: int = 80) -> str:
    """Every sample, each under its title."""
    now = now or datetime.now().astimezone()
    tide = {name: value if isinstance(value, str) else " ".join(value) for name, value in build.tide(variant).items()}
    lines = [f"{palette.THEME_NAME} prompt ({variant}), drawn from the palette; a sketch, Tide itself does not run."]
    for sample in SAMPLES:
        lines += ["", sample.title, *prompt(tide, sample, now, columns)]
    return "\n".join(lines) + "\n"
