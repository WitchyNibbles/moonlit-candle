# Moonlit Candle for OpenCode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use coven:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** an `opencode` component that installs a Moonlit Candle OpenCode theme built from `witchy/palette.py`, selects it in OpenCode's `tui.json`, and gives both back on uninstall.

**Architecture:** palette.py gains `OPENCODE` (52 keys) and a `Variant.opencode` field; validate.py holds it to the contrast rules; build.py renders it into `dist/opencode/themes/moonlit-candle.json`; a new `witchy/components/opencode.py` copies it home and sets one key in `tui.json`, shaped like `witchy/components/claude.py`.

**Tech Stack:** Python 3.10+, stdlib only, `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-22-opencode-theme-design.md` (read it first: the colour table and the contrast rules are there, verbatim values).

## Global Constraints

- Stdlib only; no new dependency. Runs on `/usr/bin/python3` and `/usr/bin/python3.10`.
- Colours are `#RRGGBB` uppercase, defined once in `witchy/palette.py`.
- Theme name `moonlit-candle`; theme file `<config>/themes/moonlit-candle.json`; selection key `"theme"` in `<config>/tui.json`.
- `<config>` = `$XDG_CONFIG_HOME/opencode` when `ctx.env["XDG_CONFIG_HOME"]` is an absolute path, else `ctx.home / ".config/opencode"`. Never read `os.environ` directly: use `ctx.env`.
- Install order: `claude, opencode, font, windows-terminal, tide, fish`.
- No contrast rule may be weakened to make a colour pass; change the OpenCode colour instead and report it.
- Tests never touch the real home: temp dirs only, `env` passed explicitly. The component runs no subprocess; it finds `opencode` with `shutil.which("opencode", path=ctx.env.get("PATH", ""))` (an empty string, never `None`, so the real PATH is never searched in tests).
- Commits: `git -c user.name=WitchyNibbles -c user.email=eimimartinezarenas@gmail.com commit ...`, conventional message, no Co-Authored-By trailer, no "Generated with" line.

## Review Focus

1. An existing `tui.json` with other keys (`keybinds`, `$schema`): install keeps them and its formatting; uninstall gives back exactly the old `theme` (or removes the key when there was none). Test in Task 2.
2. A `tui.json` with comments (JSONC): install does not abort and does not rewrite it; the theme file still lands; a warning names the file and the line to add. Test in Task 2.
3. A home with no `~/.config/opencode` and no `opencode` on PATH: install succeeds (component ok, not skipped), with a note. Test in Task 2.
4. `XDG_CONFIG_HOME` set (absolute) vs relative/empty: the right config dir is used. Test in Task 2.
5. Reinstall after the user ran `/theme` and picked another theme: OpenCode keeps that in its own kv store, not in `tui.json`, so nothing to detect; but a user who edited `tui.json`'s `theme` gets a doctor `✗` and uninstall leaves their value with a warning. Test in Task 2.

---

### Task 1: OpenCode colours, contrast rules and the built theme file

**Files:**
- Modify: `witchy/palette.py` (new `OPENCODE` dict after `CLAUDE_OVERRIDES`, with a comment naming the Spellbound VS Code theme as the syntax source; new `Variant.opencode: dict[str, str] = field(default_factory=dict)`; `midnight` gets `opencode=OPENCODE`)
- Modify: `witchy/tokens.py` (an OpenCode block: key groups below, with its source URL `https://github.com/anomalyco/opencode/blob/v1.18.34/packages/tui/src/theme/index.ts`)
- Modify: `witchy/validate.py` (new `validate_opencode`, called from `validate_all` for every variant)
- Modify: `witchy/build.py` (`OPENCODE_THEME = "opencode/themes/moonlit-candle.json"`, rendered in `render_outputs`)
- Test: `tests/test_palette.py`, `tests/test_validate.py`, `tests/test_build.py`

**Interfaces:**
- Produces: `palette.OPENCODE: dict[str, str]`; `Variant.opencode`; `tokens.OPENCODE_ALL: frozenset[str]` (52 keys) plus groups `OPENCODE_SURFACES`, `OPENCODE_TEXT`, `OPENCODE_DIFF_PAIRS` (tuple of `(fg_keys, bg_key)`), `OPENCODE_ON_ACCENT = "selectedListItemText"`, `OPENCODE_ACCENT_FILLS`, `OPENCODE_SECONDARY`, `OPENCODE_EXEMPT: dict[str, str]`; `validate.validate_opencode(theme: Mapping[str, Any], background: str, foreground: str) -> list[Failure]`; `build.OPENCODE_THEME: str`, whose output text is `{"$schema": "https://opencode.ai/theme.json", "theme": {...}}` via `_json`.

Groups (spec, "Contrast rules"): surfaces `background, backgroundPanel, backgroundElement, backgroundMenu`; text (4.5 on every surface) `primary, secondary, accent, error, warning, success, info, text, textMuted`, every `markdown*` except `markdownHorizontalRule`, every `syntax*`, `diffContext, diffHunkHeader, diffLineNumber, diffAdded, diffRemoved`; diff pairs (4.5) `text` + every `syntax*` on each of `diffAddedBg, diffRemovedBg, diffContextBg`, `diffAdded, diffHighlightAdded` on `diffAddedBg`, `diffRemoved, diffHighlightRemoved` on `diffRemovedBg`, `diffLineNumber` on `diffContextBg, diffAddedLineNumberBg, diffRemovedLineNumberBg`; on-accent (4.5) `selectedListItemText` on `primary, secondary, accent, warning, error, success, info`; secondary (3.0 on `background`) `border, borderActive, markdownHorizontalRule`; exempt `borderSubtle: "a divider line, not information"`. Every key must be in exactly one role or be a surface/diff background, so `OPENCODE_ALL` is their union.

- [ ] **Step 1: Write the failing tests**
  - `test_palette.py`: `test_opencode_has_every_theme_key` (`set(palette.OPENCODE) == tokens.OPENCODE_ALL`, `len(tokens.OPENCODE_ALL) == 52`); `test_opencode_keeps_the_candle_feel` (`OPENCODE["background"] == palette.BACKGROUND`, `["text"] == palette.FOREGROUND`, `["primary"] == CLAUDE_OVERRIDES["claude"]`, `["warning"] == CLAUDE_OVERRIDES["permission"]`); midnight `opencode is palette.OPENCODE`.
  - `test_validate.py`, each breaking one value with `dict(palette.OPENCODE, key=...)` and asserting the rule name and item in `validate_opencode(...)`: `test_opencode_passes`, `test_opencode_text_on_panel_fails` (`textMuted="#3A3050"` → `text-contrast` naming `textMuted` on `backgroundPanel`), `test_opencode_diff_text_fails` (`diffRemovedBg="#B04070"`), `test_opencode_selected_text_fails` (`selectedListItemText="#FFFFFF"` → `on-accent-contrast` on `primary`), `test_opencode_border_fails` (`border="#2A1D3A"` → `secondary-contrast`), `test_opencode_border_subtle_is_exempt` (`borderSubtle="#0E0A17"` passes), `test_opencode_unknown_and_missing_keys` (an extra `"foo"` → `unknown-token`; a dropped `syntaxType` → `missing-token`), `test_opencode_bad_format` (`"#ffd477"` → `format`), `test_opencode_background_must_match` (`background="#000000"` → `consistency`); extend `test_every_variant_is_validated` so a fake variant's broken `opencode` fails `validate_all`.
  - `test_build.py`: add `build.OPENCODE_THEME` to `test_outputs_cover_every_artifact`; `test_opencode_theme_file` (parses; `$schema == "https://opencode.ai/theme.json"`; `theme == palette.OPENCODE`; no `defs`; every value a string); `VariantBuildTest` renders the fake variant's `opencode`.

- [ ] **Step 2: Run to see them fail**
  Run: `/usr/bin/python3 -m unittest tests.test_palette tests.test_validate tests.test_build`
  Expected: errors on `palette.OPENCODE` / `validate_opencode` / `build.OPENCODE_THEME`.

- [ ] **Step 3: Implement** the palette dict with the spec's table values (all pass today: the PM checked every pair), the token groups, `validate_opencode` built on the existing `_contrast` helper and `Failure` rule names (`format`, `unknown-token`, `missing-token`, `consistency`, `text-contrast`, `background-contrast` for diff pairs, `on-accent-contrast`, `secondary-contrast`), item names prefixed `opencode.` like `claude.`/`wt.`, and the build output.

- [ ] **Step 4: Run the tests and validate**
  Run: `/usr/bin/python3 -m unittest discover -s tests -t .` → `OK`; `/usr/bin/python3 -m witchy validate` → `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit** `feat: build a Moonlit Candle theme for OpenCode from the palette`

### Task 2: the `opencode` component, registration and docs

**Files:**
- Create: `witchy/components/opencode.py`
- Modify: `witchy/components/__init__.py` (insert `OpenCodeComponent()` after `ClaudeComponent()`)
- Modify: `README.md` (line 3 intro; "It installs" bullet `The moonlit-candle OpenCode theme (~/.config/opencode/themes/), selected in tui.json`; line 31 components line; doctor rows for `opencode`; one sentence for OpenCode 2 per spec "Docs")
- Test: create `tests/test_components_opencode.py`; update `tests/test_components_fish.py::test_fish_is_a_component_name`; any end-to-end install/uninstall test that runs every component and pins counts or file lists (report each change and why)

**Interfaces:**
- Consumes: `build.OPENCODE_THEME` and `ctx.outputs[build.OPENCODE_THEME]` from Task 1.
- Produces: `class OpenCodeComponent` with `name = "opencode"` and the component protocol (`plan`, `apply`, `restore`, `check`) from `witchy/components/base.py`; module helpers `config_dir(ctx) -> Path`, `THEME = "moonlit-candle"`, notes/warnings as module constants (`NO_OPENCODE_NOTE`, `JSONC_WARNING`, `TUI_JSONC_WARNING`) so tests assert them by name.

Behaviour (spec, "The opencode component"): copy with `file_change`; `tui.json` via `jsonio.read_json` + `records.apply_keys(data, {"theme": THEME}, previous)` + `jsonio.dumps_like`, recorded as a `JsonPlan` the way `ClaudeComponent._plan_settings` does; a missing `tui.json` is created as `{"theme": "moonlit-candle"}`; a non-strict `tui.json` → no settings change, a warning with the line to add, theme file still installed, component result ok-with-warning (follow how `windows_terminal.py:74-80` handles `StrictJsonError`), and no settings record in state, so doctor reports `✗ … theme not selected in <path>`; a `tui.jsonc` holding a `theme` key → warning at install and `⚠` in doctor; `opencode` not on PATH → `NO_OPENCODE_NOTE` at install and a `·` info line in doctor. Restore: settings first, then the copy, with `restore_json` + `records.restore_keys` and `restore_copy`. Check: `✗` on changed/missing theme file or drifted `theme` key, ok lines otherwise, `backup_checks`; every fix `fix_command("opencode")`.

- [ ] **Step 1: Write the failing tests** in `tests/test_components_opencode.py` (temp home, `Context` built like `tests/test_components_claude.py:26-31`, `env` explicit):
  `test_install_writes_the_theme_and_selects_it` (file bytes equal `ctx.outputs[build.OPENCODE_THEME]`; `tui.json` == `{"theme": "moonlit-candle"}`); `test_install_keeps_other_tui_keys_and_uninstall_restores_the_old_theme` (`{"$schema": "https://opencode.ai/tui.json", "theme": "tokyonight", "keybinds": {"leader": "ctrl+x"}}` round-trips to the same parsed data); `test_uninstall_removes_a_tui_json_it_created` (file gone; theme file gone; `themes/` dir may stay); `test_uninstall_gives_back_a_theme_file_it_replaced`; `test_jsonc_tui_json_is_left_alone` (bytes unchanged, theme file present, warning `JSONC_WARNING` printed, doctor `fail` line names the path); `test_tui_jsonc_theme_is_reported` (warning + doctor `warn`); `test_no_opencode_anywhere_still_installs` (empty home, `env={"PATH": ""}` → `NO_OPENCODE_NOTE`, plan not skipped; doctor `info`); `test_opencode_on_path_gives_no_note` (a fake executable `opencode` in a temp bin dir on `PATH`); `test_xdg_config_home` (absolute → used; `"relative/dir"` → `~/.config/opencode`); `test_check_ok`, `test_check_drift_theme_key` (user sets `"theme": "nord"` → `fail` naming `theme`, and uninstall then keeps `nord` with a warning), `test_check_missing_theme_file`; `test_reinstall_keeps_the_first_previous_value`; `test_dry_run_writes_nothing` through `runner.install` with `only=("opencode",)`.
  Update `test_fish_is_a_component_name` to `("claude", "opencode", "font", "windows-terminal", "tide", "fish")`.

- [ ] **Step 2: Run to see them fail**
  Run: `/usr/bin/python3 -m unittest tests.test_components_opencode tests.test_components_fish tests.test_cli`
  Expected: import error for `witchy.components.opencode`; the names and README tests fail.

- [ ] **Step 3: Implement** `witchy/components/opencode.py`, register it, update README.

- [ ] **Step 4: Run every test**
  Run: `/usr/bin/python3 -m unittest discover -s tests -t .` and `/usr/bin/python3.10 -m unittest discover -s tests -t .` → both `OK`; `/usr/bin/python3 -m witchy validate` → all checks passed.

- [ ] **Step 5: Commit** `feat: install the OpenCode theme as the opencode component`
