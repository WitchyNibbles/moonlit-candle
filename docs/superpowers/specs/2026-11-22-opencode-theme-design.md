# Moonlit Candle for OpenCode

Date: 2026-11-22. Status: decided by the project manager from the brief and the sources below.

## Intent

The user asked for an OpenCode theme based on the Moonlit Candle Claude Code theme. It should keep
the same feel (aubergine night background, candle-gold accents, pink for permissions), pass the same
contrast bar `python3 -m witchy validate` already enforces, and install like every other piece of
witchyterm: a component with install, uninstall, doctor and tests.

Target: opencode-ai 1.18.34 (the user's work harness), checked on the 1.19.0 binary installed on
this machine too. OpenCode 2 is reported on, not targeted.

## Goals, non-goals, anti-goals

- Goal: `python3 -m witchy install` writes `~/.config/opencode/themes/moonlit-candle.json` and sets
  `"theme": "moonlit-candle"` in `~/.config/opencode/tui.json`; `uninstall` gives both back;
  `doctor` reports drift.
- Goal: every colour lives in `witchy/palette.py`, and validate holds the OpenCode theme to the
  repo's bar (4.5:1 for text, 3:1 for borders and rules).
- Non-goal: the WitchyNibbles voice, spinner verbs or status line in OpenCode (OpenCode has no
  output styles; the brief makes the colour theme alone the default).
- Non-goal: OpenCode 2's `cli.json` and its new theme format.
- Non-goal: project-level `.opencode/` files, and anything at the user's work.
- Anti-goal: an install that fails or exits 2 on a machine without OpenCode.

## Facts (sources)

OpenCode 1.18.34, read from the tag's source (`anomalyco/opencode@v1.18.34`):

- Theme files: `<config>/themes/*.json`, then `.opencode/themes/*.json` up the tree; the name is the
  file name (`packages/tui/src/context/theme.tsx:38-57`). `<config>` is `$XDG_CONFIG_HOME/opencode`,
  default `~/.config/opencode` (docs `themes.mdx`, "Hierarchy").
- Theme JSON: `{"$schema": "https://opencode.ai/theme.json", "defs"?: {...}, "theme": {...}}`. A
  value is a `#hex`, a name in `defs`/`theme`, an ANSI index, `"none"`, or `{dark, light}`; a bare
  value serves both modes (`packages/tui/src/theme/index.ts:243-264`).
- 50 required colour keys plus optional `selectedListItemText` (falls back to `background`),
  `backgroundMenu` (falls back to `backgroundElement`) and `thinkingOpacity` (index.ts:92-127,
  274-293).
- Selection: `"theme"` in `tui.json` or `tui.jsonc`, global and per project, deep-merged with
  `.jsonc` read after `.json` (`packages/opencode/src/config/tui.ts`, `paths.ts`). `opencode.json`'s
  old `theme` key is only migrated to a new `tui.json` when none exists (`tui-migrate.ts`).
- Where colours show (`packages/tui/src/`):
  - the permission card: `backgroundPanel` with a `warning` border, selected option on `warning`
    (`routes/session/permission.tsx:634-683`);
  - selected rows in dialogs: `primary` behind `selectedListItemText` (`ui/dialog-select.tsx:543,676`);
  - the input box sits on `backgroundElement`, and its border is `border`, tinted by the agent
    colour (`component/prompt/index.tsx:1289-1365`);
  - agents cycle `secondary, accent, success, warning, primary, error, info`
    (`context/local.tsx:83-91`);
  - toasts: `backgroundPanel` with a border in the variant's colour (`ui/toast.tsx:30-44`);
  - thinking text is `warning` at `thinkingOpacity` (`routes/session/index.tsx:1661`).

OpenCode 2 (`@opencode/cli` 2.3.2): the docs describe a new format (`base` plus `light`/`dark` hue
palettes) chosen with `theme.name` in `~/.config/opencode/cli.json`, and `themes/` is still read.
The 2.3.2 binary holds a V1 reader ("Invalid V1 theme color", "not found in defs or theme"), so a
1.x theme file probably loads, but nothing here ran it.

## Approaches

1. **A new `opencode` component, theme built from palette.py (chosen).** Same shape as `claude`:
   build renders the JSON into `dist/`, the component copies it home and sets one key in
   `tui.json`. One source of colours, validated, variant-aware, uninstallable.
2. A hand-written JSON file in `content/`, copied as is. Less code, but colours drift from
   palette.py and validate cannot see them.
3. Theme file only, no `tui.json` change. Safer for a user's own `tui.json`, but the Claude
   component sets its theme, so the user would expect the same here; `/theme` still works either way.

## Design

### Colours

`palette.OPENCODE` maps all 52 colour keys (the 50 required plus `selectedListItemText` and
`backgroundMenu`) to `#RRGGBB`. No `defs`, no `{dark, light}`: one bare value each, like the Claude
theme, which is dark only. `thinkingOpacity` stays at OpenCode's default.

The colours come from `CLAUDE_OVERRIDES` and, for syntax, from the VS Code
"WitchyNibbles Moonlit Candle" theme in Spellbound-Themes
(`themes/WitchyNibbles-color-theme-moonlit-candle.json`, `tokenColors`):

| OpenCode key | Colour | From |
| :- | :- | :- |
| background | `#0D0916` | `BACKGROUND` |
| backgroundPanel | `#1D1230` | `userMessageBackground` |
| backgroundElement, backgroundMenu | `#271A3D` | `userMessageBackgroundHover` |
| text | `#F3EAF7` | `FOREGROUND` |
| textMuted | `#A99AB9` | `inactive` |
| primary | `#FFD477` | `claude` (candle gold) |
| secondary | `#B99AFF` | `planMode` / `suggestion` |
| accent | `#77D9FF` | `bashBorder` / `ide` |
| warning | `#FF67B7` | `permission`: OpenCode draws the permission card in `warning` |
| error | `#FF6B9F` | `error` |
| success | `#74E8B8` | `success` |
| info | `#9C8CFF` | `rainbow_indigo` |
| selectedListItemText | `#0D0916` | `inverseText` |
| border | `#6E5A80` | `promptBorder` |
| borderActive | `#B99AFF` | VS Code `focusBorder` |
| borderSubtle | `#38234D` | VS Code `panel.border` |
| diffAdded / diffRemoved | `#74E8B8` / `#FF6B9F` | `success` / `error` |
| diffHighlightAdded / Removed | `#A8F2D4` / `#FFA3C2` | the rainbow shimmers |
| diffContext, diffLineNumber | `#A99AB9` | `inactive` |
| diffHunkHeader | `#B99AFF` | `merged` |
| diffAddedBg / diffRemovedBg | `#153042` / `#441632` | Claude `diffAdded` / `diffRemoved` |
| diffContextBg | `#120C1F` | VS Code `sideBar.background` |
| diffAddedLineNumberBg / Removed | `#111D2A` / `#2A1022` | Claude `diff*Dimmed` |
| markdownHeading, markdownListItem | `#FFD477` | gold |
| markdownStrong | `#FFB86B` | `warning` (orange) |
| markdownEmph | `#F6B5DD` | VS Code parameter |
| markdownLink, markdownListEnumeration, markdownImage | `#77D9FF` | cyan |
| markdownLinkText, markdownImageText | `#9CCBFF` | VS Code property |
| markdownCode | `#74E8B8` | VS Code string |
| markdownBlockQuote | `#B99AFF` | lavender |
| markdownText, markdownCodeBlock | `#F3EAF7` | text |
| markdownHorizontalRule | `#6E5A80` | `subtle` |
| syntaxComment | `#A99AB9` | VS Code comment |
| syntaxKeyword | `#B99AFF` | VS Code keyword |
| syntaxFunction | `#FFD477` | VS Code function |
| syntaxVariable | `#F3EAF7` | VS Code variable |
| syntaxString | `#74E8B8` | VS Code string |
| syntaxNumber | `#FF9BD7` | VS Code number |
| syntaxType | `#77D9FF` | VS Code type |
| syntaxOperator, syntaxPunctuation | `#D3B4FF` | VS Code operator |

A colour that fails a contrast rule below is changed for OpenCode only (darker surface or lighter
text, staying in the same hue); the rule is never weakened.

### Contrast rules (validate)

New groups in `witchy/tokens.py` (or a sibling `OPENCODE_*` block), checked by a new
`validate_opencode()` that `validate_all()` calls for every variant:

- Key set: exactly the 52 keys; unknown or missing keys fail, like Claude tokens. Format `#RRGGBB`
  uppercase.
- `background` must equal the variant's `background`, `text` its `foreground`.
- Surfaces: `background`, `backgroundPanel`, `backgroundElement`, `backgroundMenu`.
- Text, 4.5:1 on every surface: `primary, secondary, accent, error, warning, success, info, text,
  textMuted`, every `markdown*` except `markdownHorizontalRule`, every `syntax*`, `diffContext`,
  `diffHunkHeader`, `diffLineNumber`, `diffAdded`, `diffRemoved`.
- Diff surfaces, 4.5:1: `text` and every `syntax*` on `diffAddedBg`, `diffRemovedBg` and
  `diffContextBg`; `diffAdded` and `diffHighlightAdded` on `diffAddedBg`; `diffRemoved` and
  `diffHighlightRemoved` on `diffRemovedBg`; `diffLineNumber` on `diffContextBg`,
  `diffAddedLineNumberBg` and `diffRemovedLineNumberBg`.
- On accent fills, 4.5:1: `selectedListItemText` on `primary`, `secondary`, `accent`, `warning`,
  `error`, `success`, `info`.
- Secondary, 3:1 on `background`: `border`, `borderActive`, `markdownHorizontalRule`.
- Exempt, with a reason: `borderSubtle` (a divider line, not information).

### Build

`build.OPENCODE_THEME = "opencode/themes/moonlit-candle.json"`, rendered as
`{"$schema": "https://opencode.ai/theme.json", "theme": {...}}` from the variant's `opencode` field
(a new `Variant` field, so `mood` repaints it like the rest).

### The `opencode` component

Install order: `claude, opencode, font, windows-terminal, tide, fish`.

- Config dir: `$XDG_CONFIG_HOME/opencode` when that variable is an absolute path, else
  `~/.config/opencode`, the same rule OpenCode uses.
- Plan:
  - copy the theme to `<config>/themes/moonlit-candle.json` (with `file_change`, as `claude`
    does);
  - set `"theme": "moonlit-candle"` in `<config>/tui.json` with `records.apply_keys`, recording the
    old value. A missing `tui.json` is created holding only that key.
- Always installs, whether or not OpenCode is on this machine: two small files, and no skipped
  component (so no exit 2) on a box without OpenCode. When `opencode` is not on `PATH`, a note says
  the theme is ready for when it is installed.
- A `tui.json` that is not plain JSON (OpenCode reads it as JSONC) is not rewritten: the theme file
  still installs, and a warning says to add `"theme": "moonlit-candle"` by hand. A `<config>/tui.jsonc`
  is never edited: it is read after `tui.json`, so when it sets `theme` a warning names it.
- Uninstall: restore `tui.json` (removed when witchy created it, key by key otherwise), then remove
  the theme file or give back the one it replaced, with the shared `restore_json` and
  `restore_copy` helpers.
- Doctor:
  - `✗` when the theme file changed or is missing, or when `tui.json`'s `theme` no longer holds
    the witchy value;
  - `⚠` when `tui.jsonc` overrides it;
  - `·` when `opencode` is not on `PATH`.
  Each fix is `python3 -m witchy install --only opencode`.

### Docs

README: the intro and the "It installs" list name OpenCode; the "Components, in install order" line
(checked by `tests/test_cli.py`); doctor rows for `opencode`; one line on OpenCode 2 (copy the theme
file works there probably, and the selection goes in `cli.json` as `{"theme": {"name":
"moonlit-candle"}}`, not tested). The archify diagram is already marked "(proposed)" and lacks
Tide, so it is left alone.

## Left to the builder

Test names and file layout, following `tests/test_components_claude.py`; the exact wording of notes
and warnings; any colour tweak a contrast rule forces (report it).
