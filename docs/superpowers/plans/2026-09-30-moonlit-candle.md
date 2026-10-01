# Moonlit Candle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a stdlib-only Python tool that generates, validates, installs and uninstalls the "Moonlit Candle" witchy theme for Claude Code: color theme, Windows Terminal scheme, spinner verbs/tips, output style and a moon-phase status line.

**Architecture:** One palette module (`witchy/palette.py`) is the single source of every color. `build.py` renders all artifacts from it plus hand-written `content/`. `validate.py` enforces WCAG contrast and token/content rules. `install.py` plans every file change first (so `--dry-run` can diff), backs up before writing, writes atomically, and records previous values in `~/.claude/witchy/state.json` so `uninstall` can give them back (byte-exact when nothing else touched the file).

**Tech Stack:** Python ≥ 3.10, standard library only, `unittest`, git.

**Spec:** `docs/superpowers/specs/2026-09-30-moonlit-candle-design.md` (read it before starting any task; it is the authority on colors, formats and behavior).

## Global Constraints

- Project root: `/home/mmarenas/proyectos/witchy-claude-theme`. The Bash tool resets the working directory after every call, so **every command must start with `cd /home/mmarenas/proyectos/witchy-claude-theme && ...`**.
- **Never touch `/home/gii/apps/lexer/GII_claude_2`** (an unrelated work repo with uncommitted changes), the real `~/.claude/`, or the real Windows Terminal `settings.json`. Tests use `tempfile` directories only, and never call the real `cmd.exe` (inject a fake `run`).
- Python ≥ 3.10, standard library only, no third-party packages. Every module starts with `from __future__ import annotations`.
- Test command (run with both interpreters before each commit):
  `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest discover -s tests -t . -v && /usr/bin/python3.10 -m unittest discover -s tests -t .`
- Colors are `#RRGGBB`, uppercase hex.
- Names: theme slug `moonlit-candle`, display name `Moonlit Candle`, base preset `dark`; Windows Terminal scheme `Moonlit Candle`; output style `WitchyNibbles`; tips label `Grimoire`.
- Code, comments, docstrings, commit messages, installer output and README are plain and neutral: **no witchy voice** outside `content/`. Code comments are in English, sparse, and explain *why* (match the docstring style of the code shown in this plan).
- Commit after each task with a Conventional Commit subject (`feat:`, `test:`, `docs:`) and this trailer as the last line:
  `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`

## Review Focus

1. **Claude Code launches the status line under a non-UTF-8 locale (`LANG=C`)**: it must still print the emoji line and exit 0, not crash on encoding. Pinned by `test_runs_as_a_script_under_the_c_locale` (Task 3).
2. **Claude Code rewrites `~/.claude/settings.json` between install and uninstall** (for example `/config` or `/model` adds a key): uninstall must restore only witchy's keys and keep the new key, not roll back to the byte backup. Pinned by `test_uninstall_keeps_keys_claude_code_added_later` (Task 7).
3. **Install run from a terminal that is not Windows Terminal (VS Code: no `WT_PROFILE_ID`) or with a stale `WT_PROFILE_ID`**: fall back to the WSL profile named after `WSL_DISTRO_NAME`. If none matches, skip the terminal with a warning and still install the Claude parts. Pinned by `test_stale_profile_id_falls_back_to_distro` (Task 6), plus `test_vscode_terminal_falls_back_to_distro_name` and `test_no_windows_terminal_profile_skips_terminal` (Task 7).
4. **Windows Terminal's own formatting**: 4-space indent, non-ASCII profile names stored as `í` escapes. Rewrites keep the indent and the escaping, and install followed by uninstall is byte-identical. Pinned by `test_dumps_like_keeps_ascii_escapes_and_indent` (Task 5) and the `Símbolo del sistema` fixture in `test_install_then_uninstall_restores_bytes` (Task 7).
5. **The user edits the installed theme with `/theme` → Ctrl+E before uninstalling** (it writes to `~/.claude/themes/moonlit-candle.json`): uninstall must back up the edited file before deleting it. Pinned by `test_edited_theme_is_backed_up_before_uninstall` (Task 7).

---

## File Structure

```
witchy/__init__.py          package marker (docstring only)
witchy/contrast.py          WCAG luminance + contrast ratio
witchy/tokens.py            documented Claude Code color tokens, grouped by validation rule
witchy/palette.py           every color: Claude overrides, Windows Terminal scheme, status line palette
witchy/content.py           load content/spinner.json and content/output-style.md; parse frontmatter
witchy/validate.py          palette + content rules → list[Failure]
witchy/statusline.py        standalone status line script (copied alone to ~/.claude/witchy/)
witchy/build.py             render dist/ artifacts; rewrite statusline PALETTE block
witchy/jsonio.py            strict JSON read, style-preserving dump, atomic write, dated backup
witchy/records.py           snapshot / put_back of "previous value" records
witchy/claude_settings.py   the five ~/.claude/settings.json keys: desired, apply, restore
witchy/wt.py                Windows Terminal: locate settings, find profile, apply/restore scheme
witchy/install.py           install / uninstall orchestration, dry-run diffs, state.json
witchy/__main__.py          CLI: validate | build | install | uninstall
content/spinner.json        verbs + tips (English)
content/output-style.md     WitchyNibbles output style
tests/__init__.py           package marker (empty)
tests/test_*.py             one test module per witchy module
README.md                   usage (Spanish, neutral)
```

---

### Task 1: Palette core (contrast, tokens, palette)

**Files:**
- Create: `witchy/__init__.py`, `witchy/contrast.py`, `witchy/tokens.py`, `witchy/palette.py`
- Create: `tests/__init__.py` (empty), `tests/test_contrast.py`, `tests/test_palette.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `witchy.contrast.luminance(hex_colour: str) -> float`, `witchy.contrast.contrast_ratio(a: str, b: str) -> float`
  - `witchy.tokens`: `TEXT: tuple[str, ...]`, `SECONDARY: tuple[str, ...]`, `BACKGROUNDS: tuple[str, ...]`, `ON_ACCENT: str` (= `"inverseText"`), `ACCENT_FILLS: tuple[str, ...]`, `EXEMPT: dict[str, str]` (token → reason), `ALL: frozenset[str]` (62 tokens), `SUBAGENT_COLOURS`, `RAINBOW_COLOURS`
  - `witchy.palette`: `THEME_NAME = "Moonlit Candle"`, `THEME_SLUG = "moonlit-candle"`, `BACKGROUND = "#0D0916"`, `FOREGROUND = "#F3EAF7"`, `CLAUDE_OVERRIDES: dict[str, str]` (62 entries), `WT_SCHEME: dict[str, str]` (21 entries incl. `"name"`), `STATUSLINE: dict[str, str]` (12 entries, fixed order)

- [ ] **Step 1: Write the failing tests**

`tests/__init__.py`: empty file.

`tests/test_contrast.py`:

```python
import unittest

from witchy.contrast import contrast_ratio, luminance


class ContrastTest(unittest.TestCase):
    def test_black_and_white_are_21_to_1(self):
        self.assertAlmostEqual(contrast_ratio("#FFFFFF", "#000000"), 21.0, places=6)

    def test_order_does_not_matter(self):
        self.assertAlmostEqual(contrast_ratio("#000000", "#FFFFFF"), 21.0, places=6)

    def test_known_pair_from_the_palette(self):
        self.assertAlmostEqual(contrast_ratio("#6E5A80", "#0D0916"), 3.22, delta=0.01)

    def test_luminance_extremes(self):
        self.assertEqual(luminance("#000000"), 0.0)
        self.assertAlmostEqual(luminance("#FFFFFF"), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
```

`tests/test_palette.py`:

```python
import unittest

from witchy import palette, tokens


class TokensTest(unittest.TestCase):
    def test_rule_groups_do_not_overlap(self):
        groups = [tokens.TEXT, tokens.SECONDARY, tokens.BACKGROUNDS, (tokens.ON_ACCENT,), tuple(tokens.EXEMPT)]
        self.assertEqual(sum(len(group) for group in groups), len(tokens.ALL))

    def test_documented_token_count(self):
        self.assertEqual(len(tokens.ALL), 62)

    def test_accent_fills_are_tokens(self):
        self.assertTrue(set(tokens.ACCENT_FILLS) <= tokens.ALL)


class PaletteTest(unittest.TestCase):
    def test_every_token_has_a_colour(self):
        self.assertEqual(set(palette.CLAUDE_OVERRIDES), set(tokens.ALL))

    def test_spec_anchor_colours(self):
        overrides = palette.CLAUDE_OVERRIDES
        self.assertEqual(overrides["claude"], "#FFD477")
        self.assertEqual(overrides["permission"], "#FF67B7")
        self.assertEqual(overrides["planMode"], "#B99AFF")
        self.assertEqual(overrides["success"], "#74E8B8")
        self.assertEqual(overrides["promptBorder"], "#6E5A80")
        self.assertEqual(overrides["text"], "#F3EAF7")
        self.assertEqual(overrides["inverseText"], "#0D0916")

    def test_windows_terminal_scheme_matches_spec(self):
        scheme = palette.WT_SCHEME
        self.assertEqual(len(scheme), 21)
        self.assertEqual(scheme["name"], "Moonlit Candle")
        self.assertEqual(scheme["background"], "#0D0916")
        self.assertEqual(scheme["cursorColor"], "#FF67B7")
        self.assertEqual(scheme["black"], "#1D1230")
        self.assertEqual(scheme["brightBlack"], "#6E5A80")
        self.assertEqual(scheme["brightWhite"], "#FFFFFF")

    def test_statusline_colour_names_and_order(self):
        self.assertEqual(
            list(palette.STATUSLINE),
            ["model", "muted", "divider", "repo", "branch", "dirty",
             "context_low", "context_mid", "context_high", "left_high", "left_mid", "left_low"],
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest discover -s tests -t . -v`
Expected: errors `ModuleNotFoundError: No module named 'witchy'`.

- [ ] **Step 3: Write the implementation**

`witchy/__init__.py`:

```python
"""Moonlit Candle: a witchy theme for Claude Code, built from one palette."""
```

`witchy/contrast.py`:

```python
"""WCAG 2.x relative luminance and contrast ratio for #RRGGBB colours."""
from __future__ import annotations


def luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)
```

`witchy/tokens.py`:

```python
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
```

`witchy/palette.py`:

```python
"""Moonlit Candle: every colour the theme ships, defined once.

The night comes from Spellbound Moonlit, the candle gold from devgod/archon.
build.py turns this into the Claude Code theme, the Windows Terminal scheme
and the status line palette; validate.py holds all of it to the contrast rules.
"""
from __future__ import annotations

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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest discover -s tests -t . -v && /usr/bin/python3.10 -m unittest discover -s tests -t .`
Expected: all tests PASS on both interpreters.

- [ ] **Step 5: Commit**

```bash
cd /home/mmarenas/proyectos/witchy-claude-theme && git add witchy tests && git commit -m "feat: Moonlit Candle palette, token groups and contrast math

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Content and validation

**Files:**
- Create: `content/spinner.json`, `content/output-style.md`, `witchy/content.py`, `witchy/validate.py`
- Test: `tests/test_validate.py`

**Interfaces:**
- Consumes: `witchy.palette.*`, `witchy.tokens.*`, `witchy.contrast.contrast_ratio` (Task 1).
- Produces:
  - `witchy.content.CONTENT_DIR: Path`, `load_spinner(content_dir: Path = CONTENT_DIR) -> dict[str, Any]` (raises `OSError`/`ValueError`), `read_output_style(content_dir: Path = CONTENT_DIR) -> str`, `split_frontmatter(text: str) -> tuple[dict[str, str], str] | None`
  - `witchy.validate.Failure(rule: str, item: str, value: str, detail: str)` (frozen dataclass; `str()` gives `"<rule>: <item> <value> <detail>"`)
  - `witchy.validate.validate_palette(overrides=..., scheme=..., statusline=..., background=..., foreground=...) -> list[Failure]`
  - `witchy.validate.validate_content(spinner: Mapping[str, Any], output_style: str) -> list[Failure]`
  - `witchy.validate.validate_all(content_dir: Path = content.CONTENT_DIR) -> list[Failure]`
  - Rule names: `format`, `unknown-token`, `missing-token`, `consistency`, `text-contrast`, `secondary-contrast`, `background-contrast`, `on-accent-contrast`, `content`

- [ ] **Step 1: Write the content files**

`content/spinner.json`:

```json
{
  "verbs": [
    "Brewing",
    "Conjuring",
    "Scrying",
    "Hexing",
    "Divining",
    "Transmuting",
    "Warding",
    "Exorcising",
    "Summoning",
    "Enchanting",
    "Incanting",
    "Stirring the cauldron",
    "Consulting the grimoire",
    "Reading the runes",
    "Lighting candles",
    "Scrying the query plan",
    "Bewitching",
    "Charming",
    "Channeling",
    "Invoking",
    "Distilling",
    "Foretelling",
    "Spellcasting",
    "Binding",
    "Casting circles",
    "Drawing sigils",
    "Steeping herbs",
    "Grinding mandrake",
    "Tending the familiar",
    "Whispering to the daemon",
    "Banishing bugs",
    "Unhexing the build",
    "Reading tea leaves",
    "Gathering moonlight",
    "Sweeping the cobwebs",
    "Carving runes",
    "Chanting",
    "Shuffling the tarot",
    "Charging crystals",
    "Consulting the stars"
  ],
  "tips": [
    {"id": "haunted-houses", "text": "Legacy systems are just haunted houses with uptime requirements."},
    {"id": "love-letters", "text": "Tests are love letters to your future self."},
    {"id": "ghost-in-query-plan", "text": "Measure before you optimise — the ghost is usually in the query plan."},
    {"id": "boring-code", "text": "Boring code is good code."},
    {"id": "remembers-everything", "text": "Be kind to your code — it remembers everything."},
    {"id": "keep-the-receipts", "text": "Keep the receipts."},
    {"id": "hold-the-thread", "text": "Hold the thread."},
    {"id": "through-the-fog", "text": "Exorcising legacy systems. Shipping code through the fog."},
    {"id": "migrations-are-rituals", "text": "Migrations are rituals: rehearse them, then perform them once."},
    {"id": "ward-your-inputs", "text": "Ward your inputs — validate at the boundary, trust inside it."},
    {"id": "name-the-demon", "text": "You cannot banish a bug you have not named. Reproduce it first."},
    {"id": "small-spells", "text": "Small spells compose; giant incantations backfire."},
    {"id": "candle-in-the-logs", "text": "A log line is a candle in the dark. Light the ones you will need at 3 a.m."},
    {"id": "grimoire-runbooks", "text": "A runbook is a grimoire someone will read in a hurry. Write it plainly."},
    {"id": "circle-before-prod", "text": "Never summon production without a circle drawn: backups, a plan, a way back."},
    {"id": "restless-tests", "text": "A flaky test is a restless spirit. Find out what it is trying to tell you."},
    {"id": "scry-explain", "text": "Before blaming the ORM, scry the EXPLAIN ANALYZE."},
    {"id": "global-curse", "text": "Global state is a curse that spreads to everything it touches."},
    {"id": "rollback-charm", "text": "Every deploy deserves a rollback charm."},
    {"id": "read-the-runes", "text": "Read the error message twice before casting anything new."}
  ]
}
```

`content/output-style.md` (exact text from spec §8.3):

```markdown
---
name: WitchyNibbles
description: A backend witch's voice in chat replies only — files, code, commits and docs stay plain
keep-coding-instructions: true
---

# WitchyNibbles voice

Speak to the user in the voice of a backend witch: someone who exorcises legacy systems, keeps a grimoire of runbooks, and ships code through the fog. Precision comes first; the voice is seasoning, never a substitute for facts.

## Where the voice applies

Only in the prose you write directly to the user in this conversation.

## Where the voice never applies

Write exactly as you would without this style in:

- files you create or edit — code, comments, docstrings, configs, tests, docs, READMEs, specs, plans
- commit messages, branch names, PR titles and descriptions, issue and review comments
- tool arguments, shell commands, and anything sent to an external service or another agent
- prompts you write for subagents

## Always neutral

Drop the voice entirely, for the whole message, when reporting:

- errors, failing tests, or broken builds
- security findings or warnings
- confirmations before destructive, irreversible, or outward-facing actions
- production incidents

## How the voice sounds

- Light, dry, and competent. Vocabulary such as conjure, summon, ward, hex, exorcise, grimoire, ritual, familiar, candle, fog, haunted, ghost — at most one or two touches per message, where they fit naturally.
- "Receipts" means verification evidence: the command you ran and what it showed. When you claim something works, show the receipts.
- Keep the user's language: if they write in Spanish, answer in Spanish with the same voice.
- Never let a metaphor hide what actually happened. If a sentence would be clearer plain, write it plain.
- No emoji beyond an occasional 🕯️.
```

- [ ] **Step 2: Write the failing tests**

`tests/test_validate.py`:

```python
import copy
import tempfile
import unittest
from pathlib import Path

from witchy import content, palette, validate


def pairs(failures):
    return {(f.rule, f.item) for f in failures}


def triples(failures):
    return {(f.rule, f.item, f.value) for f in failures}


class PaletteRulesTest(unittest.TestCase):
    def test_real_palette_passes(self):
        self.assertEqual(validate.validate_palette(), [])

    def test_low_contrast_text_fails(self):
        overrides = dict(palette.CLAUDE_OVERRIDES, claude="#3A2E47")
        self.assertIn(("text-contrast", "claude.claude"), pairs(validate.validate_palette(overrides=overrides)))

    def test_mockup_prompt_border_fails_the_secondary_rule(self):
        overrides = dict(palette.CLAUDE_OVERRIDES, promptBorder="#503762")
        self.assertIn(("secondary-contrast", "claude.promptBorder"), pairs(validate.validate_palette(overrides=overrides)))

    def test_background_too_light_for_text_fails(self):
        overrides = dict(palette.CLAUDE_OVERRIDES, diffAdded="#A0A0A0")
        self.assertIn(("background-contrast", "claude.diffAdded"), pairs(validate.validate_palette(overrides=overrides)))

    def test_inverse_text_must_read_on_accent_fills(self):
        overrides = dict(palette.CLAUDE_OVERRIDES, inverseText="#FFFFFF")
        self.assertIn(("on-accent-contrast", "claude.inverseText on claude"),
                      pairs(validate.validate_palette(overrides=overrides)))

    def test_exempt_tokens_are_not_contrast_checked(self):
        overrides = dict(palette.CLAUDE_OVERRIDES, rate_limit_empty="#0E0A17", claudeShimmer="#0E0A17")
        self.assertEqual(validate.validate_palette(overrides=overrides), [])

    def test_unknown_token_fails(self):
        overrides = dict(palette.CLAUDE_OVERRIDES, claudee="#FFD477")
        self.assertIn(("unknown-token", "claudee"), pairs(validate.validate_palette(overrides=overrides)))

    def test_missing_token_fails(self):
        overrides = dict(palette.CLAUDE_OVERRIDES)
        del overrides["merged"]
        self.assertIn(("missing-token", "merged"), pairs(validate.validate_palette(overrides=overrides)))

    def test_bad_format_fails(self):
        for bad in ("#ffd477", "gold", "#FFD47", None):
            overrides = dict(palette.CLAUDE_OVERRIDES, claude=bad)
            self.assertIn(("format", "claude.claude"), pairs(validate.validate_palette(overrides=overrides)), bad)

    def test_windows_terminal_text_and_consistency(self):
        scheme = dict(palette.WT_SCHEME, red="#301020", background="#000000")
        found = pairs(validate.validate_palette(scheme=scheme))
        self.assertIn(("text-contrast", "wt.red"), found)
        self.assertIn(("consistency", "wt.background"), found)

    def test_windows_terminal_missing_colour_fails(self):
        scheme = dict(palette.WT_SCHEME)
        del scheme["brightCyan"]
        self.assertIn(("missing-token", "wt.brightCyan"), pairs(validate.validate_palette(scheme=scheme)))

    def test_windows_terminal_black_is_exempt(self):
        scheme = dict(palette.WT_SCHEME, black="#0D0916")
        self.assertEqual(validate.validate_palette(scheme=scheme), [])

    def test_statusline_divider_is_exempt_but_text_is_not(self):
        self.assertEqual(validate.validate_palette(statusline=dict(palette.STATUSLINE, divider="#0E0A17")), [])
        found = pairs(validate.validate_palette(statusline=dict(palette.STATUSLINE, repo="#2A1F35")))
        self.assertIn(("text-contrast", "statusline.repo"), found)

    def test_failure_prints_rule_item_value_detail(self):
        failure = validate.Failure("text-contrast", "claude.claude", "#3A2E47", "1.60:1 < 4.5:1")
        self.assertEqual(str(failure), "text-contrast: claude.claude #3A2E47 1.60:1 < 4.5:1")


class ContentRulesTest(unittest.TestCase):
    def setUp(self):
        self.spinner = content.load_spinner()
        self.style = content.read_output_style()

    def check(self, spinner=None, style=None):
        return validate.validate_content(spinner if spinner is not None else self.spinner,
                                         style if style is not None else self.style)

    def test_real_content_passes(self):
        self.assertEqual(self.check(), [])

    def test_verb_count_bounds(self):
        few = dict(self.spinner, verbs=self.spinner["verbs"][:35])
        self.assertIn(("content", "spinner.verbs", "35"), triples(self.check(spinner=few)))
        many = dict(self.spinner, verbs=self.spinner["verbs"] + [f"Brewing batch {c}" for c in "abcdefghi"])
        self.assertIn(("content", "spinner.verbs", "49"), triples(self.check(spinner=many)))

    def test_bad_verbs_fail(self):
        for verb in ("Hexing things…", "Hexing...", "Consulting the ancient grimoire", "brewing", "Brewed"):
            spinner = dict(self.spinner, verbs=self.spinner["verbs"][:-1] + [verb])
            self.assertIn(("content", "spinner.verbs", verb), triples(self.check(spinner=spinner)), verb)

    def test_duplicate_verb_fails(self):
        spinner = dict(self.spinner, verbs=self.spinner["verbs"][:-1] + ["Brewing"])
        self.assertIn(("content", "spinner.verbs", "Brewing"), triples(self.check(spinner=spinner)))

    def test_missing_required_verb_fails(self):
        verbs = [v for v in self.spinner["verbs"] if v != "Scrying the query plan"]
        spinner = dict(self.spinner, verbs=verbs)
        self.assertIn(("content", "spinner.verbs", "Scrying the query plan"), triples(self.check(spinner=spinner)))

    def test_tip_rules(self):
        tips = copy.deepcopy(self.spinner["tips"])
        tips = [t for t in tips if t["id"] != "keep-the-receipts"]
        tips.append({"id": "Bad ID", "text": "fine"})
        tips.append({"id": "too-long", "text": "x" * 121})
        tips.append({"id": "two-lines", "text": "one\ntwo"})
        tips.append({"id": "boring-code", "text": "Boring code is good code."})
        found = pairs(self.check(spinner=dict(self.spinner, tips=tips)))
        for item in ("spinner.tips.keep-the-receipts", "spinner.tips.Bad ID", "spinner.tips.too-long",
                     "spinner.tips.two-lines", "spinner.tips.boring-code"):
            self.assertIn(("content", item), found, item)

    def test_required_tip_text_must_match(self):
        tips = [dict(t, text="Keep receipts.") if t["id"] == "keep-the-receipts" else t for t in self.spinner["tips"]]
        self.assertIn(("content", "spinner.tips.keep-the-receipts"), pairs(self.check(spinner=dict(self.spinner, tips=tips))))

    def test_tip_count_bounds(self):
        few = dict(self.spinner, tips=self.spinner["tips"][:17])
        self.assertIn(("content", "spinner.tips", "17"), triples(self.check(spinner=few)))

    def test_output_style_frontmatter(self):
        no_keep = self.style.replace("keep-coding-instructions: true\n", "")
        self.assertIn(("content", "output-style.keep-coding-instructions"), pairs(self.check(style=no_keep)))
        renamed = self.style.replace("name: WitchyNibbles", "name: Witchy")
        self.assertIn(("content", "output-style.name"), pairs(self.check(style=renamed)))
        self.assertIn(("content", "output-style"), pairs(self.check(style="# no frontmatter\n")))

    def test_split_frontmatter(self):
        fields, body = content.split_frontmatter("---\nname: X\nkeep-coding-instructions: true\n---\nBody\n")
        self.assertEqual(fields, {"name": "X", "keep-coding-instructions": "true"})
        self.assertEqual(body, "Body\n")
        self.assertIsNone(content.split_frontmatter("no frontmatter"))


class ValidateAllTest(unittest.TestCase):
    def test_repository_passes(self):
        self.assertEqual(validate.validate_all(), [])

    def test_unreadable_content_is_a_failure(self):
        with tempfile.TemporaryDirectory() as empty:
            failures = validate.validate_all(Path(empty))
        self.assertEqual({f.rule for f in failures}, {"content"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest tests.test_validate -v`
Expected: `ImportError: cannot import name 'content' from 'witchy'` (or `validate`).

- [ ] **Step 4: Write the implementation**

`witchy/content.py`:

```python
"""Hand-written content: spinner verbs and tips, and the output style."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"
SPINNER = "spinner.json"
OUTPUT_STYLE = "output-style.md"


def load_spinner(content_dir: Path = CONTENT_DIR) -> dict[str, Any]:
    data = json.loads((content_dir / SPINNER).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{SPINNER} must hold a JSON object")
    return data


def read_output_style(content_dir: Path = CONTENT_DIR) -> str:
    return (content_dir / OUTPUT_STYLE).read_text(encoding="utf-8")


def split_frontmatter(text: str) -> tuple[dict[str, str], str] | None:
    """Split the flat ``key: value`` frontmatter that output styles use from the body."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 3)
    if end == -1:
        return None
    fields = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            return None
        fields[key.strip()] = value.strip()
    return fields, text[end + 5:]
```

`witchy/validate.py`:

```python
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


def validate_content(spinner: Mapping[str, Any], output_style: str) -> list[Failure]:
    failures: list[Failure] = []
    _validate_verbs(spinner.get("verbs"), failures)
    _validate_tips(spinner.get("tips"), failures)
    _validate_output_style(output_style, failures)
    return failures


def validate_all(content_dir: Path = content.CONTENT_DIR) -> list[Failure]:
    failures = validate_palette()
    try:
        spinner = content.load_spinner(content_dir)
        style = content.read_output_style(content_dir)
    except (OSError, ValueError) as exc:
        return failures + [Failure("content", str(content_dir), "-", f"cannot be read: {exc}")]
    return failures + validate_content(spinner, style)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest discover -s tests -t . -v && /usr/bin/python3.10 -m unittest discover -s tests -t .`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/mmarenas/proyectos/witchy-claude-theme && git add content witchy tests && git commit -m "feat: spinner content, output style and validation rules

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Status line

**Files:**
- Create: `witchy/statusline.py`
- Test: `tests/test_statusline.py`

**Interfaces:**
- Consumes: nothing from the package at runtime. **It must not import `witchy`**: it is copied alone to `~/.claude/witchy/`. Its `PALETTE` block must be byte-identical to what `build.palette_block(palette.STATUSLINE)` produces in Task 4, so copy the block below exactly.
- Produces: `witchy.statusline.PALETTE: dict[str, str]`, `moon(used: float | None) -> str`, `render(payload: Any) -> str`, `main(stdin: TextIO | None = None, stdout: TextIO | None = None) -> int`; the text between the `# BEGIN PALETTE\n` and `# END PALETTE\n` markers.

- [ ] **Step 1: Write the failing tests**

`tests/test_statusline.py`:

```python
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from witchy import statusline

ANSI = re.compile(r"\x1b\[[0-9;]*m")
P = statusline.PALETTE
FULL = {
    "model": {"display_name": "Opus 5.5 (1M context)"},
    "effort": {"level": "xhigh"},
    "context_window": {"used_percentage": 48},
    "rate_limits": {"five_hour": {"used_percentage": 29}, "seven_day": {"used_percentage": 12}},
}
EMPTY_LINE = " 🕯️ -- ⋆ 🌑 -- ⋆ 5h -- ⋆ 7d -- \n"


def plain(text):
    return ANSI.sub("", text)


def fg(hex_colour):
    red, green, blue = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return f"\x1b[38;2;{red};{green};{blue}m"


def run(text):
    out = io.StringIO()
    code = statusline.main(io.StringIO(text), out)
    return code, out.getvalue()


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "init.defaultBranch=main", *args],
                   cwd=cwd, check=True, capture_output=True)


class RenderTest(unittest.TestCase):
    def test_full_payload_outside_a_repo(self):
        with tempfile.TemporaryDirectory() as directory:
            code, out = run(json.dumps(dict(FULL, workspace={"current_dir": directory})))
        self.assertEqual(code, 0)
        self.assertEqual(plain(out), " 🕯️ Opus 5.5·xhigh ⋆ 🌓 48% ⋆ 5h 71% ⋆ 7d 88% \n")

    def test_empty_null_and_invalid_payloads(self):
        for text in ("", "null", "{", "[1, 2]", '"x"', "{}"):
            code, out = run(text)
            self.assertEqual(code, 0, text)
            self.assertEqual(plain(out), EMPTY_LINE, text)

    def test_wrong_types_read_as_dashes(self):
        payload = {"model": {"display_name": 5}, "effort": {"level": ""},
                   "context_window": {"used_percentage": "48"},
                   "rate_limits": {"five_hour": {"used_percentage": True}, "seven_day": []}}
        self.assertEqual(plain(run(json.dumps(payload))[1]), EMPTY_LINE)

    def test_nan_reads_as_a_dash(self):
        self.assertEqual(plain(run('{"context_window": {"used_percentage": NaN}}')[1]), EMPTY_LINE)

    def test_weird_nesting_never_raises(self):
        statusline.render({"model": [], "context_window": [], "rate_limits": {"five_hour": []},
                           "workspace": {"current_dir": 7}, "cwd": None})

    def test_model_without_effort(self):
        self.assertTrue(plain(statusline.render({"model": {"display_name": "Sonnet 5.5"}})).startswith(" 🕯️ Sonnet 5.5 ⋆ "))

    def test_moon_boundaries(self):
        cases = [(None, "🌑"), (0, "🌑"), (12, "🌑"), (12.4, "🌑"), (12.6, "🌒"), (13, "🌒"), (37, "🌒"),
                 (38, "🌓"), (62, "🌓"), (63, "🌔"), (87, "🌔"), (88, "🌕"), (100, "🌕")]
        for used, glyph in cases:
            self.assertEqual(statusline.moon(used), glyph, used)

    def test_context_colour_thresholds(self):
        for used, key, bold in ((49, "context_low", False), (50, "context_mid", False),
                                (79, "context_mid", False), (80, "context_high", True)):
            out = statusline.render({"context_window": {"used_percentage": used}})
            painted = fg(P[key]) + f"{used}%"
            self.assertIn(painted, out, used)
            self.assertEqual("\x1b[1m" + painted in out, bold, used)

    def test_remaining_colour_thresholds(self):
        for used, left, key, bold in ((49, 51, "left_high", False), (50, 50, "left_mid", False),
                                      (79, 21, "left_mid", False), (80, 20, "left_low", True)):
            out = statusline.render({"rate_limits": {"five_hour": {"used_percentage": used}}})
            painted = fg(P[key]) + f"{left}%"
            self.assertIn(painted, out, used)
            self.assertEqual("\x1b[1m" + painted in out, bold, used)


class GitSegmentTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "spellbook"
        self.repo.mkdir()
        git(self.repo, "init")
        (self.repo / "a.txt").write_text("a")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "init")

    def line(self, payload=None):
        return plain(statusline.render(payload or {"workspace": {"current_dir": str(self.repo)}}))

    def test_clean_repo(self):
        self.assertTrue(self.line().endswith(" ⋆ 📜 spellbook ⎇ main "), self.line())

    def test_dirty_repo_counts_changes(self):
        (self.repo / "a.txt").write_text("changed")
        (self.repo / "b.txt").write_text("new")
        self.assertTrue(self.line().endswith("⎇ main✦2 "), self.line())

    def test_long_branch_is_cut_to_28(self):
        name = "feature/INC-98560-notificacion-juzgado"
        git(self.repo, "checkout", "-b", name)
        self.assertTrue(self.line().endswith(f"⎇ {name[:27]}… "), self.line())

    def test_detached_head_shows_the_short_hash(self):
        git(self.repo, "checkout", "--detach")
        short = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=self.repo,
                               capture_output=True, text=True, check=True).stdout.strip()
        self.assertTrue(self.line().endswith(f"⎇ {short} "), self.line())

    def test_subdirectory_shows_the_repo_root_name(self):
        deep = self.repo / "deep"
        deep.mkdir()
        self.assertIn("📜 spellbook", self.line({"workspace": {"current_dir": str(deep)}}))

    def test_cwd_is_the_fallback(self):
        self.assertIn("📜 spellbook", self.line({"cwd": str(self.repo)}))

    def test_missing_directory_hides_git(self):
        self.assertNotIn("📜", self.line({"workspace": {"current_dir": "/nonexistent/witchy"}}))

    def test_git_segment_colours(self):
        out = statusline.render({"workspace": {"current_dir": str(self.repo)}})
        self.assertIn(fg(P["repo"]) + "📜 spellbook", out)
        self.assertIn(fg(P["branch"]) + "⎇ main", out)


class ProcessTest(unittest.TestCase):
    def test_runs_as_a_script_under_the_c_locale(self):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C", "LC_ALL": "C"}
        done = subprocess.run([sys.executable, "-I", str(Path(statusline.__file__))],
                              input=json.dumps(FULL).encode("utf-8"), capture_output=True, env=env, timeout=10)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("🌓".encode("utf-8"), done.stdout)
        self.assertTrue(done.stdout.endswith(b"\n"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest tests.test_statusline -v`
Expected: `ImportError: cannot import name 'statusline'`.

- [ ] **Step 3: Write the implementation**

`witchy/statusline.py`:

```python
"""Moonlit Candle status line: model, a moon for context, windows left, and git.

Claude Code pipes one JSON payload per render and shows the line printed here.
This file is copied on its own to ~/.claude/witchy/, so it imports nothing from
the witchy package; build.py rewrites the PALETTE block from palette.py. Like
the archon status line it replaces, it is a sensor, never a gate: a missing or
malformed field reads as a dash, and the script always exits 0.
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
from typing import Any, Optional, TextIO

MAX_INPUT_BYTES = 1_048_576
DASH = "--"
CANDLE = "🕯️"
SCROLL = "📜"
BRANCH = "⎇"
DIRTY = "✦"
SEPARATOR = "⋆"
# Inclusive upper bound of the rounded context percentage, and the moon shown up to it.
MOONS = ((12, "🌑"), (37, "🌒"), (62, "🌓"), (87, "🌔"), (100, "🌕"))
BRANCH_MAX = 28
GIT_TIMEOUT = 1

# BEGIN PALETTE
PALETTE = {
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
# END PALETTE

RESET = "\x1b[0m"
BOLD = "\x1b[1m"


def _paint(text: str, key: str, *, bold: bool = False) -> str:
    colour = PALETTE[key]
    red, green, blue = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return f"{BOLD if bold else ''}\x1b[38;2;{red};{green};{blue}m{text}{RESET}"


def _get(payload: Any, *path: str) -> Any:
    for name in path:
        if not isinstance(payload, dict):
            return None
        payload = payload.get(name)
    return payload


def _percent(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return min(100.0, max(0.0, float(value)))


def moon(used: Optional[float]) -> str:
    """The moon for a context percentage; a new moon while nothing is known."""
    if used is None:
        return MOONS[0][1]
    rounded = round(used)
    for limit, glyph in MOONS:
        if rounded <= limit:
            return glyph
    return MOONS[-1][1]


def _model(payload: Any) -> str:
    name = _get(payload, "model", "display_name")
    name = re.sub(r"\s*\(.*\)\s*$", "", name).strip() if isinstance(name, str) else ""
    level = _get(payload, "effort", "level")
    effort = _paint(f"·{level}", "muted") if isinstance(level, str) and level else ""
    return _paint(f"{CANDLE} {name or DASH}", "model", bold=True) + effort


def _context(payload: Any) -> str:
    used = _percent(_get(payload, "context_window", "used_percentage"))
    if used is None:
        return f"{moon(None)} {_paint(DASH, 'muted')}"
    rounded = round(used)
    key = "context_low" if rounded < 50 else "context_mid" if rounded < 80 else "context_high"
    return f"{moon(used)} {_paint(f'{rounded}%', key, bold=rounded >= 80)}"


def _left(payload: Any, window: str, label: str) -> str:
    used = _percent(_get(payload, "rate_limits", window, "used_percentage"))
    tag = _paint(label, "muted")
    if used is None:
        return f"{tag} {_paint(DASH, 'muted')}"
    left = round(100 - used)
    key = "left_high" if left > 50 else "left_mid" if left > 20 else "left_low"
    return f"{tag} {_paint(f'{left}%', key, bold=left <= 20)}"


def _git(cwd: str, *args: str) -> Optional[str]:
    try:
        done = subprocess.run(
            ["git", *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            timeout=GIT_TIMEOUT, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return done.stdout if done.returncode == 0 else None


def _repo(payload: Any) -> Optional[str]:
    cwd = _get(payload, "workspace", "current_dir")
    if not isinstance(cwd, str) or not cwd:
        cwd = _get(payload, "cwd")
    if not isinstance(cwd, str) or not os.path.isdir(cwd):
        return None
    top = (_git(cwd, "rev-parse", "--show-toplevel") or "").strip()
    if not top:
        return None
    branch = (_git(cwd, "branch", "--show-current") or "").strip()
    if not branch:
        branch = (_git(cwd, "rev-parse", "--short", "HEAD") or "").strip() or DASH
    if len(branch) > BRANCH_MAX:
        branch = branch[:BRANCH_MAX - 1] + "…"
    dirty = sum(1 for line in (_git(cwd, "status", "--porcelain") or "").splitlines() if line.strip())
    segment = _paint(f"{SCROLL} {os.path.basename(top)}", "repo") + " " + _paint(f"{BRANCH} {branch}", "branch")
    return segment + (_paint(f"{DIRTY}{dirty}", "dirty") if dirty else "")


def render(payload: Any) -> str:
    """One status line for one payload; never raises on a malformed one."""
    parts = [_model(payload), _context(payload), _left(payload, "five_hour", "5h"), _left(payload, "seven_day", "7d")]
    repo = _repo(payload)
    if repo:
        parts.append(repo)
    return " " + _paint(f" {SEPARATOR} ", "divider").join(parts) + " "


def main(stdin: Optional[TextIO] = None, stdout: Optional[TextIO] = None) -> int:
    """Render stdin's payload. Always exit 0: a blank status line tells nobody anything."""
    if stdin is None:
        stdin = sys.stdin
        stdin.reconfigure(encoding="utf-8", errors="replace")
    if stdout is None:
        stdout = sys.stdout
        # Claude Code may launch us under a C locale; the glyphs must still get out.
        stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        payload = json.loads(stdin.read(MAX_INPUT_BYTES))
    except (ValueError, OSError, RecursionError):
        payload = None
    try:
        line = render(payload)
    except Exception:  # a status line must never take the prompt down with it
        line = f" {DASH} "
    stdout.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest discover -s tests -t . -v && /usr/bin/python3.10 -m unittest discover -s tests -t .`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/mmarenas/proyectos/witchy-claude-theme && git add witchy/statusline.py tests/test_statusline.py && git commit -m "feat: moon-phase status line with git segment

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Build

**Files:**
- Create: `witchy/build.py`
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: `palette.*` (Task 1); `content.CONTENT_DIR`, `content.load_spinner`, `content.read_output_style`, `validate.validate_all`, `validate.Failure` (Task 2); the PALETTE markers in `witchy/statusline.py` (Task 3).
- Produces:
  - Constants (relative paths inside `dist/`): `THEME = "claude/themes/moonlit-candle.json"`, `OUTPUT_STYLE = "claude/output-styles/witchynibbles.md"`, `STATUSLINE = "claude/witchy/statusline.py"`, `TIPS = "claude/witchy/tips.json"`, `WT_SCHEME = "windows-terminal/moonlit-candle.scheme.json"`; `ROOT: Path`, `DIST: Path` (= `ROOT / "dist"`), `STATUSLINE_SOURCE: Path`
  - `palette_block(colours: dict[str, str]) -> str`
  - `statusline_source(colours: dict[str, str] = palette.STATUSLINE, source: Path = STATUSLINE_SOURCE) -> str` (raises `ValueError` if there is not exactly one block)
  - `render_outputs(content_dir: Path = content.CONTENT_DIR) -> dict[str, str]` (keys are the five constants)
  - `write_dist(outputs: dict[str, str], dist: Path | None = None) -> None` (`None` means `DIST`, read at call time)
  - `build(dist: Path | None = None, content_dir: Path = content.CONTENT_DIR) -> list[validate.Failure]` (writes nothing if validation fails)

- [ ] **Step 1: Write the failing tests**

`tests/test_build.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from witchy import build, content, palette


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.outputs = build.render_outputs()

    def test_outputs_cover_every_artifact(self):
        self.assertEqual(set(self.outputs), {build.THEME, build.OUTPUT_STYLE, build.STATUSLINE, build.TIPS, build.WT_SCHEME})

    def test_theme_file(self):
        self.assertEqual(json.loads(self.outputs[build.THEME]),
                         {"name": "Moonlit Candle", "base": "dark", "overrides": palette.CLAUDE_OVERRIDES})

    def test_scheme_file(self):
        self.assertEqual(json.loads(self.outputs[build.WT_SCHEME]), palette.WT_SCHEME)

    def test_tips_file(self):
        data = json.loads(self.outputs[build.TIPS])
        self.assertEqual(list(data), ["tips"])
        self.assertEqual(data["tips"], content.load_spinner()["tips"])

    def test_output_style_is_copied_verbatim(self):
        self.assertEqual(self.outputs[build.OUTPUT_STYLE], content.read_output_style())

    def test_source_palette_block_matches_palette(self):
        self.assertEqual(build.statusline_source(), build.STATUSLINE_SOURCE.read_text(encoding="utf-8"))

    def test_palette_block_is_rewritten(self):
        source = build.statusline_source(dict(palette.STATUSLINE, model="#123456"))
        self.assertIn('    "model": "#123456",\n', source)

    def test_generated_statusline_compiles(self):
        compile(self.outputs[build.STATUSLINE], "statusline.py", "exec")

    def test_missing_palette_block_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "statusline.py"
            source.write_text("PALETTE = {}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                build.statusline_source(source=source)

    def test_write_dist(self):
        with tempfile.TemporaryDirectory() as tmp:
            build.write_dist(self.outputs, Path(tmp))
            for rel, text in self.outputs.items():
                self.assertEqual((Path(tmp) / rel).read_text(encoding="utf-8"), text)

    def test_build_refuses_invalid_content(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as empty:
            failures = build.build(dist=Path(tmp) / "dist", content_dir=Path(empty))
            self.assertTrue(failures)
            self.assertFalse((Path(tmp) / "dist").exists())

    def test_build_writes_dist_when_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(build.build(dist=Path(tmp)), [])
            self.assertTrue((Path(tmp) / build.THEME).is_file())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest tests.test_build -v`
Expected: `ImportError: cannot import name 'build'`.

- [ ] **Step 3: Write the implementation**

`witchy/build.py`:

```python
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
PALETTE_BLOCK = re.compile(r"(# BEGIN PALETTE\n)(.*?)(# END PALETTE\n)", re.DOTALL)

THEME = "claude/themes/moonlit-candle.json"
OUTPUT_STYLE = "claude/output-styles/witchynibbles.md"
STATUSLINE = "claude/witchy/statusline.py"
TIPS = "claude/witchy/tips.json"
WT_SCHEME = "windows-terminal/moonlit-candle.scheme.json"


def palette_block(colours: dict[str, str]) -> str:
    lines = ["PALETTE = {", *(f'    "{key}": "{value}",' for key, value in colours.items()), "}"]
    return "\n".join(lines) + "\n"


def statusline_source(colours: dict[str, str] = palette.STATUSLINE, source: Path = STATUSLINE_SOURCE) -> str:
    """The status line script with its PALETTE block rewritten from ``colours``."""
    text = source.read_text(encoding="utf-8")
    rewritten, count = PALETTE_BLOCK.subn(lambda m: m.group(1) + palette_block(colours) + m.group(3), text)
    if count != 1:
        raise ValueError(f"{source} must contain exactly one PALETTE block, found {count}")
    return rewritten


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def render_outputs(content_dir: Path = content.CONTENT_DIR) -> dict[str, str]:
    spinner = content.load_spinner(content_dir)
    return {
        THEME: _json({"name": palette.THEME_NAME, "base": "dark", "overrides": palette.CLAUDE_OVERRIDES}),
        OUTPUT_STYLE: content.read_output_style(content_dir),
        STATUSLINE: statusline_source(),
        TIPS: _json({"tips": spinner["tips"]}),
        WT_SCHEME: _json(palette.WT_SCHEME),
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest discover -s tests -t . -v && /usr/bin/python3.10 -m unittest discover -s tests -t .`
Expected: all PASS. If `test_source_palette_block_matches_palette` fails, the `PALETTE` block in `witchy/statusline.py` does not match `palette.STATUSLINE`. Fix the block (4-space indent, trailing commas, same order); don't touch the test.

- [ ] **Step 5: Commit**

```bash
cd /home/mmarenas/proyectos/witchy-claude-theme && git add witchy/build.py tests/test_build.py && git commit -m "feat: build dist artifacts from the palette

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: JSON file handling and Claude settings keys

**Files:**
- Create: `witchy/jsonio.py`, `witchy/records.py`, `witchy/claude_settings.py`
- Test: `tests/test_jsonio.py`, `tests/test_claude_settings.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `witchy.jsonio.StrictJsonError(ValueError)`, `read_json(path: Path) -> tuple[Any, str]`, `detect_indent(text: str) -> str`, `dumps_like(data: Any, like: str | None) -> str`, `write_atomic_bytes(path: Path, data: bytes) -> None`, `backup(path: Path, stamp: str) -> Path`
  - `witchy.records.snapshot(container: dict, key: str) -> dict` (`{"value": v}` or `{"absent": True}`), `put_back(container: dict, key: str, previous: dict) -> None`
  - `witchy.claude_settings.THEME = "custom:moonlit-candle"`, `OUTPUT_STYLE = "WitchyNibbles"`, `TIPS_LABEL = "Grimoire"`, `TIPS_FILE = "~/.claude/witchy/tips.json"`, `KEYS` (5-tuple in spec order), `desired_keys(home: Path, python: str, verbs: list[str]) -> dict[str, Any]`, `apply_keys(data: dict, desired: dict[str, Any], recorded: dict | None) -> tuple[dict, dict]`, `restore_keys(data: dict, records: dict) -> tuple[dict, list[str]]`
  - Key record shape: `{"previous": {"value": ...} | {"absent": True}, "installed": <value>}`

- [ ] **Step 1: Write the failing tests**

`tests/test_jsonio.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from witchy import jsonio, records


class ReadJsonTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def write(self, name, text):
        path = self.dir / name
        path.write_bytes(text.encode("utf-8"))
        return path

    def test_reads_data_and_exact_text(self):
        text = '{\r\n    "a": 1\r\n}\r\n'
        data, raw = jsonio.read_json(self.write("a.json", text))
        self.assertEqual(data, {"a": 1})
        self.assertEqual(raw, text)

    def test_comments_trailing_commas_and_bom_are_not_plain_json(self):
        for text in ('{\n  // note\n  "a": 1\n}\n', '{"a": 1,}\n', '﻿{"a": 1}\n'):
            with self.assertRaises(jsonio.StrictJsonError, msg=text):
                jsonio.read_json(self.write("bad.json", text))

    def test_urls_with_double_slashes_are_fine(self):
        data, _ = jsonio.read_json(self.write("url.json", '{"$help": "https://aka.ms/terminal-documentation"}'))
        self.assertEqual(data["$help"], "https://aka.ms/terminal-documentation")


class DumpsLikeTest(unittest.TestCase):
    def test_detect_indent(self):
        self.assertEqual(jsonio.detect_indent('{\n  "a": 1\n}'), "  ")
        self.assertEqual(jsonio.detect_indent('{\n    "a": 1\n}'), "    ")
        self.assertEqual(jsonio.detect_indent('{\n\t"a": 1\n}'), "\t")
        self.assertEqual(jsonio.detect_indent("{}"), "  ")

    def test_round_trips_claude_style(self):
        text = json.dumps({"env": {"A": "1"}, "theme": "dark", "name": "Símbolo"}, indent=2, ensure_ascii=False) + "\n"
        self.assertEqual(jsonio.dumps_like(json.loads(text), text), text)

    def test_dumps_like_keeps_ascii_escapes_and_indent(self):
        text = json.dumps({"profiles": {"list": [{"name": "Símbolo del sistema"}]}}, indent=4) + "\n"
        self.assertIn("\\u00ed", text)
        self.assertEqual(jsonio.dumps_like(json.loads(text), text), text)

    def test_keeps_crlf_and_missing_final_newline(self):
        self.assertEqual(jsonio.dumps_like({"a": 1}, '{\r\n  "a": 0\r\n}\r\n'), '{\r\n  "a": 1\r\n}\r\n')
        self.assertEqual(jsonio.dumps_like({"a": 1}, '{\n  "a": 0\n}'), '{\n  "a": 1\n}')

    def test_fresh_file_style(self):
        self.assertEqual(jsonio.dumps_like({"a": "í"}, None), '{\n  "a": "í"\n}\n')


class WriteAndBackupTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def test_write_atomic_creates_parents_and_leaves_no_temp_files(self):
        path = self.dir / "a" / "b" / "file.json"
        jsonio.write_atomic_bytes(path, b"one")
        jsonio.write_atomic_bytes(path, b"two")
        self.assertEqual(path.read_bytes(), b"two")
        self.assertEqual([p.name for p in path.parent.iterdir()], ["file.json"])

    def test_backup_is_dated_and_never_overwrites(self):
        path = self.dir / "settings.json"
        path.write_bytes(b"original")
        first = jsonio.backup(path, "20260930-120000")
        second = jsonio.backup(path, "20260930-120000")
        self.assertEqual(first.name, "settings.json.bak-witchy-20260930-120000")
        self.assertEqual(second.name, "settings.json.bak-witchy-20260930-120000-1")
        self.assertEqual(first.read_bytes(), b"original")


class RecordsTest(unittest.TestCase):
    def test_snapshot_and_put_back(self):
        data = {"a": {"x": 1}}
        present, absent = records.snapshot(data, "a"), records.snapshot(data, "b")
        self.assertEqual(present, {"value": {"x": 1}})
        self.assertEqual(absent, {"absent": True})
        data["a"]["x"] = 2
        self.assertEqual(present, {"value": {"x": 1}})  # a deep copy, not a live reference
        data["b"] = 5
        records.put_back(data, "a", present)
        records.put_back(data, "b", absent)
        self.assertEqual(data, {"a": {"x": 1}})


if __name__ == "__main__":
    unittest.main()
```

`tests/test_claude_settings.py`:

```python
import unittest
from pathlib import Path

from witchy import claude_settings

ORIGINAL = {
    "env": {"A": "1"},
    "statusLine": {"type": "command", "command": "archon statusline", "padding": 0},
    "theme": "dark",
    "agentPushNotifEnabled": True,
}


class DesiredKeysTest(unittest.TestCase):
    def test_exact_values(self):
        desired = claude_settings.desired_keys(Path("/home/u"), "/usr/bin/python3", ["Brewing"])
        self.assertEqual(tuple(desired), claude_settings.KEYS)
        self.assertEqual(desired, {
            "theme": "custom:moonlit-candle",
            "statusLine": {"type": "command", "command": "/usr/bin/python3 -I /home/u/.claude/witchy/statusline.py",
                           "padding": 0},
            "spinnerVerbs": {"mode": "replace", "verbs": ["Brewing"]},
            "spinnerTipsOverride": {"label": "Grimoire", "tipsFile": "~/.claude/witchy/tips.json", "excludeDefault": False},
            "outputStyle": "WitchyNibbles",
        })

    def test_paths_with_spaces_are_quoted(self):
        desired = claude_settings.desired_keys(Path("/home/a b"), "/usr/bin/python3", [])
        self.assertEqual(desired["statusLine"]["command"], "/usr/bin/python3 -I '/home/a b/.claude/witchy/statusline.py'")


class ApplyRestoreTest(unittest.TestCase):
    def setUp(self):
        self.desired = claude_settings.desired_keys(Path("/home/u"), "/usr/bin/python3", ["Brewing"])

    def test_apply_keeps_unrelated_keys_and_order(self):
        result, recs = claude_settings.apply_keys(ORIGINAL, self.desired, None)
        self.assertEqual(list(result), ["env", "statusLine", "theme", "agentPushNotifEnabled",
                                        "spinnerVerbs", "spinnerTipsOverride", "outputStyle"])
        self.assertEqual(result["env"], {"A": "1"})
        self.assertEqual(recs["theme"], {"previous": {"value": "dark"}, "installed": "custom:moonlit-candle"})
        self.assertEqual(recs["outputStyle"]["previous"], {"absent": True})
        self.assertEqual(ORIGINAL["theme"], "dark")  # input untouched

    def test_reinstall_keeps_the_first_previous_value(self):
        installed, first = claude_settings.apply_keys(ORIGINAL, self.desired, None)
        _, second = claude_settings.apply_keys(dict(installed, theme="light"), self.desired, first)
        self.assertEqual(second["theme"]["previous"], {"value": "dark"})

    def test_restore_round_trip(self):
        installed, recs = claude_settings.apply_keys(ORIGINAL, self.desired, None)
        restored, warnings = claude_settings.restore_keys(installed, recs)
        self.assertEqual(restored, ORIGINAL)
        self.assertEqual(list(restored), list(ORIGINAL))
        self.assertEqual(warnings, [])

    def test_restore_leaves_a_key_the_user_changed(self):
        installed, recs = claude_settings.apply_keys(ORIGINAL, self.desired, None)
        restored, warnings = claude_settings.restore_keys(dict(installed, outputStyle="Concise"), recs)
        self.assertEqual(restored["outputStyle"], "Concise")
        self.assertEqual(restored["theme"], "dark")
        self.assertEqual(len(warnings), 1)
        self.assertIn("outputStyle", warnings[0])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest tests.test_jsonio tests.test_claude_settings -v`
Expected: `ImportError` for `jsonio` / `records` / `claude_settings`.

- [ ] **Step 3: Write the implementation**

`witchy/jsonio.py`:

```python
"""Careful JSON file handling: strict reads, style-preserving writes, dated backups.

Settings files belong to other programs (Claude Code, Windows Terminal), so a
rewrite keeps their indentation, escaping and line endings, never leaves a
half-written file behind, and a file that is not strictly JSON is never rewritten.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

_INDENT = re.compile(r"^([ \t]+)\S", re.MULTILINE)


class StrictJsonError(ValueError):
    """Not plain JSON (comments, trailing commas, a BOM), so it must not be rewritten."""


def read_json(path: Path) -> tuple[Any, str]:
    """Parse ``path`` strictly; return the data and the exact text it came from."""
    try:
        text = path.read_bytes().decode("utf-8")
        return json.loads(text), text
    except ValueError as exc:
        raise StrictJsonError(f"{path}: {exc}") from exc


def detect_indent(text: str) -> str:
    match = _INDENT.search(text)
    return match.group(1) if match else "  "


def dumps_like(data: Any, like: str | None) -> str:
    """Serialise ``data`` in the style of ``like``; a brand-new file gets two spaces and UTF-8."""
    if like is None:
        return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    # Windows Terminal stores non-ASCII names as \uXXXX escapes; an ASCII-only file stays ASCII-only.
    text = json.dumps(data, indent=detect_indent(like), ensure_ascii=like.isascii())
    newline = "\r\n" if "\r\n" in like else "\n"
    text = text.replace("\n", newline)
    return text + newline if like.endswith("\n") else text


def write_atomic_bytes(path: Path, data: bytes) -> None:
    """Replace ``path`` in one step: write a sibling temp file, then rename it over."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        if path.exists():
            try:
                shutil.copymode(path, tmp)
            except OSError:
                pass  # /mnt/c (drvfs) may refuse chmod; the content is what matters
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def backup(path: Path, stamp: str) -> Path:
    """Copy ``path`` to ``<name>.bak-witchy-<stamp>`` beside it and return the copy."""
    target = path.with_name(f"{path.name}.bak-witchy-{stamp}")
    counter = 1
    while target.exists():
        target = path.with_name(f"{path.name}.bak-witchy-{stamp}-{counter}")
        counter += 1
    shutil.copyfile(path, target)
    return target
```

`witchy/records.py`:

```python
"""What a key held before witchy set it, and how to put it back."""
from __future__ import annotations

import copy


def snapshot(container: dict, key: str) -> dict:
    return {"value": copy.deepcopy(container[key])} if key in container else {"absent": True}


def put_back(container: dict, key: str, previous: dict) -> None:
    if previous.get("absent"):
        container.pop(key, None)
    else:
        container[key] = copy.deepcopy(previous["value"])
```

`witchy/claude_settings.py`:

```python
"""The five ~/.claude/settings.json keys witchy owns, and how to hand them back."""
from __future__ import annotations

import copy
import shlex
from pathlib import Path
from typing import Any

from .records import put_back, snapshot

THEME = "custom:moonlit-candle"
OUTPUT_STYLE = "WitchyNibbles"
TIPS_LABEL = "Grimoire"
TIPS_FILE = "~/.claude/witchy/tips.json"
KEYS = ("theme", "statusLine", "spinnerVerbs", "spinnerTipsOverride", "outputStyle")


def desired_keys(home: Path, python: str, verbs: list[str]) -> dict[str, Any]:
    script = home / ".claude" / "witchy" / "statusline.py"
    return {
        "theme": THEME,
        "statusLine": {"type": "command", "command": f"{shlex.quote(python)} -I {shlex.quote(str(script))}", "padding": 0},
        "spinnerVerbs": {"mode": "replace", "verbs": list(verbs)},
        "spinnerTipsOverride": {"label": TIPS_LABEL, "tipsFile": TIPS_FILE, "excludeDefault": False},
        "outputStyle": OUTPUT_STYLE,
    }


def apply_keys(data: dict, desired: dict[str, Any], recorded: dict | None) -> tuple[dict, dict]:
    """Set every desired key. On a reinstall the first-ever previous value is kept, not witchy's own."""
    result = copy.deepcopy(data)
    records = {}
    for key, value in desired.items():
        earlier = (recorded or {}).get(key)
        previous = earlier["previous"] if earlier else snapshot(result, key)
        records[key] = {"previous": previous, "installed": copy.deepcopy(value)}
        result[key] = copy.deepcopy(value)
    return result, records


def restore_keys(data: dict, records: dict) -> tuple[dict, list[str]]:
    """Give back each key's previous value, unless it no longer holds what witchy installed."""
    result = copy.deepcopy(data)
    warnings = []
    for key, record in records.items():
        if snapshot(result, key) != {"value": record["installed"]}:
            warnings.append(f"{key} was changed after install; leaving it as it is.")
            continue
        put_back(result, key, record["previous"])
    return result, warnings
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest discover -s tests -t . -v && /usr/bin/python3.10 -m unittest discover -s tests -t .`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/mmarenas/proyectos/witchy-claude-theme && git add witchy tests && git commit -m "feat: style-preserving JSON io and Claude settings key merge/restore

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Windows Terminal

**Files:**
- Create: `witchy/wt.py`
- Test: `tests/test_wt.py`

**Interfaces:**
- Consumes: `witchy.records.snapshot`, `witchy.records.put_back` (Task 5).
- Produces:
  - `witchy.wt.PACKAGE = "Microsoft.WindowsTerminal_8wekyb3d8bbwe"`, `USERS_ROOT = Path("/mnt/c/Users")`
  - `windows_username(run: Callable[..., Any] = subprocess.run) -> str | None`
  - `settings_path_for(user: str, users_root: Path = USERS_ROOT) -> Path`
  - `locate_settings(explicit: Path | None, run=subprocess.run, users_root: Path = USERS_ROOT) -> Path | None`
  - `find_profile(data: Any, env: Mapping[str, str]) -> tuple[str | None, str | None]` → `(guid, None)` or `(None, reason)`
  - `apply_scheme(data: dict, scheme: dict, guid: str, recorded: dict | None) -> tuple[dict, dict]` (raises `ValueError` if `schemes` is not a list or the profile is missing)
  - `restore_scheme(data: dict, record: dict) -> tuple[dict, list[str]]`
  - `manual_snippet(scheme: dict, guid: str) -> str`
  - Record shape (also stored in state.json): `{"profile_guid", "previous_color_scheme", "previous_scheme", "schemes_key_absent", "installed_color_scheme"}`

- [ ] **Step 1: Write the failing tests**

`tests/test_wt.py`:

```python
import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

from witchy import palette, wt

UBUNTU = "{05f3f843-450a-55ad-a264-cacf368dafe5}"
POWERSHELL = "{61c54bbd-c2c6-5271-96e7-009a87ff44bf}"


def settings():
    return {
        "$help": "https://aka.ms/terminal-documentation",
        "profiles": {"defaults": {}, "list": [
            {"guid": POWERSHELL, "name": "Windows PowerShell"},
            {"guid": "{0caa0dad-35be-5f56-a8ff-afceeeaa6101}", "name": "Símbolo del sistema"},
            {"guid": UBUNTU, "name": "Ubuntu", "source": "Microsoft.WSL", "colorScheme": "One Half Dark"},
        ]},
        "schemes": [],
    }


def fake_run(stdout="", returncode=0, error=None):
    def run(args, **kwargs):
        if error:
            raise error
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr="")
    return run


class LocateTest(unittest.TestCase):
    def test_windows_username(self):
        self.assertEqual(wt.windows_username(fake_run("mmarenas\r\n")), "mmarenas")
        self.assertIsNone(wt.windows_username(fake_run("", returncode=1)))
        self.assertIsNone(wt.windows_username(fake_run("%USERNAME%\r\n")))
        self.assertIsNone(wt.windows_username(fake_run(error=FileNotFoundError("cmd.exe"))))

    def test_locate_uses_the_current_windows_user_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for user in ("admin", "mmarenas"):
                path = wt.settings_path_for(user, root)
                path.parent.mkdir(parents=True)
                path.write_text("{}")
            found = wt.locate_settings(None, run=fake_run("mmarenas\r\n"), users_root=root)
            self.assertEqual(found, wt.settings_path_for("mmarenas", root))
            self.assertIsNone(wt.locate_settings(None, run=fake_run("nobody\r\n"), users_root=root))

    def test_explicit_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            self.assertIsNone(wt.locate_settings(path, run=fake_run(error=AssertionError("must not run"))))
            path.write_text("{}")
            self.assertEqual(wt.locate_settings(path, run=fake_run(error=AssertionError("must not run"))), path)


class FindProfileTest(unittest.TestCase):
    def test_profile_id_match_is_case_insensitive(self):
        self.assertEqual(wt.find_profile(settings(), {"WT_PROFILE_ID": UBUNTU.upper()}), (UBUNTU, None))

    def test_stale_profile_id_falls_back_to_distro(self):
        env = {"WT_PROFILE_ID": "{00000000-0000-0000-0000-000000000000}", "WSL_DISTRO_NAME": "Ubuntu"}
        self.assertEqual(wt.find_profile(settings(), env), (UBUNTU, None))

    def test_no_profile_id_uses_distro(self):
        self.assertEqual(wt.find_profile(settings(), {"WSL_DISTRO_NAME": "Ubuntu"}), (UBUNTU, None))

    def test_nothing_to_go_on(self):
        guid, reason = wt.find_profile(settings(), {})
        self.assertIsNone(guid)
        self.assertTrue(reason)

    def test_two_matching_wsl_profiles_are_ambiguous(self):
        data = settings()
        data["profiles"]["list"].append({"guid": "{11111111-1111-1111-1111-111111111111}", "name": "Ubuntu",
                                         "source": "Microsoft.WSL"})
        self.assertIsNone(wt.find_profile(data, {"WSL_DISTRO_NAME": "Ubuntu"})[0])

    def test_profiles_as_a_plain_list(self):
        data = settings()
        data["profiles"] = data["profiles"]["list"]
        self.assertEqual(wt.find_profile(data, {"WT_PROFILE_ID": UBUNTU}), (UBUNTU, None))

    def test_missing_profiles(self):
        self.assertIsNone(wt.find_profile({}, {"WT_PROFILE_ID": UBUNTU})[0])


class ApplyRestoreTest(unittest.TestCase):
    def test_apply_sets_only_the_chosen_profile(self):
        result, record = wt.apply_scheme(settings(), palette.WT_SCHEME, UBUNTU, None)
        self.assertEqual(result["schemes"], [palette.WT_SCHEME])
        profiles = {p["guid"]: p for p in result["profiles"]["list"]}
        self.assertEqual(profiles[UBUNTU]["colorScheme"], "Moonlit Candle")
        self.assertNotIn("colorScheme", profiles[POWERSHELL])
        self.assertEqual(record, {
            "profile_guid": UBUNTU,
            "previous_color_scheme": {"value": "One Half Dark"},
            "previous_scheme": {"absent": True},
            "schemes_key_absent": False,
            "installed_color_scheme": "Moonlit Candle",
        })

    def test_apply_replaces_a_scheme_with_the_same_name(self):
        data = settings()
        data["schemes"] = [{"name": "Moonlit Candle", "background": "#000000"}]
        result, record = wt.apply_scheme(data, palette.WT_SCHEME, UBUNTU, None)
        self.assertEqual(result["schemes"], [palette.WT_SCHEME])
        self.assertEqual(record["previous_scheme"], {"value": {"name": "Moonlit Candle", "background": "#000000"}})

    def test_reinstall_keeps_the_first_record(self):
        installed, first = wt.apply_scheme(settings(), palette.WT_SCHEME, UBUNTU, None)
        _, second = wt.apply_scheme(installed, palette.WT_SCHEME, UBUNTU, first)
        self.assertEqual(second, first)

    def test_restore_round_trip(self):
        original = settings()
        installed, record = wt.apply_scheme(original, palette.WT_SCHEME, UBUNTU, None)
        restored, warnings = wt.restore_scheme(installed, record)
        self.assertEqual(restored, original)
        self.assertEqual(warnings, [])

    def test_restore_drops_a_schemes_key_it_created(self):
        original = settings()
        del original["schemes"]
        installed, record = wt.apply_scheme(original, palette.WT_SCHEME, UBUNTU, None)
        self.assertEqual(wt.restore_scheme(installed, record)[0], original)

    def test_restore_leaves_a_changed_profile_and_a_scheme_in_use(self):
        installed, record = wt.apply_scheme(settings(), palette.WT_SCHEME, UBUNTU, None)
        changed = copy.deepcopy(installed)
        for profile in changed["profiles"]["list"]:
            if profile["guid"] == UBUNTU:
                profile["colorScheme"] = "Campbell"
            if profile["guid"] == POWERSHELL:
                profile["colorScheme"] = "Moonlit Candle"
        restored, warnings = wt.restore_scheme(changed, record)
        profiles = {p["guid"]: p for p in restored["profiles"]["list"]}
        self.assertEqual(profiles[UBUNTU]["colorScheme"], "Campbell")
        self.assertEqual(restored["schemes"], [palette.WT_SCHEME])
        self.assertEqual(len(warnings), 2)

    def test_restore_when_the_profile_is_gone(self):
        installed, record = wt.apply_scheme(settings(), palette.WT_SCHEME, UBUNTU, None)
        installed["profiles"]["list"] = [p for p in installed["profiles"]["list"] if p["guid"] != UBUNTU]
        restored, warnings = wt.restore_scheme(installed, record)
        self.assertEqual(restored["schemes"], [])
        self.assertEqual(len(warnings), 1)

    def test_apply_rejects_a_non_list_schemes(self):
        data = dict(settings(), schemes={})
        with self.assertRaises(ValueError):
            wt.apply_scheme(data, palette.WT_SCHEME, UBUNTU, None)

    def test_manual_snippet(self):
        snippet = wt.manual_snippet(palette.WT_SCHEME, UBUNTU)
        self.assertIn('"name": "Moonlit Candle"', snippet)
        self.assertIn(UBUNTU, snippet)
        self.assertIn('"colorScheme": "Moonlit Candle"', snippet)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest tests.test_wt -v`
Expected: `ImportError: cannot import name 'wt'`.

- [ ] **Step 3: Write the implementation**

`witchy/wt.py`:

```python
"""Windows Terminal: find the current user's settings.json and the profile running us."""
from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

from .records import put_back, snapshot

PACKAGE = "Microsoft.WindowsTerminal_8wekyb3d8bbwe"
USERS_ROOT = Path("/mnt/c/Users")


def windows_username(run: Callable[..., Any] = subprocess.run) -> str | None:
    """The Windows user of this WSL session. Several users can have Windows Terminal installed."""
    try:
        # cwd=/mnt/c keeps cmd.exe from warning about a UNC working directory.
        done = run(["cmd.exe", "/c", "echo %USERNAME%"], capture_output=True, text=True, timeout=5, cwd="/mnt/c")
    except (OSError, subprocess.SubprocessError):
        return None
    name = (done.stdout or "").strip()
    return name if done.returncode == 0 and name and "%" not in name else None


def settings_path_for(user: str, users_root: Path = USERS_ROOT) -> Path:
    return users_root / user / "AppData" / "Local" / "Packages" / PACKAGE / "LocalState" / "settings.json"


def locate_settings(explicit: Path | None, run: Callable[..., Any] = subprocess.run,
                    users_root: Path = USERS_ROOT) -> Path | None:
    if explicit is not None:
        return explicit if explicit.is_file() else None
    user = windows_username(run)
    if not user:
        return None
    path = settings_path_for(user, users_root)
    return path if path.is_file() else None


def _profiles(data: Any) -> list | None:
    if not isinstance(data, dict):
        return None
    profiles = data.get("profiles")
    if isinstance(profiles, list):
        return profiles
    if isinstance(profiles, dict) and isinstance(profiles.get("list"), list):
        return profiles["list"]
    return None


def _profile(data: Any, guid: str) -> dict | None:
    for profile in _profiles(data) or []:
        if isinstance(profile, dict) and str(profile.get("guid", "")).lower() == guid.lower():
            return profile
    return None


def find_profile(data: Any, env: Mapping[str, str]) -> tuple[str | None, str | None]:
    """The profile to theme: WT_PROFILE_ID if it exists, else the one WSL profile named after the distro."""
    profiles = _profiles(data)
    if profiles is None:
        return None, "profiles list not found in Windows Terminal settings"
    wanted = env.get("WT_PROFILE_ID", "").strip()
    if wanted:
        profile = _profile(data, wanted)
        if profile is not None:
            return profile["guid"], None
    distro = env.get("WSL_DISTRO_NAME", "")
    matches = [p for p in profiles if isinstance(p, dict) and distro
               and p.get("source") == "Microsoft.WSL" and p.get("name") == distro]
    if len(matches) == 1:
        return matches[0]["guid"], None
    return None, (f"no profile matches WT_PROFILE_ID={wanted or 'unset'} and found {len(matches)} "
                  f"WSL profiles named {distro!r}")


def _scheme_index(schemes: list, name: str) -> int | None:
    return next((i for i, scheme in enumerate(schemes) if isinstance(scheme, dict) and scheme.get("name") == name), None)


def _scheme_in_use(data: Any, name: str) -> bool:
    holders = list(_profiles(data) or [])
    profiles = data.get("profiles") if isinstance(data, dict) else None
    if isinstance(profiles, dict) and isinstance(profiles.get("defaults"), dict):
        holders.append(profiles["defaults"])
    for holder in holders:
        value = holder.get("colorScheme") if isinstance(holder, dict) else None
        if value == name or (isinstance(value, dict) and name in value.values()):
            return True
    return False


def apply_scheme(data: dict, scheme: dict, guid: str, recorded: dict | None) -> tuple[dict, dict]:
    """Add or replace the scheme and point one profile at it. A reinstall keeps the first record."""
    result = copy.deepcopy(data)
    schemes_key_absent = "schemes" not in result
    schemes = result.setdefault("schemes", [])
    if not isinstance(schemes, list):
        raise ValueError("schemes in Windows Terminal settings is not a list")
    profile = _profile(result, guid)
    if profile is None:
        raise ValueError(f"profile {guid} not found")
    index = _scheme_index(schemes, scheme["name"])
    fresh = {
        "profile_guid": profile["guid"],
        "previous_color_scheme": snapshot(profile, "colorScheme"),
        "previous_scheme": {"value": copy.deepcopy(schemes[index])} if index is not None else {"absent": True},
        "schemes_key_absent": schemes_key_absent,
    }
    record = {key: copy.deepcopy(recorded[key]) if recorded else value for key, value in fresh.items()}
    record["installed_color_scheme"] = scheme["name"]
    if index is None:
        schemes.append(copy.deepcopy(scheme))
    else:
        schemes[index] = copy.deepcopy(scheme)
    profile["colorScheme"] = scheme["name"]
    return result, record


def restore_scheme(data: dict, record: dict) -> tuple[dict, list[str]]:
    """Undo apply_scheme, leaving alone whatever the user changed since."""
    result = copy.deepcopy(data)
    warnings = []
    name = record["installed_color_scheme"]
    profile = _profile(result, record["profile_guid"])
    if profile is None:
        warnings.append(f"Windows Terminal profile {record['profile_guid']} no longer exists; its colour scheme was not restored.")
    elif profile.get("colorScheme") == name:
        put_back(profile, "colorScheme", record["previous_color_scheme"])
    else:
        warnings.append("The Windows Terminal profile colour scheme was changed after install; leaving it as it is.")
    schemes = result.get("schemes")
    index = _scheme_index(schemes, name) if isinstance(schemes, list) else None
    if index is not None:
        previous = record["previous_scheme"]
        if not previous.get("absent"):
            schemes[index] = copy.deepcopy(previous["value"])
        elif _scheme_in_use(result, name):
            warnings.append(f"The Windows Terminal scheme {name!r} is still used by a profile; keeping it.")
        else:
            del schemes[index]
            if record["schemes_key_absent"] and not schemes:
                del result["schemes"]
    return result, warnings


def manual_snippet(scheme: dict, guid: str) -> str:
    body = json.dumps(scheme, indent=4, ensure_ascii=False)
    return (
        'Add this object to the "schemes" list:\n'
        f"{body}\n"
        f'Then, in the profile with "guid": "{guid}", set:\n'
        f'    "colorScheme": "{scheme["name"]}"'
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest discover -s tests -t . -v && /usr/bin/python3.10 -m unittest discover -s tests -t .`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/mmarenas/proyectos/witchy-claude-theme && git add witchy/wt.py tests/test_wt.py && git commit -m "feat: Windows Terminal settings lookup and scheme apply/restore

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Install and uninstall

**Files:**
- Create: `witchy/install.py`
- Test: `tests/test_install.py`

**Interfaces:**
- Consumes: `build.render_outputs`, `build.write_dist`, `build.DIST`, `build.THEME|OUTPUT_STYLE|STATUSLINE|TIPS` (Task 4); `validate.validate_all` (Task 2); `content.load_spinner` (Task 2); `palette.WT_SCHEME` (Task 1); `jsonio.*`, `claude_settings.*` (Task 5); `wt.*` (Task 6).
- Produces:
  - `witchy.install.Context(home: Path, env: Mapping[str, str], out: TextIO, dry_run: bool = False, wt_settings: Path | None = None, python: str | None = None, stamp: str = <now %Y%m%d-%H%M%S>, run: Callable = subprocess.run, dist: Path = <build.DIST at call time>)`
  - `install(ctx: Context) -> int`, `uninstall(ctx: Context) -> int` (0 = ok, 1 = aborted with nothing written)
  - Constants: `RESTART_NOTE`, `WT_SKIP`, `STATE_VERSION = 1`, `DEFAULT_PYTHON = "/usr/bin/python3"`

**Notes on dry-run output.** Existing files that change get a unified diff. Files that would be created or removed get a one-line `create <path> (<n> lines)` or `remove <path>`, so the four new copied files don't flood the terminal. `state.json` is not shown.

- [ ] **Step 1: Write the failing tests**

`tests/test_install.py`:

```python
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import install, validate

UBUNTU = "{05f3f843-450a-55ad-a264-cacf368dafe5}"
CLAUDE_ORIGINAL = {
    "env": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:8787"},
    "statusLine": {"type": "command", "command": "archon statusline", "padding": 0},
    "theme": "dark",
    "agentPushNotifEnabled": True,
}
WT_ORIGINAL = {
    "$help": "https://aka.ms/terminal-documentation",
    "profiles": {"defaults": {}, "list": [
        {"guid": "{61c54bbd-c2c6-5271-96e7-009a87ff44bf}", "name": "Windows PowerShell"},
        {"guid": "{0caa0dad-35be-5f56-a8ff-afceeeaa6101}", "name": "Símbolo del sistema"},
        {"guid": UBUNTU, "name": "Ubuntu", "source": "Microsoft.WSL", "colorScheme": "One Half Dark"},
    ]},
    "schemes": [],
}


def refuse_cmd(*args, **kwargs):
    raise AssertionError("cmd.exe must not run in tests")


class InstallTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.claude = self.home / ".claude"
        self.claude.mkdir(parents=True)
        self.settings = self.claude / "settings.json"
        self.settings.write_text(json.dumps(CLAUDE_ORIGINAL, indent=2) + "\n", encoding="utf-8")
        self.wt = self.root / "wt" / "settings.json"
        self.wt.parent.mkdir()
        # Windows Terminal writes ASCII escapes and 4-space indents.
        self.wt.write_text(json.dumps(WT_ORIGINAL, indent=4) + "\n", encoding="utf-8")

    def ctx(self, dry_run=False, env=None, stamp="20260930-120000"):
        self.out = io.StringIO()
        return install.Context(home=self.home, env={"WT_PROFILE_ID": UBUNTU} if env is None else env, out=self.out,
                               dry_run=dry_run, wt_settings=self.wt, python="/usr/bin/python3", stamp=stamp,
                               run=refuse_cmd, dist=self.root / "dist")

    def snapshot(self):
        files = {}
        for base in (self.home, self.wt.parent):
            for path in sorted(base.rglob("*")):
                if path.is_file() and ".bak-witchy-" not in path.name:
                    files[str(path)] = path.read_bytes()
        return files

    def claude_settings(self):
        return json.loads(self.settings.read_text(encoding="utf-8"))

    def wt_settings(self):
        return json.loads(self.wt.read_text(encoding="utf-8"))

    def ubuntu(self):
        return next(p for p in self.wt_settings()["profiles"]["list"] if p["guid"] == UBUNTU)


class InstallTest(InstallTestCase):
    def test_install_puts_every_piece_in_place(self):
        self.assertEqual(install.install(self.ctx()), 0)
        for rel in ("themes/moonlit-candle.json", "output-styles/witchynibbles.md",
                    "witchy/statusline.py", "witchy/tips.json", "witchy/state.json"):
            self.assertTrue((self.claude / rel).is_file(), rel)
        data = self.claude_settings()
        self.assertEqual(data["theme"], "custom:moonlit-candle")
        self.assertEqual(data["outputStyle"], "WitchyNibbles")
        self.assertEqual(data["spinnerVerbs"]["mode"], "replace")
        self.assertEqual(data["spinnerTipsOverride"]["label"], "Grimoire")
        self.assertEqual(data["env"], CLAUDE_ORIGINAL["env"])
        self.assertTrue(data["agentPushNotifEnabled"])
        self.assertEqual(self.ubuntu()["colorScheme"], "Moonlit Candle")
        self.assertEqual(self.wt_settings()["schemes"][0]["name"], "Moonlit Candle")
        self.assertTrue(list(self.claude.glob("settings.json.bak-witchy-20260930-120000")))
        self.assertTrue(list(self.wt.parent.glob("settings.json.bak-witchy-20260930-120000")))
        self.assertIn(install.RESTART_NOTE, self.out.getvalue())
        self.assertTrue((self.root / "dist" / "claude" / "themes" / "moonlit-candle.json").is_file())

    def test_statusline_command_runs_the_installed_copy(self):
        install.install(self.ctx())
        command = self.claude_settings()["statusLine"]["command"]
        script = self.claude / "witchy" / "statusline.py"
        self.assertEqual(command, f"/usr/bin/python3 -I {script}")
        done = subprocess.run([sys.executable, "-I", str(script)], input=b"{}", capture_output=True, timeout=10)
        self.assertEqual(done.returncode, 0)
        self.assertIn("🌑".encode("utf-8"), done.stdout)

    def test_install_then_uninstall_restores_bytes(self):
        before = self.snapshot()
        install.install(self.ctx())
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 0)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.claude / "witchy").exists())

    def test_install_twice_is_idempotent(self):
        install.install(self.ctx())
        after_first = self.snapshot()
        install.install(self.ctx(stamp="20260930-120500"))
        self.assertEqual(self.snapshot(), after_first)

    def test_reinstall_keeps_the_original_previous_value(self):
        install.install(self.ctx())
        data = self.claude_settings()
        data["theme"] = "light"
        self.settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        install.install(self.ctx(stamp="20260930-120500"))
        state = json.loads((self.claude / "witchy" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["claude_settings"]["keys"]["theme"]["previous"], {"value": "dark"})
        install.uninstall(self.ctx(stamp="20260930-130000"))
        self.assertEqual(self.claude_settings()["theme"], "dark")

    def test_uninstall_keeps_keys_claude_code_added_later(self):
        install.install(self.ctx())
        data = self.claude_settings()
        data["model"] = "opus"
        self.settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        install.uninstall(self.ctx(stamp="20260930-130000"))
        self.assertEqual(self.claude_settings(), dict(CLAUDE_ORIGINAL, model="opus"))

    def test_uninstall_leaves_a_key_the_user_changed(self):
        install.install(self.ctx())
        data = self.claude_settings()
        data["outputStyle"] = "Concise"
        self.settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        install.uninstall(self.ctx(stamp="20260930-130000"))
        self.assertEqual(self.claude_settings()["outputStyle"], "Concise")
        self.assertEqual(self.claude_settings()["theme"], "dark")
        self.assertIn("outputStyle was changed after install", self.out.getvalue())

    def test_dry_run_writes_nothing(self):
        before = self.snapshot()
        self.assertEqual(install.install(self.ctx(dry_run=True)), 0)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / "dist").exists())
        self.assertEqual(list(self.claude.glob("*.bak-witchy-*")), [])
        output = self.out.getvalue()
        self.assertIn('+  "theme": "custom:moonlit-candle",', output)
        self.assertIn("create ", output)
        self.assertIn("Dry run: nothing was written.", output)

    def test_uninstall_dry_run_writes_nothing(self):
        install.install(self.ctx())
        before = self.snapshot()
        self.assertEqual(install.uninstall(self.ctx(dry_run=True, stamp="20260930-130000")), 0)
        self.assertEqual(self.snapshot(), before)

    def test_fresh_home_without_settings(self):
        self.settings.unlink()
        self.assertEqual(install.install(self.ctx()), 0)
        self.assertEqual(self.claude_settings()["theme"], "custom:moonlit-candle")
        install.uninstall(self.ctx(stamp="20260930-130000"))
        self.assertFalse(self.settings.exists())
        self.assertFalse((self.claude / "witchy").exists())

    def test_windows_terminal_with_comments_is_left_alone(self):
        self.wt.write_text('{\n    // my comment\n    "profiles": {"list": []}\n}\n', encoding="utf-8")
        before = self.wt.read_bytes()
        self.assertEqual(install.install(self.ctx()), 0)
        self.assertEqual(self.wt.read_bytes(), before)
        self.assertIn('"colorScheme": "Moonlit Candle"', self.out.getvalue())
        self.assertEqual(self.claude_settings()["theme"], "custom:moonlit-candle")
        state = json.loads((self.claude / "witchy" / "state.json").read_text(encoding="utf-8"))
        self.assertIsNone(state["windows_terminal"])

    def test_no_windows_terminal_profile_skips_terminal(self):
        before = self.wt.read_bytes()
        self.assertEqual(install.install(self.ctx(env={})), 0)
        self.assertEqual(self.wt.read_bytes(), before)
        self.assertIn(install.WT_SKIP, self.out.getvalue())
        self.assertEqual(self.claude_settings()["theme"], "custom:moonlit-candle")

    def test_vscode_terminal_falls_back_to_distro_name(self):
        self.assertEqual(install.install(self.ctx(env={"WSL_DISTRO_NAME": "Ubuntu"})), 0)
        self.assertEqual(self.ubuntu()["colorScheme"], "Moonlit Candle")

    def test_edited_theme_is_backed_up_before_uninstall(self):
        install.install(self.ctx())
        theme = self.claude / "themes" / "moonlit-candle.json"
        theme.write_text('{"name": "Moonlit Candle (mine)"}\n', encoding="utf-8")
        install.uninstall(self.ctx(stamp="20260930-130000"))
        self.assertFalse(theme.exists())
        backups = list(theme.parent.glob("moonlit-candle.json.bak-witchy-*"))
        self.assertEqual(len(backups), 1)
        self.assertIn("(mine)", backups[0].read_text(encoding="utf-8"))

    def test_invalid_claude_settings_aborts(self):
        self.settings.write_text('{\n  // comment\n  "theme": "dark"\n}\n', encoding="utf-8")
        before = self.snapshot()
        self.assertEqual(install.install(self.ctx()), 1)
        self.assertEqual(self.snapshot(), before)

    def test_validation_failure_changes_nothing(self):
        before = self.snapshot()
        failure = validate.Failure("text-contrast", "claude.claude", "#3A2E47", "1.60:1 < 4.5:1")
        with mock.patch("witchy.install.validate.validate_all", return_value=[failure]):
            self.assertEqual(install.install(self.ctx()), 1)
        self.assertEqual(self.snapshot(), before)
        self.assertIn("text-contrast: claude.claude", self.out.getvalue())

    def test_uninstall_without_state(self):
        self.assertEqual(install.uninstall(self.ctx()), 0)
        self.assertIn("Nothing to uninstall", self.out.getvalue())

    def test_uninstall_when_a_copied_file_is_already_gone(self):
        install.install(self.ctx())
        (self.claude / "witchy" / "statusline.py").unlink()
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 0)
        self.assertEqual(self.claude_settings(), CLAUDE_ORIGINAL)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest tests.test_install -v`
Expected: `ImportError: cannot import name 'install'`.

- [ ] **Step 3: Write the implementation**

`witchy/install.py`:

```python
"""install / uninstall: put every piece in place, remember what was there, give it back.

Every file change is planned first, so --dry-run can show it and a real run can
back each file up before touching it. state.json records what each setting held
before; uninstall gives exactly that back, and restores a settings file's
original bytes when nothing else has touched it since.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, TextIO

from . import build, claude_settings, content, jsonio, palette, validate, wt

STATE_VERSION = 1
DEFAULT_PYTHON = "/usr/bin/python3"
RESTART_NOTE = "Restart Claude Code once so it starts watching ~/.claude/themes/"
NEW_SESSION_NOTE = "Start a new Claude Code session to load the output style."
WT_SKIP = "skipping the terminal colour scheme"

# dist/ file -> its home under ~/.claude
COPIES = {
    build.THEME: Path("themes/moonlit-candle.json"),
    build.OUTPUT_STYLE: Path("output-styles/witchynibbles.md"),
    build.STATUSLINE: Path("witchy/statusline.py"),
    build.TIPS: Path("witchy/tips.json"),
}


def _sha(data: bytes | None) -> str | None:
    return None if data is None else hashlib.sha256(data).hexdigest()


def _read(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


class Abort(Exception):
    """Stop before anything is written; the message says why."""


@dataclass
class Change:
    """One file's planned content; ``None`` means absent (before) or deleted (after)."""

    path: Path
    before: bytes | None
    after: bytes | None
    backup: bool = True


@dataclass
class JsonPlan:
    """A planned settings-file rewrite plus what state.json must remember about it."""

    change: Change
    previous: dict | None
    extra: dict

    def entry(self, backup: Path | None) -> dict:
        after = _sha(self.change.after)
        if self.previous:
            # Byte-exact restore stays possible only while every reinstall lands on the same bytes.
            ok = self.previous["byte_restore_ok"] and after == self.previous["installed_sha256"]
            base = {**self.previous, "installed_sha256": after, "byte_restore_ok": ok}
        else:
            existed = self.change.before is not None
            base = {"path": str(self.change.path), "existed": existed,
                    "backup": str(backup) if backup else None, "installed_sha256": after,
                    "byte_restore_ok": not existed or backup is not None}
        return {**base, **self.extra}


@dataclass
class Context:
    home: Path
    env: Mapping[str, str]
    out: TextIO
    dry_run: bool = False
    wt_settings: Path | None = None
    python: str | None = None
    stamp: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d-%H%M%S"))
    run: Callable[..., Any] = subprocess.run
    dist: Path = field(default_factory=lambda: build.DIST)

    @property
    def claude_dir(self) -> Path:
        return self.home / ".claude"

    @property
    def state_path(self) -> Path:
        return self.claude_dir / "witchy" / "state.json"

    def say(self, message: str) -> None:
        print(message, file=self.out)


def _python(ctx: Context) -> str:
    # Not the pyenv shim: its version follows each project's .python-version.
    if ctx.python:
        return ctx.python
    return DEFAULT_PYTHON if Path(DEFAULT_PYTHON).is_file() else sys.executable


def _load_state(ctx: Context) -> dict | None:
    if not ctx.state_path.is_file():
        return None
    try:
        state, _ = jsonio.read_json(ctx.state_path)
    except jsonio.StrictJsonError as exc:
        raise Abort(f"{exc}\nThe state file is damaged; fix or remove {ctx.state_path} by hand.") from exc
    if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
        raise Abort(f"{ctx.state_path} has an unknown format; fix or remove it by hand.")
    return state


def _plan_copies(ctx: Context, outputs: dict[str, str], state: dict | None) -> tuple[list, list[Change]]:
    earlier = {Path(entry["path"]): entry for entry in (state or {}).get("files", [])}
    files, changes = [], []
    for rel, target in COPIES.items():
        path = ctx.claude_dir / target
        before = _read(path)
        after = outputs[rel].encode("utf-8")
        previous = earlier.get(path)
        ours = previous is not None and _sha(before) == previous["installed_sha256"]
        changes.append(Change(path, before, after, backup=not ours))
        files.append((path, previous, after))
    return files, changes


def _plan_claude_settings(ctx: Context, state: dict | None) -> JsonPlan:
    path = ctx.claude_dir / "settings.json"
    before = _read(path)
    data, text = {}, None
    if before is not None:
        try:
            data, text = jsonio.read_json(path)
        except jsonio.StrictJsonError as exc:
            raise Abort(f"{exc}\n{path} is not plain JSON; nothing was changed.") from exc
        if not isinstance(data, dict):
            raise Abort(f"{path} does not hold a JSON object; nothing was changed.")
    previous = state["claude_settings"] if state else None
    desired = claude_settings.desired_keys(ctx.home, _python(ctx), content.load_spinner()["verbs"])
    new_data, keys = claude_settings.apply_keys(data, desired, previous["keys"] if previous else None)
    after = jsonio.dumps_like(new_data, text).encode("utf-8")
    return JsonPlan(Change(path, before, after), previous, {"keys": keys})


def _plan_windows_terminal(ctx: Context, state: dict | None) -> JsonPlan | None:
    previous = (state or {}).get("windows_terminal")
    path = wt.locate_settings(ctx.wt_settings, run=ctx.run)
    if path is None:
        ctx.say(f"Windows Terminal settings.json not found; {WT_SKIP}.")
        return None
    try:
        data, text = jsonio.read_json(path)
    except jsonio.StrictJsonError:
        ctx.say(f"{path} is not plain JSON (comments?), so it was left untouched. Add this by hand:")
        ctx.say(wt.manual_snippet(palette.WT_SCHEME, ctx.env.get("WT_PROFILE_ID") or "<your WSL profile guid>"))
        return None
    guid, reason = wt.find_profile(data, ctx.env)
    if guid is None:
        ctx.say(f"Windows Terminal: {reason}; {WT_SKIP}.")
        return None
    if previous and (previous["path"] != str(path) or previous["profile_guid"].lower() != guid.lower()):
        ctx.say(f"Windows Terminal: already installed for profile {previous['profile_guid']} in {previous['path']}; "
                f"run uninstall first to move it; {WT_SKIP}.")
        return None
    try:
        new_data, record = wt.apply_scheme(data, palette.WT_SCHEME, guid, previous)
    except ValueError as exc:
        ctx.say(f"Windows Terminal: {exc}; {WT_SKIP}.")
        return None
    after = jsonio.dumps_like(new_data, text).encode("utf-8")
    return JsonPlan(Change(path, path.read_bytes(), after), previous, record)


def _show(ctx: Context, changes: list[Change]) -> None:
    for change in changes:
        if change.before == change.after:
            continue
        if change.before is None:
            ctx.say(f"create {change.path} ({len(change.after.splitlines())} lines)")
        elif change.after is None:
            ctx.say(f"remove {change.path}")
        else:
            before = change.before.decode("utf-8", "replace").splitlines(keepends=True)
            after = change.after.decode("utf-8", "replace").splitlines(keepends=True)
            ctx.out.writelines(difflib.unified_diff(before, after, f"{change.path} (now)", f"{change.path} (after)"))
            ctx.say("")


def _apply(ctx: Context, changes: list[Change]) -> dict[Path, Path]:
    backups: dict[Path, Path] = {}
    for change in changes:
        if change.before == change.after:
            continue
        if change.before is not None and change.backup:
            backups[change.path] = jsonio.backup(change.path, ctx.stamp)
        if change.after is None:
            change.path.unlink(missing_ok=True)
            verb = "removed"
        else:
            jsonio.write_atomic_bytes(change.path, change.after)
            verb = "created" if change.before is None else "updated"
        note = f" (backup: {backups[change.path]})" if change.path in backups else ""
        ctx.say(f"{verb} {change.path}{note}")
    return backups


def install(ctx: Context) -> int:
    failures = validate.validate_all()
    if failures:
        for failure in failures:
            ctx.say(str(failure))
        ctx.say("Validation failed; nothing was changed.")
        return 1
    try:
        state = _load_state(ctx)
        outputs = build.render_outputs()
        files, changes = _plan_copies(ctx, outputs, state)
        claude = _plan_claude_settings(ctx, state)
    except Abort as exc:
        ctx.say(str(exc))
        return 1
    terminal = _plan_windows_terminal(ctx, state)
    changes += [claude.change] + ([terminal.change] if terminal else [])
    themes_existed = (ctx.claude_dir / "themes").is_dir()
    if ctx.dry_run:
        _show(ctx, changes)
        ctx.say("Dry run: nothing was written.")
        return 0

    build.write_dist(outputs, ctx.dist)
    backups = _apply(ctx, changes)
    previous_terminal = (state or {}).get("windows_terminal")
    new_state = {
        "version": STATE_VERSION,
        "files": [
            {"path": str(path),
             "backup": previous["backup"] if previous else (str(backups[path]) if path in backups else None),
             "installed_sha256": _sha(after)}
            for path, previous, after in files
        ],
        "claude_settings": claude.entry(backups.get(claude.change.path)),
        "windows_terminal": terminal.entry(backups.get(terminal.change.path)) if terminal else previous_terminal,
    }
    jsonio.write_atomic_bytes(ctx.state_path, (json.dumps(new_state, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    ctx.say("Moonlit Candle installed. Undo with: python3 -m witchy uninstall")
    if not themes_existed:
        ctx.say(RESTART_NOTE)
    ctx.say(NEW_SESSION_NOTE)
    return 0


def _restore_copy(entry: dict) -> Change | None:
    path = Path(entry["path"])
    current = _read(path)
    original = _read(Path(entry["backup"])) if entry.get("backup") else None
    if current is None and original is None:
        return None
    # Keep a copy of anything the user edited (for example with /theme → Ctrl+E) before it goes.
    edited = current is not None and _sha(current) != entry["installed_sha256"]
    return Change(path, current, original, backup=edited)


def _restore_json(entry: dict, restore: Callable[[dict], tuple[dict, list[str]]], warnings: list[str]) -> Change | None:
    path = Path(entry["path"])
    current = _read(path)
    if current is None:
        warnings.append(f"{path} no longer exists; nothing to restore there.")
        return None
    if entry["byte_restore_ok"] and _sha(current) == entry["installed_sha256"]:
        if not entry["existed"]:
            return Change(path, current, None, backup=False)
        original = _read(Path(entry["backup"])) if entry.get("backup") else None
        if original is not None:
            return Change(path, current, original, backup=False)
    try:
        data, text = jsonio.read_json(path)
    except jsonio.StrictJsonError:
        warnings.append(f"{path} is no longer plain JSON; restore it by hand from {entry.get('backup')}.")
        return None
    if not isinstance(data, dict):
        warnings.append(f"{path} no longer holds a JSON object; restore it by hand from {entry.get('backup')}.")
        return None
    restored, notes = restore(data)
    warnings.extend(notes)
    return Change(path, current, jsonio.dumps_like(restored, text).encode("utf-8"))


def uninstall(ctx: Context) -> int:
    try:
        state = _load_state(ctx)
    except Abort as exc:
        ctx.say(str(exc))
        return 1
    if state is None:
        ctx.say("Nothing to uninstall: ~/.claude/witchy/state.json not found.")
        return 0
    warnings: list[str] = []
    changes = [_restore_copy(entry) for entry in state["files"]]
    claude = state["claude_settings"]
    changes.append(_restore_json(claude, lambda data: claude_settings.restore_keys(data, claude["keys"]), warnings))
    terminal = state.get("windows_terminal")
    if terminal:
        changes.append(_restore_json(terminal, lambda data: wt.restore_scheme(data, terminal), warnings))
    planned = [change for change in changes if change is not None]
    if ctx.dry_run:
        _show(ctx, planned)
        for warning in warnings:
            ctx.say(warning)
        ctx.say("Dry run: nothing was written.")
        return 0
    _apply(ctx, planned)
    ctx.state_path.unlink(missing_ok=True)
    witchy_dir = ctx.state_path.parent
    if witchy_dir.is_dir() and not any(witchy_dir.iterdir()):
        witchy_dir.rmdir()
    for warning in warnings:
        ctx.say(warning)
    ctx.say("Moonlit Candle uninstalled.")
    return 0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest discover -s tests -t . -v && /usr/bin/python3.10 -m unittest discover -s tests -t .`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/mmarenas/proyectos/witchy-claude-theme && git add witchy/install.py tests/test_install.py && git commit -m "feat: install and uninstall with backups, state and dry-run

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: CLI and README

**Files:**
- Create: `witchy/__main__.py`, `README.md`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `validate.validate_all` (Task 2); `build.build`, `build.DIST` (Task 4); `install.Context`, `install.install`, `install.uninstall` (Task 7).
- Produces: `witchy.__main__.main(argv: list[str] | None = None) -> int`, runnable as `python3 -m witchy <command>`.

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:

```python
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import build
from witchy.__main__ import main

ROOT = Path(__file__).resolve().parent.parent
UBUNTU = "{05f3f843-450a-55ad-a264-cacf368dafe5}"


class CliTest(unittest.TestCase):
    def test_validate_command_passes(self):
        done = subprocess.run([sys.executable, "-m", "witchy", "validate"], cwd=ROOT, capture_output=True, text=True,
                              timeout=60)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("all checks passed", done.stdout)

    def test_build_command_writes_dist(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(build, "DIST", Path(tmp)):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["build"]), 0)
            self.assertTrue((Path(tmp) / build.THEME).is_file())

    def test_install_and_uninstall_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, wt_file = Path(tmp) / "home", Path(tmp) / "wt.json"
            home.mkdir()
            wt_file.write_text(json.dumps({"profiles": {"list": [
                {"guid": UBUNTU, "name": "Ubuntu", "source": "Microsoft.WSL"}]}}, indent=4) + "\n")
            env = {"HOME": str(home), "WT_PROFILE_ID": UBUNTU}
            with mock.patch.dict(os.environ, env), mock.patch.object(build, "DIST", Path(tmp) / "dist"), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["install", "--wt-settings", str(wt_file)]), 0)
                self.assertTrue((home / ".claude" / "themes" / "moonlit-candle.json").is_file())
                self.assertEqual(main(["uninstall"]), 0)
            self.assertFalse((home / ".claude" / "themes" / "moonlit-candle.json").exists())

    def test_command_is_required(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main([])
        self.assertEqual(raised.exception.code, 2)

    def test_help_lists_commands(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            main(["--help"])
        for command in ("validate", "build", "install", "uninstall"):
            self.assertIn(command, out.getvalue())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest tests.test_cli -v`
Expected: `ModuleNotFoundError: No module named 'witchy.__main__'`.

- [ ] **Step 3: Write the implementation**

`witchy/__main__.py`:

```python
"""python3 -m witchy validate | build | install [--dry-run] [--wt-settings PATH] | uninstall [--dry-run]"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import build, install, validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m witchy", description="Moonlit Candle theme for Claude Code")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="check palette contrast, tokens and content")
    commands.add_parser("build", help="validate, then write dist/")
    install_parser = commands.add_parser("install", help="build and put every piece in place")
    install_parser.add_argument("--dry-run", action="store_true", help="show the changes without writing anything")
    install_parser.add_argument("--wt-settings", type=Path, help="path to Windows Terminal settings.json")
    uninstall_parser = commands.add_parser("uninstall", help="give back everything install changed")
    uninstall_parser.add_argument("--dry-run", action="store_true", help="show the changes without writing anything")
    args = parser.parse_args(argv)

    if args.command == "validate":
        failures = validate.validate_all()
        for failure in failures:
            print(failure)
        if not failures:
            print("Moonlit Candle: all checks passed")
        return 1 if failures else 0
    if args.command == "build":
        failures = build.build()
        for failure in failures:
            print(failure)
        if failures:
            print("Validation failed; dist/ was not written.")
            return 1
        print(f"Wrote {build.DIST}")
        return 0
    ctx = install.Context(home=Path.home(), env=os.environ, out=sys.stdout, dry_run=args.dry_run,
                          wt_settings=getattr(args, "wt_settings", None))
    return install.install(ctx) if args.command == "install" else install.uninstall(ctx)


if __name__ == "__main__":
    sys.exit(main())
```

`README.md`:

````markdown
# Moonlit Candle

Tema para Claude Code inspirado en [WitchyNibbles/Spellbound-Themes](https://github.com/WitchyNibbles/Spellbound-Themes): fondo berenjena de Moonlit, acento oro de vela y rosa para los permisos.

Incluye:

- Tema `moonlit-candle` para Claude Code (`~/.claude/themes/`)
- Esquema "Moonlit Candle" para el perfil WSL de Windows Terminal
- Verbos y tips del spinner (`spinnerVerbs`, `spinnerTipsOverride`)
- Output style "WitchyNibbles", que solo cambia el tono de las respuestas en el chat
- Status line con fases lunares según el contexto usado, límites de 5 h / 7 d y git

## Uso

```sh
/usr/bin/python3 -m witchy validate           # contraste, tokens y contenido
/usr/bin/python3 -m witchy install --dry-run  # muestra los cambios sin escribir
/usr/bin/python3 -m witchy install
/usr/bin/python3 -m witchy uninstall
```

`install` hace una copia `*.bak-witchy-<fecha>` de cada fichero que modifica y guarda los valores anteriores en `~/.claude/witchy/state.json`. `uninstall` los restaura. Si un `settings.json` no es JSON estricto (comentarios), no se toca y se muestra el fragmento para añadirlo a mano.

Después de instalar, reinicia Claude Code.

## Desarrollo

```sh
/usr/bin/python3 -m unittest discover -s tests -t . -v
/usr/bin/python3.10 -m unittest discover -s tests -t .
```

Los colores están en `witchy/palette.py`. El diseño está en `docs/superpowers/specs/2026-09-30-moonlit-candle-design.md`.
````

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest discover -s tests -t . -v && /usr/bin/python3.10 -m unittest discover -s tests -t . && /usr/bin/python3 -m witchy validate`
Expected: all PASS; last line `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
cd /home/mmarenas/proyectos/witchy-claude-theme && git add witchy/__main__.py README.md tests/test_cli.py && git commit -m "feat: command line entry point and README

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Rollout on the real machine (controller + human, no subagent)

This task touches the real `~/.claude/settings.json` and Windows Terminal settings. The controller runs it in the main session, with the user watching. It is not delegated.

**Files:** none created. Reads `~/.claude/settings.json`, `/mnt/c/Users/mmarenas/AppData/Local/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json`.

- [ ] **Step 1: Full verification**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m unittest discover -s tests -t . && /usr/bin/python3.10 -m unittest discover -s tests -t . && /usr/bin/python3 -m witchy validate`
Expected: `OK` twice, then `Moonlit Candle: all checks passed`.

- [ ] **Step 2: Dry run against the real machine and show it to the user**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m witchy install --dry-run`
Expected:
- 4 `create` lines under `~/.claude/`.
- A diff of `~/.claude/settings.json` touching only `theme`, `statusLine`, `spinnerVerbs`, `spinnerTipsOverride` and `outputStyle`.
- A diff of the Windows Terminal `settings.json` adding the scheme and changing only the Ubuntu profile's `colorScheme` from `One Half Dark`. Because WT writes arrays on their own line, re-serialising may also reformat `"key": \n [` into `"key": [`. That formatting is expected; the uninstall byte-restore covers it.

Show the output to the user and **wait for an explicit go** before Step 3.

- [ ] **Step 3: Install**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m witchy install`
Then verify:
`/usr/bin/python3 -c "import json,os; d=json.load(open(os.path.expanduser('~/.claude/settings.json'))); print(d['theme'], d['outputStyle'], d['statusLine']['command'])"`
Expected: `custom:moonlit-candle WitchyNibbles /usr/bin/python3 -I /home/mmarenas/.claude/witchy/statusline.py`

- [ ] **Step 4: Visual acceptance by the user**

Ask the user to open a new Claude Code session in the Ubuntu tab and check:
1. `/theme` shows "Moonlit Candle" selected.
2. The background is aubergine.
3. The spinner shows witchy verbs and `Grimoire:` tips.
4. The status line shows 🕯️ model·effort ⋆ moon % ⋆ 5h ⋆ 7d ⋆ 📜 repo ⎇ branch.
5. Chat replies have the WitchyNibbles voice, while files and commits stay plain.

Collect any tweaks. Color changes go in `witchy/palette.py`, followed by `install` again. Iterate until the user approves.

- [ ] **Step 5: Uninstall check, then reinstall if the user wants to keep it**

Run: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m witchy uninstall`
Verify: `~/.claude/settings.json` has `"theme": "dark"` and the archon `statusLine` command again; the Ubuntu profile has `"colorScheme": "One Half Dark"`; `~/.claude/witchy/` is gone.
Then, if the user wants to keep the theme: `cd /home/mmarenas/proyectos/witchy-claude-theme && /usr/bin/python3 -m witchy install`.
