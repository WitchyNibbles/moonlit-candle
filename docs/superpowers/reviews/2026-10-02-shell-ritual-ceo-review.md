# CEO review: Shell Ritual spec

- **Date:** 2026-10-02
- **Spec:** [`../specs/2026-10-02-shell-ritual-design.md`](../specs/2026-10-02-shell-ritual-design.md) (revision 2 incorporates every decision below)
- **Diagram:** [`../../diagrams/witchy-components.html`](../../diagrams/witchy-components.html)
- **Status:** DONE. All 11 sections evaluated.

## Summary

- **Approach:** C, refactor the installer into components first, then build the shell features on top.
- **Mode:** scope expansion. Every expansion was opted into individually.
- **Strongest challenges:**
  1. Two writers on Windows Terminal's `settings.json` (installer and the runtime sky job). Resolved with a shared `flock`, hash re-check and atomic replace; the windows-terminal component owns all 8 sky values.
  2. Silent partial installs (offline font, missing Tide). Resolved with exit code 2, an end-of-install summary, `last_install` in state and `witchy doctor`.
  3. Publishing personal details in a public repo. Resolved by rewording the output style neutrally.
- **Recommended path:** the user reviews spec revision 2, then writing-plans. The plan follows strict C order: refactor, then components, then greeting.

## Accepted scope

Baseline (spec revision 1) plus:

| Item | Decision |
| :- | :- |
| Architecture | Component contract `plan / apply / restore / check`, runner loop, state v2 with v1 migration |
| `witchy doctor` | In |
| Real-moon sky | In: 8 pre-rendered phase images, swapped by a background job; gated on a spike proving Windows Terminal hot-reloads a changed `backgroundImage` path, with a fixed-crescent fallback |
| Wheel of the Year and lunar events | In: 8 sabbats (Meeus for solstices and equinoxes), 7-day countdown, seasonal accent, full, new and blue moon lines |
| Variants | Variant-ready palette and components; `mood` command with only `midnight` |
| eza | In: `EZA_COLORS`, `ll` and `lt` functions with `ls` fallback; eza is not installed by witchy |
| Sky job placement | Background job from `conf.d`, gated by a stamp file |
| Exit codes | 0 ok, 1 nothing changed, 2 installed with warnings |
| Output style | Neutral wording in the repo, same rules |
| Split panes | One-line omen within 10 minutes of the last full ritual or under 60 columns |
| Greeting code | Directory package `witchy/ritual/`, installed to `~/.claude/witchy/ritual/` |
| CI | GitHub Actions, Python 3.10 and 3.12, with fish |
| Partial runs | `--only <component>` for install and uninstall |
| Sequencing | Strict C order |

## Deferred

- **Dawn variant palette:** the architecture is variant-ready; only the palette design remains.
- **bat theme (`.tmTheme`) and fzf colours:** about 3 hours together; add as a component later.

## Not in scope

- Installing fish, fisher, Tide or eza.
- Removing Maple Mono on uninstall.
- The hidden duplicate `Windows.Terminal.Wsl` profile.
- Windows Terminal Preview.

## Section findings

1. **Architecture:** component contract, ordering claude → font → windows-terminal → fish, state v2, reverse-order uninstall, install-time sky config written by the windows-terminal component.
2. **Error and rescue:** every failure named with its rescue and message (spec section 9); greeting catch-all logs to `~/.cache/witchy/ritual.log` and doctor surfaces it.
3. **Security:** pinned font digest, safe zip extraction, list-argument subprocesses, control-character stripping in the greeting, shared lock for `settings.json`, absolute interpreter path.
4. **Data flow:** hand-installed fonts detected by family, per-prompt moon recompute, once-a-day retry on sky failures, install lock, export flags in Tide snapshots.
5. **Code quality:** `witchy/components/` package, one moon algorithm per language with a parity test, no plugin registry, injectable `run`, `now`, `fetch`.
6. **Tests:** coverage map in spec section 12; v1 fixture from the real state, golden art files, Tide stub, 1 s timing guard, CI.
7. **Observability:** doctor, `last_install`, `ritual --debug`, README troubleshooting table.
8. **State:** doctor verifies backups that state depends on; `~/.cache/witchy/` is disposable.
9. **CLI contract:** existing commands unchanged; new `doctor`, `mood`, `--only`.
10. **Performance:** shell start under 1 ms extra, greeting about 30 ms, cached sky renders, doctor under 2 s.
11. **Design and UX:** hierarchy, `NO_COLOR`, contrast-validated colours, shared glyph set with the status line.
