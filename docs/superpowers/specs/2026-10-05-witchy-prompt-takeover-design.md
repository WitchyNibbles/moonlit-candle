# Prompt Takeover: a witchier Tide that installs the same way on every PC

- **Date:** 2026-10-05
- **Status:** draft, pending review
- **Use:** personal (eimi, WSL2 Ubuntu inside Windows Terminal, fish 3.7.0)
- **Builds on:** [`2026-10-02-shell-ritual-design.md`](2026-10-02-shell-ritual-design.md). Everything there still holds unless this spec changes it. Section numbers below such as "ritual 5.2" point into that spec.

## 1. Problem

On a second PC (WSL Ubuntu, fish), `python3 -m witchy install` themed Windows Terminal and the greeting, but the prompt kept its old look. On this PC the prompt still shows the old "pastel princess" icons. Causes found in the code and on this machine:

1. witchy does not install Tide. Without it, the fish component records `skipped: Tide not found` and the run exits 2. The only signal is one line in the summary. The second PC has no Tide.
2. witchy sets only Tide's colours and item lists (`palette.TIDE`, 31 variables). Tide has 161 universal variables. The icons, caps, separators, time format and the colours of unused items come from `~/change_this_bitch.sh` (🎀 🏰 🌷 💖 ✨ 🍰 and round caps), and witchy never touches them.
3. doctor checks the 31 variables only. It does not check that Tide's `fish_prompt` is the active one, and its snapshot erases globals in its own process, so a `set -g tide_*` in `config.fish` or a starship init line would pass as ✓.
4. Windows Terminal keeps `PastelOneDark` as `profiles.defaults` scheme and on the PowerShell and cmd profiles.

## 2. Goal

After `python3 -m witchy install` on any PC that has fish:

- fisher and Tide 6.1.1 are present (installed by witchy when missing).
- Tide is the active prompt, and every Tide variable holds witchy's value.
- The prompt looks the same on every PC: slanted caps, gold `❯` caret, the witchy glyph map (section 6).
- No pastel-princess value remains in the prompt or Windows Terminal.
- If any of that did not happen, install exits non-zero with a banner that cannot be missed, and doctor shows a ✗ with the fix.

## 3. Decisions (from the 2026-10-05 grilling session)

| # | Decision |
| :- | :- |
| D1 | Missing fisher or Tide: witchy installs them, pinned (fisher 4.4.5, Tide 6.1.1). |
| D2 | witchy owns every `tide_*` universal variable, not only colours. Values outside the spec are replaced. |
| D3 | Any other prompt owner is taken over: backed up, disabled, reported. |
| D4 | Pastel purge: Tide variables (by D2), Windows Terminal `PastelOneDark`, `~/change_this_bitch.sh` (one-off on this PC), repo fixtures and docs. `state.json` "previous" values stay as recorded, so uninstall on this PC still gives back the old prompt. |
| D5 | Prompt icons are emoji, one code point each: no variation selector (U+FE0F), no ZWJ (U+200D), no skin-tone modifier. Enforced by validate. |
| D6 | Caret is the text glyph `❯` in candle gold `#FFD477`, rose-red `#FF6B9F` on failure. |
| D7 | Slanted caps and separators (Tide's own "Slanted" preset). |
| D8 | Layout unchanged: two lines, frame on, transient prompt on. |
| D9 | Unused Tide items get witchy icons and palette colours too. |
| D10 | Drift (for example after `tide configure`): doctor reports ✗; `install` puts the spec back. Nothing re-applies at shell start. |
| D11 | One glyph table in `palette.py`, shared by the prompt, the status line and the greeting. 🕯️ stays in the status line and greeting (D5 applies to the prompt only). |
| D12 | Proof: doctor checks the whole prompt chain; a skipped or failed component makes install print a banner and exit non-zero. |
| D13 | Uninstall removes fisher and Tide only when witchy installed them. |
| D14 | Unwritable-directory icon is 🪦. doctor prints a glyph test line so each PC can confirm it renders. |

## 4. Scope

In:

1. New `tide` component: bootstrap fisher and Tide, take over other prompt owners (section 5).
2. Full Tide variable set in the palette, the glyph map and the slanted look (section 6).
3. Shared glyph table used by `statusline.py` and the ritual (section 7).
4. Windows Terminal: purge `PastelOneDark` (section 8).
5. doctor checks and the install banner (section 9).
6. Uninstall changes (section 10).
7. Validation rules (section 11) and tests (section 12).
8. Repo purge of pastel fixtures and docs (section 13).

Out:

- Installing fish itself, or anything that needs `sudo`. Missing fish stays a loud failure with the install command.
- A new greeting layout or new greeting content. The greeting only takes its glyphs from the shared table.
- The hidden duplicate "Ubuntu" profile (still FiraCode) and Windows Terminal Preview.
- `~/projects/pastel-princess/` (a separate VS Code theme project).

## 5. The `tide` component

New file `witchy/components/tide.py`. Component order becomes `claude`, `font`, `windows-terminal`, `tide`, `fish`. `fish` keeps the fish files and the Tide variables; `tide` makes sure Tide is installed and is the only prompt.

### 5.1 Bootstrap

`plan` runs one `fish -c` call that reports: fish version, whether `fisher` is a function and its version, whether `tide` is a function and `tide --version`, the path of `functions --details fish_prompt`, and the universal list `_fisher_ilancosman_2f_tide_files`.

| Found | Action |
| :- | :- |
| fish missing | `skipped: fish not found` (install fish: `sudo apt install fish`). |
| fisher missing | Download `https://raw.githubusercontent.com/jorgebucaran/fisher/4.4.5/functions/fisher.fish` with `fonts.fetch_url`, check its pinned SHA-256, cache it in `~/.cache/witchy/`, then `fish -c 'source <file>; fisher install jorgebucaran/fisher@4.4.5'`. |
| Tide missing | `fisher install ilancosman/tide@v6.1.1`. |
| Tide present, version ≠ 6.1.1 | `fisher install ilancosman/tide@v6.1.1`; the previous `fish_plugins` line for Tide is recorded. |
| Tide 6.1.1 present | Nothing. |

- fisher needs `curl`. Missing `curl` → `failed: curl not found (sudo apt install curl)` before anything is downloaded.
- After fisher installs Tide, witchy checks `tide --version` is `6.1.1` and that the SHA-256 of the installed `functions/fish_prompt.fish` equals a pinned value. A mismatch is `failed: Tide 6.1.1 did not install as expected`. This is the trust check for the Tide tarball, which fisher downloads by tag.
- Network failure, a SHA mismatch or a fisher error → `failed: <reason>`. Nothing that ran before is undone; the record keeps what was installed so far (same rule as ritual 3.3).
- The entry records `installed_fisher: bool`, `installed_tide: bool`, `previous_tide_plugin: str | null`.
- `--dry-run` lists the downloads and fisher commands and runs none of them.

### 5.2 Taking over other prompt owners

Runs in `plan` (detection) and `apply` (changes), before the bootstrap in the same `apply`, because fisher refuses to overwrite files it does not own.

| Owner | Detection | Takeover |
| :- | :- | :- |
| A hand-written `functions/fish_prompt.fish` | The file exists and is not in `_fisher_ilancosman_2f_tide_files`. | Moved to `fish_prompt.fish.bak-witchy-<stamp>`. |
| Another fisher plugin that ships `fish_prompt.fish` (pure, hydro, bobthefish, …) | Its `_fisher_<plugin>_files` lists `fish_prompt.fish`. | `fisher remove <plugin>`; the plugin name is recorded. |
| `starship init fish`, `oh-my-posh init fish`, `set -g`/`set -gx`/`set --global` of a `tide_*` name | A matching line in `config.fish` or in a `conf.d/*.fish` that is neither witchy's nor fisher-managed. | The file is backed up, then each matching line is prefixed with `# witchy-disabled: `. |
| `function fish_prompt` inside `config.fish` or `conf.d` | Matching line. | Not edited: a multi-line block cannot be commented safely. `failed: config.fish defines fish_prompt at line N; remove that function`. |

Every takeover prints one line, for example `tide: disabled starship init in ~/.config/fish/config.fish (backup: …)`.

## 6. The prompt

### 6.1 Every variable

`palette.TIDE` grows from 31 entries to every universal variable Tide 6.1.1 defines (161 names on this PC; the exact list comes from Tide 6.1.1's `functions/tide/configure/configs/rainbow.fish` plus `icons.fish`, and is checked into `tests/fixtures/tide-6.1.1-variables.txt`).

- A variable this spec does not name keeps Tide 6.1.1's Rainbow-preset default (for example `tide_pwd_markers`, `tide_git_truncation_length`, `tide_prompt_min_cols`).
- A universal `tide_*` variable that is not in Tide 6.1.1's list is erased and recorded, so uninstall can give it back. Tide's private `_tide_*` variables are never touched.

### 6.2 Shape

| Variable | Value |
| :- | :- |
| `tide_left_prompt_items` | `moon pwd git newline character` (unchanged) |
| `tide_right_prompt_items` | `status cmd_duration jobs time` (adds `jobs`: shown only when jobs run in the background) |
| `tide_left_prompt_prefix` | `` (Slanted tail) |
| `tide_left_prompt_suffix` | `` (Slanted head) |
| `tide_right_prompt_prefix` | `` (Slanted head) |
| `tide_right_prompt_suffix` | `` (Slanted tail) |
| `tide_left_prompt_separator_diff_color` | `` |
| `tide_right_prompt_separator_diff_color` | `` |
| `tide_left_prompt_separator_same_color`, `tide_right_prompt_separator_same_color` | Tide 6.1.1's Rainbow defaults |
| `tide_left_prompt_frame_enabled`, `tide_right_prompt_frame_enabled` | `true` |
| `tide_prompt_transient_enabled`, `tide_prompt_add_newline_before` | `true` |
| `tide_prompt_icon_connection` | `·` |
| `tide_prompt_color_frame_and_connection` | `38234D` (deep violet) |

### 6.3 Glyph map (visible items)

| Item | Variable | Glyph |
| :- | :- | :- |
| moon | (the `moon` item) | today's phase 🌑…🌘 (unchanged) |
| pwd | `tide_pwd_icon` | 🧹 |
| pwd at home | `tide_pwd_icon_home` | 🔮 |
| pwd unwritable | `tide_pwd_icon_unwritable` | 🪦 |
| git | `tide_git_icon` | 🌿 |
| status ok | `tide_status_icon` | 🧪 |
| status fail | `tide_status_icon_failure` | 💀 |
| cmd duration | `tide_cmd_duration_icon` | 🔥 |
| jobs | `tide_jobs_icon` | 🐈 |
| time | `tide_time_format` | `%H:%M 🦉` |
| caret | `tide_character_icon` | `❯` |
| vi modes | `tide_character_vi_icon_default` / `_replace` / `_visual` | `❮` / `▶` / `V` |

Caret colours: `tide_character_color` `FFD477`, `tide_character_color_failure` `FF6B9F`. The other visible colours stay as in ritual 5.2.

### 6.4 Unused items

All unused items use background `1D1230` and text `A99AB9` (muted, already a validated pair). Their icons:

| Item | Icon | Item | Icon | Item | Icon |
| :- | :- | :- | :- | :- | :- |
| aws | 🏺 | gcloud | ⛅ | private_mode | 🎭 |
| bun | 🥟 | go | 🐹 | pulumi | 🧬 |
| crystal | 💠 | java | ☕ | python | 🐍 |
| direnv | 🍃 | kubectl | 🎡 | ruby | 💎 |
| distrobox | 📦 | nix_shell | 🧊 | rustc | 🦀 |
| docker | 🐳 | node | 🍄 | shlvl | 🌀 |
| elixir | 💧 | os | 🐧 | terraform | 🧱 |
| php | 🐘 | toolbox | 🧰 | zig | ⚡ |

`context` and `vi_mode` have no emoji: `context` keeps Tide's text, `vi_mode` keeps Tide's letters, both in palette colours. `tide_direnv_*_denied` and the `context` root/ssh colours use rose-red `FF6B9F` text on `1D1230`.

## 7. Shared glyph table

`palette.GLYPHS: dict[str, str]` is the single source of icons:

```python
GLYPHS = {
    "candle": "🕯️",      # status line model, greeting sabbat day; never in the prompt (D5)
    "scroll": "📜",      # status line repo
    "branch": "🌿",      # status line branch, Tide git icon
    "dirty": "✦",
    "separator": "⋆",
    "cwd": "🧹", "home": "🔮", "unwritable": "🪦",
    "ok": "🧪", "fail": "💀", "duration": "🔥", "jobs": "🐈", "time": "🦉",
    "caret": "❯",
}
```

- `palette.TIDE` takes its icons from `GLYPHS`; the unused-item icons in 6.4 live in TIDE directly.
- `statusline.py` is copied on its own and imports nothing, so `build.py` rewrites a `# BEGIN GLYPHS` / `# END GLYPHS` block in it the same way it rewrites `PALETTE`. The branch glyph changes from `⎇` to 🌿.
- The ritual takes `candle`, `dirty` and `separator` from the table through `ritual/data.json`. `ritual/layout.WIDE` becomes the moon phases plus every table emoji, so width stays right.

## 8. Windows Terminal: purge PastelOneDark

`palette.PURGED_SCHEMES = ("PastelOneDark",)`. The `windows-terminal` component, in the same settings write it already makes:

1. Sets `profiles.defaults.colorScheme` to `Moonlit Candle` if it names a purged scheme.
2. Removes `colorScheme` from every profile whose value is a purged scheme, so it inherits the default.
3. Deletes the purged scheme definitions from `schemes`.

Each previous value (defaults key, each profile's key by GUID, each scheme object) is recorded in the component entry with the first-install-wins rule. Uninstall puts them back, and leaves alone anything the user changed since (same rule as `restore_scheme`). The backup of `settings.json` is the one the component already takes.

## 9. Proof

### 9.1 doctor

The `tide` component's `check`:

- ✓/✗ fisher found; Tide is version 6.1.1.
- ✓/✗ the active `fish_prompt` is Tide's (`functions --details fish_prompt` is in `_fisher_ilancosman_2f_tide_files`).
- ✓/✗ no other prompt owner from 5.2 is active.
- An info line: `glyph test: 🧹 🔮 🪦 🌿 🧪 💀 🔥 🐈 🦉 ❯ — each should be one clear symbol`.

The `fish` component's `check`:

- The snapshot no longer erases globals. It reads each name twice: the universal value and the value a fresh interactive shell sees (`fish -i -c` with `WITCHY_DOCTOR=1` set, which makes `conf.d/witchy.fish` skip the greeting and the sky job). A global hiding a universal is ✗ `tide_X is overridden by a global in config.fish or conf.d`.
- ✓/✗ every `tide_*` in the spec matches (all 161, not 31); ✗ lists the names that drifted, fix `python3 -m witchy install --only fish`.
- ✗ any universal `tide_*` not in Tide 6.1.1's list.

`windows-terminal` `check`: ✗ if any purged scheme is still defined or referenced.

### 9.2 Install banner

When any selected component ends `skipped:` or `failed:`, install prints, after the summary line:

```
✗✗✗ witchy is NOT fully installed ✗✗✗
  tide: failed: curl not found (sudo apt install curl)
  fish: skipped: Tide not found
Fix the lines above, then run: python3 -m witchy install
```

Exit codes stay 0 / 1 / 2. `fish` now plans as `skipped: Tide not ready` whenever `tide` did not end `ok`, instead of setting variables Tide cannot use.

## 10. Uninstall

Reverse order: `fish` (variables, files), then `tide`:

1. Put back each file it commented out, from its backup (existing `restore_copy` rule: leave a file the user changed since).
2. Move back a hand-written `fish_prompt.fish` it moved aside, after Tide is removed.
3. `fisher install <plugin>` for each prompt plugin it removed.
4. If `previous_tide_plugin` is set: `fisher install <that>`. Else if `installed_tide`: `fisher remove ilancosman/tide`.
5. If `installed_fisher`: `fisher remove jorgebucaran/fisher`.

On this PC (Tide and fisher were already there) uninstall restores the recorded variables, which are the pastel ones (D4).

## 11. Validation additions (`validate.py`)

1. **Prompt glyphs:** every `*_icon` value and `tide_time_format` in TIDE holds at most one emoji; none contains U+FE0F, U+200D or U+1F3FB–U+1F3FF. Text glyphs (`❯`, `·`, Nerd Font private-use caps) are allowed.
2. **Completeness:** TIDE's names equal `tests/fixtures/tide-6.1.1-variables.txt` (checked by a test, since the fixture is not shipped).
3. **No pastel:** no TIDE value and no `WT_SCHEME` value is one of the recorded pastel hex values (`FFB7C5`, `F8A4C9`, `FF6EC7`, `FBAED2`, `F5C6E0`, `FFC8DD`, …) or one of the pastel icons (🎀 🏰 🌷 💖 💔 ✨ 🍰 🌸). The list lives in `validate.py` as `PASTEL`.
4. **Contrast:** each new visible pair (caret on the terminal background, muted on `1D1230` for unused items, frame `38234D` against `0D0916` as non-text ≥ 1.5:1) joins the existing pairs.
5. **Width:** every emoji in `GLYPHS` is in `ritual/layout.WIDE` or East-Asian-Wide.

## 12. Tests

- Unit tests stub every `fish` call and download, as the current component tests do.
- `test_components_tide.py`: each bootstrap row of 5.1, each takeover row of 5.2, uninstall steps 1–5, dry run runs nothing, SHA mismatch fails.
- `test_components_fish.py`: the global-shadow check, the 161-name drift check, skip when `tide` did not end `ok`.
- `test_wt.py`: purge and restore of defaults, per-profile overrides and scheme definitions; a user change after install is left alone.
- `test_prompt_palette.py`: rules 11.1–11.5.
- `test_runner.py`: the banner appears for skipped and failed components and not for a clean run.
- Integration (`test_fish_integration.py`): real fish with a local fake fisher and a fake Tide 6.1.1 tree served from a temp dir, so CI needs no network. One opt-in test (`WITCHY_NETWORK_TESTS=1`) bootstraps the real fisher and Tide into a throwaway `HOME`.

## 13. Repo purge

- Test fixtures: `FFB7C5` becomes Tide 6.1.1's default pwd background (`3465A4`), in `tests/test_components_fish.py`, `tests/test_fish_integration.py` and `tests/test_install.py`. `tests/fixtures/state-v1.json` uses `Campbell` instead of `PastelOneDark`.
- `2026-10-02-shell-ritual-design.md`: line 438 ("the pink 🌸 Tide prompt") becomes "the prompt that was there before install"; section 2 "Out" drops "Installing fish, fisher, Tide" with a pointer to this spec.
- Plans under `docs/superpowers/plans/` are records of past work and stay as written.

## 14. Choices made while writing this spec (not covered by the grilling)

1. `jobs` joins the right prompt items, because the agreed glyph map gives it 🐈. Without it the icon never shows.
2. A `function fish_prompt` block in `config.fish` is reported as a failure, not edited (5.2): commenting one line of a block breaks the file.
3. Another fisher prompt plugin is removed with `fisher remove` and re-installed on uninstall (5.2).
4. All unused items share one colour pair (6.4) instead of one colour each.
5. Old plans keep their pastel mentions; only the live spec is edited (13).
6. doctor's interactive-shell read needs a new `WITCHY_DOCTOR` guard in `conf.d/witchy.fish` (9.1).

## 15. One-off steps on this PC (not installer code)

1. Show `~/change_this_bitch.sh` to the user, then delete it.
2. Run `python3 -m witchy install`, open a new tab, run `python3 -m witchy doctor`: no ✗.

## 16. Acceptance criteria

1. A PC with fish but no fisher or Tide: install exits 0; a new tab shows the section 6 prompt; doctor shows no ✗.
2. This PC: after install, no `tide_*` variable holds a value from validate's `PASTEL` list; Windows Terminal has no `PastelOneDark`; doctor shows no ✗; the glyph test line renders every symbol.
3. A `starship init fish | source` line in `config.fish`: install comments it out, keeps a backup, and the Tide prompt shows; uninstall gives the line back.
4. No network and no fisher: install exits 2 with the banner; doctor shows ✗ with the fix.
5. `tide configure` after install: doctor ✗ lists drifted names; install restores them.
6. Uninstall on the PC from criterion 1 removes Tide and fisher; on this PC it leaves both and restores the recorded variables.
7. `/usr/bin/python3 -m unittest discover -s tests -t . -v` passes on Python 3.10 and 3.12 in CI.
