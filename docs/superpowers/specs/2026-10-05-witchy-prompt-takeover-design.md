# Prompt Takeover: a witchier Tide that installs the same way on every PC

- **Date:** 2026-10-05
- **Revision:** 2 (folds in the [CEO review](../../reviews/2026-10-05-prompt-takeover-ceo-review.md))
- **Status:** revision 1 approved; revision 2 pending review
- **Use:** personal (eimi, WSL2 Ubuntu inside Windows Terminal, fish 3.7.0)
- **Builds on:** [`2026-10-02-shell-ritual-design.md`](2026-10-02-shell-ritual-design.md). Everything there still holds unless this spec changes it. Section numbers below such as "ritual 5.2" point into that spec.

## 1. Problem

On a second PC (WSL Ubuntu, fish), `python3 -m witchy install` themed Windows Terminal and the greeting, but the prompt kept its old look. On this PC the prompt still shows the old "pastel princess" icons. Causes found in the code and on this machine:

1. witchy does not install Tide. Without it, the fish component records `skipped: Tide not found` and the run exits 2. The only signal is one line in the summary. The second PC has no Tide.
2. witchy sets only Tide's colours and item lists (`palette.TIDE`, 31 variables). This PC has 161 universal `tide_*` variables (its Tide is a development build that still calls itself 6.1.1; the 6.1.1 release defines 156, and witchy's moon item adds 2). The icons, caps, separators, time format and the colours of unused items come from `~/change_this_bitch.sh` (🎀 🏰 🌷 💖 ✨ 🍰 and round caps), and witchy never touches them.
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

`plan` runs one `fish -c` call that reports: fish version, whether `fisher` is a function and its version, whether `tide` is a function and `tide --version`, the path of `functions --details fish_prompt`, and each fisher plugin with its file list (`_fisher_ilancosman_2F_tide_files`; installed from a tag, `_fisher_ilancosman_2F_tide_40_v6_2E_31_2E_31__files`).

| Found | Action |
| :- | :- |
| fish missing | `skipped: fish not found (sudo apt install fish)`. |
| fisher missing | Download `https://raw.githubusercontent.com/jorgebucaran/fisher/4.4.5/functions/fisher.fish` with `fonts.fetch_url`, check its pinned SHA-256, cache it in `~/.cache/witchy/`, then `fish -c 'source <file>; fisher install jorgebucaran/fisher@4.4.5'`. |
| Tide missing | `fisher install ilancosman/tide@v6.1.1`. |
| Tide present, version ≠ 6.1.1, or files that differ from the pins (Tide's development branch, `ilancosman/tide`, also prints 6.1.1) | `fisher remove <its name>`, then `fisher install ilancosman/tide@v6.1.1` in the same fish call, which keeps every universal `tide_*` variable (Tide's uninstall erases them and its install sets its defaults); its name is recorded as `previous_tide_plugin`. A Tide witchy installed (`ilancosman/tide@v6.1.1`) with a changed file is installed again instead. |
| Tide 6.1.1 present, every file as pinned | Nothing. |
| A `tide` function that fisher did not install | `failed: Tide is installed without fisher, so witchy can neither check nor replace it; remove it`. |

- fisher needs `curl`. Missing `curl` → `failed: curl not found (sudo apt install curl)` before anything is downloaded (only when something must be installed).
- A fisher the user installed (any name but `jorgebucaran/fisher@4.4.5`) is used as it is and never pinned; witchy's own fisher with a changed file is installed again. Every fisher call gets empty standard input: fisher reads more plugin names from a pipe.
- **Pins (D21):** `content/pins.json` holds the SHA-256 of the bootstrap `fisher.fish` and of every file fisher 4.4.5 and Tide 6.1.1 install. Before each `fisher install`, witchy downloads the release tarball fisher will fetch (`api.github.com/repos/<repo>/tarball/<ref>`, 120 s, logged to `install.log`) and hashes every file fisher would copy; unless all match, nothing is installed and the component ends `failed: <plugin> release does not match the pinned files` (fisher runs a plugin's `conf.d` as soon as it installs it, so the check must come first). After each `fisher install`, witchy hashes each file listed in `_fisher_<plugin>_files` again. A mismatch removes the plugin. fisher and a fresh Tide (no Tide was there before) go with `fisher remove`, and a fresh Tide's uninstall takes its `tide_*` variables with it (D13). Any other Tide goes through the variable-preserving swap, so every `tide_*` variable survives: a Tide that replaced another one is replaced back by the previous plugin, and the user's own Tide 6.1.1 that an update failed is recorded as `previous_tide_plugin`, so uninstall puts it back. Either way it ends `failed: <plugin> files do not match the pinned release`. The pins are generated by `scripts/pins.py` from the real releases and checked in. `tide --version` must also print `6.1.1`.
- **Timeouts and log (D20):** `Command` gains `timeout` (default 5 s, as today). Downloads and `fisher install` use 120 s. Their stdout and stderr are appended to `~/.cache/witchy/install.log` (capped at 200 KB, oldest run dropped first), and a failure reads `failed: could not install Tide (exit 1): <last stderr line> (details: ~/.cache/witchy/install.log)`.
- Network failure, a SHA mismatch or a fisher error → `failed: <reason>`. Nothing that ran before is undone; the record keeps what was installed so far (same rule as ritual 3.3).
- The entry records `installed_fisher: bool`, `installed_tide: bool`, `previous_tide_plugin: str | null`, `removed_plugins: list[str]`, `disabled_files: list[file record]` (the existing record shape, with backup), `moved_prompt: file record | null`.
- `--dry-run` lists the downloads and fisher commands and runs none of them.

### 5.2 Taking over other prompt owners

Runs in `plan` (detection) and `apply` (changes). In `apply`, a hand-written `fish_prompt.fish` and other prompt plugins go after fisher is installed and before Tide, because fisher refuses to put a file where another one already is. The lines in `config.fish` and `conf.d` are disabled last, once Tide is in place and matches the pins, so a failed Tide install leaves the user's own prompt line working. Only then does `tide` ask fish whether `fish_prompt` is Tide's (`fish -c` reads those lines until they are disabled); it asks after any Tide install, update or replacement and after disabling any line, and when it is not, the component ends `failed: Tide is installed but not ready: <reason>` with what it did recorded, so uninstall can put it back. Any case below that fails (a `fish_prompt` function, a continued line, a line fish could not read the file without, a symlink, a file that cannot be read) stops the whole component before it changes anything. witchy's own `conf.d/witchy.fish` and every file fisher lists for a plugin are never scanned.

| Owner | Detection | Takeover |
| :- | :- | :- |
| A hand-written `functions/fish_prompt.fish` | The file exists and no fisher plugin lists it. | Moved to `fish_prompt.fish.bak-witchy-<stamp>` (a symlink is moved as a link; its target is not touched). |
| Another fisher plugin that ships `fish_prompt.fish` (pure, hydro, bobthefish, …) | Its `_fisher_<plugin>_files` lists `fish_prompt.fish`. | `fisher remove <plugin>`; the plugin name is recorded. |
| `starship init fish`, `oh-my-posh init fish`, `set -g`/`set -gx`/`set --global` of a `tide_*` name | A matching line in `config.fish` or in a `conf.d/*.fish` that is neither witchy's nor fisher-managed. | The file is backed up, then each matching line is prefixed with `# witchy-disabled: `. A file's first backup stays its record. |
| `function fish_prompt` inside `config.fish` or `conf.d` | Matching line. | Not edited: a multi-line block cannot be commented safely. `failed: config.fish defines fish_prompt at line N; remove that function`. |

Every takeover prints one line, for example `tide: disabled starship init in ~/.config/fish/config.fish line 2 (backup: …)`.

Edge cases:

- A line already starting with `# witchy-disabled: ` is left alone, so a second run changes nothing.
- A matching line that ends in `\`, or follows a line that does (continued), fails like a `function fish_prompt` block, naming file and line: `failed: config.fish line N is continued over several lines; disable it yourself`.
- A matching line whose command substitution `(…)` or quoted string goes on over the next lines is caught by fish itself: for each file with lines to disable, `plan` writes the planned result to a temporary file and runs `fish --no-execute` on it, with HOME and the XDG folders in a throwaway folder. If fish cannot read it (and could read the file as it is now), each line whose disabling alone breaks it fails, naming file and line: `failed: config.fish line N is part of a command or string over several lines (fish could not read the file with it disabled); disable it yourself`. doctor shows the same ✗. Without fish only the cheap checks above apply.
- A file whose path is a symlink (for example into a dotfiles repo) is never edited (D22): `failed: config.fish is a symlink to <target>; disable line N there yourself`.
- Line endings and bytes are kept exactly: files are read and written as bytes, lines split on `\n`, non-UTF-8 bytes kept (`surrogateescape`).
- A disabled line the user turns back on is drift: doctor ✗, and install disables it again.
- A missing or empty `config.fish` or `conf.d` has nothing to take over; that is not an error.

## 6. The prompt

### 6.1 Every variable

witchy now sets every universal variable the Tide 6.1.1 release defines (156 names) and the moon item's two (`tide_moon_bg_color`, `tide_moon_color`): 158 names. Defaults and taste are kept apart (D23):

- `content/tide-6.1.1-defaults.json` holds Tide 6.1.1's Rainbow-preset values, generated once by `scripts/tide_defaults.py` from Tide's `functions/tide/configure/configs/rainbow.fish` and `icons.fish` in the v6.1.1 release tag, and checked in. The generator refuses any other tree, including a development build that also prints `tide, version 6.1.1` (it pins the SHA-256 of both files). Tide's own colour names (`$_tide_color_green`, …) are resolved from `_tide_sub_configure.fish`. The OS branding differs per machine, so the file records Tide's generic Linux branding; witchy overrides all three `tide_os_*` anyway.
- `palette.TIDE` holds only witchy's overrides (sections 6.2–6.4 and the colours from ritual 5.2).
- `build.tide(variant)` merges them. A test checks the merge has exactly the names in the defaults file plus the moon item's (`palette.TIDE_OWN`), and every override names one of those.
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
| `tide_prompt_color_frame_and_connection` | `6E5A80` (unchanged: the deep violet `38234D` is 1.42:1 on `#0D0916`, below the 3:1 rule for the frame in ritual 11.3) |

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

Caret colours: `tide_character_color` `FFD477`, `tide_character_color_failure` `FF6B9F`. `jobs` wears the muted pair of section 6.4 (`A99AB9` on `1D1230`). The other visible colours stay as in ritual 5.2.

### 6.4 Unused items

All unused items use background `1D1230` and text `A99AB9` (muted, already a validated pair). Their icons:

| Item | Icon | Item | Icon | Item | Icon |
| :- | :- | :- | :- | :- | :- |
| aws | 🏺 | gcloud | ⛅ | private_mode | 🎭 |
| crystal | 💠 | go | 🐹 | pulumi | 🧬 |
| direnv | 🍃 | java | ☕ | python | 🐍 |
| distrobox | 📦 | kubectl | 🎡 | ruby | 💎 |
| docker | 🐳 | nix_shell | 🧊 | rustc | 🦀 |
| elixir | 💧 | node | 🍄 | shlvl | 🌀 |
| php | 🐘 | os | 🐧 | terraform | 🧱 |
| | | toolbox | 🧰 | zig | ⚡ |

The Tide 6.1.1 release has no `bun` item (only Tide's development branch does), so witchy sets no `tide_bun_*` variable.

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
- The ritual takes `candle`, `dirty` and `separator` from the table through a `# BEGIN GLYPHS` block in `witchy/ritual/palette.py`, which `build.py` rewrites like its PALETTE block. (`ritual/data.json` would not do: the repository copy reads `content/ritual.json`, which no build step touches.) `ritual/layout.WIDE` becomes the moon phases plus every table emoji, so width stays right.

## 8. Windows Terminal: purge PastelOneDark

`palette.PURGED_SCHEMES = ("PastelOneDark",)`. The `windows-terminal` component, in the same settings write it already makes:

1. Sets `profiles.defaults.colorScheme` to `Moonlit Candle` if it names a purged scheme.
2. Removes `colorScheme` from every profile whose value is a purged scheme, so it inherits the default.
3. Deletes the purged scheme definitions from `schemes`.

Each previous value (defaults key, each profile's key by GUID, each scheme object) is recorded in the component entry with the first-install-wins rule. Uninstall puts them back, and leaves alone anything the user changed since (same rule as `restore_scheme`). The backup of `settings.json` is the one the component already takes.

## 9. Proof

### 9.1 doctor

The `tide` component's `check`:

- ✓/✗ fisher found (⚠ when a fisher the user installed is not 4.4.5: witchy leaves the user's fisher alone); Tide is version 6.1.1.
- ✓/✗ every Tide file, and every fisher file when witchy installed fisher, matches `content/pins.json` (D21); ✗ lists the first 5 files, then a count.
- ✓/✗ the active `fish_prompt` is Tide's (`functions --details fish_prompt` is in Tide's fisher file list).
- ✓/✗ no other prompt owner from 5.2 is active; a disabled line turned back on is ✗ (drift). The ✗ of a `function fish_prompt` block, a continued line or a symlink gives the step to take by hand as its fix.
- An info line (`·`, never a problem): `glyph test: 🧹 🔮 🪦 🌿 🧪 💀 🔥 🐈 🦉 ❯ — each should be one clear symbol`.

The `fish` component's `check`:

- A global no longer passes as ✓. The snapshot still reads the universal value by erasing globals inside its own `fish -c` process (the one exact way fish 3.7 offers), and doctor reads each name a second time in a fresh interactive shell (`fish -i -c` with `WITCHY_DOCTOR=1` set, which makes `conf.d/witchy.fish` skip the sky job and `fish_greeting` stay quiet; empty standard input, 15 s timeout). A global hiding a universal is ✗ `tide_X is overridden by a global in config.fish or conf.d`, fix `python3 -m witchy install --only tide`.
- ✓/✗ every variable in the spec matches (all 158 and `fish_emoji_width`, not 31), whatever an older install recorded; ✗ lists the names that drifted (the first 10, then a count), fix `python3 -m witchy install --only fish`.
- ✗ any universal `tide_*` not in Tide 6.1.1's list.
- When Tide is not ready, these three are replaced by one ⚠ `Tide variables not checked: <reason>`, fix `python3 -m witchy install --only tide` (the `tide` check carries the ✗).

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

`fish` checks Tide itself (D19), from its own snapshot: Tide is installed, `tide --version` is `6.1.1`, and the active `fish_prompt` is Tide's. If not, it plans as `skipped: Tide not ready (run: python3 -m witchy install --only tide)` and sets no variable. This works the same with `--only fish` and with `doctor --fix`. The runner plans every component before it applies any, so when the same run's `tide` plan installs or updates fisher, installs, updates or replaces Tide, moves a `fish_prompt` aside, removes a fisher plugin that ships one, or disables a line in `config.fish` or `conf.d` (`fish -c` reads them, so such a line still hides Tide's prompt or variables until `tide` applies), `fish` asks to be planned again (`Plan.replan`) and the runner plans it once more right before applying it; that second plan asks fish again. A `tide` plan with nothing to do, or one that cannot go ahead, lets `fish` plan at once. If the second plan fails, `fish` ends `failed: …` and the run goes on to the summary and the banner. A dry run shows `fish: set 159 prompt variables once tide has installed Tide (fish is asked again then)`. Without a `tide` plan in the run (`--only fish`), fish asks right away.

## 10. Uninstall

Reverse order: `fish` (variables, files), then `tide`. `tide` asks fish which plugins are installed now, so a retry after a failed step only runs what is left, in this order:

1. If `previous_tide_plugin` is set: `fisher remove` witchy's Tide and `fisher install <that>`, keeping every universal `tide_*` variable as `fish` just restored it (Tide's uninstall erases them and its install sets its defaults). Else if `installed_tide`: a plain `fisher remove` of witchy's Tide, whose uninstall erases its `tide_*` variables: the PC had none before (D13).
2. `fisher install <plugin>` for each prompt plugin it removed (after Tide is gone: both ship `fish_prompt.fish`).
3. If `installed_fisher`: `fisher remove` witchy's fisher.
4. Each file it commented out gets its `# witchy-disabled: ` prefixes taken away, which gives back the original bytes and keeps any later edit of the user's. A file the user changed since is backed up first; one that became a symlink is left, with a warning (D22).
5. A hand-written `fish_prompt.fish` it moved aside goes back, once Tide's is gone: it is renamed back, so a symlink (even one that points nowhere) comes back as the same link and a file keeps its mode. If something else holds that place (a file or a link), or the moved file is gone, a warning says so; a place taken between the plan and the move keeps the component installed (run uninstall again).

Without fish, steps 1–3 are skipped with a warning; 4 and 5 still run.

On this PC (Tide and fisher were already there) uninstall restores the recorded variables, which are the pastel ones (D4).

## 11. Validation additions (`validate.py`)

1. **Prompt glyphs:** every `*_icon` value and `tide_time_format` in the merged prompt (`build.tide`) holds at most one emoji; none contains U+FE0F, U+200D or U+1F3FB–U+1F3FF. Text glyphs (`❯`, `·`, Nerd Font private-use caps) are allowed. An emoji is a symbol (category So) that is East Asian Wide or lies past U+1F000.
2. **Completeness:** every key in `palette.TIDE` is a name in `content/tide-6.1.1-defaults.json` (a typo fails validation instead of creating a stray variable).
3. **No pastel:** no value of the merged prompt and no `WT_SCHEME` value is one of the recorded pastel hex values (`FFB7C5`, `F8A4C9`, `FF6EC7`, `FBAED2`, `F5C6E0`, `FFC8DD`, …) or holds one of the pastel icons (🎀 🏰 🌷 💖 💔 ✨ 🍰 🌸, …). The list lives in `validate.py` as `PASTEL`: every colour and icon of `~/change_this_bitch.sh`, except the icons witchy uses on purpose (🔮 🐍 💎 🦀 ☕ 🐳).
4. **Contrast:** each new visible pair (caret on the terminal background, muted on `1D1230` for `jobs` and the unused items, rose-red on `1D1230` for the denied direnv and the root and ssh context) joins the existing pairs. The frame keeps its 3:1 rule on `0D0916` (ritual 11.3).
5. **Width:** every emoji in `GLYPHS` is in `ritual/layout.WIDE` or East-Asian-Wide.

## 12. Tests

- Unit tests stub every `fish` call and download, as the current component tests do.
- `test_components_tide.py`: each bootstrap row of 5.1, each takeover row of 5.2, uninstall steps 1–5, dry run runs nothing, SHA mismatch fails.
- `test_components_fish.py`: the global-shadow check, the drift check over all 158 names and `fish_emoji_width`, skip when `tide` did not end `ok`.
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
- `2026-10-02-shell-ritual-design.md`: line 438 ("the pink 🌸 Tide prompt") and the matching "pink Tide prompt" in its section 1 Success line become "the prompt that was there before install"; section 2 "Out" drops "Installing fish, fisher, Tide" with a pointer to this spec.
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
2. If any are, asks once: `sudo apt install fish curl eza? [y/N]` (only the missing ones). Yes runs `sudo apt-get update`, then `sudo apt-get install -y` with the missing `fish` and `curl`, then the same for `eza` on its own, each with the terminal attached so sudo can ask for the password. A fresh WSL image has no package lists, so `install` alone would fail; `eza` is optional (`ll` and `lt` fall back to `ls`, and older Ubuntu releases do not package it), so its failure is a note. No, or a failed `update` or `fish`/`curl` install → exit 1, nothing else runs.
3. If the login shell (`getent passwd $USER`) is not fish, or cannot be read, asks `make fish your login shell (chsh -s <fish>)? [y/N]` and runs `chsh` on yes. A refusal is not an error; a failed `chsh` is a note.
4. Continues into the normal install.

Without a terminal on stdin, `--fresh` exits 1 with `--fresh needs a terminal to ask before using sudo`, unless it has nothing to ask. `--fresh --dry-run` lists what it would ask and runs nothing.

### 15.2 `preview` (D16)

`python3 -m witchy preview [--variant NAME]` prints the left and right prompt as fish would draw them, in 24-bit colour, from `build.tide(variant)`, for these sample states: home, a project with dirty git, an unwritable directory, a failed command with duration, background jobs. It needs neither fish nor Tide, writes nothing and exits 0. It is a sketch: Tide's truncation and padding rules are copied for the samples, not run. It lives in `witchy/preview.py`.

The lines fill the terminal's width, today's moon phase and time included. The failed command exits 2: with `character` on the left, Tide shows no status item for exit 1 and only turns the caret rose-red. The golden files hold each sample's two lines at 80 columns on 2026-10-31 21:13 UTC.

### 15.3 Seasonal caret (D17)

- The sky job (ritual 4.5) also writes `~/.cache/witchy/caret`, two lines: one for today and one for tomorrow, each `<YYYY-MM-DD> <HEX> <sabbat>` when that day or the next is a sabbat, else `<YYYY-MM-DD>` alone (on 2026-10-31: `2026-10-31 FFB86B samhain`, then `2026-11-01`). Tomorrow's line lets the first shell of a day show the right caret before the job has run that day. Colours come from `palette.RITUAL` (the sabbat colours, already contrast-checked against the background), upper case and without `#`. `ritual --caret` writes the file and leaves the sky alone; `ritual --sky` writes it, then moves the sky.
- `conf.d/witchy.fish` reads that file with `read` (no Python) and, only from the line whose date is today and only for a six-digit upper-case hex colour, runs `set -g tide_character_color <HEX>`. It does so before its `status is-interactive` check: Tide draws the prompt in a non-interactive `fish -c` child, which reads conf.d too and would otherwise never see the global. The universal value stays gold. The failure colour is not changed.
- Daily refresh: the sky job used to start only when the moon-phase bin changed (ritual 4.5). `conf.d/witchy.fish` now also starts it as `ritual --caret` when the cache's first line is not today's date, on any interactive shell that is not doctor's (Windows Terminal or not, with or without `ritual-config.json`), unless the job failed today. A changed phase in Windows Terminal starts `ritual --sky`, which writes the cache as well, so a shell starts at most one job.
- A missing, stale or damaged file leaves the caret gold. A write failure goes to `ritual.log` as a `sky:` line and marks the day failed (`sky-fail`), like other sky-job errors; the sky step still runs.
- doctor: the global-shadow check (9.1) accepts `tide_character_color` when its global is exactly the colour on today's line of the caret file. doctor shows one info line (`·`, never a problem): `caret: gold` or `caret: samhain FFB86B (today's cache)`, and ⚠ when the cache holds no line for today (`caret: gold (the caret cache was written on <date>, not today)`, fix: show the log; `… is damaged`; `no caret cache yet; a new tab writes it`). A cache written yesterday still holds today's line and passes.

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
