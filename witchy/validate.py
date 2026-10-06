"""The rules Moonlit Candle must pass before build or install touch anything."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from . import content, palette, sky_render, tokens
from .contrast import contrast_ratio
from .ritual import layout

HEX = re.compile(r"^#[0-9A-F]{6}$")
TIDE_HEX = re.compile(r"^[0-9A-F]{6}$")  # Tide colours carry no "#"
TEXT_MIN = 4.5
SECONDARY_MIN = 3.0

WT_COLOUR_KEYS = (
    "background", "foreground", "cursorColor", "selectionBackground",
    "black", "red", "green", "yellow", "blue", "purple", "cyan", "white",
    "brightBlack", "brightRed", "brightGreen", "brightYellow",
    "brightBlue", "brightPurple", "brightCyan", "brightWhite",
)
WT_TEXT = (
    "foreground", "red", "green", "yellow", "blue", "purple", "cyan", "white",
    "brightRed", "brightGreen", "brightYellow", "brightBlue", "brightPurple", "brightCyan", "brightWhite",
)
WT_SECONDARY = ("brightBlack", "cursorColor")
WT_BACKGROUNDS = ("selectionBackground",)
# ANSI black sits next to the background by convention; it is never used for body text.
WT_EXEMPT = ("black",)
# The ⋆ separator is decoration, not information.
STATUSLINE_EXEMPT = ("divider",)

REQUIRED_VERBS = (
    "Brewing", "Conjuring", "Scrying", "Hexing", "Divining", "Transmuting", "Warding", "Exorcising",
    "Summoning", "Enchanting", "Incanting", "Stirring the cauldron", "Consulting the grimoire",
    "Reading the runes", "Lighting candles", "Scrying the query plan",
)
REQUIRED_TIPS = {
    "haunted-houses": "Legacy systems are just haunted houses with uptime requirements.",
    "love-letters": "Tests are love letters to your future self.",
    "ghost-in-query-plan": "Measure before you optimise — the ghost is usually in the query plan.",
    "boring-code": "Boring code is good code.",
    "remembers-everything": "Be kind to your code — it remembers everything.",
    "keep-the-receipts": "Keep the receipts.",
    "hold-the-thread": "Hold the thread.",
    "through-the-fog": "Exorcising legacy systems. Shipping code through the fog.",
}
# Claude Code appends its own ellipsis, so verbs must not carry one.
VERB = re.compile(r"^[A-Z][a-z]*ing( [A-Za-z'-]+)*$")
TIP_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
VERBS_RANGE = (36, 48)
TIPS_RANGE = (18, 24)
VERB_MAX = 28
TIP_MAX = 120
TIP_ID_MAX = 64

# The greeting's texts (spec 11.1)
SABBATS = ("Imbolc", "Ostara", "Beltane", "Litha", "Lughnasadh", "Mabon", "Samhain", "Yule")
LUNAR_LINES = ("new", "full", "blue")
TAROT_CARDS = 22
NAME_MAX = 24
LINE_MAX = 48
MEANING_MAX = 60


# Tide (spec 11.3): (text, background) pairs; None stands for the terminal background.
GIT_PARTS = ("branch", "conflicted", "dirty", "operation", "staged", "stash", "untracked", "upstream")
GIT_BACKGROUNDS = ("tide_git_bg_color", "tide_git_bg_color_unstable", "tide_git_bg_color_urgent")
TIDE_TEXT_PAIRS: tuple[tuple[str, str | None], ...] = (
    ("tide_moon_color", "tide_moon_bg_color"),
    ("tide_pwd_color_anchors", "tide_pwd_bg_color"),
    ("tide_pwd_color_dirs", "tide_pwd_bg_color"),
    *((f"tide_git_color_{part}", background) for part in GIT_PARTS for background in GIT_BACKGROUNDS),
    ("tide_status_color", "tide_status_bg_color"),
    ("tide_status_color_failure", "tide_status_bg_color_failure"),
    ("tide_cmd_duration_color", "tide_cmd_duration_bg_color"),
    ("tide_time_color", "tide_time_bg_color"),
    ("tide_character_color", None),
    ("tide_character_color_failure", None),
)
# The items witchy does not show (spec 6.4) and jobs: each one's text on its own background.
TIDE_ITEMS = ("aws", "crystal", "direnv", "distrobox", "docker", "elixir", "gcloud", "go", "java", "jobs",
              "kubectl", "nix_shell", "node", "os", "php", "private_mode", "pulumi", "python", "ruby", "rustc",
              "shlvl", "terraform", "toolbox", "zig")
TIDE_ITEM_PAIRS: tuple[tuple[str, str | None], ...] = (
    *((f"tide_{item}_color", f"tide_{item}_bg_color") for item in TIDE_ITEMS),
    ("tide_direnv_color_denied", "tide_direnv_bg_color_denied"),
    *((f"tide_context_color_{kind}", "tide_context_bg_color") for kind in ("default", "root", "ssh")),
    *((f"tide_vi_mode_color_{mode}", f"tide_vi_mode_bg_color_{mode}") for mode in palette.VI_MODES),
)
TIDE_SECONDARY_PAIRS: tuple[tuple[str, str | None], ...] = (
    ("tide_pwd_color_truncated_dirs", "tide_pwd_bg_color"),
    ("tide_prompt_color_frame_and_connection", None),
)


# Every colour and icon of the old "pastel princess" prompt (~/change_this_bitch.sh), so none comes back
# (spec 11.3). Icons witchy uses on purpose (🔮 🐍 💎 🦀 ☕ 🐳) are left off; icons are stored without U+FE0F.
PASTEL = frozenset({
    "012A4A", "034078", "05386B", "1C0035", "1F0322", "280659", "2B061E", "2D132C", "371B58", "3A0F29", "3E005D",
    "490B3D", "4B1139", "52052E", "541C1D", "5A4500", "5C3A21", "5D1E41", "780116", "A2D2FF", "BDE0FE", "BEE3DB",
    "CBC3E3", "D4E6FB", "D8B4FE", "E0AAFF", "E2CFEA", "E7C6FF", "E8CFF8", "F4978E", "F4ACB7", "F5C6E0", "F8A4C9",
    "FBAED2", "FCD5CE", "FDE68A", "FF3E96", "FF6B6B", "FF6EC7", "FFAAA5", "FFAFCC", "FFB7C5", "FFC8DD", "FFD1DC",
    "FFD6E0", "FFDAC1", "FFDFD3", "FFE5B4", "FFF5C2",
    "🎀", "🏰", "🌷", "💖", "💔", "✨", "🍰", "🌸", "🔒", "⏳", "🪡", "🍬", "🐬", "🦄", "☸", "☁", "🍯", "🌼",
    "🕶", "🧁", "🖋", "🎨", "🩹", "👑",
})
# Spec 11.1 (D5): a prompt icon is one code point. These would join or restyle the emoji before them.
PROMPT_GLYPH_MARKS = frozenset({"\uFE0F", "\u200D", *map(chr, range(0x1F3FB, 0x1F400))})


@dataclass(frozen=True)
class Failure:
    rule: str
    item: str
    value: str
    detail: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.item} {self.value} {self.detail}"


def _contrast(failures: list[Failure], rule: str, item: str, foreground: str, background: str,
              minimum: float, shown: str) -> None:
    ratio = contrast_ratio(foreground, background)
    if ratio < minimum:
        failures.append(Failure(rule, item, shown, f"{ratio:.2f}:1 < {minimum}:1"))


def validate_palette(
    overrides: Mapping[str, Any] = palette.CLAUDE_OVERRIDES,
    scheme: Mapping[str, Any] = palette.WT_SCHEME,
    statusline: Mapping[str, Any] = palette.STATUSLINE,
    background: str = palette.BACKGROUND,
    foreground: str = palette.FOREGROUND,
) -> list[Failure]:
    failures: list[Failure] = []
    colours = {"background": background, "foreground": foreground}
    colours.update({f"claude.{k}": v for k, v in overrides.items()})
    colours.update({f"wt.{k}": v for k, v in scheme.items() if k != "name"})
    colours.update({f"statusline.{k}": v for k, v in statusline.items()})
    bad = set()
    for item, value in colours.items():
        if not isinstance(value, str) or not HEX.match(value):
            failures.append(Failure("format", item, str(value), "is not #RRGGBB in uppercase"))
            bad.add(item)
    if {"background", "foreground"} & bad:
        return failures

    def usable(prefix: str, mapping: Mapping[str, Any], key: str) -> bool:
        return key in mapping and f"{prefix}.{key}" not in bad

    for name, value in overrides.items():
        if name not in tokens.ALL:
            failures.append(Failure("unknown-token", name, str(value), "is not a documented Claude Code colour token"))
    for name in sorted(tokens.ALL - set(overrides)):
        failures.append(Failure("missing-token", name, "-", "has no colour, so it would fall through to the base preset"))
    for name in tokens.TEXT:
        if usable("claude", overrides, name):
            _contrast(failures, "text-contrast", f"claude.{name}", overrides[name], background, TEXT_MIN, overrides[name])
    for name in tokens.SECONDARY:
        if usable("claude", overrides, name):
            _contrast(failures, "secondary-contrast", f"claude.{name}", overrides[name], background, SECONDARY_MIN,
                      overrides[name])
    for name in tokens.BACKGROUNDS:
        if usable("claude", overrides, name):
            _contrast(failures, "background-contrast", f"claude.{name}", foreground, overrides[name], TEXT_MIN,
                      overrides[name])
    if usable("claude", overrides, tokens.ON_ACCENT):
        inverse = overrides[tokens.ON_ACCENT]
        for fill in tokens.ACCENT_FILLS:
            if usable("claude", overrides, fill):
                _contrast(failures, "on-accent-contrast", f"claude.{tokens.ON_ACCENT} on {fill}", inverse,
                          overrides[fill], TEXT_MIN, inverse)

    for key in WT_COLOUR_KEYS:
        if key not in scheme:
            failures.append(Failure("missing-token", f"wt.{key}", "-", "is missing from the Windows Terminal scheme"))
    if scheme.get("name") != palette.THEME_NAME:
        failures.append(Failure("consistency", "wt.name", str(scheme.get("name")), f"must be {palette.THEME_NAME}"))
    for key, expected in (("background", background), ("foreground", foreground)):
        if key in scheme and scheme[key] != expected:
            failures.append(Failure("consistency", f"wt.{key}", str(scheme[key]), f"must equal the palette {key} {expected}"))
    for key, value in scheme.items():
        if key != "name" and isinstance(value, str) and is_pastel(value):
            failures.append(Failure("pastel", f"wt.{key}", value, "is a colour of the old pastel theme"))
    for key in WT_TEXT:
        if usable("wt", scheme, key):
            _contrast(failures, "text-contrast", f"wt.{key}", scheme[key], background, TEXT_MIN, scheme[key])
    for key in WT_SECONDARY:
        if usable("wt", scheme, key):
            _contrast(failures, "secondary-contrast", f"wt.{key}", scheme[key], background, SECONDARY_MIN, scheme[key])
    for key in WT_BACKGROUNDS:
        if usable("wt", scheme, key):
            _contrast(failures, "background-contrast", f"wt.{key}", foreground, scheme[key], TEXT_MIN, scheme[key])

    for key, value in statusline.items():
        if key not in STATUSLINE_EXEMPT and usable("statusline", statusline, key):
            _contrast(failures, "text-contrast", f"statusline.{key}", value, background, TEXT_MIN, value)
    return failures


def _validate_verbs(verbs: Any, failures: list[Failure]) -> None:
    if not isinstance(verbs, list) or not all(isinstance(v, str) for v in verbs):
        failures.append(Failure("content", "spinner.verbs", "-", "must be a list of strings"))
        return
    low, high = VERBS_RANGE
    if not low <= len(verbs) <= high:
        failures.append(Failure("content", "spinner.verbs", str(len(verbs)), f"must have between {low} and {high} verbs"))
    seen: set[str] = set()
    for verb in verbs:
        if verb in seen:
            failures.append(Failure("content", "spinner.verbs", verb, "is repeated"))
        seen.add(verb)
        if len(verb) > VERB_MAX or not VERB.match(verb):
            failures.append(Failure("content", "spinner.verbs", verb,
                                    f"must be an -ing word or phrase of at most {VERB_MAX} characters, without an ellipsis"))
    for verb in REQUIRED_VERBS:
        if verb not in seen:
            failures.append(Failure("content", "spinner.verbs", verb, "is required by the spec"))


def _validate_tips(tips: Any, failures: list[Failure]) -> None:
    if not isinstance(tips, list):
        failures.append(Failure("content", "spinner.tips", "-", "must be a list"))
        return
    low, high = TIPS_RANGE
    if not low <= len(tips) <= high:
        failures.append(Failure("content", "spinner.tips", str(len(tips)), f"must have between {low} and {high} tips"))
    texts: dict[str, str] = {}
    for tip in tips:
        if not (isinstance(tip, dict) and isinstance(tip.get("id"), str) and isinstance(tip.get("text"), str)):
            failures.append(Failure("content", "spinner.tips", repr(tip)[:60], "must be an object with string id and text"))
            continue
        tip_id, text = tip["id"], tip["text"]
        item = f"spinner.tips.{tip_id}"
        if tip_id in texts:
            failures.append(Failure("content", item, tip_id, "is repeated"))
        texts.setdefault(tip_id, text)
        if len(tip_id) > TIP_ID_MAX or not TIP_ID.match(tip_id):
            failures.append(Failure("content", item, tip_id, f"id must be kebab-case, at most {TIP_ID_MAX} characters"))
        if not text.strip() or len(text) > TIP_MAX or "\n" in text or "\r" in text:
            failures.append(Failure("content", item, text[:40], f"text must be one line of 1-{TIP_MAX} characters"))
    for tip_id, text in REQUIRED_TIPS.items():
        if texts.get(tip_id) != text:
            failures.append(Failure("content", f"spinner.tips.{tip_id}", text[:40], "is required by the spec with this exact text"))


def _validate_output_style(text: str, failures: list[Failure]) -> None:
    parsed = content.split_frontmatter(text)
    if parsed is None:
        failures.append(Failure("content", "output-style", "-", "needs a --- frontmatter block"))
        return
    fields, body = parsed
    if fields.get("name") != "WitchyNibbles":
        failures.append(Failure("content", "output-style.name", str(fields.get("name")), "must be WitchyNibbles"))
    if fields.get("keep-coding-instructions") != "true":
        failures.append(Failure("content", "output-style.keep-coding-instructions",
                                str(fields.get("keep-coding-instructions")), "must be true"))
    if not fields.get("description"):
        failures.append(Failure("content", "output-style.description", "-", "must not be empty"))
    if not body.strip():
        failures.append(Failure("content", "output-style", "-", "body must not be empty"))


def _short_text(failures: list[Failure], item: str, value: Any, limit: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\n" in value:
        failures.append(Failure("content", item, str(value)[:40], f"must be one line of 1-{limit} characters"))


def validate_ritual(data: Mapping[str, Any]) -> list[Failure]:
    """content/ritual.json: the salutation name, 8 sabbat blessings, 3 lunar lines and 22 tarot cards."""
    failures: list[Failure] = []
    _short_text(failures, "ritual.name", data.get("name"), NAME_MAX)
    sabbats = data.get("sabbats") if isinstance(data.get("sabbats"), dict) else {}
    for name in SABBATS:
        _short_text(failures, f"ritual.sabbats.{name}", sabbats.get(name), LINE_MAX)
    lunar = data.get("lunar") if isinstance(data.get("lunar"), dict) else {}
    for name in LUNAR_LINES:
        _short_text(failures, f"ritual.lunar.{name}", lunar.get(name), LINE_MAX)
    cards = data.get("tarot")
    if not isinstance(cards, list) or not all(isinstance(card, dict) for card in cards):
        return failures + [Failure("content", "ritual.tarot", "-", "must be a list of objects")]
    if len(cards) != TAROT_CARDS:
        failures.append(Failure("content", "ritual.tarot", str(len(cards)), f"must hold exactly {TAROT_CARDS} cards"))
    numbers = [card.get("number") for card in cards]
    if sorted(n for n in numbers if isinstance(n, int)) != list(range(TAROT_CARDS)):
        failures.append(Failure("content", "ritual.tarot", str(numbers)[:40], "numbers must be 0-21, each once"))
    names = [card.get("name") for card in cards]
    if len(set(map(str, names))) != len(names):
        failures.append(Failure("content", "ritual.tarot", "-", "card names must be unique"))
    for card in cards:
        item = f"ritual.tarot.{card.get('number')}"
        _short_text(failures, f"{item}.name", card.get("name"), MEANING_MAX)
        for side in ("upright", "reversed"):
            _short_text(failures, f"{item}.{side}", card.get(side), MEANING_MAX)
    return failures


def validate_ritual_palette(colours: Mapping[str, Any], background: str = palette.BACKGROUND) -> list[Failure]:
    """Every greeting colour is #RRGGBB; text and the sabbat accents reach 4.5:1 (spec 11.2)."""
    failures: list[Failure] = []
    for key in palette.RITUAL:
        if key not in colours:
            failures.append(Failure("missing-token", f"ritual.{key}", "-", "is missing from the ritual palette"))
    for key, value in colours.items():
        if not isinstance(value, str) or not HEX.match(value):
            failures.append(Failure("format", f"ritual.{key}", str(value), "is not #RRGGBB in uppercase"))
        elif key not in palette.RITUAL_DECORATIVE:
            _contrast(failures, "text-contrast", f"ritual.{key}", value, background, TEXT_MIN, value)
    return failures


# Tide names these with the word "color", but they hold the glyph drawn between two segments (spec 6.2).
TIDE_SEPARATOR_GLYPHS = frozenset({"tide_left_prompt_separator_diff_color", "tide_left_prompt_separator_same_color",
                                   "tide_right_prompt_separator_diff_color", "tide_right_prompt_separator_same_color"})


def is_tide_colour(key: str) -> bool:
    """Tide names a colour variable with the word ``color``: ``tide_pwd_bg_color``, ``tide_git_color_branch``."""
    return "color" in key.split("_") and key not in TIDE_SEPARATOR_GLYPHS


def is_emoji(char: str) -> bool:
    """A pictograph a terminal draws as an emoji: a symbol that is East Asian Wide, or one past U+1F000 (🕯 is
    narrow in Unicode). Text symbols such as ❯, ✦ or Nerd Font glyphs are not emoji."""
    return unicodedata.category(char) == "So" and (unicodedata.east_asian_width(char) in ("W", "F")
                                                    or ord(char) >= 0x1F000)


def is_pastel(value: str) -> bool:
    """``value`` is a colour of the old pastel theme (with or without "#"), or holds one of its icons."""
    return value.lstrip("#").upper() in PASTEL or any(char in PASTEL for char in value)


def _prompt_glyph(failures: list[Failure], key: str, text: str) -> None:
    if any(char in PROMPT_GLYPH_MARKS for char in text):
        failures.append(Failure("prompt-glyph", f"tide.{key}", text,
                                "holds a variation selector, a joiner or a skin tone; use one plain code point"))
    elif sum(map(is_emoji, text)) > 1:
        failures.append(Failure("prompt-glyph", f"tide.{key}", text, "holds more than one emoji"))


def validate_glyphs(glyphs: Mapping[str, str]) -> list[Failure]:
    """Spec 11.5: the greeting measures every emoji of the glyph table two cells wide."""
    failures: list[Failure] = []
    for key, glyph in glyphs.items():
        narrow = [char for char in glyph if is_emoji(char) and char not in layout.WIDE
                  and unicodedata.east_asian_width(char) not in ("W", "F")]
        if narrow:
            failures.append(Failure("width", f"glyphs.{key}", glyph,
                                    "is an emoji the greeting would measure one cell wide; add it to ritual/layout.WIDE"))
    return failures


def validate_sky(sky: Mapping[str, Any]) -> list[Failure]:
    """Every colour the sky renderer reads is present and #RRGGBB. The sky is decorative: no contrast rule."""
    failures: list[Failure] = []
    for key in sky_render.COLOURS:
        if key not in sky:
            failures.append(Failure("missing-token", f"sky.{key}", "-", "is missing from the sky colours"))
    for key, value in sky.items():
        if not isinstance(value, str) or not HEX.match(value):
            failures.append(Failure("format", f"sky.{key}", str(value), "is not #RRGGBB in uppercase"))
    return failures


def validate_tide(overrides: Mapping[str, Any], background: str = palette.BACKGROUND,
                  defaults: Mapping[str, Any] | None = None) -> list[Failure]:
    """A variant's Tide overrides, and the whole prompt they make with Tide's ``defaults`` (spec 11).

    Every override of palette.TIDE is present and names a Tide 6.1.1 variable or one of witchy's own; in the
    merged prompt, colours are RRGGBB without "#", segment text reads on its background, each icon is one plain
    emoji at most, and no value comes from the old pastel theme.
    """
    if defaults is None:
        defaults = content.load_tide_defaults()
    failures: list[Failure] = []
    for key in palette.TIDE:
        if key not in overrides:
            failures.append(Failure("missing-token", f"tide.{key}", "-", "is missing from the Tide variables"))
    for key, value in overrides.items():
        if key not in defaults and key not in palette.TIDE_OWN:
            failures.append(Failure("unknown-variable", f"tide.{key}", str(value), "is not a Tide 6.1.1 variable"))
    tide = {**defaults, **overrides}
    bad = set()
    for key, value in tide.items():
        if isinstance(value, str):
            texts = [value]
        elif isinstance(value, tuple):
            texts = list(value)
        else:
            texts = []
        if "icon" in key.split("_") or key == "tide_time_format":
            _prompt_glyph(failures, key, "".join(text for text in texts if isinstance(text, str)))
        if any(isinstance(text, str) and is_pastel(text) for text in texts):
            failures.append(Failure("pastel", f"tide.{key}", str(value), "comes from the old pastel theme"))
        colour = is_tide_colour(key)
        if colour and not (isinstance(value, str) and TIDE_HEX.match(value)):
            failures.append(Failure("format", f"tide.{key}", str(value), "is not RRGGBB in uppercase, without #"))
            bad.add(key)
        elif not colour and not (isinstance(value, str) or
                                 (isinstance(value, tuple) and all(isinstance(v, str) for v in value))):
            failures.append(Failure("format", f"tide.{key}", str(value), "must be a string or a tuple of strings"))
    for pairs, rule, minimum in ((TIDE_TEXT_PAIRS + TIDE_ITEM_PAIRS, "text-contrast", TEXT_MIN),
                                 (TIDE_SECONDARY_PAIRS, "secondary-contrast", SECONDARY_MIN)):
        for text, on in pairs:
            if text not in tide or text in bad or (on is not None and (on not in tide or on in bad)):
                continue
            behind = background if on is None else "#" + tide[on]
            _contrast(failures, rule, f"tide.{text} on {on or 'background'}", "#" + tide[text], behind, minimum,
                      tide[text])
    return failures


def validate_eza(eza: Mapping[str, Any], background: str = palette.BACKGROUND) -> list[Failure]:
    """Every eza colour is present, #RRGGBB, and reads at 4.5:1 on the background (spec 11.4)."""
    failures: list[Failure] = []
    for key in palette.EZA:
        if key not in eza:
            failures.append(Failure("missing-token", f"eza.{key}", "-", "is missing from the eza colours"))
    for key, value in eza.items():
        if not isinstance(value, str) or not HEX.match(value):
            failures.append(Failure("format", f"eza.{key}", str(value), "is not #RRGGBB in uppercase"))
        else:
            _contrast(failures, "text-contrast", f"eza.{key}", value, background, TEXT_MIN, value)
    return failures


def validate_content(spinner: Mapping[str, Any], output_style: str) -> list[Failure]:
    failures: list[Failure] = []
    _validate_verbs(spinner.get("verbs"), failures)
    _validate_tips(spinner.get("tips"), failures)
    _validate_output_style(output_style, failures)
    return failures


def validate_all(content_dir: Path = content.CONTENT_DIR) -> list[Failure]:
    failures: list[Failure] = []
    try:
        defaults = content.load_tide_defaults(content_dir)
    except (OSError, ValueError) as exc:
        defaults = None
        failures.append(Failure("content", str(content_dir / content.TIDE_DEFAULTS), "-", f"cannot be read: {exc}"))
    for variant in palette.VARIANTS.values():
        failures += validate_palette(variant.claude_overrides, variant.wt_scheme, variant.statusline,
                                     variant.background, variant.foreground)
        failures += validate_sky(variant.sky)
        failures += validate_ritual_palette(variant.ritual, variant.background)
        if defaults is not None:
            failures += validate_tide(variant.tide, variant.background, defaults)
        failures += validate_eza(variant.eza, variant.background)
    failures += validate_glyphs(palette.GLYPHS)
    try:
        spinner = content.load_spinner(content_dir)
        style = content.read_output_style(content_dir)
        ritual = content.load_ritual(content_dir)
    except (OSError, ValueError) as exc:
        return failures + [Failure("content", str(content_dir), "-", f"cannot be read: {exc}")]
    return failures + validate_content(spinner, style) + validate_ritual(ritual)
