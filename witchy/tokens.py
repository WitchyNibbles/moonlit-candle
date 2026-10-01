"""Every colour token Claude Code documents for custom themes, grouped by the rule it answers to.

Source: https://code.claude.com/docs/en/terminal-config.md#create-a-custom-theme
(colour token reference, checked 2026-09-30). A token missing here is one
validate.py rejects, so a typo can never silently fall through to the base preset.
"""
from __future__ import annotations

SUBAGENT_COLOURS = ("red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan")
RAINBOW_COLOURS = ("red", "orange", "yellow", "green", "blue", "indigo", "violet")

# Read as text: 4.5:1 against the terminal background.
TEXT = (
    "claude", "text", "inactive", "suggestion", "permission", "remember",
    "success", "error", "warning", "merged",
    "planMode", "autoAccept", "bashBorder", "ide", "fastMode", "effortUltra",
    "briefLabelYou", "briefLabelClaude",
    *(f"{colour}_FOR_SUBAGENTS_ONLY" for colour in SUBAGENT_COLOURS),
    *(f"rainbow_{colour}" for colour in RAINBOW_COLOURS),
)
# Secondary text and non-text UI: 3:1 against the terminal background.
SECONDARY = ("subtle", "promptBorder", "rate_limit_fill")
# Surfaces under the default text colour: the text must reach 4.5:1 on them.
BACKGROUNDS = (
    "diffAdded", "diffRemoved", "diffAddedDimmed", "diffRemovedDimmed", "diffAddedWord", "diffRemovedWord",
    "userMessageBackground", "userMessageBackgroundHover", "bashMessageBackgroundColor",
    "memoryBackgroundColor", "selectionBg",
)
# inverseText is drawn on accent fills such as status badges: 4.5:1 against each.
ON_ACCENT = "inverseText"
ACCENT_FILLS = ("claude", "permission", "success", "error", "warning")
# No contrast rule applies to these, for the reason given.
EXEMPT = {
    "rate_limit_empty": "decorative track of the usage meter",
    **{
        name: "animated highlight of its base token"
        for name in (
            "claudeShimmer", "warningShimmer", "permissionShimmer",
            "promptBorderShimmer", "inactiveShimmer", "fastModeShimmer",
            *(f"rainbow_{colour}_shimmer" for colour in RAINBOW_COLOURS),
        )
    },
}
ALL = frozenset((*TEXT, *SECONDARY, *BACKGROUNDS, ON_ACCENT, *EXEMPT))
