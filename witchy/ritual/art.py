"""The ASCII moon: an 11 × 22 disc lit for the moon's age, and a few stars that move once a day."""
from __future__ import annotations

import math
import random
from datetime import date

ROWS, COLS = 11, 22  # two columns per row: terminal cells are about twice as tall as they are wide
MARGIN = 3
WIDTH = COLS + 2 * MARGIN
STAR_GLYPHS = ("✦", "⋆", "·", "˚")
STAR_COLOURS = ("star", "star_violet")
STAR_CLEARANCE = 1.25  # stars keep this far from the disc centre, in disc radii
# A cell: its character and the palette key it is drawn in (None for blank).
Cell = tuple  # (str, str | None)


def disc(fraction: float) -> list[list[Cell]]:
    """The moon ``fraction`` of the way through its cycle (0 new, 0.5 full); waxing light on the right."""
    phase = 2 * math.pi * fraction
    lit = (1 - math.cos(phase)) / 2 > 0.005
    waxing = fraction % 1 <= 0.5
    rows = []
    for r in range(ROWS):
        y = (r + 0.5 - ROWS / 2) / (ROWS / 2)
        row = []
        for c in range(COLS):
            x = (c + 0.5 - COLS / 2) / (COLS / 2)
            distance = math.hypot(x, y)
            if distance > 1:
                row.append((" ", None))
            elif lit and (x if waxing else -x) >= math.cos(phase) * math.sqrt(max(0.0, 1 - y * y)):
                row.append(("█", "lit") if distance < 0.55 else ("▓", "lit_mid") if distance < 0.8
                           else ("▒", "lit_soft"))
            else:
                row.append(("░", "earthshine"))
        rows.append(row)
    return rows


def picture(fraction: float, day: date) -> list[list[Cell]]:
    """The disc with a margin on each side and 6–10 stars placed from ``day``: they move daily, not hourly."""
    rows = [[(" ", None)] * MARGIN + row + [(" ", None)] * MARGIN for row in disc(fraction)]
    rng = random.Random(day.toordinal())
    wanted = rng.randint(6, 10)
    placed = 0
    for _ in range(200):
        if placed == wanted:
            break
        r, c = rng.randrange(ROWS), rng.randrange(WIDTH)
        x = (c - MARGIN + 0.5 - COLS / 2) / (COLS / 2)
        y = (r + 0.5 - ROWS / 2) / (ROWS / 2)
        neighbours = [rows[rr][cc][1] for rr in range(max(0, r - 1), min(ROWS, r + 2))
                      for cc in range(max(0, c - 1), min(WIDTH, c + 2))]
        if math.hypot(x, y) < STAR_CLEARANCE or any(key in STAR_COLOURS for key in neighbours):
            continue
        rows[r][c] = (rng.choice(STAR_GLYPHS), rng.choice(STAR_COLOURS))
        placed += 1
    return rows
