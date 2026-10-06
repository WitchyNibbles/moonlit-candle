# Moonlit Candle

A witchy theme for Claude Code and Windows Terminal on WSL, inspired by [WitchyNibbles/Spellbound-Themes](https://github.com/WitchyNibbles/Spellbound-Themes): an aubergine night background, candle-gold accents, and pink for permissions.

It installs:

- The `moonlit-candle` Claude Code theme (`~/.claude/themes/`)
- Maple Mono NF for your Windows user (no admin rights needed; it stays installed after uninstall)
- On your WSL profile in Windows Terminal: the "Moonlit Candle" colour scheme, Maple Mono NF, a box cursor, a 🌙 tab titled "witchyterm", and a starfield whose moon shows the current phase
- Windows Terminal's default colour scheme becomes "Moonlit Candle" when it was `PastelOneDark`; that old scheme is removed from every profile and from `schemes` (uninstall gives it back)
- Spinner verbs and tips (`spinnerVerbs`, `spinnerTipsOverride`)
- The "WitchyNibbles" output style, which only changes the tone of chat replies
- A status line with moon phases for context used, 5 h / 7 d limits, and git
- For fish: fisher 4.4.5 and Tide 6.1.1 when they are missing, every file checked against the pinned release, and Tide as the only prompt; the Tide prompt recoloured, with tonight's moon phase as its first segment; a greeting on new Windows Terminal tabs (a moon drawn to tonight's phase, the Wheel of the Year, a tarot card of the day and a short system summary); `ll` and `lt` through eza

## Usage

```sh
/usr/bin/python3 -m witchy validate                      # contrast, tokens and content
/usr/bin/python3 -m witchy install --dry-run             # show every change without writing
/usr/bin/python3 -m witchy install                       # install everything
/usr/bin/python3 -m witchy install --fresh               # on a new WSL box: apt install fish, curl, eza first (asks)
/usr/bin/python3 -m witchy install --only claude         # re-apply one component
/usr/bin/python3 -m witchy doctor                        # check what is installed and how to fix it
/usr/bin/python3 -m witchy doctor --fix                  # re-install what doctor marks ✗, then check again
/usr/bin/python3 -m witchy mood                          # show the active colour variant
/usr/bin/python3 -m witchy uninstall                     # give everything back
```

Components, in install order: `claude`, `font`, `windows-terminal`, `tide`, `fish`.

- `tide` installs [fisher](https://github.com/jorgebucaran/fisher) 4.4.5 and [Tide](https://github.com/IlanCosman/tide) 6.1.1 when they are missing (fisher needs `curl`), replaces another Tide version, and checks every file against `content/pins.json` twice: each release before fisher installs it (nothing unverified runs), and each installed file after. If the check after fails, fisher and a freshly installed Tide are removed again; a Tide that replaced another one is swapped back for the earlier version, with your Tide variables kept. It makes Tide the only prompt: a hand-written `functions/fish_prompt.fish` is moved aside, another fisher prompt plugin (pure, hydro, …) is removed, and `starship init`, `oh-my-posh init` and `set -g tide_…` lines in `config.fish` and `conf.d` are commented out with `# witchy-disabled: `, after a backup. Text inside comments and quotes is not mistaken for such a line. A `function fish_prompt` block, a line that cannot be commented out safely (continued with `\`, `&&`, `||` or `|`, or one that opens or closes a block), and a symlinked `config.fish`, `conf.d` file or folder (only when it holds a line witchy would disable) are never edited: install fails and says what to change. Downloads and fisher's output go to `~/.cache/witchy/install.log`. `uninstall` gives all of it back: a Tide that witchy installed fresh is removed with a plain `fisher remove`, so its variables go with it; an earlier Tide is swapped back and your Tide variables are kept; fisher is removed only when witchy installed it.
- `fish` sets every Tide variable once Tide 6.1.1 is the active prompt. Without it, `fish` still installs the greeting and `ll`/`lt`, and the summary line says `skipped: Tide not ready (run: python3 -m witchy install --only tide)` (or `skipped: fish not found`).
- `install --fresh` first lists which of `fish`, `curl` and `eza` are missing, asks once before `sudo apt-get install`, and offers `chsh -s` to make fish the login shell. It needs a terminal to ask.

`install` backs up every file it changes as `*.bak-witchy-<date>` and records the previous values in `~/.claude/witchy/state.json`; `uninstall` restores them. A `settings.json` that is not strict JSON (comments, trailing commas) is never rewritten: for Windows Terminal you get a snippet to paste by hand and the rest continues; for `~/.claude/settings.json` the install stops without changing anything.

Exit codes for `install` and `uninstall`: `0` everything done, `1` nothing changed, `2` done with warnings (a component was skipped or failed: install names it in its summary line, `4/5 components installed · skipped: …`, and, for every component whose result is not ok, in a `✗✗✗ witchy is NOT fully installed ✗✗✗` banner below it with each reason; uninstall in its last line, `… still installed: …`).

Restart Claude Code and Windows Terminal after installing, and open a new tab for the new prompt and greeting.

## The greeting

A new top-level Windows Terminal tab shows the full ritual; another tab within 10 minutes, or a window narrower than 60 columns, shows a one-line omen instead. tmux, VS Code, Claude Code's shells and nested shells stay quiet.

```sh
ritual                     # the full ritual, anywhere
ritual --date 2026-10-31   # preview another day
ritual --debug             # time each stage
```

The sky job runs in the background when a tab opens and moves the Windows Terminal moon to tonight's phase. Errors from the greeting and the sky job go to `~/.cache/witchy/ritual.log`; `doctor` shows the newest ones.

## Troubleshooting

Run `python3 -m witchy doctor`. Each `⚠` or `✗` line is followed by what fixes it. `doctor --fix` re-installs every component that a `✗` line's fix names (`python3 -m witchy install --only <component>`, even when the `✗` is on another component's line), then checks again (exit 0 when no `✗` is left); `⚠` lines and fixes you do by hand are only printed. A `·` line is information, never a problem.

| Doctor says | Meaning | Fix |
| :- | :- | :- |
| `✗ claude  changed or missing: …` | an installed file was edited or deleted | `python3 -m witchy install --only claude` |
| `✗ claude  settings changed: theme, …` | a settings key no longer holds the witchy value | same as above, or keep your change |
| `✗ windows-terminal  profile colour scheme is …` | the profile uses another scheme | `python3 -m witchy install --only windows-terminal` |
| `⚠ windows-terminal  not installed` | `settings.json` was not found (install prints "Windows Terminal settings.json not found") or the profile did not match | pass `--wt-settings PATH` or set `WT_PROFILE_ID`, then install |
| `⚠ font  not installed` | Maple Mono NF was not downloaded or registered | `python3 -m witchy install --only font`, then restart Windows Terminal |
| `✗ font  not registered: …` | a font registry value is gone | same as above |
| `✗ font  changed or missing: …` | a Maple Mono NF file witchy installed was edited or deleted | `python3 -m witchy install --only font`, then restart Windows Terminal |
| `⚠ font  cannot read the font registry (reg.exe)` | `reg.exe` could not be run from WSL | check that Windows interop is enabled, then run doctor again |
| `✗ windows-terminal  profile keys changed: …` | a profile setting no longer holds the witchy value | `python3 -m witchy install --only windows-terminal`, or keep your change |
| `✗ windows-terminal  changed or missing: …` | a sky image or `ritual-config.json` was edited or deleted | `python3 -m witchy install --only windows-terminal` |
| `✗ windows-terminal  PastelOneDark is still in settings.json: …` | an old scheme is still defined, the default, or set on a profile | `python3 -m witchy install --only windows-terminal` (uninstall gives it back) |
| `⚠ …  backup … is missing` | a backup was deleted | uninstall still works, key by key |
| `✗ fish  changed or missing: …` | a fish function, `conf.d/witchy.fish` or a greeting file was edited or deleted | `python3 -m witchy install --only fish` |
| `✗ fish  prompt variables changed: …` | a Tide variable no longer holds the witchy value (for example after `tide configure`) | `python3 -m witchy install --only fish`, or `doctor --fix` |
| `✗ fish  tide_… is overridden by a global in config.fish or conf.d` | a `set -g tide_…` line hides witchy's value in every new shell | `python3 -m witchy install --only tide` comments the line out |
| `⚠ fish  Tide variables not checked: …` | Tide is missing, not 6.1.1, or not the active prompt (the `tide` lines say which) | `python3 -m witchy install --only tide` |
| `✗ tide  fisher not found` or `Tide not found` | fisher or Tide is not installed | `python3 -m witchy install --only tide` |
| `✗ tide  Tide is …, not 6.1.1` or `ilancosman/tide files do not match the pinned release: …` | another Tide version, or a Tide file was edited | `python3 -m witchy install --only tide` puts Tide 6.1.1 back |
| `✗ tide  fish_prompt is not Tide's (…)` | another `fish_prompt` is the active one | `python3 -m witchy install --only tide` |
| `✗ tide  starship init in ~/.config/fish/config.fish line N is active` | a line witchy commented out was turned back on, or a new one appeared | `python3 -m witchy install --only tide` |
| `✗ tide  config.fish defines fish_prompt at line N` | a `function fish_prompt` block in `config.fish` or `conf.d` | remove that function by hand, then install |
| `✗ tide  config.fish line N is continued over several lines` or `opens or closes a block` | the line cannot be commented out without breaking the commands around it | comment out that line yourself |
| `✗ tide  config.fish is a symlink to …` | the file, its `conf.d` folder or fish's config folder is a link into another place (a dotfiles repository) | comment out the named line there yourself |
| `⚠ tide  fisher is …; witchy was tested with 4.4.5` | your own fisher, another version; witchy leaves it alone | nothing to do |
| `· tide  glyph test: …` | each symbol should show as one clear glyph | if one shows as a box or two, check the font (Maple Mono NF) |
| `tide: failed: curl not found (sudo apt install curl)` (install) | fisher downloads with curl | `sudo apt install curl`, or `install --fresh` |
| `tide: failed: could not install Tide (exit 1): … (details: ~/.cache/witchy/install.log)` (install) | fisher could not download or install Tide | read the log, check the network, install again |
| `⚠ fish  cannot check the Tide variables: …` or `⚠ tide  cannot check fisher and Tide: …` | `fish` is not on PATH, or did not answer within 5 s | put `fish` on PATH (`install --fresh` installs it), or run doctor again |
| `⚠ fish  sky: the sky job failed today (it retries tomorrow)` | the sky job failed today and logged no error from today | `tail -n 20 ~/.cache/witchy/ritual.log` |
| `⚠ fish  eza missing — sudo apt install eza` | `ll` and `lt` fall back to `ls` | `sudo apt install eza` |
| `⚠ fish  greeting: last run failed …` | the greeting hit an error in the last 7 days and printed nothing | `tail -n 20 ~/.cache/witchy/ritual.log`; `ritual` shows the greeting |
| `⚠ fish  sky: last run failed …` | the sky job could not move the moon (for example, you set your own `backgroundImage`); it retries once a day | `python3 -m witchy install --only windows-terminal` puts the moon sky back |
| `⚠ …  last install (…): skipped: …` or `failed: …` | a component was skipped or failed at the last install | read the reason, then install `--only` that component |
| `✗ state  … damaged` | `state.json` is not readable | fix or remove the file by hand |

`install` and `uninstall` stop with `another witchy command is running` (exit 1) while a second witchy command holds the lock; wait for it to finish.

## Development

```sh
/usr/bin/python3 -m unittest discover -s tests -t . -v
/usr/bin/python3.10 -m unittest discover -s tests -t .
```

Colours live in `witchy/palette.py` (`VARIANTS`). Each installable piece is a component in `witchy/components/`. Designs: `docs/superpowers/specs/`. Architecture diagram: `docs/diagrams/witchy-components.html`.
