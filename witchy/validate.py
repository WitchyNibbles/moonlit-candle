"""The rules Moonlit Candle must pass before build or install touch anything."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from . import content, palette, tokens
from .contrast import contrast_ratio

HEX = re.compile(r"^#[0-9A-F]{6}$")
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


def validate_content(spinner: Mapping[str, Any], output_style: str) -> list[Failure]:
    failures: list[Failure] = []
    _validate_verbs(spinner.get("verbs"), failures)
    _validate_tips(spinner.get("tips"), failures)
    _validate_output_style(output_style, failures)
    return failures


def validate_all(content_dir: Path = content.CONTENT_DIR) -> list[Failure]:
    failures: list[Failure] = []
    for variant in palette.VARIANTS.values():
        failures += validate_palette(variant.claude_overrides, variant.wt_scheme, variant.statusline,
                                     variant.background, variant.foreground)
        failures += [Failure("format", f"sky.{key}", str(value), "is not #RRGGBB in uppercase")
                     for key, value in variant.sky.items() if not isinstance(value, str) or not HEX.match(value)]
        if variant.ritual:
            failures += validate_ritual_palette(variant.ritual, variant.background)
    try:
        spinner = content.load_spinner(content_dir)
        style = content.read_output_style(content_dir)
        ritual = content.load_ritual(content_dir)
    except (OSError, ValueError) as exc:
        return failures + [Failure("content", str(content_dir), "-", f"cannot be read: {exc}")]
    return failures + validate_content(spinner, style) + validate_ritual(ritual)
