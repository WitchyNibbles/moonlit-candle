# Moonlit Candle

A witchy theme for Claude Code and Windows Terminal on WSL, inspired by [WitchyNibbles/Spellbound-Themes](https://github.com/WitchyNibbles/Spellbound-Themes): an aubergine night background, candle-gold accents, and pink for permissions.

It installs:

- The `moonlit-candle` Claude Code theme (`~/.claude/themes/`)
- Maple Mono NF for your Windows user (no admin rights needed; it stays installed after uninstall)
- On your WSL profile in Windows Terminal: the "Moonlit Candle" colour scheme, Maple Mono NF, a box cursor, a 🌙 tab titled "witchyterm", and a starfield whose moon shows the current phase
- Spinner verbs and tips (`spinnerVerbs`, `spinnerTipsOverride`)
- The "WitchyNibbles" output style, which only changes the tone of chat replies
- A status line with moon phases for context used, 5 h / 7 d limits, and git
- For fish: the Tide prompt recoloured, with tonight's moon phase as its first segment; a greeting on new Windows Terminal tabs (a moon drawn to tonight's phase, the Wheel of the Year, a tarot card of the day and a short system summary); `ll` and `lt` through eza

## Usage

```sh
/usr/bin/python3 -m witchy validate                      # contrast, tokens and content
/usr/bin/python3 -m witchy install --dry-run             # show every change without writing
/usr/bin/python3 -m witchy install                       # install everything
/usr/bin/python3 -m witchy install --only claude         # re-apply one component
/usr/bin/python3 -m witchy doctor                        # check what is installed and how to fix it
/usr/bin/python3 -m witchy mood                          # show the active colour variant
/usr/bin/python3 -m witchy uninstall                     # give everything back
```

Components, in install order: `claude`, `font`, `windows-terminal`, `fish`. The `fish` component needs [Tide](https://github.com/IlanCosman/tide) for the prompt colours; without Tide (or fish) it still installs the greeting and `ll`/`lt`, and the last line says `skipped: Tide not found`.

`install` backs up every file it changes as `*.bak-witchy-<date>` and records the previous values in `~/.claude/witchy/state.json`; `uninstall` restores them. A `settings.json` that is not strict JSON (comments, trailing commas) is never rewritten: for Windows Terminal you get a snippet to paste by hand and the rest continues; for `~/.claude/settings.json` the install stops without changing anything.

Exit codes for `install` and `uninstall`: `0` everything done, `1` nothing changed, `2` done with warnings (a component was skipped or failed; the last line says which).

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

Run `python3 -m witchy doctor`. Each `⚠` or `✗` line is followed by the command that fixes it.

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
| `⚠ …  backup … is missing` | a backup was deleted | uninstall still works, key by key |
| `✗ fish  changed or missing: …` | a fish function, `conf.d/witchy.fish` or a greeting file was edited or deleted | `python3 -m witchy install --only fish` |
| `✗ fish  Tide variables changed: …` | a Tide colour no longer holds the witchy value (for example after `tide configure`) | `python3 -m witchy install --only fish`, or keep your change |
| `⚠ fish  cannot check the Tide variables: …` | `fish` did not answer within 5 s | run doctor again |
| `⚠ fish  eza missing — sudo apt install eza` | `ll` and `lt` fall back to `ls` | `sudo apt install eza` |
| `⚠ fish  greeting: last run failed …` | the greeting hit an error in the last 7 days and printed nothing | see `~/.cache/witchy/ritual.log`; `ritual` shows the greeting |
| `⚠ fish  sky: last run failed …` | the sky job could not move the moon (for example, you set your own `backgroundImage`); it retries once a day | `python3 -m witchy install --only windows-terminal` puts the moon sky back |
| `⚠ …  last install (…): skipped: …` | a component was skipped or failed at the last install | read the reason, then install `--only` that component |
| `✗ state  … damaged` | `state.json` is not readable | fix or remove the file by hand |

`install` and `uninstall` stop with `another witchy command is running` (exit 1) while a second witchy command holds the lock; wait for it to finish.

## Development

```sh
/usr/bin/python3 -m unittest discover -s tests -t . -v
/usr/bin/python3.10 -m unittest discover -s tests -t .
```

Colours live in `witchy/palette.py` (`VARIANTS`). Each installable piece is a component in `witchy/components/`. Designs: `docs/superpowers/specs/`. Architecture diagram: `docs/diagrams/witchy-components.html`.
