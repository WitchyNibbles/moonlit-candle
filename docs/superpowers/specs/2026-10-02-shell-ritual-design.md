# Shell Ritual: Moonlit Candle for Windows Terminal and fish

- **Date:** 2026-10-02
- **Revision:** 2 (folds in the [CEO review](../reviews/2026-10-02-shell-ritual-ceo-review.md))
- **Status:** revision 1 approved; revision 2 pending review
- **Use:** personal (eimi, WSL2 Ubuntu 24.04 inside Windows Terminal, fish 3.7.0, Tide 6.1.1, Claude Code 2.1.287)
- **Builds on:** [`2026-09-30-moonlit-candle-design.md`](2026-09-30-moonlit-candle-design.md) (Spanish, historical). Everything in that spec still holds unless this one changes it.
- **Diagram:** [`docs/diagrams/witchy-components.html`](../../diagrams/witchy-components.html)

## 1. Goal

Extend Moonlit Candle from Claude Code to the whole terminal, and make it feel alive:

- Windows Terminal profile: Maple Mono NF, a starfield whose moon matches tonight's real phase, pink box cursor, moon tab icon.
- fish prompt: Tide recoloured to the palette, with today's moon phase as the first segment.
- A greeting ("the ritual") on top-level shells: a live ASCII moon drawn to today's phase beside a salutation, the Wheel of the Year, lunar events, a tarot card of the day and a short system fetch.
- A witchy `ll`/`lt` through eza.
- `witchy doctor` to see at a glance what is installed and what broke.

**Success:** after `python3 -m witchy install` and a Windows Terminal restart, a new Ubuntu tab matches sections 4–7, `python3 -m witchy doctor` shows no `✗`, and `python3 -m witchy uninstall` gives back the pink Tide prompt, the previous profile settings and the default greeting, leaving only the Maple Mono font files installed.

## 2. Scope

In:

1. Installer refactor into components (section 3).
2. Windows Terminal profile settings, profile lookup fix, Maple Mono NF, sky images and the sky job (section 4).
3. Tide recolour, layout and `moon` item (section 5).
4. The greeting package, full ritual and one-line omen (section 6).
5. eza colours and `ll`/`lt` (section 7).
6. CLI: `doctor`, `mood`, `--only`, exit codes, lock (section 8).
7. Repo housekeeping: adopt the user's edited output style with neutral wording (section 3.5), translate `README.md` to English with a Troubleshooting table, GitHub Actions CI.

Out:

- Installing fish, fisher, Tide or eza. Missing tools are skipped with a warning; doctor prints the install command.
- Removing Maple Mono on uninstall.
- The hidden duplicate `Windows.Terminal.Wsl` "Ubuntu" profile and Windows Terminal Preview.

Deferred (written down, not planned):

- The dawn variant palette. The code is variant-ready (section 3.4).
- bat (`.tmTheme`) and fzf colours, as a future component.

Consequence the user accepted: the right prompt shows only `status cmd_duration time`. Tide's current right items (`context jobs direnv bun node python … zig`) are dropped while installed and restored on uninstall.

## 3. Architecture

Python 3.10+, stdlib only. One installer, one `state.json`, one palette.

### 3.1 Component contract

`witchy/components/base.py`:

```python
class Component(Protocol):
    name: str                                    # "claude" | "font" | "windows-terminal" | "fish"
    def plan(self, ctx, entry: dict | None) -> Plan          # changes + new state entry, or Plan.skip(reason)
    def apply(self, ctx, plan: Plan) -> dict                 # performs the plan, returns the state entry
    def restore(self, ctx, entry: dict) -> Plan              # the uninstall plan
    def check(self, ctx, entry: dict | None) -> list[Check]  # doctor lines: ok | warn | fail, message, fix
```

`Plan` holds file `Change`s (the existing dataclass), commands to run (fish, `reg.exe`), notes and warnings. `--dry-run` prints every plan and runs nothing.

### 3.2 Runner (`witchy/runner.py`)

1. Take `$XDG_RUNTIME_DIR/witchy-<uid>.lock` (system temp dir as fallback; outside HOME so uninstall leaves nothing behind) (`fcntl.flock`, non-blocking). Busy: print "another witchy command is running" and exit 1.
2. Validate (section 11). Failure: exit 1, nothing written.
3. Load state, migrating v1 (section 3.3).
4. Plan every selected component in order: `claude`, `font`, `windows-terminal`, `fish`. `claude` aborting (its `settings.json` is not plain JSON) stops everything with exit 1, as today.
5. Apply each component in order. After each one, save state. A failing `font`, `windows-terminal` or `fish` step records `skipped: <reason>` (its plan skipped) or `failed: <reason>` (applying it failed) and the runner continues.
6. Uninstall runs `restore` in reverse order.
7. Print an end summary, e.g. `3/4 components installed · failed: font (download failed (…))`, and exit 0 (all ok), 1 (nothing changed) or 2 (installed with warnings).

Component code lives in `witchy/components/{claude,font,windows_terminal,fish}.py`. `jsonio.py` and `records.py` are reused unchanged. `install.py` shrinks to the CLI glue around the runner.

### 3.3 State v2

```json
{
  "version": 2,
  "variant": "midnight",
  "last_install": { "at": "20261002-211403", "results": { "claude": "ok", "font": "failed: download failed (…)" } },
  "components": { "claude": {}, "font": {}, "windows-terminal": {}, "fish": {} }
}
```

- v1 migrates on load: `files` and `claude_settings` go to `components.claude`; `windows_terminal` goes to `components["windows-terminal"]`. Every recorded previous value is kept. The next write saves v2.
- A component's entry is absent until it is installed. Reinstall keeps the first recorded previous values, as today.
- `~/.claude/witchy/` is durable. `~/.cache/witchy/` (stamps, fail marker, log, font zip, sky render cache) is disposable at any time.
- `last_install.at` is the run stamp used for backups.

### 3.4 Variants

`palette.VARIANTS = {"midnight": Variant(...)}` holds every colour set: Claude overrides, Windows Terminal scheme, status line, Tide, ritual and sky. Components read the active variant from state (default `midnight`). Adding dawn later means adding one entry and passing validation.

Variants change colours only; theme name, scheme name and installed paths stay the same.

### 3.5 Content changes

- `content/output-style.md` becomes the user's edited version (one vocabulary touch per message; the reply-shape section), with the sentence that names a diagnosis reworded to *"Write for a reader who skims: short blocks, one idea per line."* The rules stay the same.
- `content/ritual.json`: salutation `name` (`eimi`), the 22 tarot cards, the 8 sabbats and the lunar event lines.

### 3.6 Files by component

| Component | Owns |
| :- | :- |
| `claude` | `~/.claude/themes/moonlit-candle.json`, `output-styles/witchynibbles.md`, `witchy/statusline.py`, `witchy/tips.json`; the 5 keys in `~/.claude/settings.json` |
| `font` | 4 Maple Mono NF TTFs in the Windows user Fonts folder and their HKCU registry values |
| `windows-terminal` | the scheme; the profile keys (4.2); `<WT LocalState>/moonlit-candle-sky-{0..7}.png`; `~/.claude/witchy/ritual-config.json` (settings path, profile GUID, the 8 sky values) |
| `fish` | `~/.claude/witchy/ritual/` (greeting package); `~/.config/fish/functions/{fish_greeting,ritual,_tide_item_moon,_witchy_moon_bin,ll,lt}.fish`; `~/.config/fish/conf.d/witchy.fish`; the Tide universal variables (5.2) |

fish files are rendered at install time from `content/fish/*.fish` templates (placeholders `@PYTHON@`, `@WITCHY_DIR@`).

## 4. Windows Terminal

### 4.1 Profile lookup

1. `WT_PROFILE_ID`, if it names an existing profile.
2. Otherwise the single profile that is not `"hidden": true`, whose `name` equals `$WSL_DISTRO_NAME`, and whose `source` is `Microsoft.WSL`, `Windows.Terminal.Wsl` or starts with `CanonicalGroupLimited.`.
3. Zero or several matches: skip the component with a warning.

On this machine step 2 selects `{51855cb2-8cce-5362-8f54-464b92b32386}`, the profile the current state already records.

`settings.json` is found first, in this order: `--wt-settings`; the path recorded in state, if it still exists; `%USERPROFILE%` mapped to `/mnt/<drive>/…`; `C:\Users\%USERNAME%`. On this machine the account name and the profile folder differ.

### 4.2 Profile keys (`WT_PROFILE` in the variant)

```json
{
  "font": { "face": "Maple Mono NF", "size": 12, "cellHeight": "1.1" },
  "cursorShape": "filledBox",
  "padding": "14",
  "opacity": 93,
  "useAcrylic": true,
  "backgroundImage": "ms-appdata:///local/moonlit-candle-sky-<bin>.png",
  "backgroundImageOpacity": 0.12,
  "backgroundImageAlignment": "bottomRight",
  "backgroundImageStretchMode": "uniformToFill",
  "icon": "🌙",
  "tabTitle": "witchyterm",
  "suppressApplicationTitle": true
}
```

- Each key is snapshotted before the first install and restored only if it still holds an installed value; for `backgroundImage`, any of the 8 sky values counts as installed.
- `font` replaces the whole object (the current `"features": {"aalt": 0}` goes away while installed). It is set only if Maple Mono NF is registered: the `font` component is recorded in state, or it is planned in this run and installs successfully. Otherwise the key is left untouched and the summary says so.
- The background keys are set only after the sky images are copied.
- `suppressApplicationTitle` keeps the tab title at "witchyterm".
- Install, uninstall and the sky job all take `~/.cache/witchy/wt.lock` before touching `settings.json`, re-check its hash, then replace it atomically. The installer holds it only while it writes the Windows Terminal files.

### 4.3 Maple Mono NF (`font` component)

- The release zip from `github.com/subframe7536/maple-font`, pinned in `font.py` to one release tag and its SHA-256, downloaded over HTTPS with default certificate checks into `~/.cache/witchy/`.
- Extract only the `Regular`, `Italic`, `Bold` and `BoldItalic` TTF members, by exact name, each capped at 20 MB, to fixed file names in `/mnt/c/Users/<U>/AppData/Local/Microsoft/Windows/Fonts/`.
- Register each with `reg.exe add "HKCU\Software\Microsoft\Windows NT\CurrentVersion\Fonts" /v "<name> (TrueType)" /t REG_SZ /d "<windows path>" /f`. `<name>` is read from the TTF `name` table (full font name, ID 4), not hard-coded.
- Already present: Maple Mono NF counts as installed when all four styles are registered (`Maple Mono NF Regular|Italic|Bold|Bold Italic (TrueType)`) and point to existing files; nothing is downloaded or copied, and a witchy install already recorded in state is kept as it is. A partial set (for example after a failed `reg.exe` call) is completed by the next install. An identical file already in place is not rewritten.
- Windows Terminal needs a restart to see a newly installed font; the summary says so.
- A failed download, checksum, copy or `reg.exe` call records `failed: <reason>` for `font`; font files already copied stay (uninstall never removes fonts).

### 4.4 Sky images

- 8 PNGs, `moonlit-candle-sky-0.png` (new) to `-7.png` (waning crescent), 2560×1440 RGB on `#0D0916`, rendered by `witchy/sky_render.py` with a stdlib PNG writer into a pre-filled `bytearray`, touching only star and moon pixels.
- Shared starfield: a fixed seed places about 220 stars (single pixels and 2×2 dots in `#F3EAF7`, `#FFD477`, `#B99AFF`) and 6–8 four-point sparkles; identical in all 8 images.
- The moon: radius 150 px, centred about 260 px from the right and bottom edges. The lit part is drawn for the bin's phase in `#FFD477`; the dark part is a faint `#1D1230` disc with a `#38234D` rim; a soft glow scales with illumination.
- Output is deterministic. Renders are cached in `~/.cache/witchy/sky/<hash of renderer source + palette>/`, so only the first build pays (about 1 s per image).
- **Spike gate:** before building the sky job, a manual check confirms that Windows Terminal applies a changed `backgroundImage` path without a restart. If it does not, ship a single image for the install-day phase (`moonlit-candle-sky.png`) and no sky job; everything else in this spec is unchanged.
- **Spike result (2026-10-03): passed.** An atomic replace of `settings.json` that only changed `backgroundImage` was applied to an open tab without a restart, so the eight images and the sky job stay in scope.

### 4.5 Sky job

- `conf.d/witchy.fish`, on interactive shells with `WT_SESSION` set and `~/.claude/witchy/ritual-config.json` present, computes the phase bin with `_witchy_moon_bin` and compares it with `~/.cache/witchy/sky-bin`.
- Equal, or a fail marker for today exists: do nothing. Different: start `@PYTHON@ -I @WITCHY_DIR@/ritual --sky` in the background (`&; disown`), silently.
- The job takes the lock, reads `settings.json` strictly, and finds the profile from `ritual-config.json`. If the profile's `backgroundImage` is not one of the 8 sky values (the user changed it), it does nothing and logs once. Otherwise it sets the new value, re-checks the file hash, writes atomically and updates `sky-bin`.
- Any failure writes `~/.cache/witchy/sky-fail` with today's date and logs the error. Retries happen at most once a day. Two windows opening at once are serialised by the lock; the second sees the updated stamp and exits.

## 5. Prompt (Tide)

### 5.1 Moon item

- `_witchy_moon_bin` computes the phase bin 0–7 with fish `math` from `date +%s` (the same mean-synodic algorithm as section 6.3).
- `_tide_item_moon` maps the bin to `🌑🌒🌓🌔🌕🌖🌗🌘` and prints it with `_tide_print_item moon <glyph>`. Tide renders items asynchronously, so recomputing on every prompt is invisible and a shell left open for days stays correct.
- A test compares `_witchy_moon_bin` with the Python implementation over 60 consecutive days.

### 5.2 Variables (`TIDE` in the variant)

Tide colours are written without `#`.

| Variable | Value |
| :- | :- |
| `tide_left_prompt_items` | `moon pwd git newline character` |
| `tide_right_prompt_items` | `status cmd_duration time` |
| `tide_moon_bg_color` / `tide_moon_color` | `1D1230` / `FFD477` |
| `tide_pwd_bg_color` | `B99AFF` |
| `tide_pwd_color_anchors` / `_dirs` / `_truncated_dirs` | `0D0916` / `1D1230` / `38234D` |
| `tide_git_bg_color` / `_unstable` / `_urgent` | `FFD477` / `FFB86B` / `FF6B9F` |
| `tide_git_color_*` (branch, conflicted, dirty, operation, staged, stash, untracked, upstream) | `0D0916` |
| `tide_character_color` / `_failure` | `FF67B7` / `FF6B9F` |
| `tide_prompt_color_frame_and_connection` | `6E5A80` |
| `tide_prompt_color_separator_same_color` | `A99AB9` |
| `tide_status_bg_color` / `tide_status_color` | `1D1230` / `74E8B8` |
| `tide_status_bg_color_failure` / `tide_status_color_failure` | `1D1230` / `FF6B9F` |
| `tide_cmd_duration_bg_color` / `tide_cmd_duration_color` | `1D1230` / `A99AB9` |
| `tide_cmd_duration_threshold` | `3000` |
| `tide_time_bg_color` / `tide_time_color` | `1D1230` / `A99AB9` |

The names are checked against Tide 6.1.1 during implementation; a test pins the list.

### 5.3 Rules

- Tide check: `fish -c 'functions -q tide'`. Missing fish or Tide: skip the variables with a warning; the fish files and greeting still install. The component result is `skipped: Tide not found`.
- Snapshot each variable before the first install: its values (read NUL-separated), its export flag, or `{"absent": true}`.
- Set with `set -U` (`-Ux` when the snapshot was exported) after the fish files exist.
- If a `set -U` exits non-zero, stop; state records only the variables already set.
- Uninstall restores a variable (or erases it with `set -e -U`) only if it still holds the installed value; otherwise it warns and leaves it.
- Every `fish` call uses list arguments and a 5 s timeout through the injectable `ctx.run`.
- Running shells keep their old prompt; the summary says to open a new tab.

## 6. Greeting (the ritual)

### 6.1 Package

`witchy/ritual/` is a directory package that imports nothing from `witchy`. It is installed to `~/.claude/witchy/ritual/` and run as `@PYTHON@ -I @WITCHY_DIR@/ritual`.

| Module | Purpose |
| :- | :- |
| `__main__.py` | arguments: default (auto), `--full`, `--omen`, `--sky`, `--debug` (timing per stage), `--date YYYY-MM-DD` (preview another day) |
| `moon.py` | mean-synodic phase, bin, illumination; Meeus ch. 49 exact new and full moon instants |
| `wheel.py` | the 8 sabbats; Meeus ch. 27 solstices and equinoxes |
| `art.py` | the ASCII moon disc and stars |
| `tarot.py` | card of the day |
| `fetch.py` | system lines |
| `layout.py` | side-by-side, stacked and omen layouts; glyph width table; `NO_COLOR` |
| `sky.py` | the sky job (4.5) |
| `log.py` | `~/.cache/witchy/ritual.log`, trimmed to the last 20 lines |
| `palette.py` | colours; `build` rewrites its `# BEGIN PALETTE` block from the active variant |
| `data.json` | copied from `content/ritual.json` |

### 6.2 When it runs

`fish_greeting` runs the package only when all hold: `status is-interactive`; `WT_SESSION` is set; `TMUX`, `CLAUDECODE` and `WITCHY_RITUAL_SHOWN` are unset; `TERM_PROGRAM` is not `vscode`. It then sets `set -gx WITCHY_RITUAL_SHOWN 1`, so nested shells and anything they launch stay quiet.

In auto mode the package picks:

- **Full ritual** when the last full ritual (`~/.cache/witchy/last-ritual` mtime) is older than 10 minutes and the terminal has at least 60 columns.
- **One-line omen** otherwise, e.g. `🌔 Waxing Gibbous 74% · ✦ The Star (reversed) · 🕯️ Samhain`.

The `ritual` fish command always runs the full ritual, ignoring every condition. If the package or Python is missing, `fish_greeting` prints nothing.

### 6.3 Moon

- Display phase: age = days since the new moon of 2000-01-06 18:14 UTC, modulo 29.530588853. Illumination = `(1 − cos(2π · age / 29.530588853)) / 2`, as a whole percent.
- Eight bins, each 1/8 of the cycle centred on its phase: New 🌑, Waxing Crescent 🌒, First Quarter 🌓, Waxing Gibbous 🌔, Full 🌕, Waning Gibbous 🌖, Last Quarter 🌗, Waning Crescent 🌘.
- Northern-hemisphere view: waxing light on the right.
- Event days (6.6) use Meeus ch. 49 for the exact instant of each new and full moon, converted to the local date.

### 6.4 Art

- A disc of 11 rows × 22 columns (2:1 cell aspect). A cell is lit when it lies on the illuminated side of the terminator ellipse for the current age.
- Lit cells use `█▓▒` by distance from the limb, in `#FFD477` fading to `#FFE3A3`. Unlit cells use `░` in `#38234D` (earthshine).
- 6–10 stars (`✦ ⋆ · ˚`) in `#B99AFF` and `#F3EAF7` around the disc, positioned by a seed from the date: they change daily and stay put within a day.
- No emoji inside the art grid.

### 6.5 Info column

```
Good witching hour, eimi
🕯️ Samhain — the veil is thin tonight
🌕 Full moon — charge your crystals
⋆ Waxing Gibbous  74%
✦ XVII · The Star (reversed)
  despair, lost faith; rest and wait
os      Ubuntu 24.04.4 LTS
kernel  6.6.87.2-microsoft-standard-WSL2
uptime  3h 12m
memory  4.1 / 15.6 GiB
shell   fish 3.7.0
```

- **Salutation** by local hour: 00–03 "Good witching hour", 04–11 "Good morning", 12–17 "Good afternoon", 18–23 "Good evening", then `, <name>`. Gold bold, or the sabbat accent on a sabbat day.
- **Sabbat line** (6.6): only on a sabbat day or during the 7 days before.
- **Lunar line** (6.6): only on an event day.
- **Tarot:** `sha256("YYYY-MM-DD")` of the local date picks the card (`digest[0] mod 22`) and the orientation (reversed when `digest[1] < 85`, about one day in three).
- **Fetch:** `PRETTY_NAME` from `/etc/os-release`, `os.uname().release`, `/proc/uptime`, `MemTotal − MemAvailable` from `/proc/meminfo`, and `fish $FISH_VERSION`. A missing value shows `--`. Control characters are stripped from every external string.
- **Colours:** salutation `#FFD477` bold; labels `#A99AB9`; values `#F3EAF7`; moon line `#B99AFF`; tarot name `#FF67B7`; reversed marker and meaning `#CFC3DB`.

### 6.6 Wheel of the Year and lunar events

| Sabbat | Date | Accent |
| :- | :- | :- |
| Imbolc | 1 Feb | `#F3EAF7` |
| Ostara | March equinox | `#74E8B8` |
| Beltane | 1 May | `#FF67B7` |
| Litha | June solstice | `#FFD477` |
| Lughnasadh | 1 Aug | `#FFB86B` |
| Mabon | September equinox | `#FFB86B` |
| Samhain | 31 Oct | `#FFB86B` |
| Yule | December solstice | `#E6DCEE` |

- Solstices and equinoxes come from Meeus ch. 27, converted to the local date. Northern hemisphere.
- On the day: `🕯️ <Sabbat> — <blessing>`. During the 7 days before: `⋆ <Sabbat> in N days` (`tomorrow` for 1).
- Lunar lines: new moon `🌑 New moon — <line>`; full moon `🌕 Full moon — <line>`; a blue moon (the second full moon in a calendar month) `🌕 Blue moon — <line>`.
- Blessings and lunar lines live in `content/ritual.json`, at most 48 characters each.
- Both lines can appear on the same day, sabbat first.

### 6.7 Layout and safety

- Width from `shutil.get_terminal_size()`, 80 when unknown. At 80 or more: art left, three spaces, info right, vertically centred. 40–79: art first, info below. Under 40: info only. (Auto mode under 60 columns shows the omen instead, so these narrow layouts are reached through `ritual`.)
- One blank line after the greeting.
- A fixed width table covers every glyph we print (emoji are 2 cells), so columns line up.
- `NO_COLOR` set: plain text, no escape sequences.
- Any exception: print nothing, exit 0, and append the error to `ritual.log`. Doctor shows the last logged error.
- Budget: median under 200 ms over 10 runs. A test fails above 1 s, as a regression guard that never flakes.

## 7. eza

- `conf.d/witchy.fish` exports `EZA_COLORS` built from the variant: directories `#B99AFF`, executables `#74E8B8`, symlinks `#77D9FF`, sizes and dates `#A99AB9`, git status in the git colours.
- `ll` runs `eza -la --icons --group-directories-first --git`; `lt` runs `eza --tree --level=2 --icons`. Without eza they fall back to `ls -la` and `ls -R`.
- `ls` itself is not aliased.
- Doctor shows `⚠ eza missing — sudo apt install eza` when eza is absent.

## 8. CLI

```
python3 -m witchy validate
python3 -m witchy build
python3 -m witchy install   [--dry-run] [--wt-settings PATH] [--only NAME]...
python3 -m witchy uninstall [--dry-run] [--only NAME]...
python3 -m witchy doctor
python3 -m witchy mood [VARIANT]
```

- Existing commands and flags are unchanged.
- `--only` accepts `claude`, `font`, `windows-terminal`, `fish` (repeatable). Components not named keep their state untouched.
- Install and uninstall exit 0 (all ok), 1 (nothing changed: validation, lock, abort), 2 (done with warnings).
- An uninstall whose restore cannot be written keeps that component in state and exits 2; running uninstall again retries it.
- `doctor` prints one line per check, `✓`, `⚠` or `✗`, each `✗`/`⚠` with its fix (often `python3 -m witchy install --only <name>`). It uses the paths recorded in state (no `cmd.exe` lookup) and finishes under 2 s. Exit 1 on any `✗`, else 0. A `check()` that raises is reported as `✗` with the exception text.
- Doctor checks: installed files match their recorded hashes; settings keys and profile keys hold installed values; the theme is active; the font is registered; the sky images and `ritual-config.json` exist; Tide variables match; eza is present; the backups state relies on still exist; the last `ritual.log` error; the sky fail marker; components skipped at the last install.
- `mood` without an argument prints the active and available variants. With a variant it records it in state and re-runs install; an unknown variant exits 1 with `available: midnight`.

## 9. Error and rescue map

| Path | Failure | Rescue | Message |
| :- | :- | :- | :- |
| runner | lock held | exit 1 | `another witchy command is running` |
| claude | `settings.json` not plain JSON | abort everything, exit 1 | existing message |
| font | Windows user folder not found; `reg.exe query` cannot run (while planning) | `skipped: <reason>`; `font` key untouched | `font: …; keeping the current font` |
| font | `URLError` / `TimeoutError` | `failed: download failed (…)`, exit 2; nothing recorded for `font`; `font` key untouched | `font: download failed (…); keeping the current font` |
| font | digest mismatch | delete the cached zip; `failed: checksum mismatch`, exit 2; nothing recorded for `font` | `font: checksum mismatch, nothing installed` |
| font | bad archive (`FontArchiveError`); `OSError` on copy | `failed: <reason>`, exit 2; nothing recorded for `font`; files already copied stay | `font: …; keeping the current font` |
| font | `reg.exe add` `OSError` / `TimeoutExpired` / non-zero exit | `failed: could not register <name>`, exit 2; nothing recorded for `font`; files already copied stay | warning naming the registry value |
| windows-terminal | sky image copy `OSError` | set no background keys; the rest applies | `windows-terminal: sky images not copied (…)` |
| windows-terminal | `StrictJsonError`, profile not found, write `OSError` | existing handling | existing messages |
| fish | no fish, no Tide, `TimeoutExpired` | skip the variables; files still install | `fish: Tide not found; prompt not recoloured` |
| fish | `set -U` non-zero (`CalledProcessError`) | stop; record the variables already set | warning naming the variable |
| greeting | any exception | exit 0, no output, log | doctor `⚠ greeting: last run failed …` |
| sky job | hash changed, not plain JSON, profile gone, value changed by user | skip, log, fail marker for today | doctor `⚠ sky: …` |
| eza | missing | `ll`/`lt` fall back to `ls` | doctor `⚠ eza missing …` |

## 10. Security

1. Font download: HTTPS with certificate checks, pinned tag and SHA-256, exact-name extraction, 20 MB cap per member.
2. Every subprocess (`reg.exe`, `fish`, `cmd.exe`, `eza`) gets list arguments, never a shell string; values come from constants.
3. The greeting strips control characters from external strings before printing.
4. `settings.json` writers share a lock, re-check the hash and replace atomically.
5. fish functions call `/usr/bin/python3 -I` by absolute path (falling back to the installer's `sys.executable` when absent, as for the status line).
6. No personal health details in the public repo (3.5).

## 11. Validation additions

1. `ritual.json`: exactly 22 tarot cards, `number` 0–21 each once, unique names, `upright` and `reversed` non-empty and at most 60 characters; `name` non-empty, at most 24 characters; the 8 sabbats present with a blessing; the 3 lunar lines present; blessings and lunar lines at most 48 characters.
2. Ritual text colours and the 8 sabbat accents at least 4.5:1 on `#0D0916`; the earthshine `#38234D`, the sky images and the stars are exempt as decorative.
3. Tide pairs at least 4.5:1: each segment's text colour on its background (moon, pwd anchors and dirs, git colours on all three git backgrounds, status, cmd_duration, time), and `character` colours on `#0D0916`. `tide_pwd_color_truncated_dirs` and the frame colour need 3:1.
4. eza colours at least 4.5:1 on `#0D0916`.
5. Every variant passes every rule; colour format `^#?[0-9A-F]{6}$` (Tide values without `#`).

## 12. Tests and CI

`python3 -m unittest discover -s tests -t .` on `/usr/bin/python3` (3.12) and `/usr/bin/python3.10`. No test touches the real `~/.claude`, `~/.config/fish`, Windows Terminal, the registry, the network or today's date (`ctx.run`, `ctx.fetch`, `ctx.now` are injected).

| Area | Tests |
| :- | :- |
| runner | order; state saved after each component; exit codes 0/1/2; lock busy; `--only`; reverse-order uninstall |
| state | v1 → v2 migration on an anonymised copy of the real v1 `state.json` |
| claude | existing tests, moved to the component |
| font | fresh install, already installed (by family name), digest mismatch, offline, `reg.exe` failure; dry run makes no calls |
| windows-terminal | lookup by `WT_PROFILE_ID`, by Canonical source, hidden duplicate ignored, zero and two matches; profile keys apply and restore; a user-changed key is kept; any sky value counts as installed |
| sky | renders at 256×144 are deterministic and put the moon in the bottom-right; one full-size render; cache hit; job: lock, hash conflict, comments, user-changed value, fail marker |
| fish | fake runner for snapshot, set, partial failure and restore; integration with real `fish`, a temporary `XDG_CONFIG_HOME` and a stub `tide` function (skipped without fish); `_witchy_moon_bin` parity over 60 days |
| ritual | phase at 2024-04-08 (New) and 2024-09-18 (Full) and bin edges; Meeus events and blue moons against published dates; Meeus solstices and equinoxes 2024–2030 against published dates; golden files for the 8 phase discs; tarot stable per date; sabbat day and countdown; full, omen and stacked layouts at 100, 70 and 39 columns; `NO_COLOR`; missing `/proc` values; control characters stripped; exception → exit 0, no output, log line; 1 s guard |
| doctor | ok, warn and fail per component; a raising `check()`; missing backup |
| round trip | install then uninstall restores every file byte for byte (excluding backups) and every fish variable |
| validate | each new rule catches an injected failure; the real content passes |

CI: `.github/workflows/tests.yml` on push and pull request, `ubuntu-latest`, Python 3.10 and 3.12, `sudo apt-get install -y fish` so the fish integration tests run.

## 13. Implementation order

Strict component-first order, as chosen in the review:

1. Housekeeping: adopt the output style (3.5), translate the README, add CI.
2. Refactor into components, runner and state v2 with migration; no behaviour change; all existing tests pass.
3. CLI: lock, exit codes, `--only`, `doctor`, `mood`, variant-ready palette.
4. `windows-terminal`: lookup fix and profile keys.
5. `font`.
6. Spike (4.4 gate), then sky images.
7. `fish`: files, Tide variables, eza.
8. Greeting package, including the sky job.
9. Acceptance on the real machine, screenshot, PR.

## 14. Acceptance criteria

1. `python3 -m witchy validate` exits 0; all tests pass on 3.12 and 3.10 locally and in CI.
2. `python3 -m witchy install --dry-run` on the real machine shows only the changes in sections 3–7.
3. After a real install and a Windows Terminal restart, a new Ubuntu tab shows Maple Mono NF, the starfield with tonight's moon phase, the pink box cursor, 🌙 and "witchyterm" on the tab, the side-by-side greeting, the recoloured prompt starting with today's moon glyph, and a coloured `ll`.
4. A second tab within 10 minutes and a split pane show the one-line omen; tmux, a nested `fish` and Claude Code's shells show nothing; `ritual` shows the full ritual anywhere.
5. `ritual --date 2026-10-31` shows the Samhain line and accent; `ritual --date 2026-10-26` shows `Samhain in 5 days`.
6. The greeting's median time is under 200 ms (`ritual --debug`, 10 runs).
7. `python3 -m witchy doctor` shows no `✗`.
8. A screenshot of criterion 3 is attached to the PR.
9. `uninstall` brings back the pink 🌸 Tide prompt, the previous profile settings and the default greeting, and leaves Maple Mono installed; the user then reinstalls if they want.
