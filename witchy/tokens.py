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


# OpenCode's theme keys, grouped the same way. Source (the colour keys and where they show):
# https://github.com/anomalyco/opencode/blob/v1.18.34/packages/tui/src/theme/index.ts
OPENCODE_SURFACES = ("background", "backgroundPanel", "backgroundElement", "backgroundMenu")
OPENCODE_MARKDOWN = (
    "markdownText", "markdownHeading", "markdownLink", "markdownLinkText", "markdownCode", "markdownBlockQuote",
    "markdownEmph", "markdownStrong", "markdownListItem", "markdownListEnumeration", "markdownImage",
    "markdownImageText", "markdownCodeBlock",
)
OPENCODE_SYNTAX = (
    "syntaxComment", "syntaxKeyword", "syntaxFunction", "syntaxVariable", "syntaxString", "syntaxNumber",
    "syntaxType", "syntaxOperator", "syntaxPunctuation",
)
# Read as text: 4.5:1 on every surface.
OPENCODE_TEXT = (
    "primary", "secondary", "accent", "error", "warning", "success", "info", "text", "textMuted",
    *OPENCODE_MARKDOWN, *OPENCODE_SYNTAX,
    "diffContext", "diffHunkHeader", "diffLineNumber", "diffAdded", "diffRemoved",
)
# (text keys, surface key): the text must reach 4.5:1 on the surface.
OPENCODE_DIFF_PAIRS: tuple[tuple[tuple[str, ...], str], ...] = (
    *((("text", *OPENCODE_SYNTAX), surface) for surface in ("diffAddedBg", "diffRemovedBg", "diffContextBg")),
    (("diffAdded", "diffHighlightAdded"), "diffAddedBg"),
    (("diffRemoved", "diffHighlightRemoved"), "diffRemovedBg"),
    (("diffLineNumber",), "diffContextBg"),
    (("diffLineNumber",), "diffAddedLineNumberBg"),
    (("diffLineNumber",), "diffRemovedLineNumberBg"),
)
# Drawn on accent fills (selected rows, the permission card's chosen option): 4.5:1 against each.
OPENCODE_ON_ACCENT = "selectedListItemText"
OPENCODE_ACCENT_FILLS = ("primary", "secondary", "accent", "warning", "error", "success", "info")
# Borders and rules: 3:1 on the background.
OPENCODE_SECONDARY = ("border", "borderActive", "markdownHorizontalRule")
OPENCODE_EXEMPT = {
    "borderSubtle": "a divider line, not information",
}
# The diff surfaces and the highlights are only named in OPENCODE_DIFF_PAIRS, so the key set takes them from there.
OPENCODE_ALL = frozenset((
    *OPENCODE_SURFACES, *OPENCODE_TEXT, OPENCODE_ON_ACCENT, *OPENCODE_SECONDARY, *OPENCODE_EXEMPT,
    *(key for keys, surface in OPENCODE_DIFF_PAIRS for key in (*keys, surface)),
))
