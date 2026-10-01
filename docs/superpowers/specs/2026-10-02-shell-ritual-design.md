# Shell Ritual: Moonlit Candle for Windows Terminal and fish

- **Date:** 2026-10-02
- **Status:** design approved in conversation (grill-me session), pending review of this spec
- **Use:** personal (eimi, WSL2 Ubuntu 24.04 inside Windows Terminal, fish 3.7.0, Tide 6.1.1, Claude Code 2.1.287)
- **Builds on:** [`2026-09-30-moonlit-candle-design.md`](2026-09-30-moonlit-candle-design.md) (Spanish, historical). Everything in that spec still holds unless this one changes it.

## 1. Goal

Extend Moonlit Candle from Claude Code to the whole terminal, so a new Windows Terminal tab looks like part of the same theme:

- Windows Terminal profile: Maple Mono NF, a faint starfield with a crescent moon, pink box cursor, moon tab icon.
- fish prompt: Tide recoloured to the palette, with today's moon phase as the first segment.
- A greeting ("the ritual") on every top-level shell: a live ASCII moon drawn to today's real phase, beside a salutation, the moon phase, a tarot card of the day and a short system fetch.

**Success:** after `python3 -m witchy install` and a Windows Terminal restart, a new Ubuntu tab matches sections 4–6; `python3 -m witchy uninstall` gives back the pink Tide prompt, the previous profile settings and the previous greeting, leaving only the Maple Mono font files installed.

## 2. Scope

In:

1. Windows Terminal profile settings for the Ubuntu profile (section 4), including a generated background image.
2. Maple Mono NF download and per-user install on Windows (section 4.3).
3. Profile lookup fix: find the `CanonicalGroupLimited.*` Ubuntu profile without `WT_PROFILE_ID` (section 4.1).
4. Tide recolour and prompt layout, plus a `moon` Tide item (section 5).
5. The greeting `fish_greeting` and a `ritual` command (section 6).
6. Repo housekeeping: adopt the user's edited output style into `content/output-style.md`; translate `README.md` to English; new docs in English.

Out:

- A light "dawn" variant or any variant switching.
- Themes for bat, eza, fzf, tmux, btop.
- Installing fish, fisher or Tide. If Tide is missing, the prompt step is skipped with a warning.
- Removing Maple Mono on uninstall (section 7.3).
- The hidden duplicate `Windows.Terminal.Wsl` "Ubuntu" profile; only the visible profile is themed.

Consequence the user accepted: the right prompt shows only `status cmd_duration time`. Tide's current right items (`context jobs direnv bun node python … zig`) are dropped while installed and restored on uninstall.

## 3. Architecture

The existing `witchy` package grows; there is still one installer, one `state.json` and one palette. Python 3.10+, stdlib only.

New and changed modules:

| Module | Purpose |
| :- | :- |
| `witchy/palette.py` | **changed:** adds `WT_PROFILE`, `TIDE`, `RITUAL` and `BACKGROUND_IMAGE` constants |
| `witchy/wt.py` | **changed:** `find_profile` fix; `apply_profile` / `restore_profile` for profile keys (same snapshot/put-back rules as `colorScheme`) |
| `witchy/background.py` | renders the background PNG with a stdlib PNG writer (`zlib` + `struct`), deterministic |
| `witchy/fonts.py` | downloads, verifies and registers Maple Mono NF on the Windows side |
| `witchy/fishvars.py` | snapshots, sets and restores fish universal variables by running `fish` |
| `witchy/ritual.py` | standalone greeting script (stdlib only, imports nothing from `witchy`); `build` rewrites its `# BEGIN PALETTE` block like `statusline.py` |
| `witchy/build.py` | **changed:** renders the ritual script, `ritual.json` and background PNG into `dist/` |
| `witchy/install.py` | **changed:** home-relative copies, new plan steps, state v2 |
| `witchy/validate.py` | **changed:** rules for the new palettes and `ritual.json` (section 8) |
| `content/ritual.json` | greeting data: the salutation `name` and the 22 Major Arcana with upright and reversed meanings |
| `content/fish/*.fish` | fish function and conf.d templates with `@PYTHON@` and `@WITCHY_DIR@` placeholders, filled at install |

### 3.1 Installed files

`COPIES` targets become relative to `HOME` instead of `~/.claude` (existing entries gain the `.claude/` prefix; `state.json` already stores absolute paths, so no migration is needed for them).

| `dist/` file | Installed at |
| :- | :- |
| `claude/witchy/ritual.py` | `~/.claude/witchy/ritual.py` |
| `claude/witchy/ritual.json` | `~/.claude/witchy/ritual.json` |
| `fish/functions/fish_greeting.fish` | `~/.config/fish/functions/fish_greeting.fish` |
| `fish/functions/ritual.fish` | `~/.config/fish/functions/ritual.fish` |
| `fish/functions/_tide_item_moon.fish` | `~/.config/fish/functions/_tide_item_moon.fish` |
| `fish/conf.d/witchy.fish` | `~/.config/fish/conf.d/witchy.fish` |
| `windows-terminal/moonlit-candle-night.png` | `<WT LocalState>/moonlit-candle-night.png` (next to Windows Terminal's `settings.json`; recorded in the `windows_terminal` state entry, not in `files`) |

The fish files are rendered at install time (they need the chosen Python path and `~/.claude/witchy`), so they are part of the install plan, not of `build.render_outputs()`; `--dry-run` shows them like any other file.

### 3.2 State

`STATE_VERSION` becomes 2. `_load_state` accepts 1 and 2; a version 1 state has no `fish`, `fonts` or profile-key records, which means "not installed yet". Every install writes version 2. New top-level entries:

- `windows_terminal` gains `previous_profile_keys` (one snapshot per key in `WT_PROFILE`), `installed_profile_keys`, and `background_file` (`{path, existed, backup, installed_sha256}`).
- `fish`: `{"variables": {name: {"previous": snapshot, "installed": [values]}}}` or absent when the Tide step was skipped.
- `fonts`: `{"files": [windows paths], "registry_values": [names]}`, informational only (section 7.3).

Reinstall keeps the first recorded previous values, as today.

## 4. Windows Terminal

### 4.1 Profile lookup

`find_profile` order:

1. `WT_PROFILE_ID`, if it names an existing profile (unchanged).
2. Otherwise the single profile that is not `"hidden": true`, whose `name` equals `$WSL_DISTRO_NAME`, and whose `source` is `Microsoft.WSL`, `Windows.Terminal.Wsl` or starts with `CanonicalGroupLimited.`.
3. Zero or several matches: warn and skip Windows Terminal, as today.

On this machine step 2 selects `{51855cb2-8cce-5362-8f54-464b92b32386}` (`source` `CanonicalGroupLimited.Ubuntu_79rhkp1fndgsc`), the same profile the existing `state.json` records.

### 4.2 Profile keys (`palette.WT_PROFILE`)

Set on that profile only, each snapshotted before the first install:

```json
{
  "font": { "face": "Maple Mono NF", "size": 12, "cellHeight": "1.1" },
  "cursorShape": "filledBox",
  "padding": "14",
  "opacity": 93,
  "useAcrylic": true,
  "backgroundImage": "ms-appdata:///local/moonlit-candle-night.png",
  "backgroundImageOpacity": 0.12,
  "backgroundImageAlignment": "bottomRight",
  "backgroundImageStretchMode": "uniformToFill",
  "icon": "🌙",
  "tabTitle": "witchyterm",
  "suppressApplicationTitle": true
}
```

- `font` replaces the whole object, so the current `"features": {"aalt": 0}` goes away while installed. Ligatures stay on (Maple Mono default).
- The cursor colour already comes from the scheme (`cursorColor` `#FF67B7`).
- `suppressApplicationTitle` is what keeps the tab title at "witchyterm"; without it fish's `fish_title` overwrites it.
- If the font step (4.3) fails and Maple Mono NF is not already registered, `font` is left untouched and the install says so.
- Uninstall restores each key with the existing rule: only if it still holds the installed value; otherwise warn and leave it.

### 4.3 Maple Mono NF

- Source: the Maple Mono NF release zip from `github.com/subframe7536/maple-font` releases, pinned in `fonts.py` to one release tag and its SHA-256. A digest mismatch aborts the font step.
- Download cache: `~/.cache/witchy/`. The zip is reused when its digest matches.
- Files installed: `Regular`, `Italic`, `Bold`, `BoldItalic` TTFs only, copied to `/mnt/c/Users/<U>/AppData/Local/Microsoft/Windows/Fonts/`.
- Registration: `reg.exe add "HKCU\Software\Microsoft\Windows NT\CurrentVersion\Fonts" /v "<family style> (TrueType)" /t REG_SZ /d "C:\Users\<U>\AppData\Local\Microsoft\Windows\Fonts\<file>" /f`. No admin rights needed.
- Already installed (all four registry values present and pointing to existing files): nothing is downloaded or copied.
- Any failure (offline, `reg.exe` missing, write refused): warn, skip the font, continue the install.
- `--dry-run` prints what it would download and register, without network access.
- Windows Terminal needs a restart to see a newly installed font; the install prints that note.

### 4.4 Background image (`witchy/background.py`)

- 2560×1440 PNG, RGB, base `#0D0916`, generated with a fixed seed so the bytes are identical on every build.
- About 220 stars: single pixels and 2×2 dots in `#F3EAF7`, `#FFD477` and `#B99AFF`, plus 6–8 four-point sparkles.
- A crescent moon of radius 150 px centred about 260 px from the right and bottom edges, in `#FFD477` with a soft radial glow fading into the background.
- Shown at `backgroundImageOpacity` 0.12 over acrylic. Both the opacity and the image palette live in `palette.BACKGROUND_IMAGE`, so tuning is one edit.
- Written to `<WT LocalState>/moonlit-candle-night.png`; uninstall removes it (or restores the previous file if one existed).

## 5. Prompt (Tide)

### 5.1 Moon item

- `conf.d/witchy.fish` computes today's phase once per shell with fish `math` and stores the glyph in the global `_witchy_moon_glyph`.
- `_tide_item_moon` prints it with `_tide_print_item moon $_witchy_moon_glyph`.
- The phase algorithm matches `ritual.py` (section 6.2); a test compares both.

### 5.2 Variables (`palette.TIDE`)

Tide colours are written without `#`, as Tide expects.

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

The variable names are checked against Tide 6.1.1 during implementation; a test pins the list.

### 5.3 Install rules (`witchy/fishvars.py`)

- Tide check: `fish -c 'functions -q tide'`. Missing fish or Tide: warn, skip section 5, and still install the greeting.
- Snapshot each variable as `{"value": [list]}` or `{"absent": true}` before the first install.
- Set with `set -U name values…`, after the fish function files exist, so a running shell never sees `moon` in the items without `_tide_item_moon`.
- Uninstall: for each variable, restore the snapshot (or `set -e -U`) only if its current value equals the installed one; otherwise warn and leave it.
- Every `fish` call has a 5 s timeout. `ctx.run` is injectable, as for `cmd.exe`.
- Running shells keep their old prompt; the install says to open a new tab.

## 6. Greeting (the ritual)

### 6.1 When it runs

`fish_greeting` runs `@PYTHON@ -I @WITCHY_DIR@/ritual.py` only when **all** hold:

- `status is-interactive`
- `WT_SESSION` is set (inside Windows Terminal)
- `TMUX`, `CLAUDECODE` and `WITCHY_RITUAL_SHOWN` are unset, and `TERM_PROGRAM` is not `vscode`

After running it sets `set -gx WITCHY_RITUAL_SHOWN 1`, so nested shells and anything launched from this shell stay quiet. The `ritual` command runs the script regardless of these conditions. If the script or Python is missing, `fish_greeting` prints nothing.

### 6.2 Moon

- Phase age = days since the new moon of 2000-01-06 18:14 UTC, modulo 29.530588853.
- Illumination = `(1 − cos(2π · age / 29.530588853)) / 2`, shown as a whole percent.
- Eight names and glyphs by age (New 🌑, Waxing Crescent 🌒, First Quarter 🌓, Waxing Gibbous 🌔, Full 🌕, Waning Gibbous 🌖, Last Quarter 🌗, Waning Crescent 🌘), each bin 1/8 of the cycle centred on its phase.
- Northern-hemisphere view: waxing light on the right.
- Fixed checks: 2024-04-08 is New and 2024-09-18 is Full.

### 6.3 Art

- An ASCII disc 11 rows × 22 columns (2:1 cell aspect). Each cell is lit when it lies on the illuminated side of the terminator ellipse for the current age.
- Lit cells use `█▓▒` by distance from the limb, in `#FFD477` fading to `#FFE3A3`; unlit cells use `░` in `#38234D` (earthshine).
- 6–10 stars (`✦ ⋆ · ˚`) in `#B99AFF` and `#F3EAF7` around the disc, positioned by a seed derived from the date, so they change daily and stay still within a day.

### 6.4 Info column

```
Good witching hour, eimi
⋆ Waxing Gibbous  74%
✦ XVII · The Star (reversed)
  despair, lost faith; rest and wait
os      Ubuntu 24.04.4 LTS
kernel  6.6.87.2-microsoft-standard-WSL2
uptime  3h 12m
memory  4.1 / 15.6 GiB
shell   fish 3.7.0
```

- **Salutation** by local hour: 00–03 "Good witching hour", 04–11 "Good morning", 12–17 "Good afternoon", 18–23 "Good evening"; name from `ritual.json` → `name` (`eimi`).
- **Tarot:** `sha256("YYYY-MM-DD")` of the local date picks the card (`digest[0] mod 22`) and the orientation (reversed when `digest[1] < 85`, about one day in three). Meanings are at most 60 characters.
- **Fetch:** `PRETTY_NAME` from `/etc/os-release`, `os.uname().release`, `/proc/uptime`, `MemTotal − MemAvailable` from `/proc/meminfo`, and `fish $FISH_VERSION` (passed by the fish function). A missing value shows `--`.
- **Colours (`palette.RITUAL`):** salutation `#FFD477` bold; labels `#A99AB9`; values `#F3EAF7`; moon line `#B99AFF`; tarot name `#FF67B7`; reversed marker and meaning `#CFC3DB`.

### 6.5 Layout and safety

- Columns from `shutil.get_terminal_size()`. At 80 or more: art left, three spaces, info right, vertically centred against the art. Under 80: art first, info below.
- One blank line after the greeting.
- Any exception: print nothing and exit 0. The shell must never break because of the greeting.
- Budget: median wall time of the script under 200 ms (10 runs, warm cache).

## 7. Install and uninstall

### 7.1 Install order

1. Validate (section 8); abort on failure, as today.
2. Plan everything: home copies (Claude and fish files), Claude settings, Windows Terminal (scheme, profile keys, background file), fonts, fish variables. `--dry-run` shows all of it and writes nothing.
3. Apply local files and Claude settings, then save state.
4. Fonts (Windows side), then Windows Terminal settings and background file, saving state after each.
5. fish variables last, saving state.
6. Print notes: restart Windows Terminal (font), open a new tab (prompt), restart Claude Code if the theme does not update.

Each Windows-side or `fish` step can fail on its own without undoing the others; the state written so far always describes what is really installed.

### 7.2 Upgrade from the current install

The machine already has a version 1 state. The first v2 install keeps every recorded previous value (`colorScheme`, Claude keys, files) and records fresh snapshots only for what is new. The adopted output style equals the installed file, so it produces no change.

### 7.3 Uninstall

Gives back everything in this spec plus everything the 2026-09-30 spec lists, with the existing "only if still ours" rule. Removes the fish files, `ritual.py`, `ritual.json` and the background image. The Maple Mono files and registry values stay; restoring `font` returns the profile to FiraCode Nerd Font. The `fonts` record is dropped from state.

## 8. Validation additions

1. `ritual.json` → `tarot`: exactly 22 cards, `number` 0–21 each once, unique names, `upright` and `reversed` non-empty and at most 60 characters.
2. `ritual.json` → `name`: non-empty, at most 24 characters.
3. Text colours in `RITUAL` at least 4.5:1 on `#0D0916`; the earthshine `#38234D` and the stars are exempt as decorative.
4. Tide pairs at least 4.5:1: each segment's text colour on its background (moon, pwd anchors and dirs, git colours on all three git backgrounds, status, cmd_duration, time), and `character` colours on `#0D0916`. `tide_pwd_color_truncated_dirs` and the frame colour need 3:1.
5. All new colours match `^#?[0-9A-F]{6}$` (Tide values without `#`).

## 9. Tests

`python3 -m unittest discover -s tests -t .` with `/usr/bin/python3` (3.12) and `/usr/bin/python3.10`. Nothing touches the real `~/.claude`, `~/.config/fish`, Windows Terminal, registry or network.

- **wt:** lookup by `WT_PROFILE_ID`, by Canonical source, hidden duplicate ignored, zero and two matches; profile keys apply and restore; a key the user changed is kept with a warning.
- **background:** PNG signature, size 2560×1440, byte-identical across two renders, moon pixels in the bottom-right quadrant.
- **fonts:** fake downloader and fake `reg.exe` via `ctx.run`: fresh install, already installed, digest mismatch, offline; dry run makes no calls.
- **fishvars:** fake runner for snapshot/set/restore rules; one integration test with real `fish` and a temporary `XDG_CONFIG_HOME`, skipped when `fish` is missing.
- **ritual:** phase for the two fixed dates and bin edges; disc shape for New (no lit cells), Full (all cells lit) and First Quarter (right half lit); tarot pick is stable per date; wide and narrow layouts; missing `/proc` values; exceptions exit 0 with no output. The fish phase glyph matches `ritual.py` for 60 consecutive days (real `fish`, skipped if missing).
- **install:** v1 state upgrade keeps old previous values; full install then uninstall restores every file byte for byte (excluding backups) and every fish variable; Tide missing skips section 5 only; font failure leaves `font` untouched; dry run writes nothing.
- **validate:** each new rule catches an injected failure; the real content passes.

## 10. Acceptance criteria

1. `python3 -m witchy validate` exits 0; all tests pass on 3.12 and 3.10.
2. `python3 -m witchy install --dry-run` on the real machine shows only the changes in sections 3–5.
3. After a real install and a Windows Terminal restart, a new Ubuntu tab shows: Maple Mono NF, the starfield and moon, the pink box cursor, 🌙 and "witchyterm" on the tab, the side-by-side greeting, and the recoloured prompt starting with today's moon glyph.
4. No greeting inside tmux, in a nested `fish`, or in a shell started by Claude Code; `ritual` shows it anywhere.
5. The greeting's median time is under 200 ms (`ritual.py`, 10 runs).
6. A screenshot of criterion 3 is attached to the PR.
7. `uninstall` brings back the pink 🌸 Tide prompt, the previous profile settings and the default greeting; the user then reinstalls if they want.
