"""Moonlit Candle: every colour the theme ships, defined once.

The night comes from Spellbound Moonlit, the candle gold from devgod/archon.
build.py turns this into the Claude Code theme, the Windows Terminal scheme
and the status line palette; validate.py holds all of it to the contrast rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

THEME_NAME = "Moonlit Candle"
THEME_SLUG = "moonlit-candle"
BACKGROUND = "#0D0916"
FOREGROUND = "#F3EAF7"

CLAUDE_OVERRIDES: dict[str, str] = {
    # Accents and text
    "claude": "#FFD477",
    "claudeShimmer": "#FFF1C9",
    "text": FOREGROUND,
    "inverseText": BACKGROUND,
    "inactive": "#A99AB9",
    "inactiveShimmer": "#CFC3DB",
    "subtle": "#6E5A80",
    "suggestion": "#B99AFF",
    "permission": "#FF67B7",
    "permissionShimmer": "#FFB3DA",
    "remember": "#B99AFF",
    # Status
    "success": "#74E8B8",
    "error": "#FF6B9F",
    "warning": "#FFB86B",
    "warningShimmer": "#FFD6A3",
    "merged": "#B99AFF",
    # Input box and modes
    "promptBorder": "#6E5A80",
    "promptBorderShimmer": "#9A82B0",
    "planMode": "#B99AFF",
    "autoAccept": "#FF67B7",
    "bashBorder": "#77D9FF",
    "ide": "#77D9FF",
    "fastMode": "#FF9BD7",
    "fastModeShimmer": "#FFC8E9",
    "effortUltra": "#FFD477",
    # Diffs (opaque: terminals have no alpha)
    "diffAdded": "#153042",
    "diffRemoved": "#441632",
    "diffAddedDimmed": "#111D2A",
    "diffRemovedDimmed": "#2A1022",
    "diffAddedWord": "#1C4F65",
    "diffRemovedWord": "#712049",
    # Message backgrounds
    "userMessageBackground": "#1D1230",
    "userMessageBackgroundHover": "#271A3D",
    "bashMessageBackgroundColor": "#0F1E28",
    "memoryBackgroundColor": "#1A1433",
    "selectionBg": "#633B79",
    # Usage meter and speaker labels
    "rate_limit_fill": "#FFD477",
    "rate_limit_empty": "#38234D",
    "briefLabelYou": "#77D9FF",
    "briefLabelClaude": "#FFD477",
    # Subagents
    "red_FOR_SUBAGENTS_ONLY": "#FF6B9F",
    "blue_FOR_SUBAGENTS_ONLY": "#7FA6FF",
    "green_FOR_SUBAGENTS_ONLY": "#74E8B8",
    "yellow_FOR_SUBAGENTS_ONLY": "#FFD477",
    "purple_FOR_SUBAGENTS_ONLY": "#B99AFF",
    "orange_FOR_SUBAGENTS_ONLY": "#FFB86B",
    "pink_FOR_SUBAGENTS_ONLY": "#FF67B7",
    "cyan_FOR_SUBAGENTS_ONLY": "#74E0E8",
    # ultrathink rainbow
    "rainbow_red": "#FF6B9F",
    "rainbow_red_shimmer": "#FFA3C2",
    "rainbow_orange": "#FFB86B",
    "rainbow_orange_shimmer": "#FFD3A3",
    "rainbow_yellow": "#FFD477",
    "rainbow_yellow_shimmer": "#FFE7B3",
    "rainbow_green": "#74E8B8",
    "rainbow_green_shimmer": "#A8F2D4",
    "rainbow_blue": "#77D9FF",
    "rainbow_blue_shimmer": "#B0E9FF",
    "rainbow_indigo": "#9C8CFF",
    "rainbow_indigo_shimmer": "#C4BAFF",
    "rainbow_violet": "#D59BFF",
    "rainbow_violet_shimmer": "#E8C7FF",
}

WT_SCHEME: dict[str, str] = {
    "name": THEME_NAME,
    "background": BACKGROUND,
    "foreground": FOREGROUND,
    "cursorColor": "#FF67B7",
    "selectionBackground": "#633B79",
    "black": "#1D1230",
    "red": "#FF6B9F",
    "green": "#74E8B8",
    "yellow": "#FFD477",
    "blue": "#77D9FF",
    "purple": "#B99AFF",
    "cyan": "#74D7E8",
    "white": "#E6DCEE",
    "brightBlack": "#6E5A80",
    "brightRed": "#FF8FB5",
    "brightGreen": "#9DF2CE",
    "brightYellow": "#FFE3A3",
    "brightBlue": "#A3E6FF",
    "brightPurple": "#D0B8FF",
    "brightCyan": "#A0E9F2",
    "brightWhite": "#FFFFFF",
}

# Order matters: build.py writes this dict into statusline.py's PALETTE block verbatim.
STATUSLINE: dict[str, str] = {
    "model": "#FFD477",
    "muted": "#A99AB9",
    "divider": "#503762",
    "repo": "#B99AFF",
    "branch": "#77D9FF",
    "dirty": "#FF67B7",
    "context_low": "#FFD477",
    "context_mid": "#FF67B7",
    "context_high": "#FF6B9F",
    "left_high": "#FFD477",
    "left_mid": "#B99AFF",
    "left_low": "#FF67B7",
}

# The Windows Terminal sky (sky_render.py). Decorative, so exempt from the contrast rules (spec 11.2).
SKY: dict[str, str] = {
    "background": BACKGROUND,
    "moon": "#FFD477",
    "moon_dark": "#1D1230",
    "moon_rim": "#38234D",
    "star": FOREGROUND,
    "star_gold": "#FFD477",
    "star_violet": "#B99AFF",
}


# Windows Terminal profile settings (spec 4.2). backgroundImage is chosen at install time from the moon phase.
WT_PROFILE: dict[str, Any] = {
    "font": {"face": "Maple Mono NF", "size": 12, "cellHeight": "1.1"},
    "cursorShape": "filledBox",
    "padding": "14",
    "opacity": 93,
    "useAcrylic": True,
    "backgroundImageOpacity": 0.12,
    "backgroundImageAlignment": "bottomRight",
    "backgroundImageStretchMode": "uniformToFill",
    "icon": "\U0001F319",
    "tabTitle": "witchyterm",
    "suppressApplicationTitle": True,
}


@dataclass(frozen=True)
class Variant:
    """One complete colour set. Variants change colours only: theme name, scheme name and
    installed paths stay the same, so switching never has to move files."""

    name: str
    claude_base: str
    background: str
    foreground: str
    claude_overrides: dict[str, str]
    wt_scheme: dict[str, str]
    statusline: dict[str, str]
    sky: dict[str, str] = field(default_factory=dict)
    wt_profile: dict[str, Any] = field(default_factory=dict)


DEFAULT_VARIANT = "midnight"
VARIANTS: dict[str, Variant] = {
    "midnight": Variant("midnight", "dark", BACKGROUND, FOREGROUND, CLAUDE_OVERRIDES, WT_SCHEME, STATUSLINE,
                        sky=SKY, wt_profile=WT_PROFILE),
}
