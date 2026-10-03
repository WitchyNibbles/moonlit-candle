"""Lines of coloured segments, their width in terminal cells, and the three layouts."""
from __future__ import annotations

import unicodedata

# Emoji we print, drawn two cells wide. 🕯 is narrow in Unicode but terminals draw it wide with its VS16.
WIDE = frozenset("🌑🌒🌓🌔🌕🌖🌗🌘🕯")
ZERO_WIDTH = frozenset("️‍")
GAP = 3
ELLIPSIS = "…"
# A segment: (text, palette key or None, bold). A line: a list of segments.
Segment = tuple
Line = list


def cell_width(text: str) -> int:
    width = 0
    for ch in text:
        if ch in ZERO_WIDTH or unicodedata.combining(ch):
            continue
        width += 2 if ch in WIDE or unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def line_width(line: Line) -> int:
    return sum(cell_width(text) for text, _, _ in line)


def fit(line: Line, width: int) -> Line:
    """``line`` cut to ``width`` cells, ending in an ellipsis when it was too long."""
    if line_width(line) <= width:
        return line
    result, used = [], 0
    for text, key, bold in line:
        kept = ""
        for ch in text:
            size = cell_width(ch)
            if used + size > width - 1:
                result.append((kept + ELLIPSIS, key, bold))
                return result
            kept += ch
            used += size
        result.append((kept, key, bold))
    return result


def side_by_side(art: list[Line], info: list[Line], art_width: int) -> list[Line]:
    """Art on the left, ``GAP`` spaces, info on the right; the shorter block is centred vertically."""
    height = max(len(art), len(info))
    art_top, info_top = (height - len(art)) // 2, (height - len(info)) // 2
    rows = []
    for index in range(height):
        left = art[index - art_top] if 0 <= index - art_top < len(art) else []
        right = info[index - info_top] if 0 <= index - info_top < len(info) else []
        if right:
            left = left + [(" " * (art_width - line_width(left) + GAP), None, False)]
        rows.append(left + right)
    return rows


def render(line: Line, palette: dict[str, str] | None) -> str:
    """The line as text: 24-bit colour escapes, or plain text when ``palette`` is None (NO_COLOR)."""
    parts = []
    for text, key, bold in line:
        if palette is None or key is None:
            parts.append(text)
            continue
        colour = palette[key]
        red, green, blue = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
        parts.append(f"\x1b[{'1;' if bold else ''}38;2;{red};{green};{blue}m{text}\x1b[0m")
    return "".join(parts).rstrip(" ")
