# Moonlit Candle

A witchy theme for Claude Code and Windows Terminal on WSL, inspired by [WitchyNibbles/Spellbound-Themes](https://github.com/WitchyNibbles/Spellbound-Themes): an aubergine night background, candle-gold accents, and pink for permissions.

It installs:

- The `moonlit-candle` Claude Code theme (`~/.claude/themes/`)
- Maple Mono NF for your Windows user (no admin rights needed; it stays installed after uninstall)
- On your WSL profile in Windows Terminal: the "Moonlit Candle" colour scheme, Maple Mono NF, a box cursor, a 🌙 tab titled "witchyterm", and a starfield whose moon shows the current phase
- Spinner verbs and tips (`spinnerVerbs`, `spinnerTipsOverride`)
- The "WitchyNibbles" output style, which only changes the tone of chat replies
- A status line with moon phases for context used, 5 h / 7 d limits, and git

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

Components, in install order: `claude`, `font`, `windows-terminal`.

`install` backs up every file it changes as `*.bak-witchy-<date>` and records the previous values in `~/.claude/witchy/state.json`; `uninstall` restores them. A `settings.json` that is not strict JSON (comments, trailing commas) is never rewritten: for Windows Terminal you get a snippet to paste by hand and the rest continues; for `~/.claude/settings.json` the install stops without changing anything.

Exit codes for `install` and `uninstall`: `0` everything done, `1` nothing changed, `2` done with warnings (a component was skipped or failed; the last line says which).

Restart Claude Code and Windows Terminal after installing.

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
| `✗ windows-terminal  profile keys changed: …` | a profile setting no longer holds the witchy value | `python3 -m witchy install --only windows-terminal`, or keep your change |
| `✗ windows-terminal  changed or missing: …` | a sky image or `ritual-config.json` was edited or deleted | `python3 -m witchy install --only windows-terminal` |
| `⚠ …  backup … is missing` | a backup was deleted | uninstall still works, key by key |
| `⚠ …  last install (…): skipped: …` | a component was skipped at the last install | read the reason, then install `--only` that component |
| `✗ state  … damaged` | `state.json` is not readable | fix or remove the file by hand |

`install` and `uninstall` stop with `another witchy command is running` (exit 1) while a second witchy command holds the lock; wait for it to finish.

## Development

```sh
/usr/bin/python3 -m unittest discover -s tests -t . -v
/usr/bin/python3.10 -m unittest discover -s tests -t .
```

Colours live in `witchy/palette.py` (`VARIANTS`). Each installable piece is a component in `witchy/components/`. Designs: `docs/superpowers/specs/`. Architecture diagram: `docs/diagrams/witchy-components.html`.
