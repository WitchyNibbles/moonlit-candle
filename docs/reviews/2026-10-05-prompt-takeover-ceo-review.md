# CEO review: prompt takeover

- **Date:** 2026-10-05
- **Spec:** [`2026-10-05-witchy-prompt-takeover-design.md`](../superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md)
- **Status:** DONE

## Summary

- **Mode:** SCOPE EXPANSION, approach C (the spec as written, including full takeover of other prompt owners).
- **Strongest challenges:**
  1. Every fish call has a 5 s timeout and discards its output (`base.py:21`, `base.py:236`), so `fisher install` would time out on a slow connection and its error would be lost.
  2. fisher and Tide are fetched by tag, and only two files were to be checked, although every Tide file runs in every shell.
  3. `fish` skipping "when `tide` did not end ok" breaks `install --only fish` and `doctor --fix`.
- **Recommended path:** fold the decisions below into the spec, have the user approve it, then write the implementation plan.
- **Accepted scope:** the spec's sections 5–13, plus `install --fresh`, `preview`, the seasonal caret and `doctor --fix`.
- **Deferred:** none.
- **NOT in scope:** `witchy fingerprint` (declined), the greeting layout, the hidden duplicate "Ubuntu" profile, Windows Terminal Preview, `~/projects/pastel-princess/`.

## Expansions

| # | Expansion | Decision |
| :- | :- | :- |
| E1 | `install --fresh`: apt-installs fish, curl and eza after one prompt, offers `chsh` | in |
| E2 | `fingerprint`: one hash per area to compare PCs | out |
| E3 | `preview`: draw the prompt from the palette without installing | in |
| E4 | Seasonal caret: the caret takes the sabbat colour on the day and the day before | in |
| E5 | `doctor --fix`: re-install the components doctor marks ✗ | in |

## Issues

| # | Section | Issue | Decision |
| :- | :- | :- | :- |
| 1 | Architecture | `fish` depended on this run's `tide` result | `fish` checks Tide 6.1.1 and the active `fish_prompt` itself |
| 2 | Architecture | A background job cannot set a variable in the shell | The sky job writes `~/.cache/witchy/caret`; `conf.d` reads it |
| 3 | Errors | 5 s timeout and lost output for fisher | `Command.timeout` (120 s for downloads), output in `~/.cache/witchy/install.log` |
| 4 | Security | Only two fisher/Tide files verified | `content/pins.json` with every file's SHA-256; mismatch removes and fails |
| 5 | Data flow | A symlinked `config.fish` would be replaced by a file | Refuse, naming the target and line |
| 6 | Code quality | 161 values hand-typed in `palette.py` | Generated `content/tide-6.1.1-defaults.json` plus overrides in `palette.TIDE` |
| 7 | Tests | The real download path never runs in CI | Weekly scheduled job plus manual dispatch |

Sections 7–11 found no further decisions. Defaults adopted: doctor reports the caret cache, doctor's interactive read has a 15 s timeout, `fish_emoji_width` is pinned to `2`, and state keeps version 2 with new entries.
