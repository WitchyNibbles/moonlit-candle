# Prompt Takeover: a witchier Tide that installs the same way on every PC

- **Date:** 2026-10-05
- **Revision:** 2 (folds in the [CEO review](../../reviews/2026-10-05-prompt-takeover-ceo-review.md))
- **Status:** revision 1 approved; revision 2 pending review
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

From the CEO review (approach C, scope expansion):

| # | Decision |
| :- | :- |
| D15 | `install --fresh` installs missing apt packages and offers `chsh` after one prompt (section 15.1). |
| D16 | `preview` draws the prompt from the palette without installing (section 15.2). |
| D17 | The caret takes the sabbat colour on a sabbat day and the day before (section 15.3). |
| D18 | `doctor --fix` re-installs the components doctor marks ✗ (section 15.4). |
| D19 | `fish` checks Tide's readiness itself; it never depends on this run's `tide` result. |
| D20 | Commands carry their own timeout; fisher and download output goes to `~/.cache/witchy/install.log`. |
| D21 | Every fisher and Tide file is checked against `content/pins.json`. |
| D22 | A symlinked fish config file is never edited. |
| D23 | Tide's defaults are generated data; `palette.TIDE` holds only witchy's overrides. |
| D24 | A weekly CI job runs the real download path. |

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
9. `install --fresh`, `preview`, the seasonal caret and `doctor --fix` (section 15).

Out:

- Running `sudo` without `--fresh`. Without it, missing fish stays a loud failure with the install command.
- `witchy fingerprint` (declined in the CEO review).
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
- **Pins (D21):** `content/pins.json` holds the SHA-256 of the bootstrap `fisher.fish` and of every file fisher 4.4.5 and Tide 6.1.1 install. After each `fisher install`, witchy hashes each file listed in `_fisher_<plugin>_files`. A mismatch runs `fisher remove <plugin>` and ends `failed: <plugin> files do not match the pinned release`. The pins are generated by `scripts/pins.py` from the real releases and checked in. `tide --version` must also print `6.1.1`.
- **Timeouts and log (D20):** `Command` gains `timeout` (default 5 s, as today). Downloads and `fisher install` use 120 s. Their stdout and stderr are appended to `~/.cache/witchy/install.log` (capped at 200 KB, oldest run dropped first), and a failure reads `failed: could not install Tide (exit 1): <last stderr line> (details: ~/.cache/witchy/install.log)`.
- Network failure, a SHA mismatch or a fisher error → `failed: <reason>`. Nothing that ran before is undone; the record keeps what was installed so far (same rule as ritual 3.3).
- The entry records `installed_fisher: bool`, `installed_tide: bool`, `previous_tide_plugin: str | null`, `removed_plugins: list[str]`, `disabled_files: list[file record]` (the existing record shape, with backup), `moved_prompt: file record | null`.
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

Edge cases:

- A line already starting with `# witchy-disabled: ` is left alone, so a second run changes nothing.
- A matching line that ends in `\` (continued) fails like a `function fish_prompt` block, naming file and line.
- A file whose path is a symlink (for example into a dotfiles repo) is never edited (D22): `failed: config.fish is a symlink to <target>; disable line N there yourself`.
- Line endings and bytes are kept exactly: files are read and written as bytes, lines split on `\n`, non-UTF-8 bytes kept (`surrogateescape`).
- A disabled line the user turns back on is drift: doctor ✗, and install disables it again.
- A missing or empty `config.fish` or `conf.d` has nothing to take over; that is not an error.

## 6. The prompt

### 6.1 Every variable

witchy now sets every universal variable Tide 6.1.1 defines (161 names on this PC). Defaults and taste are kept apart (D23):

- `content/tide-6.1.1-defaults.json` holds Tide 6.1.1's Rainbow-preset values, generated once by `scripts/tide_defaults.py` from Tide's `functions/tide/configure/configs/rainbow.fish` and `icons.fish`, and checked in.
- `palette.TIDE` holds only witchy's overrides (sections 6.2–6.4 and the colours from ritual 5.2).
- `build.tide(variant)` merges them. A test checks the merge has exactly the names in the defaults file and every override names one of them.
- A variable this spec does not name keeps the default (for example `tide_pwd_markers`, `tide_git_truncation_length`, `tide_prompt_min_cols`).
- witchy also sets the universal `fish_emoji_width` to `2`, which is how Windows Terminal draws emoji. Without it fish guesses per terminal. It is recorded and restored like a Tide variable.
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
- ✓/✗ every fisher and Tide file matches `content/pins.json` (D21).
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

Exit codes stay 0 / 1 / 2.

`fish` checks Tide itself (D19), from its own snapshot: Tide is installed, `tide --version` is `6.1.1`, and the active `fish_prompt` is Tide's. If not, it plans as `skipped: Tide not ready (run: python3 -m witchy install --only tide)` and sets no variable. This works the same with `--only fish` and with `doctor --fix`.

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
2. **Completeness:** every key in `palette.TIDE` is a name in `content/tide-6.1.1-defaults.json` (a typo fails validation instead of creating a stray variable).
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
- Integration (`test_fish_integration.py`): real fish with a local fake fisher and a fake Tide 6.1.1 tree served from a temp dir, so pushes need no network. One opt-in test (`WITCHY_NETWORK_TESTS=1`) bootstraps the real fisher and Tide into a throwaway `HOME` and checks the pins.
- CI (D24): pushes run the offline suite as today. `.github/workflows/network.yml` runs the opt-in test weekly (cron) and on manual dispatch.
- `test_fresh.py`: package list, the prompt, a refused prompt, `chsh` offered only when the login shell is not fish, apt failure.
- `test_preview.py`: golden files `tests/golden/prompt-*.txt` for each sample state.
- Seasonal caret: fixed dates for a sabbat day, the day before, an ordinary day, and a stale or damaged cache file; a fish integration test that `conf.d/witchy.fish` sets the global only from today's file.
- `doctor --fix`: picks only witchy-fixable components, runs them, re-checks, exit codes.
- Takeover edge cases from 5.2: second run, `\` continuation, symlink, CRLF, non-UTF-8.

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

## 15. Additions from the CEO review

### 15.1 `install --fresh` (D15)

Runs before validation and the lock, and only with `--fresh`:

1. Lists which of `fish`, `curl`, `eza` are missing (`shutil.which`).
2. If any are, asks once: `sudo apt install fish curl eza? [y/N]` (only the missing ones). Yes runs `sudo apt-get install -y <packages>` with the terminal attached so sudo can ask for the password. No or a failed command → exit 1, nothing else runs.
3. If the login shell (`getent passwd $USER`) is not fish, asks `make fish your login shell (chsh -s <fish>)? [y/N]` and runs `chsh` on yes. A refusal is not an error.
4. Continues into the normal install.

Without a terminal on stdin, `--fresh` exits 1 with `--fresh needs a terminal to ask before using sudo`. `--fresh --dry-run` lists what it would ask and runs nothing.

### 15.2 `preview` (D16)

`python3 -m witchy preview [--variant NAME]` prints the left and right prompt as fish would draw them, in 24-bit colour, from `build.tide(variant)`, for these sample states: home, a project with dirty git, an unwritable directory, a failed command with duration, background jobs. It needs neither fish nor Tide, writes nothing and exits 0. It is a sketch: Tide's truncation and padding rules are copied for the samples, not run. It lives in `witchy/preview.py`.

### 15.3 Seasonal caret (D17)

- The daily sky job (ritual 4.5) also writes `~/.cache/witchy/caret`: `<YYYY-MM-DD> <HEX> <sabbat>` when today or tomorrow is a sabbat, else `<YYYY-MM-DD>` alone. Colours come from `palette.RITUAL` (the sabbat colours, already contrast-checked against the background).
- `conf.d/witchy.fish` reads that file with `read` (no Python) and, only if its date is today and it holds a colour, runs `set -g tide_character_color <HEX>`. The universal value stays gold. The failure colour is not changed.
- A missing, stale or damaged file leaves the caret gold. A write failure goes to `ritual.log` like other sky-job errors.
- doctor: the global-shadow check (9.1) accepts `tide_character_color` when its global equals the colour in today's caret file. doctor shows one line: `caret: gold` or `caret: samhain FFB86B (today's cache)`, and ⚠ when the cache is older than today.

### 15.4 `doctor --fix` (D18)

1. Runs doctor as usual.
2. Collects the components with a ✗ whose fix is `python3 -m witchy install --only <component>`.
3. Runs `install --only <those, in component order>`, then doctor again.
4. Fixes that are not witchy commands (`sudo apt …`, removing a `function fish_prompt` block, a symlinked file) are printed, never run.

Exit 0 when the second doctor has no ✗, else 1.

## 16. One-off steps on this PC (not installer code)

1. Show `~/change_this_bitch.sh` to the user, then delete it.
2. Run `python3 -m witchy install`, open a new tab, run `python3 -m witchy doctor`: no ✗.

## 17. Acceptance criteria

1. A PC with fish but no fisher or Tide: install exits 0; a new tab shows the section 6 prompt; doctor shows no ✗.
2. This PC: after install, no `tide_*` variable holds a value from validate's `PASTEL` list; Windows Terminal has no `PastelOneDark`; doctor shows no ✗; the glyph test line renders every symbol.
3. A `starship init fish | source` line in `config.fish`: install comments it out, keeps a backup, and the Tide prompt shows; uninstall gives the line back.
4. No network and no fisher: install exits 2 with the banner; doctor shows ✗ with the fix.
5. `tide configure` after install: doctor ✗ lists drifted names; install restores them.
6. Uninstall on the PC from criterion 1 removes Tide and fisher; on this PC it leaves both and restores the recorded variables.
7. `/usr/bin/python3 -m unittest discover -s tests -t . -v` passes on Python 3.10 and 3.12 in CI, and the weekly network job passes.
8. On a WSL box with no fish: `python3 -m witchy install --fresh`, answering yes twice, ends with exit 0 and criterion 1 holds.
9. `python3 -m witchy preview` shows the section 6 prompt on a PC without Tide.
10. With the date set to 2026-10-30 or 2026-10-31, a new tab's caret is Samhain amber; on 2026-11-01 it is gold.
11. After `tide configure`, `python3 -m witchy doctor --fix` ends with exit 0 and no ✗.
