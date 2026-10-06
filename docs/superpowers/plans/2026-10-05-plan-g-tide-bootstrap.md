# Plan G: Tide Bootstrap and Install Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `python3 -m witchy install` on a PC that has only fish ends with fisher 4.4.5 and Tide 6.1.1 installed (every file checked against pinned hashes), Tide as the only prompt, and the witchy prompt set in the same run. Anything that did not happen gives a banner and exit 2; doctor checks the whole chain and `doctor --fix` repairs what a witchy command can; `install --fresh` installs the apt packages a new WSL box lacks; uninstall gives everything back.

**Architecture:** A new `tide` component (`witchy/components/tide.py`) sits between `windows-terminal` and `fish`. It reads fish once through Plan F's `fishprobe`, decides what to install (Task 4), finds other prompt owners with the new `witchy/takeover.py` (Tasks 2 and 5), runs fisher with a 120 s timeout and logs its output to `~/.cache/witchy/install.log` (`witchy/installlog.py`, Task 3), and checks every installed file against `content/pins.json`, which `scripts/pins.py` generates from the real releases (Task 1). Uninstall and doctor follow (Tasks 6 and 7). The runner gains `Plan.replan`, so `fish` is planned again after `tide` applied, and an install banner (Task 8). Tasks 9–12 add the real-fish and weekly network tests, `doctor --fix`, `install --fresh` and the README. Task 13 runs the result end to end in temporary HOMEs.

**Tech Stack:** Python 3.10+ standard library only (`subprocess`, `tarfile`, `hashlib`, `urllib`, `unittest`); fish 3.7; fisher 4.4.5 and Tide 6.1.1 (downloaded only by `scripts/pins.py`, the opt-in network test and Task 13).

**Spec:** `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (revision 2, as Plan F corrected it), sections 5, 9.1 (the `tide` checks), 9.2 (the banner), 10, 12 (the tests for these, `network.yml`), 15.1 and 15.4, and the "Plan G must know" notes in Plan F's header. Tasks that change behaviour or correct the spec edit the spec in the same commit (5.1, 5.2, 9.1, 9.2, 10, 15.1). Plan G is the second of three: it executes **after Plan F** and is written against branch `proto/plan-f` at `f811020` (Plan F's prototype after Plan F regenerated its Tide defaults from the 6.1.1 release; Plan F reproduces it). Plan H (Windows Terminal purge, seasonal caret, preview, docs purge) is rebased onto this plan's result.

## Global Constraints

- Python 3.10 or newer, standard library only. Every test passes on `/usr/bin/python3` (3.12) and `/home/eimi/.pyenv/versions/3.10.0/bin/python3`.
- Test command, from the repo root: `/usr/bin/python3 -m unittest discover -s tests -t .`, and the same with the 3.10 interpreter. `python3 -m witchy validate` must print `Moonlit Candle: all checks passed`.
- No test touches the real `~/.claude`, `~/.cache`, `~/.config/fish`, fish universal variables, Windows Terminal, `cmd.exe`, `reg.exe`, the registry or the network. Use `tests/fakes.py` and temporary folders. Tests that run real fish set `HOME` and `XDG_CONFIG_HOME` to a temporary folder and are skipped when fish is missing. The one exception is `tests/test_tide_network.py`, which is skipped unless `WITCHY_NETWORK_TESTS=1` and then downloads only into a temporary HOME.
- **Every manual run of witchy code uses a temporary HOME** (`HOME=$(mktemp -d)`, and `XDG_RUNTIME_DIR` in the same folder). Never run a real `install`, `uninstall`, `mood`, `doctor --fix`, `sudo`, `apt`, `apt-get` or `chsh` against the real HOME. Reading real files (for example `~/.config/fish`) is allowed; Task 13 copies them into a temporary HOME before anything runs. Never use `fish --no-config` for Tide work.
- Network use is limited to `raw.githubusercontent.com/jorgebucaran/fisher/4.4.5/functions/fisher.fish` and the GitHub release tarballs of fisher 4.4.5 and Tide 6.1.1 (`api.github.com/repos/<repo>/tarball/<tag>`).
- Exit codes stay 0 / 1 / 2.
- Messages, docstrings and comments are English and neutral in tone. Plan prose and code comments never use the witchy voice.
- Lines stay within 120 characters (a few older lines in `runner.py`, `base.py`, `test_cli.py` and `test_runner.py` are longer; leave them).
- Commit messages end with the `Co-Authored-By:` trailer of the model that wrote the commit. The commit blocks below show the prototype's message; keep the subject and body, and put your own trailer.
- SDD workspaces go under `.superpowers/sdd/` (git-excluded).

## Decisions

Given with the task:

1. **Fresh-PC planning (the issue Plan F raised).** The runner plans every component before it applies any, and `fish` checks Tide's readiness while it plans (D19), so on a PC without Tide `fish` used to skip even when `tide` installs Tide in the same run. The fix (Task 8):
   - `Plan` gains `replan: bool = False`. When the runner reaches a plan with `replan` set, it calls that component's `plan` again right before applying it (`ctx.entries` gives it the same entry) and uses the new plan; `ctx.planned` is updated.
   - The `tide` plan sets `data["reprobe"] = True` when it will change which prompt fish runs: a fisher install, update or replacement, a `fish_prompt.fish` moved aside, or a prompt plugin removed. A `tide` plan that will fail (`data["error"]`) never sets it.
   - `fish.tide_goes_first(ctx)` is true when `ctx.planned["tide"]` exists, is not skipped, has `reprobe`, and `"tide"` is not yet in `ctx.results`. Then `fish` plans its files, sets `plan.replan`, and its only action is `fish: set 159 prompt variables once tide has installed Tide (fish is asked again then)`, which is what a dry run shows. Its second plan probes fish again, so readiness still comes from fish itself, never from how `tide` ended (D19): when `tide` failed, `fish` ends `skipped: Tide not ready (…)`.
   - With `--only fish` (or `doctor --fix` picking only `fish`) there is no `tide` plan, so `fish` asks fish right away, as Plan F built it.
   - The CLI's `--only` choices come from `components.NAMES`, which now lists `tide`, so the fix Plan F prints (`install --only tide`) is valid.

Made while prototyping (each task's **Decisions** block has the details):

2. **Prototype first.** Every task was built and tested in a scratch worktree (`proto/plan-g`, from `proto/plan-f`), test-first, one commit per task. Every stage is green on both interpreters with `validate` clean; each task's new tests were run against the stage before it and fail there (Task 9's real-fish tests pin behaviour that Task 8 completed; only its workflow test fails before). Counts: 638 → 646 → 659 → 668 → 695 → 708 → 721 → 732 → 742 → 748 → 755 → 765 → 766 (two of them skipped unless `WITCHY_NETWORK_TESTS=1`).
3. **This PC's Tide is not the 6.1.1 release; the user accepted replacing it (spec gap, decided).** It was installed as `ilancosman/tide` (Tide's development branch), still prints `tide, version 6.1.1`, and 12 of the release's 83 files differ from it (it also has a `bun` item the `v6.1.1` tag does not). So "Tide 6.1.1 present" in spec 5.1 is split: a Tide whose files match the pins is left alone; a Tide whose version or files differ is replaced by the release (`fisher remove <its name>`, then `fisher install ilancosman/tide@v6.1.1`), and its name goes into `previous_tide_plugin` so uninstall puts it back. Without this, doctor's pin check (D21) would be ✗ on this PC forever. **The user decided (2026-10-06) to accept this swap on this PC.** Task 13 ran it against a copy of this PC's fish folder: doctor clean afterwards, and uninstall put the development branch back with every universal `tide_*` value (161 names, the three `tide_bun_*` included) byte for byte. Plan F now takes its defaults from the release (156 names, so `fish` sets 159 variables): the development build's three `tide_bun_*` variables are erased by `fish` after the swap and given back by uninstall, like any `tide_*` variable Tide 6.1.1 does not define.
4. **A Tide swap keeps every universal `tide_*` variable.** Tide's uninstall handler erases all of them and its install handler loads its defaults, so swapping Tides would lose the user's prompt both at install (the `previous` values `fish` records) and at uninstall (after `fish` gave them back). `SWAP_SCRIPT` saves each value and export flag in globals, runs `fisher remove` and `fisher install` in the same fish process, and sets them back, even when the install fails.
5. **The user's own fisher is left alone.** A fisher witchy did not install (any name but `jorgebucaran/fisher@4.4.5`) is never pinned, replaced or removed; doctor shows ⚠ when it is not 4.4.5. witchy's own fisher is pin-checked and re-installed (an update) when a file differs. Spec 9.1 said every fisher file is checked; replacing fisher with itself needs a remove, a fresh bootstrap and a reinstall for a gain nobody asked for.
6. **Order inside `apply` (spec 5.2 corrected):** fisher first, then the hand-written `fish_prompt.fish` and other prompt plugins (fisher refuses to put Tide's file where another one is), then Tide, then its pin check, then the lines in `config.fish` and `conf.d` last. A failed Tide install therefore leaves the user's `starship init` line working. Any case that cannot be taken over (a `function fish_prompt` block, a continued line, a symlink) and a missing `curl` fail the component in `plan`, before anything changes.
7. **Uninstall un-comments instead of restoring the backup (spec 10 corrected).** Removing the `# witchy-disabled: ` prefix is the exact inverse of adding it (bytes, CRLF and all) and keeps every later edit of the user's; a file changed since install is backed up first; a file that became a symlink is left with a warning. The backup made at install stays as a safety copy.
8. **Uninstall order (spec 10 corrected):** commands first — Tide goes (or the earlier Tide comes back), then removed prompt plugins come back (they ship `fish_prompt.fish` too, so after Tide), then witchy's fisher goes — then the file changes (lines, the moved `fish_prompt.fish`). The commands are planned from what fish reports at uninstall time, so a retry after a failed step runs only what is left.
9. **Pins layout:** `{"bootstrap": {"url", "sha256"}, "plugins": {"owner/repo@ref": {path: sha256}}}`, paths below fisher's folder (`functions/tide/configure/icons.fish`). `scripts/pins.py` copies fisher's rule (the entries of `functions/`, `themes/`, `conf.d/`, `completions/` in the tarball's top folder, not dot-files, with everything below a folder). The component hashes the files fisher lists, walking a listed folder (`functions/tide`); a missing, extra or different file is a mismatch.
10. **The install log** keeps one `=== witchy install <stamp> ===` section per run, drops whole runs oldest first above 200 KB (a single run that is still too large keeps its end, cut at a line start), strips fisher's colour codes, and never fails an install. A fisher failure reads `could not <label> (exit N): <last stderr line> (details: ~/.cache/witchy/install.log)`.
11. **fisher reads standard input.** Every fisher call sends empty standard input: fisher appends plugin names read from a pipe when stdin is not a terminal.
12. **`fonts.DOWNLOAD_TIMEOUT = 120`** is the default of `fonts.fetch_url`, so the font download also waits 120 s (spec D20: downloads use 120 s).
13. **doctor gains an `info` level** (`·`, never a problem, no fix line) for the glyph test. A ✗ that no witchy command fixes (a `function fish_prompt` block, a symlink, a continued line) carries the step to take by hand as its fix; `doctor --fix` collects only fixes that are exactly `python3 -m witchy install --only <component>`, in component order.
14. **`install --fresh` (spec 15.1 corrected):** `sudo apt-get update` runs before `install` (a fresh WSL image has no package lists); `eza` is installed on its own and its failure is a note (Ubuntu 22.04 does not package it); a terminal is needed only when there is something to ask; an unreadable login shell counts as "not fish".
15. **Messages about the user's files show `~` for HOME** (`base.tilde`), as the spec examples do.
16. **A Tide without a fisher record** (installed by hand or another plugin manager) fails the component: it can be neither pin-checked nor replaced. Without fish, `tide` ends `skipped: fish not found (sudo apt install fish)`.
17. **Import order.** `witchy.components` imports `tide.py` on package import, and `tide.py` imports `fishprobe`, which imports `components.base`. So `tide.py` spells out `FISHER_SOURCE` and `TIDE_SOURCE` instead of building them from `fishprobe` constants at import time; a test imports each new module first in a fresh interpreter.
18. **Test doubles.** `FakeFisher` (unit tests) keeps plugins as real files in a temporary fish folder so the pin check hashes real bytes; `FAKE_FISHER_FISH` (real-fish tests) is a fish function that installs from a local folder and keeps fisher's records and events; `test_tide_network.py` runs the real path when `WITCHY_NETWORK_TESTS=1` (it passed in the prototype: about 3 s).

## Review Focus

1. **This PC's development-branch Tide, swapped for the release and back,** must keep every universal `tide_*` value and its export flag, also when the install in the middle fails, so uninstall gives back the user's prompt (D4, acceptance 6). Tests: Task 4 `test_tide_6_1_1_with_files_that_differ_from_the_release_is_replaced`, `RealFishSwapTest.test_a_swap_keeps_every_tide_variable`, `test_a_swap_whose_install_fails_still_keeps_them`; Task 9 `test_another_tide_is_replaced_and_comes_back_with_the_users_values`.
2. **`config.fish` and `conf.d` bytes:** CRLF, bytes that are not UTF-8, a line continued with `\`, a symlink into a dotfiles repository, an already disabled line, a line turned back on, and the user's edits after install. Tests: Task 2 `test_line_endings_and_bytes_are_kept`, `test_a_continued_line_blocks_the_takeover`, `test_a_symlinked_file_is_never_edited`, `test_a_second_run_finds_nothing`; Task 5 `test_a_line_turned_back_on_is_disabled_again_and_the_first_backup_stays`; Task 6 `test_disabled_lines_come_back_byte_for_byte`, `test_the_users_later_edits_stay_and_the_edited_file_is_kept_as_a_backup`.
3. **A failure part-way through `apply`** (offline after fisher went in, a file that does not match its pin, a fisher error) must record what was installed, undo nothing, remove a mismatching plugin again, and leave the user's prompt line enabled. Tests: Task 4 `test_what_installed_before_a_failure_stays_recorded`, `test_files_that_do_not_match_the_pins_are_removed_again`, `test_a_bootstrap_file_that_does_not_match_its_pin_is_never_run`; Task 5 `test_lines_are_disabled_only_once_tide_is_in_place`.
4. **An uninstall that fails in the middle and is run again** must not repeat or reverse what already worked, nor remove a Tide the user removed. Tests: Task 6 `test_a_retry_after_a_failed_command_does_not_repeat_what_worked`, `test_a_tide_the_user_removed_is_not_removed_again`, `test_a_moved_prompt_whose_place_is_taken_stays_aside`.
5. **The fresh-PC run order:** `fish` waits for `tide` only when this run's `tide` plan changes the prompt, plans again from fish's own answer, and never waits with `--only fish`; a dry run says so. Tests: Task 8 `test_a_pc_with_fish_only_ends_with_the_witchy_prompt`, `test_when_tide_fails_fish_finds_tide_not_ready_by_itself`, `test_only_fish_never_waits_for_tide`, `test_the_dry_run_says_fish_waits_for_tide`, `ReplanTest`.

## Scope → tasks

| Task | Spec |
|---|---|
| 1 | 5.1 and D21 (pins: `content/pins.json`, `scripts/pins.py`) |
| 2 | 5.2 detection and line disabling, with its edge cases |
| 3 | D20 (`install.log`, 120 s downloads) |
| 4 | 5 component, 5.1 bootstrap table, curl, pin check and removal, entry fields, dry run |
| 5 | 5.2 takeover in `plan`/`apply`; spec 5.1/5.2/9.1 name and order corrections |
| 6 | 10 (uninstall steps) |
| 7 | 9.1 (the `tide` checks) |
| 8 | 5 (component order), 9.2 (banner), D19 with the runner fix, CLI `--only tide` |
| 9 | 12 (integration with real fish, opt-in network test), D24 (`network.yml`) |
| 10 | 15.4 (`doctor --fix`, D18) |
| 11 | 15.1 (`install --fresh`, D15) |
| 12 | README: `tide`, `--fresh`, `doctor --fix`, the new doctor lines and the banner |
| 13 | End-to-end check in temporary HOMEs (acceptance 1, 3, 6, 11) |

## File structure

| Task | Source | Tests | Data and docs |
|---|---|---|---|
| 1 | `scripts/pins.py` (new), `witchy/content.py` | `tests/test_pins.py` (new) | `content/pins.json` (new) |
| 2 | `witchy/takeover.py` (new) | `tests/test_takeover.py` (new) | n/a |
| 3 | `witchy/installlog.py` (new), `witchy/fonts.py` | `tests/test_installlog.py` (new) | n/a |
| 4 | `witchy/components/tide.py` (new) | `tests/fakes.py`, `tests/test_components_tide.py` (new) | n/a |
| 5 | `witchy/components/tide.py`, `witchy/components/base.py`, `witchy/installlog.py` | `tests/test_components_tide.py` | spec 5.1, 5.2, 9.1 |
| 6 | `witchy/components/tide.py` | `tests/test_components_tide.py` | spec 10 |
| 7 | `witchy/components/tide.py`, `witchy/components/base.py`, `witchy/runner.py` | `tests/test_components_tide.py`, `tests/test_runner.py` | spec 9.1 |
| 8 | `witchy/components/__init__.py`, `witchy/components/base.py`, `witchy/components/fish.py`, `witchy/runner.py` | `tests/test_components_tide.py`, `tests/test_components_fish.py`, `tests/test_runner.py`, `tests/test_cli.py` | spec 9.2 |
| 9 | n/a | `tests/fakes.py`, `tests/test_tide_integration.py` (new), `tests/test_tide_network.py` (new) | `.github/workflows/network.yml` (new) |
| 10 | `witchy/runner.py`, `witchy/__main__.py` | `tests/test_runner.py`, `tests/test_cli.py`, `tests/test_components_tide.py` | n/a |
| 11 | `witchy/fresh.py` (new), `witchy/__main__.py` | `tests/test_fresh.py` (new) | spec 15.1 |
| 12 | n/a | `tests/test_cli.py` | `README.md` |
| 13 | none | none | none |

Order: each task needs the ones before it (Task 4 needs Tasks 1 and 3; Task 5 needs Task 2; Task 8 needs Tasks 4–7; Task 10 needs Task 7's checks). Test counts in each step assume this order.

## Interfaces for Plan H

As built (Plan H is rebased onto these):

```python
# witchy/components/__init__.py
all_components() -> [ClaudeComponent(), FontComponent(), WindowsTerminalComponent(), TideComponent(), FishComponent()]
NAMES == ("claude", "font", "windows-terminal", "tide", "fish")

# witchy/components/base.py
@dataclass
class Plan: ...; replan: bool = False      # the runner plans the component again right before applying it
@dataclass(frozen=True)
class Check: level: str  # "ok", "warn", "fail" or "info" (printed with "·", never a problem, no fix line)
def tilde(ctx, path) -> str                 # "~/…" for a path below ctx.home, else the path

# witchy/runner.py
SYMBOLS = {"ok": "✓", "warn": "⚠", "fail": "✗", "info": "·"}
BANNER = "✗✗✗ witchy is NOT fully installed ✗✗✗"
BANNER_FIX = "Fix the lines above, then run: python3 -m witchy install"
def doctor(ctx, components=None, fix: bool = False) -> int   # fix: install --only <✗ components>, check again
def _doctor(ctx, components) -> list[Check] | None           # prints every check; None for a damaged state.json

# witchy/components/fish.py
def tide_goes_first(ctx) -> bool            # this run's tide plan has data["reprobe"] and has not applied yet

# witchy/components/tide.py
FISHER_VERSION = "4.4.5"; FISHER_SOURCE = "jorgebucaran/fisher@4.4.5"; TIDE_SOURCE = "ilancosman/tide@v6.1.1"
FISHER_TIMEOUT = 120
BOOTSTRAP_SCRIPT, FISHER_SCRIPT, SWAP_SCRIPT: str
GLYPH_TEST: str   # "glyph test: 🧹 🔮 🪦 🌿 🧪 💀 🔥 🐈 🦉 ❯ — each should be one clear symbol"
def fisher_command(label, *args) -> Command; def swap_command(label, remove, install) -> Command
def installed_name(found, plugin) -> str | None; def file_hashes(paths) -> dict[str, str]
def mismatches(found, plugin, pinned) -> list[str]
def owners(ctx, found) -> tuple[Path | None, list[str], takeover.Scan]   # skips witchy's own fish files
class TideComponent(pins: dict | None = None)   # plan / apply / restore / check
# tide entry: installed_fisher, installed_tide, previous_tide_plugin, removed_plugins, disabled_files, moved_prompt
# tide plan.data: entry, error, fisher, tide, replace, prompt, plugins, lines, reprobe

# witchy/takeover.py
PREFIX = b"# witchy-disabled: "
def owner(line: str) -> str | None; def scan(folder, skip=frozenset()) -> Scan
def disable(data: bytes, numbers) -> bytes; def enable(data: bytes) -> bytes

# witchy/installlog.py
NAME = "install.log"; LIMIT = 200 * 1024
def append(ctx, text); def run(ctx, command) -> CompletedProcess; def failure(ctx, label, done) -> str
def shown(ctx) -> str   # "~/.cache/witchy/install.log"

# witchy/content.py
PINS = "pins.json"; def load_pins(content_dir=CONTENT_DIR) -> dict

# witchy/fresh.py
PACKAGES = ("fish", "curl", "eza"); def prepare(ctx, ask=input, interactive=None) -> int | None

# tests/fakes.py
FISHER_FILE, TIDE_FILES, RELEASES; def fake_pins(releases=None, bootstrap=FISHER_FILE)
class FakeFisher(config, installed=None, served=None, variables=None, calls=None, missing=False)  # .run, .plugins
FAKE_FISHER_FISH, FAKE_TIDE_INIT; def fake_tide_tree(version="6.1.1"); def serve_plugins(folder, releases, env)
```

Things Plan H must know:

- **witchy's own fish files are never scanned for prompt owners.** `tide.owners` skips every file `build.fish_files` ships, so Plan H's `set -g tide_character_color` in `conf.d/witchy.fish` is not disabled. Plan F's doctor global-shadow check (`fish`) is what Plan H teaches to accept today's caret colour.
- **Use `Check("info", …)` for doctor's `caret: gold` line** (spec 15.3); a stale cache is still a ⚠.
- **Plan G touches `README.md`** (the "It installs" fish bullet, the usage block, the components paragraph, exit codes and the troubleshooting table) and `witchy/__main__.py` (`--fresh`, `doctor --fix`). It does not touch `witchy/wt.py`, `witchy/components/windows_terminal.py`, `witchy/ritual/sky.py` or `content/fish/conf.d/witchy.fish`.
- The install summary is now followed by the banner when anything was skipped or failed; on a PC without Windows Terminal that is always the case.

---

### Task 1: Pin every file of fisher 4.4.5 and Tide 6.1.1, generated from the real releases

**Items:** spec 5.1 "Pins (D21)": `content/pins.json` holds the SHA-256 of the bootstrap `fisher.fish` and of every file fisher 4.4.5 and Tide 6.1.1 install; `scripts/pins.py` generates it from the real releases.

**Files:**
- Create: `scripts/pins.py`
- Create: `content/pins.json` (generated, checked in)
- Modify: `witchy/content.py` (`PINS`, `SHA256`, `_hashes`, `load_pins`)
- Test: `tests/test_pins.py` (new)

**Interfaces:**
- Consumes: `content.CONTENT_DIR`.
- Produces:
  - `scripts/pins.py`: `OUTPUT`, `BOOTSTRAP = "https://raw.githubusercontent.com/jorgebucaran/fisher/4.4.5/functions/fisher.fish"`, `PLUGINS = ("jorgebucaran/fisher@4.4.5", "ilancosman/tide@v6.1.1")`, `FOLDERS`, `tarball_url(plugin) -> str`, `plugin_files(archive: bytes) -> dict[str, str]`, `pins(fetch) -> dict`, `download(url) -> bytes`, `main(argv, fetch=download) -> int` (0 written, 1 error, 2 usage).
  - `content.PINS = "pins.json"`, `content.load_pins(content_dir=CONTENT_DIR) -> dict` (raises `ValueError("pins.json must hold …")` for a file without every hash).
  - `content/pins.json`: `{"bootstrap": {"url", "sha256"}, "plugins": {"jorgebucaran/fisher@4.4.5": {2 files}, "ilancosman/tide@v6.1.1": {83 files}}}`.

**Decisions:**
1. **Hash files, not tarballs.** GitHub builds tarballs on demand and their bytes can change; the files fisher copies cannot. The keys are paths below fisher's folder, the same shape the component builds from fisher's file lists (Task 4).
2. **The script copies fisher's rule** (`fisher.fish` 4.4.5: `cp -Rf $temp/*/* $source`, then `$source/{functions,themes,conf.d,completions}/*`): the entries of those four folders in the tarball's top folder, not the ones starting with a dot, with everything below a folder among them. A link in the tarball is refused (fisher copies with `cp -L`, which would copy the target).
3. **The bootstrap file is fisher's own `functions/fisher.fish`:** the test checks that both hashes are equal, which they are for 4.4.5.
4. **The script is standalone** (like `scripts/tide_defaults.py`) and takes its `fetch` as a parameter, so its tests never download; `main` writes nothing when a download fails.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pins.py`:

```python
import contextlib
import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from witchy import content

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "pins.py"
_spec = importlib.util.spec_from_file_location("pins", SCRIPT)
pins = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pins)


def tarball(members, links=()):
    """A gzip tarball like GitHub's: every path below one top folder; ``links`` are symlinks."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(f"owner-repo-abc1234/{name}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for name in links:
            info = tarfile.TarInfo(f"owner-repo-abc1234/{name}")
            info.type, info.linkname = tarfile.SYMTYPE, "../README.md"
            tar.addfile(info)
    return buffer.getvalue()


def digest(data):
    return hashlib.sha256(data).hexdigest()


class PluginFilesTest(unittest.TestCase):
    def test_hashes_every_file_fisher_copies(self):
        archive = tarball({"functions/tide.fish": b"a", "functions/tide/configure/icons.fish": b"b",
                           "conf.d/_tide_init.fish": b"c", "completions/tide.fish": b"d", "themes/x.theme": b"e",
                           "functions/.hidden.fish": b"f", "README.md": b"g", "tests/tide.fish": b"h"})
        self.assertEqual(pins.plugin_files(archive), {
            "completions/tide.fish": digest(b"d"), "conf.d/_tide_init.fish": digest(b"c"),
            "functions/tide.fish": digest(b"a"), "functions/tide/configure/icons.fish": digest(b"b"),
            "themes/x.theme": digest(b"e")})

    def test_refuses_a_link(self):
        with self.assertRaisesRegex(ValueError, "functions/x.fish is a link"):
            pins.plugin_files(tarball({"functions/tide.fish": b"a"}, links=["functions/x.fish"]))

    def test_refuses_an_archive_with_nothing_to_install(self):
        with self.assertRaisesRegex(ValueError, "no file fisher would install"):
            pins.plugin_files(tarball({"README.md": b"a"}))

    def test_the_urls_are_the_ones_fisher_downloads(self):
        self.assertEqual(pins.tarball_url("ilancosman/tide@v6.1.1"),
                         "https://api.github.com/repos/ilancosman/tide/tarball/v6.1.1")


class MainTest(unittest.TestCase):
    def test_writes_the_bootstrap_hash_and_every_plugins_files(self):
        served = {pins.BOOTSTRAP: b"function fisher\nend\n",
                  pins.tarball_url("jorgebucaran/fisher@4.4.5"): tarball({"functions/fisher.fish": b"f"}),
                  pins.tarball_url("ilancosman/tide@v6.1.1"): tarball({"functions/tide.fish": b"t"})}
        fetched = []

        def fetch(url):
            fetched.append(url)
            return served[url]

        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as out:
            output = Path(tmp) / "pins.json"
            self.assertEqual(pins.main([str(output)], fetch=fetch), 0)
            written = json.loads(output.read_text(encoding="ascii"))
            loaded = content.load_pins(Path(tmp))
        self.assertEqual(fetched, list(served))
        self.assertEqual(written, loaded)
        self.assertEqual(written, {
            "bootstrap": {"url": pins.BOOTSTRAP, "sha256": digest(b"function fisher\nend\n")},
            "plugins": {"jorgebucaran/fisher@4.4.5": {"functions/fisher.fish": digest(b"f")},
                        "ilancosman/tide@v6.1.1": {"functions/tide.fish": digest(b"t")}}})
        self.assertIn("wrote the pins of 2 files to", out.getvalue())

    def test_a_download_that_fails_writes_nothing(self):
        def fetch(url):
            raise OSError("network is unreachable")

        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()) as err:
            output = Path(tmp) / "pins.json"
            self.assertEqual(pins.main([str(output)], fetch=fetch), 1)
            self.assertFalse(output.exists())
        self.assertEqual(err.getvalue(), "pins: network is unreachable\n")


class CheckedInPinsTest(unittest.TestCase):
    def test_pins_fisher_4_4_5_and_tide_6_1_1(self):
        data = content.load_pins()
        self.assertEqual(data["bootstrap"]["url"], pins.BOOTSTRAP)
        self.assertEqual(tuple(data["plugins"]), pins.PLUGINS)
        fisher, tide = data["plugins"].values()
        # The bootstrap file is the one fisher then installs as its own function.
        self.assertEqual(fisher["functions/fisher.fish"], data["bootstrap"]["sha256"])
        self.assertEqual(sorted(fisher), ["completions/fisher.fish", "functions/fisher.fish"])
        for name in ("functions/fish_prompt.fish", "functions/tide.fish", "conf.d/_tide_init.fish",
                     "functions/tide/configure/icons.fish"):
            self.assertIn(name, tide)
        self.assertEqual(len(tide), 83)

    def test_a_file_without_every_hash_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            for broken in ({}, {"bootstrap": {"url": "u", "sha256": "x"}, "plugins": {"a@1": {"f": "0" * 64}}},
                           {"bootstrap": {"url": "u", "sha256": "0" * 64}, "plugins": {"a@1": {}}}):
                (Path(tmp) / content.PINS).write_text(json.dumps(broken), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "pins.json must hold"):
                    content.load_pins(Path(tmp))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_pins`
Expected: the module cannot load the script:
```
FileNotFoundError: [Errno 2] No such file or directory: '…/scripts/pins.py'
```

- [ ] **Step 3: Write the script, the loader and the pins**

Create `scripts/pins.py`:

```python
"""Write content/pins.json from the real fisher 4.4.5 and Tide 6.1.1 releases (spec 5.1, D21).

Usage: python3 scripts/pins.py [<output file>]

It downloads fisher's bootstrap file and the release tarball of each plugin from the URLs fisher itself uses,
and records the SHA-256 of the bootstrap file and of every file fisher copies when it installs the plugin.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import tarfile
import urllib.request
from pathlib import Path
from typing import Callable

OUTPUT = Path(__file__).resolve().parent.parent / "content" / "pins.json"
BOOTSTRAP = "https://raw.githubusercontent.com/jorgebucaran/fisher/4.4.5/functions/fisher.fish"
PLUGINS = ("jorgebucaran/fisher@4.4.5", "ilancosman/tide@v6.1.1")
FOLDERS = ("functions", "themes", "conf.d", "completions")  # what fisher copies from a plugin
TIMEOUT = 120
LIMIT = 16 * 1024 * 1024


def tarball_url(plugin: str) -> str:
    """The URL fisher 4.4.5 downloads ``owner/repo@ref`` from."""
    repo, ref = plugin.split("@", 1)
    return f"https://api.github.com/repos/{repo}/tarball/{ref}"


def plugin_files(archive: bytes) -> dict[str, str]:
    """The SHA-256 of each file fisher installs from a release tarball, by path below fisher's folder.

    fisher copies the entries of functions/, themes/, conf.d/ and completions/ in the archive's top folder
    (not the ones whose name starts with a dot), with everything below a folder among them.
    """
    found = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        for member in tar.getmembers():
            parts = member.name.split("/")
            if len(parts) < 3 or parts[1] not in FOLDERS or parts[2].startswith("."):
                continue
            if member.issym() or member.islnk():
                raise ValueError(f"{member.name} is a link; fisher would copy its target")
            if member.isfile():
                found["/".join(parts[1:])] = hashlib.sha256(tar.extractfile(member).read()).hexdigest()
    if not found:
        raise ValueError("the archive holds no file fisher would install")
    return dict(sorted(found.items()))


def pins(fetch: Callable[[str], bytes]) -> dict:
    return {"bootstrap": {"url": BOOTSTRAP, "sha256": hashlib.sha256(fetch(BOOTSTRAP)).hexdigest()},
            "plugins": {plugin: plugin_files(fetch(tarball_url(plugin))) for plugin in PLUGINS}}


def download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
        data = response.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError(f"{url} is larger than {LIMIT} bytes")
    return data


def main(argv: list[str], fetch: Callable[[str], bytes] = download) -> int:
    if len(argv) > 1:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    output = Path(argv[0]) if argv else OUTPUT
    try:
        found = pins(fetch)
        output.write_text(json.dumps(found, indent=2) + "\n", encoding="ascii")
    except (OSError, ValueError, tarfile.TarError) as exc:
        print(f"pins: {exc}", file=sys.stderr)
        return 1
    count = sum(len(files) for files in found["plugins"].values())
    print(f"wrote the pins of {count} files to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

In `witchy/content.py`, replace:

```python
import json
from pathlib import Path
```

with:

```python
import json
import re
from pathlib import Path
```

replace:

```python
TIDE_DEFAULTS = "tide-6.1.1-defaults.json"  # written by scripts/tide_defaults.py (spec 6.1)
```

with:

```python
TIDE_DEFAULTS = "tide-6.1.1-defaults.json"  # written by scripts/tide_defaults.py (spec 6.1)
PINS = "pins.json"  # written by scripts/pins.py (spec 5.1, D21)
SHA256 = re.compile(r"[0-9a-f]{64}")
```

and add, before `def read_output_style(`:

```python
def _hashes(files: Any) -> bool:
    return isinstance(files, dict) and bool(files) and all(SHA256.fullmatch(str(digest)) for digest in files.values())


def load_pins(content_dir: Path = CONTENT_DIR) -> dict[str, Any]:
    """The SHA-256 of fisher's bootstrap file and of every file each pinned plugin installs, by path below
    fisher's folder: ``{"bootstrap": {"url", "sha256"}, "plugins": {"owner/repo@ref": {path: sha256}}}``."""
    data = json.loads((content_dir / PINS).read_text(encoding="utf-8"))
    bootstrap = data.get("bootstrap") if isinstance(data, dict) else None
    plugins = data.get("plugins") if isinstance(data, dict) else None
    if not (isinstance(bootstrap, dict) and isinstance(bootstrap.get("url"), str)
            and SHA256.fullmatch(str(bootstrap.get("sha256"))) and isinstance(plugins, dict) and plugins
            and all(_hashes(files) for files in plugins.values())):
        raise ValueError(f"{PINS} must hold the bootstrap file's URL and SHA-256 and each plugin's file hashes")
    return data
```

Generate the pins from the real releases (the only network use of this task):

Run: `python3 scripts/pins.py`
Expected: `wrote the pins of 85 files to /home/eimi/projects/witchyterm/content/pins.json`

The file must be exactly this (if GitHub is unreachable, write it by hand from here):

```json
{
  "bootstrap": {
    "url": "https://raw.githubusercontent.com/jorgebucaran/fisher/4.4.5/functions/fisher.fish",
    "sha256": "59640d07bda182f2ad0fdfe9dc8a799fb79f46e6e5fc460354ffe2e21f759688"
  },
  "plugins": {
    "jorgebucaran/fisher@4.4.5": {
      "completions/fisher.fish": "6ef51da07e11ed534ce828770dfa3135551bafe9aa3c28700cee1fc5f053cd48",
      "functions/fisher.fish": "59640d07bda182f2ad0fdfe9dc8a799fb79f46e6e5fc460354ffe2e21f759688"
    },
    "ilancosman/tide@v6.1.1": {
      "completions/tide.fish": "c1adfcc038c8ee7fd7fba3521536521238320d40f94c456852ef1a20d9c2421b",
      "conf.d/_tide_init.fish": "f0ff297c367ca4809740974076e77dc1f2a282381a8b2d12074bf70adad23cfd",
      "functions/_tide_1_line_prompt.fish": "07ada4537876fbb8bad7536db11f2b0365f212f10b23c5c067cac50ab2d03483",
      "functions/_tide_2_line_prompt.fish": "58177c617a714943f50d1e486ecfa37dc677f9b1685de7bffda829e7a3af1691",
      "functions/_tide_cache_variables.fish": "5a04ba5c55c90fb6473aaa9cd2bb4d6818eaee35aad16a085d977ac573a7b985",
      "functions/_tide_detect_os.fish": "7b9b59aeb64fe299875d1af25ade995b15165d131d4b1a74f225460159214459",
      "functions/_tide_find_and_remove.fish": "5f6365c6ef83cf83c3cfed264697fe5e75e555dc0cfeeb3e87b24756d8d39483",
      "functions/_tide_fish_colorize.fish": "cc834b51ea9393e52ffa0f26cfc9cc617d3a8587957bcbed9c425fcf203decd6",
      "functions/_tide_item_aws.fish": "16735f84647d6f2da6ba4b3ec330ecb6b12dd6ee571a0990a84d537e99aab72f",
      "functions/_tide_item_character.fish": "d343c67ac40f2a069d60f54bc4515a94991fdd7c7c0e683a7718462780cb0ccd",
      "functions/_tide_item_cmd_duration.fish": "80457f7a7c73819758364363313d9ae0d472b06eb644906bcad1b6d8ad0ca1ed",
      "functions/_tide_item_context.fish": "7636c6685617db4f8ed0f76bbab6215554c453ce543a9d23f2b74f37def03d26",
      "functions/_tide_item_crystal.fish": "2052076028eba9f218a60a8817368e163fc4dff4e38fe972d300c50460e9ff9c",
      "functions/_tide_item_direnv.fish": "7735c00c4a66f31005d1342f3881108e47c5015c3679248286508820b2d36a30",
      "functions/_tide_item_distrobox.fish": "c02b20a59d5f4ac30faf48fffaabc65a6372f548290f800f02bcf8b70ad98c4f",
      "functions/_tide_item_docker.fish": "5d1d552d157c136aa52622105572a6e9cb19db47f96515a3ddbd6b4545d3be36",
      "functions/_tide_item_elixir.fish": "e2fffc2b7e598405e271d6499f3a7d9d0f2a13a21ae7b74e83036fe694743b6d",
      "functions/_tide_item_gcloud.fish": "22c8dc2f363a64addb9186058c12b31455a062006ae16b9e5fb1b6aa3207f445",
      "functions/_tide_item_git.fish": "8153ba02221a686d9074fd42ec8d572df3b89bfc39b57ad31b1a6970bc0d534c",
      "functions/_tide_item_go.fish": "fde7804d6617afd8bac17b1d7cbf89180a6f988eb361c919fa096efea15c167a",
      "functions/_tide_item_java.fish": "869c8f45790a86d04ef5a26d7f022e2fed30a6298e92a31469c004065c7d85e5",
      "functions/_tide_item_jobs.fish": "e15106d365d8eb69e624426b2433a245ec80259467547a24435ad9d6b557c691",
      "functions/_tide_item_kubectl.fish": "c29fbee2b7e00046a6ea4b9717fdca044e805d4c3545c0f0604bba27e11daec8",
      "functions/_tide_item_nix_shell.fish": "b3901a7b275efd88f11fc2058a324b5b81700b026bd6943307e5c0eb2b3f8e27",
      "functions/_tide_item_node.fish": "e3f0a2d616746d2369b699d4c95f36475f99698612d1fcee315cd6628bbf8a7a",
      "functions/_tide_item_os.fish": "5d28e2e9d533e2109c1bd0ce45b186eddab84d760f2c26895eb6a87720bcea91",
      "functions/_tide_item_php.fish": "781c07e6f955f4f5826ee97bdbbfaa6d9250c343c03e92b914d9b1c0ebcdf8cb",
      "functions/_tide_item_private_mode.fish": "02d8f9b2231c723f95f0b31e762dae1ffca224ea2feda6f0a9297404e3fcfd2c",
      "functions/_tide_item_pulumi.fish": "4633996f2dea42a074cde56f9260a5b24a1a253743e4f27cec5a2874efe5a0ac",
      "functions/_tide_item_python.fish": "84e3af112cd6b2b8313678efd097492d55f43c80278f18f2902e25614d7f5247",
      "functions/_tide_item_ruby.fish": "912af8f9e461a4c454a70a7a27340f74882f551849a60a2e4e86d0a37c315e27",
      "functions/_tide_item_rustc.fish": "fa3731390392f5d4dcf4fe67be6a7d74de83dde5dc2dddfebb9b32f7ce8804de",
      "functions/_tide_item_shlvl.fish": "843e7492ab59b6415ba195990f4a48fa4be518713f5c2f3ffd023135c826c98b",
      "functions/_tide_item_status.fish": "c0547c73bdd793a1e5b326c4dc2641a66c4fcadddf80785f25964ca16a7dc29b",
      "functions/_tide_item_terraform.fish": "e23a36068db704203cc8919902c48988a0b9543f0e164853686eb336df96a744",
      "functions/_tide_item_time.fish": "2cdeb2cf6f764ce2f1cc743905a914c412552f6f07e004462ac720625fc8d7a0",
      "functions/_tide_item_toolbox.fish": "83d3a2d38a79f0f42b02ff6bae1041a3882036a579c0da24a76376742ba06d06",
      "functions/_tide_item_vi_mode.fish": "dc50b7b7399b2877298b9758158f24436562a92d1a969c87b72aea69f7b78687",
      "functions/_tide_item_zig.fish": "12a37dd048f8d580cd7c637cd80c827e4d668cf5f5cfa2adc2321929c6825572",
      "functions/_tide_parent_dirs.fish": "b45e4f012c8c5f149c93b137436b61f70dae28bfc7c23a9448d031a217cb2059",
      "functions/_tide_print_item.fish": "35dd0d3f522f53270c4153f904e257c844bb7ae1d8c4639bd05b6d596f3b1d53",
      "functions/_tide_pwd.fish": "c764e1f7d4fffdae82d20b67734ddf95fdcdbec8cb548f27ca6f20f575bfb57a",
      "functions/_tide_remove_unusable_items.fish": "1f7a0a691d5a9c23f636e959303aceb4e3b12284b5f6c0a7fb199a50a9edd0f0",
      "functions/_tide_sub_bug-report.fish": "bf1c2f0c3f52e9c2fcf297cbb47ead8fca99317496fac3a456d0da453e374a37",
      "functions/_tide_sub_configure.fish": "a073ddbd00c40966cc5461ff9a0e35ec6ab131e7bbd8a2759640beab9107896a",
      "functions/_tide_sub_reload.fish": "601e4e2c4198bfbc551b0b91abfb32dc3db76b365c7864372dcb24decc0f6e82",
      "functions/fish_mode_prompt.fish": "71d0a205d8dfdc350e47abfa5d01e90593f1cadeb6ca33e99f0b3758b0a21b21",
      "functions/fish_prompt.fish": "29d6c578b01f0edd36baab08f10ef9b4217c60cad9736ecc5f5a26e2f7d277ff",
      "functions/tide.fish": "22046f44a5865035f2ab0e53c3e6c9c0dcbf23fca4f620c122e7059bca74438f",
      "functions/tide/configure/choices/all/finish.fish": "04cce4bd8799982ae92db5d94db667f6fba6a2ae16b9bde6b8278472fc2120cb",
      "functions/tide/configure/choices/all/icons.fish": "bf96ca28d9f32b2bbaf8ecd9afa29b058fb7af757c8a71e3fac56d1893d7ef2d",
      "functions/tide/configure/choices/all/prompt_colors.fish": "29eccbecf79adc900abb0bcc402562b533707e446431ea3fe4ff9ece04035bc7",
      "functions/tide/configure/choices/all/prompt_connection.fish": "331d6cc10f42264d7e7a8515d000e86e306f570a205f34beaf04d1bfdab05a9a",
      "functions/tide/configure/choices/all/prompt_connection_andor_frame_color.fish": "ace9f756bc8c3ce1d1c4e19bc764e7816ee60c0754d2267ecd06eb76a6ffcda6",
      "functions/tide/configure/choices/all/prompt_spacing.fish": "2b2fbda35f359e68ce2e3fa1cb5faf6f43a0f9417b847b38a5f869c4e740fa81",
      "functions/tide/configure/choices/all/show_time.fish": "278b15ebc42cfcbbf5f5abe868940e1aa56f45e67fa97f18566a00fe38df0289",
      "functions/tide/configure/choices/all/style.fish": "4878b851c4922b407f2a8b7e9d7905bcb7bbd15b9ad4b2a2dd576315305d1110",
      "functions/tide/configure/choices/all/transient.fish": "e73bc1c52723d0abad31bf4b8fd2f2e69546294b4a5b296193294697a74844e6",
      "functions/tide/configure/choices/classic/classic_prompt_color.fish": "9ad34a01435aac04814fd65b7d22d8e4007cbdd328058aee7b95fd2bc83fcfa1",
      "functions/tide/configure/choices/classic/classic_prompt_separators.fish": "964c36141588b9de1f847c4de9f156cb5cbbcc7f91d78525b5640be6b38250e6",
      "functions/tide/configure/choices/lean/lean_prompt_height.fish": "99c9be1b4699ab6c58ce36ca62e0ff1fe10accdad3f71dccfea5bdb4e864d36e",
      "functions/tide/configure/choices/powerline/powerline_prompt_heads.fish": "1cd8c0fd1066bc92a24706ccdba6f67cb807128fcdf18d0326ba37e7595778b0",
      "functions/tide/configure/choices/powerline/powerline_prompt_style.fish": "e7eb05e6f311701ddf7c78a4cba334d31538186c97e29057bb6d206ef82e2ec4",
      "functions/tide/configure/choices/powerline/powerline_prompt_tails.fish": "7e6b63aa58809c35e49c5c102a7b2de21aa6feaab4aae39cabf03a2e6f1c7654",
      "functions/tide/configure/choices/powerline/powerline_right_prompt_frame.fish": "fa9237607a83ad0b2043baf94f96c8e39fb89127b50c21de42edd6cb0cf12874",
      "functions/tide/configure/choices/rainbow/rainbow_prompt_separators.fish": "dbe76b7aeaf48095eb7465bf536cd717926eee1f2eddef60706be21cd140ac46",
      "functions/tide/configure/configs/classic.fish": "cf826947a1e01e5f55798a2c04b7cb004830842ce464da424015d2874cdb3365",
      "functions/tide/configure/configs/classic_16color.fish": "6cbf738b115701d66c1b5d15e1d0d8989679e0b858b83709c6f50c637d1891fe",
      "functions/tide/configure/configs/lean.fish": "f4cc602b7aa64a4e0d847f0e5f4efbae726f06f2a6be8f23775a98ec9705ea2b",
      "functions/tide/configure/configs/lean_16color.fish": "5f6ac7865eb11a44b1c0c5aa4aba197dca61e4dd2f3b58ccac48220a7caa164f",
      "functions/tide/configure/configs/rainbow.fish": "01b12b0ec93f4ce54846c8987f4a93cf5c394b7acc0265e7a3906cf8620bc1bb",
      "functions/tide/configure/configs/rainbow_16color.fish": "44f99faa88895f88f86a6d263540c13953b4facbe9bc8473d84edc9332a56fbe",
      "functions/tide/configure/functions/_fake_tide_cache_variables.fish": "086f9833fc1b48e5a0f9cb3934b6215a089ee86c88ca5cc1ac899e37cdc8e419",
      "functions/tide/configure/functions/_fake_tide_item_character.fish": "3314d9df190e1e35da1927b68872e349572dccb8873c24982405ce5a2b1ad130",
      "functions/tide/configure/functions/_fake_tide_item_cmd_duration.fish": "aafc7cbd70de62dc9b19ad0cddc58406eafcf3519aa217547c7b21ed47b7472f",
      "functions/tide/configure/functions/_fake_tide_item_git.fish": "b7a1adb27043e646e60b20c6c6167c4cd885084d44db00ae7da66662fbffbcbb",
      "functions/tide/configure/functions/_fake_tide_item_newline.fish": "80a455a44ea64dff39007cf6c326d9cf930797680bf9f394b7692788610d05aa",
      "functions/tide/configure/functions/_fake_tide_item_os.fish": "26f678fd3581acce5b6dc19b1fb0d02159c2fc41063b58ba096e6d9d5103539b",
      "functions/tide/configure/functions/_fake_tide_item_time.fish": "a3671980c24fa489bb27adbc75169e52a0085f78a01b8d1eeaddc053713e5a00",
      "functions/tide/configure/functions/_fake_tide_print_item.fish": "464bcf8aae13202567b5bc5caf1f6a0121c0ef5cd0d2aca19cc2c02252c91db3",
      "functions/tide/configure/functions/_fake_tide_prompt.fish": "e48fa0af23dbe3d696e58a157607d861de3b8c9925e0894b3671f2466ed817bf",
      "functions/tide/configure/functions/_fake_tide_pwd.fish": "8ee8663da5f436d4e92842d7f39dbfe8ce7eb82701f4c5abfb86534aa3f9da1a",
      "functions/tide/configure/icons.fish": "a800efbf63092067534c593127e0008dd8d6e3e4de2b022ca308bb659e8f0d87"
    }
  }
}
```

- [ ] **Step 4: Run the tests and the whole suite**

Run: `/usr/bin/python3 -m unittest tests.test_pins`
Expected: `Ran 8 tests … OK`

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 646 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add scripts/pins.py content/pins.json witchy/content.py tests/test_pins.py
git commit -m "feat: pin every file of fisher 4.4.5 and Tide 6.1.1, generated from the real releases" -m "scripts/pins.py downloads fisher's bootstrap file and both release tarballs from the URLs fisher uses and writes content/pins.json: the SHA-256 of the bootstrap file and of every file fisher copies." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Find other prompt owners in config.fish and conf.d and disable them line by line

**Items:** spec 5.2, the third and fourth rows of the takeover table and every edge case: `starship init fish`, `oh-my-posh init fish` and `set -g`/`-gx`/`--global` of a `tide_*` name are disabled with a `# witchy-disabled: ` prefix; a `function fish_prompt` block, a continued line and a symlinked file are refused (D22); a second run changes nothing; a line turned back on is found again; bytes and line endings are kept; a missing or empty config is fine.

**Files:**
- Create: `witchy/takeover.py`
- Test: `tests/test_takeover.py` (new)

**Interfaces:**
- Consumes: `base.Change`.
- Produces:
  - `takeover.PREFIX = b"# witchy-disabled: "`.
  - `@dataclass(frozen=True) class Line: path: Path; number: int; what: str` (`"starship init"`, `"oh-my-posh init"`, `"set -g tide_…"`).
  - `@dataclass class Scan: lines: list[Line]; blockers: list[str]; changes: list[Change]`.
  - `takeover.owner(line: str) -> str | None`, `config_files(folder, skip) -> list[Path]`, `scan(folder, skip=frozenset()) -> Scan`, `disable(data: bytes, numbers) -> bytes`, `enable(data: bytes) -> bytes`.
  - Blocker texts (Task 4 fails with them, Task 7 splits them at the last `"; "` into problem and fix): `"<file> defines fish_prompt at line N; remove that function"`, `"<file> line N is continued over several lines; disable it yourself"`, `"<file> is a symlink to <target>; disable line N there yourself"` (`lines N, M` for several), `"cannot read <file> (<why>)"`. `<file>` is relative to fish's config folder (`config.fish`, `conf.d/mine.fish`).

**Decisions:**
1. **Bytes in, bytes out.** A file is split on `b"\n"` only; each line is decoded with `surrogateescape` just to match it (a trailing `\r` is ignored for the match), and the prefix goes in front of the raw line. `enable` removes the prefix from every line that starts with it, which gives the original bytes back exactly.
2. **The prefix goes at column 0,** before any indentation, so "already disabled" is one exact test and `enable` is its inverse. A comment line (first non-blank character `#`) is never an owner, so a disabled line is skipped on the next run.
3. **What counts as a global `tide_` set:** `set` followed by flags and a name starting with `tide_`, where a short flag cluster holds `g` or a long flag is `--global`, and no flag reads or erases (`-q`, `-e`, `-n`, `-S`, `--query`, `--erase`, `--names`, `--show`). `set -U` is the user's universal value (Plan F's `fish` component owns those); `_tide_*` names are Tide's private ones.
4. **A continued line** is a matching line that ends in `\`, or follows a line that does; both are blockers, because commenting one physical line of a continued command changes what the rest means.
5. **A symlinked file is never edited (D22),** but only a symlink that holds something to take over is a blocker; a symlinked `config.fish` with nothing in it to disable is fine.
6. **Only `config.fish` and the top-level `conf.d/*.fish` files are scanned;** the caller passes `skip` (witchy's own files and every file fisher lists, Task 5).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_takeover.py`:

```python
import os
import tempfile
import unittest
from pathlib import Path

from witchy import takeover


class OwnerTest(unittest.TestCase):
    def test_lines_that_own_the_prompt(self):
        cases = {
            "starship init fish | source": "starship init",
            "    starship init fish | source": "starship init",
            "if type -q starship; starship init fish | source; end": "starship init",
            "oh-my-posh init fish --config ~/theme.json | source": "oh-my-posh init",
            "oh-my-posh --init --shell fish --config ~/theme.json | source": "oh-my-posh init",
            "set -g tide_pwd_icon x": "set -g tide_pwd_icon",
            "set -gx tide_time_color 5F8787": "set -g tide_time_color",
            "set -xg tide_time_color 5F8787": "set -g tide_time_color",
            "set -g -x tide_time_color 5F8787": "set -g tide_time_color",
            "set --global tide_character_icon '>'": "set -g tide_character_icon",
            "test -n x; and set -g tide_git_icon y": "set -g tide_git_icon",
            "set -q tide_x; or set -g tide_x y": "set -g tide_x",
        }
        for line, what in cases.items():
            with self.subTest(line=line):
                self.assertEqual(takeover.owner(line), what)

    def test_lines_that_do_not(self):
        for line in ("# starship init fish | source", "   # set -g tide_x y",
                     "# witchy-disabled: starship init fish | source", "set -U tide_pwd_icon x",
                     "set -l tide_pwd_icon x", "set tide_pwd_icon x", "set -q -g tide_pwd_icon",
                     "set -e -g tide_pwd_icon", "set --erase --global tide_pwd_icon", "set -g _tide_left_items",
                     "set -g fish_greeting", "echo starship", "set -g offset_tide_x 1", ""):
            with self.subTest(line=line):
                self.assertIsNone(takeover.owner(line))


class ScanTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name) / "fish"
        (self.folder / "conf.d").mkdir(parents=True)

    def write(self, name, data):
        path = self.folder / name
        path.write_bytes(data)
        return path

    def test_finds_each_owner_and_disables_only_those_lines(self):
        config = self.write("config.fish", b"if status is-interactive\n    starship init fish | source\nend\n"
                                           b"set -g tide_pwd_icon x\n")
        mine = self.write("conf.d/mine.fish", b"oh-my-posh init fish | source\n")
        found = takeover.scan(self.folder)
        self.assertEqual(found.lines, [takeover.Line(config, 2, "starship init"),
                                       takeover.Line(config, 4, "set -g tide_pwd_icon"),
                                       takeover.Line(mine, 1, "oh-my-posh init")])
        self.assertEqual(found.blockers, [])
        self.assertEqual([(change.path, change.after) for change in found.changes], [
            (config, b"if status is-interactive\n# witchy-disabled:     starship init fish | source\nend\n"
                     b"# witchy-disabled: set -g tide_pwd_icon x\n"),
            (mine, b"# witchy-disabled: oh-my-posh init fish | source\n")])
        self.assertEqual(found.changes[0].before, config.read_bytes())

    def test_a_second_run_finds_nothing(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.write("config.fish", takeover.scan(self.folder).changes[0].after)
        found = takeover.scan(self.folder)
        self.assertEqual((found.lines, found.blockers, found.changes), ([], [], []))
        self.assertEqual(config.read_bytes(), b"# witchy-disabled: starship init fish | source\n")

    def test_a_line_turned_back_on_is_found_again(self):
        self.write("config.fish", b"# witchy-disabled: starship init fish | source\nstarship init fish | source\n")
        self.assertEqual([line.number for line in takeover.scan(self.folder).lines], [2])

    def test_a_fish_prompt_function_blocks_the_takeover(self):
        self.write("config.fish", b"set -g tide_x y\nfunction fish_prompt --description 'mine'\n    echo '> '\nend\n"
                                  b"function fish_prompt_extra\nend\n")
        found = takeover.scan(self.folder)
        self.assertEqual(found.blockers, ["config.fish defines fish_prompt at line 2; remove that function"])

    def test_a_continued_line_blocks_the_takeover(self):
        self.write("config.fish", b"set -g tide_left_prompt_items pwd \\\n    git\n")
        self.write("conf.d/mine.fish", b"echo one \\\nstarship init fish | source\n")
        found = takeover.scan(self.folder)
        self.assertEqual(found.blockers, [
            "config.fish line 1 is continued over several lines; disable it yourself",
            "conf.d/mine.fish line 2 is continued over several lines; disable it yourself"])

    def test_a_symlinked_file_is_never_edited(self):
        dotfiles = Path(self.folder.parent) / "dotfiles.fish"
        dotfiles.write_bytes(b"starship init fish | source\nset -g tide_x y\n")
        os.symlink(dotfiles, self.folder / "config.fish")
        found = takeover.scan(self.folder)
        self.assertEqual(found.blockers, [f"config.fish is a symlink to {dotfiles}; disable lines 1, 2 there yourself"])
        self.assertEqual(found.changes, [])

    def test_a_symlinked_file_with_nothing_to_take_over_is_fine(self):
        dotfiles = Path(self.folder.parent) / "dotfiles.fish"
        dotfiles.write_bytes(b"alias ll 'ls -l'\n")
        os.symlink(dotfiles, self.folder / "config.fish")
        self.assertEqual(takeover.scan(self.folder).blockers, [])

    def test_line_endings_and_bytes_are_kept(self):
        data = b"echo \xff\xfe\r\nstarship init fish | source\r\nset -g tide_x \xe9\r\n"
        self.write("config.fish", data)
        change = takeover.scan(self.folder).changes[0]
        self.assertEqual(change.after, b"echo \xff\xfe\r\n# witchy-disabled: starship init fish | source\r\n"
                                       b"# witchy-disabled: set -g tide_x \xe9\r\n")
        self.assertEqual(takeover.enable(change.after), data)

    def test_a_missing_or_empty_config_has_nothing_to_take_over(self):
        self.assertEqual(takeover.scan(self.folder / "nowhere"), takeover.Scan())
        self.assertEqual(takeover.scan(self.folder), takeover.Scan())
        self.write("config.fish", b"")
        self.assertEqual(takeover.scan(self.folder), takeover.Scan())

    def test_files_it_must_leave_are_skipped(self):
        witchy = self.write("conf.d/witchy.fish", b"set -g tide_character_color FFB86B\n")
        fisher = self.write("conf.d/_tide_init.fish", b"set -g tide_x y\n")
        self.write("conf.d/notes.txt", b"starship init fish | source\n")
        self.assertEqual(takeover.scan(self.folder, {witchy, fisher}), takeover.Scan())

    def test_enable_takes_back_only_what_witchy_added(self):
        self.assertEqual(takeover.enable(b"# witchy-disabled: a\n# a comment\n  # witchy-disabled: b\n"),
                         b"a\n# a comment\n  # witchy-disabled: b\n")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_takeover`
Expected:
```
ImportError: cannot import name 'takeover' from 'witchy' (…/witchy/__init__.py)
FAILED (errors=1)
```

- [ ] **Step 3: Implement**

Create `witchy/takeover.py`:

```python
"""Other prompt owners in config.fish and conf.d: found, and disabled line by line (spec 5.2).

Files are read and written as bytes and split on ``\\n`` only, so line endings and bytes that are not UTF-8 stay
exactly as they were; disabling a line puts ``# witchy-disabled: `` in front of it, and enabling takes it away.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .components.base import Change

PREFIX = b"# witchy-disabled: "
STARSHIP = re.compile(r"\bstarship\s+init\s+fish\b")
OH_MY_POSH = re.compile(r"\boh-my-posh\b.*(?:\binit\s+fish\b|--shell\s+fish\b)")
SET = re.compile(r"\bset\s+((?:-[-\w]+\s+)+)(tide_\w+)")
FUNCTION = re.compile(r"^\s*function\s+fish_prompt(?:\s|;|$)")
NOT_A_SET = set("qenS")  # set -q, -e, -n, -S read or erase; they never give a value
NOT_A_SET_LONG = {"--query", "--erase", "--names", "--show"}


@dataclass(frozen=True)
class Line:
    """An active line that makes something other than Tide own the prompt."""

    path: Path
    number: int  # from 1
    what: str  # "starship init", "oh-my-posh init" or "set -g tide_…"


@dataclass
class Scan:
    lines: list[Line] = field(default_factory=list)
    # Why the takeover cannot go ahead (a fish_prompt function, a continued line, a symlink); nothing is changed.
    blockers: list[str] = field(default_factory=list)
    changes: list[Change] = field(default_factory=list)  # each file with its owner lines disabled


def _global_set(line: str) -> str | None:
    for match in SET.finditer(line):
        flags = match.group(1).split()
        short = "".join(flag[1:] for flag in flags if not flag.startswith("--"))
        long = {flag for flag in flags if flag.startswith("--")}
        if NOT_A_SET & set(short) or NOT_A_SET_LONG & long:
            continue
        if "g" in short or "--global" in long:
            return f"set -g {match.group(2)}"
    return None


def owner(line: str) -> str | None:
    """What an active line does to the prompt, or None (a comment, already disabled, or unrelated)."""
    if line.lstrip().startswith("#"):
        return None
    if STARSHIP.search(line):
        return "starship init"
    if OH_MY_POSH.search(line):
        return "oh-my-posh init"
    return _global_set(line)


def config_files(folder: Path, skip: set[Path]) -> list[Path]:
    """config.fish, then each conf.d/*.fish by name, leaving out ``skip`` (witchy's own and fisher's files)."""
    conf_d = folder / "conf.d"
    found = [folder / "config.fish"] + (sorted(conf_d.glob("*.fish")) if conf_d.is_dir() else [])
    return [path for path in found if (path.is_file() or path.is_symlink()) and path not in skip]


def _numbers(numbers: list[int]) -> str:
    return f"line {numbers[0]}" if len(numbers) == 1 else "lines " + ", ".join(map(str, numbers))


def scan(folder: Path, skip: set[Path] = frozenset()) -> Scan:
    """Every other prompt owner in ``folder`` (fish's config folder), and the changes that disable them."""
    found = Scan()
    for path in config_files(folder, skip):
        name = path.relative_to(folder).as_posix()
        try:
            data = path.read_bytes()
        except OSError as exc:
            found.blockers.append(f"cannot read {name} ({exc.strerror or exc})")
            continue
        raw = data.split(b"\n")
        numbers = []
        for index, line in enumerate(raw):
            text = line.decode("utf-8", "surrogateescape").rstrip("\r")
            if FUNCTION.match(text):
                found.blockers.append(f"{name} defines fish_prompt at line {index + 1}; remove that function")
                continue
            what = owner(text)
            if what is None:
                continue
            continued = index > 0 and raw[index - 1].rstrip(b"\r").endswith(b"\\")
            if text.endswith("\\") or continued:
                found.blockers.append(f"{name} line {index + 1} is continued over several lines; "
                                      "disable it yourself")
                continue
            numbers.append(index + 1)
            found.lines.append(Line(path, index + 1, what))
        if numbers and path.is_symlink():
            # A file that lives elsewhere (a dotfiles repository) is never edited (spec D22).
            found.blockers.append(f"{name} is a symlink to {os.readlink(path)}; disable {_numbers(numbers)} there "
                                  "yourself")
        elif numbers:
            found.changes.append(Change(path, data, disable(data, numbers)))
    return found


def disable(data: bytes, numbers: list[int]) -> bytes:
    lines = data.split(b"\n")
    for number in numbers:
        lines[number - 1] = PREFIX + lines[number - 1]
    return b"\n".join(lines)


def enable(data: bytes) -> bytes:
    """Every line witchy disabled, back as it was."""
    return b"\n".join(line[len(PREFIX):] if line.startswith(PREFIX) else line for line in data.split(b"\n"))
```

- [ ] **Step 4: Run the tests and the whole suite**

Run: `/usr/bin/python3 -m unittest tests.test_takeover`
Expected: `Ran 13 tests … OK`

Run the suite on both interpreters and `python3 -m witchy validate`.
Expected: `Ran 659 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/takeover.py tests/test_takeover.py
git commit -m "feat: find other prompt owners in config.fish and conf.d and disable them line by line" -m "starship and oh-my-posh init lines and global tide_ variables are prefixed with '# witchy-disabled: ', byte for byte. A fish_prompt function, a continued line or a symlinked file stops the takeover." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Downloads and fisher output go to ~/.cache/witchy/install.log; downloads wait 120 s

**Items:** spec 5.1 "Timeouts and log (D20)": downloads and `fisher install` use 120 s; their output is appended to `~/.cache/witchy/install.log`, capped at 200 KB with the oldest run dropped first; a failure reads `failed: could not install Tide (exit 1): <last stderr line> (details: ~/.cache/witchy/install.log)`. (`Command.timeout` itself came with Plan F Task 1.)

**Files:**
- Create: `witchy/installlog.py`
- Modify: `witchy/fonts.py` (`DOWNLOAD_TIMEOUT`, `fetch_url`'s default)
- Test: `tests/test_installlog.py` (new)

**Interfaces:**
- Consumes: `base.Command`, `base.ComponentFailed`, `base.run_command(ctx, command, check=False)`, `jsonio.write_atomic_bytes`, `ctx.cache_dir`, `ctx.stamp`, `ctx.home`.
- Produces:
  - `installlog.NAME = "install.log"`, `LIMIT = 200 * 1024`, `RUN` (the header pattern), `ESCAPE`.
  - `installlog.path(ctx) -> Path`, `shown(ctx) -> str` (`~/.cache/witchy/install.log`), `plain(text) -> str` (colour codes removed).
  - `installlog.append(ctx, text) -> None`: never raises.
  - `installlog.run(ctx, command) -> subprocess.CompletedProcess`: runs without checking the exit code and logs `--- <label> (exit N)` and the output; a command that cannot start or times out is logged as `--- <label>: <message>` and its `ComponentFailed` raised again.
  - `installlog.failure(ctx, label, done) -> str`: `could not <label> (exit N): <last line> (details: ~/.cache/witchy/install.log)`; the last non-blank stderr line, else stdout's; no `: …` when both are empty.
  - `fonts.DOWNLOAD_TIMEOUT = 120`; `fonts.fetch_url(url, timeout=DOWNLOAD_TIMEOUT)`.

**Decisions:**
1. **One section per run,** headed `=== witchy install <ctx.stamp> ===`; a second write in the same run goes under the same header. Above 200 KB, whole runs are dropped from the oldest; a run that is still too large alone keeps its last 200 KB, cut at the next line start.
2. **Writing the log never fails an install:** a read or write `OSError` is ignored. The log only explains a failure.
3. **fisher's colour codes are removed** (`set_color` prints them even into a pipe), in the log and in the failure line.
4. **The 120 s default applies to the font download too** (D20 says downloads use 120 s); `ctx.fetch` stays `fonts.fetch_url`, so tests that pass their own `fetch` keep working.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_installlog.py`:

```python
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import fonts, installlog
from witchy.components.base import Command, ComponentFailed
from witchy.context import Context


class InstallLogTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)

    def ctx(self, stamp="20261005-120000", run=None):
        return Context(home=self.home, env={}, out=io.StringIO(), stamp=stamp, run=run or subprocess.run)

    def log(self):
        return (self.home / ".cache" / "witchy" / "install.log").read_text(encoding="utf-8")


class AppendTest(InstallLogTestCase):
    def test_one_header_per_run(self):
        installlog.append(self.ctx(), "first")
        installlog.append(self.ctx(), "second\n")
        installlog.append(self.ctx("20261005-130000"), "third")
        self.assertEqual(self.log(), "=== witchy install 20261005-120000 ===\nfirst\nsecond\n"
                                     "=== witchy install 20261005-130000 ===\nthird\n")

    def test_the_oldest_runs_go_first(self):
        for hour in range(10, 15):
            installlog.append(self.ctx(f"20261005-{hour}0000"), "x" * 60_000)
        log = self.log()
        self.assertLessEqual(len(log.encode("utf-8")), installlog.LIMIT)
        self.assertEqual(installlog.RUN.findall(log),
                         [f"=== witchy install 20261005-{hour}0000 ===" for hour in (12, 13, 14)])

    def test_a_run_too_large_alone_keeps_its_end_from_a_line_start(self):
        installlog.append(self.ctx(), "".join(f"line {number}\n" for number in range(40_000)))
        log = self.log()
        self.assertLessEqual(len(log.encode("utf-8")), installlog.LIMIT)
        self.assertTrue(log.startswith("line "))
        self.assertTrue(log.endswith("line 39999\n"))

    def test_a_log_that_cannot_be_written_is_no_error(self):
        (self.home / ".cache").write_text("a file where the folder should be", encoding="utf-8")
        installlog.append(self.ctx(), "lost")

    def test_shown_with_a_tilde(self):
        self.assertEqual(installlog.shown(self.ctx()), "~/.cache/witchy/install.log")


class RunTest(InstallLogTestCase):
    def test_logs_the_label_the_exit_code_and_the_output_without_colours(self):
        def run(args, **kwargs):
            return subprocess.CompletedProcess(args, 1, stdout="\x1b[1mfisher install version 4.4.5\x1b(B\x1b[m\n",
                                               stderr="fisher: Invalid plugin name or host unavailable\n")

        done = installlog.run(self.ctx(run=run), Command(("fish", "-c", "fisher install x"), "install Tide",
                                                         timeout=120))
        self.assertEqual(done.returncode, 1)
        self.assertEqual(self.log(), "=== witchy install 20261005-120000 ===\n--- install Tide (exit 1)\n"
                                     "fisher install version 4.4.5\nfisher: Invalid plugin name or host unavailable\n")

    def test_a_timeout_is_logged_and_still_raised(self):
        def run(args, **kwargs):
            raise subprocess.TimeoutExpired(args, kwargs["timeout"])

        with self.assertRaisesRegex(ComponentFailed, r"could not install Tide \(timed out after 120 s\)"):
            installlog.run(self.ctx(run=run), Command(("fish",), "install Tide", timeout=120))
        self.assertIn("--- install Tide: could not install Tide (timed out after 120 s)\n", self.log())

    def test_a_failure_names_the_last_error_line_and_the_log(self):
        done = subprocess.CompletedProcess([], 1, stdout="Fetching x\n",
                                           stderr="\x1b[31mfisher: Cannot install\x1b[m\n  conflict\n\n")
        self.assertEqual(installlog.failure(self.ctx(), "install Tide", done),
                         "could not install Tide (exit 1): conflict (details: ~/.cache/witchy/install.log)")
        quiet = subprocess.CompletedProcess([], 2, stdout="", stderr="")
        self.assertEqual(installlog.failure(self.ctx(), "install Tide", quiet),
                         "could not install Tide (exit 2) (details: ~/.cache/witchy/install.log)")


class DownloadTimeoutTest(unittest.TestCase):
    def test_downloads_wait_120_seconds(self):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b"data"
        with mock.patch("urllib.request.urlopen", return_value=response) as urlopen:
            self.assertEqual(fonts.fetch_url("https://example.invalid/x"), b"data")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 120)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_installlog`
Expected:
```
ImportError: cannot import name 'installlog' from 'witchy' (…/witchy/__init__.py)
FAILED (errors=1)
```

- [ ] **Step 3: Implement**

Create `witchy/installlog.py`:

```python
"""~/.cache/witchy/install.log: what downloads and fisher printed during an install (spec 5.1, D20).

Each run starts with a header line. The log stays under 200 KB: the oldest runs go first, and a run that is
still too large alone keeps its end. Writing the log never fails an install.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from . import jsonio
from .components.base import Command, ComponentFailed, run_command

NAME = "install.log"
LIMIT = 200 * 1024
RUN = re.compile(r"^=== witchy install \S+ ===$", re.MULTILINE)
ESCAPE = re.compile(r"\x1b(?:\[[0-9;?]*[A-Za-z]|\([A-Z0-9])")  # the colours fisher prints


def path(ctx: Any) -> Path:
    return ctx.cache_dir / NAME


def shown(ctx: Any) -> str:
    """The log's path with ~ for HOME, as messages show it."""
    target = path(ctx)
    try:
        return "~/" + target.relative_to(ctx.home).as_posix()
    except ValueError:
        return str(target)


def plain(text: str) -> str:
    return ESCAPE.sub("", text)


def append(ctx: Any, text: str) -> None:
    target = path(ctx)
    try:
        old = target.read_bytes().decode("utf-8", "replace")
    except OSError:
        old = ""
    starts = [match.start() for match in RUN.finditer(old)]
    runs = [old[start:end] for start, end in zip(starts, starts[1:] + [len(old)])]
    header = f"=== witchy install {ctx.stamp} ===\n"
    if not runs or not runs[-1].startswith(header):
        runs.append(header)
    runs[-1] += text if text.endswith("\n") else text + "\n"
    while len(runs) > 1 and len("".join(runs).encode("utf-8")) > LIMIT:
        runs.pop(0)
    data = "".join(runs).encode("utf-8")
    if len(data) > LIMIT:
        data = data[-LIMIT:]
        data = data[data.find(b"\n") + 1:]
    try:
        jsonio.write_atomic_bytes(target, data)
    except OSError:
        pass  # the log only explains a failure; it never causes one


def run(ctx: Any, command: Command) -> subprocess.CompletedProcess:
    """Run ``command`` without checking its exit code, and log what it printed under its label."""
    try:
        done = run_command(ctx, command, check=False)
    except ComponentFailed as exc:
        append(ctx, f"--- {command.label}: {exc}")
        raise
    output = "".join(plain(text) for text in (done.stdout, done.stderr) if text)
    append(ctx, f"--- {command.label} (exit {done.returncode})\n{output}")
    return done


def _last(text: str | None) -> str:
    return next((line.strip() for line in reversed(plain(text or "").splitlines()) if line.strip()), "")


def failure(ctx: Any, label: str, done: subprocess.CompletedProcess) -> str:
    """``could not <label> (exit N): <its last error line> (details: ~/.cache/witchy/install.log)``."""
    last = _last(done.stderr) or _last(done.stdout)
    said = f": {last}" if last else ""
    return f"could not {label} (exit {done.returncode}){said} (details: {shown(ctx)})"
```

In `witchy/fonts.py`, replace:

```python
DOWNLOAD_LIMIT = 64 * 1024 * 1024
```

with:

```python
DOWNLOAD_LIMIT = 64 * 1024 * 1024
DOWNLOAD_TIMEOUT = 120  # seconds (spec D20)
```

and replace:

```python
def fetch_url(url: str, timeout: float = 60) -> bytes:
```

with:

```python
def fetch_url(url: str, timeout: float = DOWNLOAD_TIMEOUT) -> bytes:
```

- [ ] **Step 4: Run the tests and the whole suite**

Run: `/usr/bin/python3 -m unittest tests.test_installlog`
Expected: `Ran 9 tests … OK`

Run the suite on both interpreters and `python3 -m witchy validate`.
Expected: `Ran 668 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/installlog.py witchy/fonts.py tests/test_installlog.py
git commit -m "feat: downloads and fisher output go to ~/.cache/witchy/install.log; downloads wait 120 s" -m "The log keeps one section per run and stays under 200 KB, dropping the oldest run first. A failure names the last error line and the log." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The tide component installs fisher 4.4.5 and Tide 6.1.1 and checks every file against the pins

**Items:** spec 5 and 5.1: the bootstrap table (fish missing, fisher missing, Tide missing, another Tide version, Tide 6.1.1 present), `curl` checked before anything is downloaded, the pin check after each `fisher install` (`fisher remove` and `failed: <plugin> files do not match the pinned release` on a mismatch), `tide --version` must print `6.1.1`, 120 s and the install log for every fisher call, a failure keeps the record of what was installed so far, the entry fields, and a dry run that runs nothing. Decisions 3, 4, 5, 11, 16 and 17 of this plan.

**Files:**
- Create: `witchy/components/tide.py`
- Modify: `tests/fakes.py` (imports; `FISHER_FILE`, `TIDE_FILES`, `RELEASES`, `fake_pins`, `FakeFisher`)
- Test: `tests/test_components_tide.py` (new)
- Docs: spec 5.1 (the table rows for another Tide and fish missing; the user's fisher; curl only when needed)

**Interfaces:**
- Consumes: `fishprobe.probe`, `Probe`, `plugin_files`, `tide_ready`, `TIDE_VERSION`, `TIDE_PLUGIN`, `FISHER_PLUGIN` (Plan F); `content.load_pins` (Task 1); `installlog.run`, `append`, `failure`, `shown` (Task 3); `base.Command`, `ComponentFailed`, `Plan`, `read`, `sha`; `jsonio.write_atomic_bytes`; `ctx.fetch`, `ctx.cache_dir`, `ctx.env["PATH"]`.
- Produces:
  - `tide.FISH`, `FISHER_VERSION = "4.4.5"`, `FISHER_SOURCE = "jorgebucaran/fisher@4.4.5"`, `TIDE_SOURCE = "ilancosman/tide@v6.1.1"`, `FISHER_TIMEOUT = 120`, `FISH_MISSING = "fish not found (sudo apt install fish)"`, `CURL_MISSING = "curl not found (sudo apt install curl)"`, `NOT_PINNED`.
  - `BOOTSTRAP_SCRIPT` (argv: the cached `fisher.fish`, `FISHER_SOURCE`), `FISHER_SCRIPT` (`fisher $argv`), `SWAP_SCRIPT` (argv: the plugin to remove or `""`, the one to install).
  - `fisher_command(label, *args) -> Command` and `swap_command(label, remove, install) -> Command`: input `""`, timeout 120.
  - `installed_name(found, plugin) -> str | None`, `file_hashes(paths) -> dict[str, str]`, `mismatches(found, plugin, pinned) -> list[str]`.
  - `class TideComponent(pins: dict | None = None)` with `name = "tide"`, `plan`, `apply`. `plan.data`: `entry`, `error`, `fisher` (`None`/`"install"`/`"update"`), `tide` (`None`/`"install"`/`"update"`/`"replace"`), `replace` (the name being replaced), and `installs` (renamed `reprobe` in Task 5).
  - The entry: `{"installed_fisher": bool, "installed_tide": bool, "previous_tide_plugin": str | None, "removed_plugins": [], "disabled_files": [], "moved_prompt": None}` (Task 5 fills the last three). A reinstall keeps what the first install recorded.
  - The bootstrap file is cached as `~/.cache/witchy/fisher-4.4.5.fish`.
  - `tests/fakes.py`: `FISHER_FILE`, `TIDE_FILES`, `RELEASES`, `fake_pins(releases=None, bootstrap=FISHER_FILE)`, `FakeFisher(config, installed=None, served=None, variables=None, calls=None, missing=False)` with `.run`, `.plugins`, `.served`, `.variables`, `.calls`, `.missing`, `.fisher(command, names)`, `.probe()`.

**Decisions:**
1. **What `plan` decides, from one probe** (spec 5.1, plan Decisions 3 and 5): fisher missing → bootstrap; fisher named `FISHER_SOURCE` whose files differ from the pins → `fisher install FISHER_SOURCE` (an update); any other fisher → left alone. Tide missing → `fisher install TIDE_SOURCE`; Tide named `TIDE_SOURCE` whose version or files differ → the same install (an update); Tide under another name whose version or files differ → replaced through `SWAP_SCRIPT`; Tide that matches → nothing. A `tide` function with no fisher record → `failed`.
2. **`curl` only matters when fisher will download:** missing `curl` with nothing to install is fine.
3. **Every install is checked by probing again:** the plugin is listed, the version is the pinned one, and `mismatches` is empty; otherwise `fisher remove <its name>` runs and the component fails. After Tide, `tide_ready` must hold too. fisher's own exit code is also checked, but it says nothing about which bytes were copied.
4. **`installed_fisher` and `installed_tide` are set only after the check passed,** so a removed mismatching plugin is never recorded as installed. `previous_tide_plugin` is recorded before the swap runs, because from then on the user's Tide may be gone.
5. **A failure keeps the record** (`plan.outcome = "failed: …"`, the entry returned) unless nothing changed and there was no earlier entry, in which case `ComponentFailed` propagates and nothing is recorded (ritual 3.3).
6. **fisher always gets empty standard input** (plan Decision 11), and `BOOTSTRAP_SCRIPT` runs `source` and `fisher install` in one fish process, so fisher exists only for that call until it has installed itself.
7. **`FakeFisher` keeps plugins as files** in the temporary fish folder: the component's pin check hashes them for real, and tests change a file to make it differ. It models fisher's refusal to overwrite a file (unless it updates that plugin) and Tide's uninstall erasing every universal `tide_*` variable; its swap keeps them, as `SWAP_SCRIPT` does. `RealFishSwapTest` checks the script itself with real fish.

- [ ] **Step 1: Write the test doubles and the failing tests**

In `tests/fakes.py`, replace the imports:

```python
import io
import shutil
import struct
import subprocess
import zipfile
```

with:

```python
import hashlib
import io
import re
import shutil
import struct
import subprocess
import zipfile
from pathlib import Path
```

and add at the end of the file:

```python
# What `fisher install` fetches in tests: fisher 4.4.5 and a cut-down Tide 6.1.1, as files below fisher's folder.
FISHER_FILE = b"function fisher\n    echo 'fisher, version 4.4.5'\nend\n"
TIDE_FILES = {"functions/tide.fish": b"function tide\n    echo 'tide, version 6.1.1'\nend\n",
              "functions/fish_prompt.fish": b"function fish_prompt\n    echo '> '\nend\n",
              "functions/tide/configure/icons.fish": b"tide_pwd_icon x\n",
              "conf.d/_tide_init.fish": b"function _tide_init_install --on-event _tide_init_install\nend\n"}
RELEASES = {"jorgebucaran/fisher@4.4.5": {"functions/fisher.fish": FISHER_FILE,
                                          "completions/fisher.fish": b"complete -c fisher\n"},
            "ilancosman/tide@v6.1.1": TIDE_FILES}


def fake_pins(releases=None, bootstrap=FISHER_FILE):
    """content/pins.json for ``releases``: the bootstrap file's hash and each plugin's file hashes."""
    def digest(data):
        return hashlib.sha256(data).hexdigest()

    return {"bootstrap": {"url": "https://example.invalid/fisher.fish", "sha256": digest(bootstrap)},
            "plugins": {name: {path: digest(data) for path, data in files.items()}
                        for name, files in (RELEASES if releases is None else releases).items()}}


class FakeFisher:
    """fish with fisher, whose plugins are real files in ``config`` (a temporary fish folder), so witchy can hash
    them.

    ``installed`` maps the plugins there at the start (by fisher's name, such as ``ilancosman/tide``) to their files;
    ``served`` is what `fisher install` can fetch, by ``owner/repo@ref``. fisher is a function when
    functions/fisher.fish exists or while a bootstrap script runs; `fisher --version` and `tide --version` print the
    version their file holds, and fish_prompt comes from functions/fish_prompt.fish. Like the real fisher, install
    refuses a file that is already there (unless it updates that plugin), remove deletes the plugin's files, and
    removing Tide erases every universal tide_ variable. Other fish calls go to fake_fish with ``variables``.
    ``calls`` gets each command.
    """

    VERSION = re.compile(rb"version (\S+)'")

    def __init__(self, config, installed=None, served=None, variables=None, calls=None, missing=False):
        self.config, self.missing, self.bootstrapping = config, missing, False
        self.served = RELEASES if served is None else served
        self.variables = {} if variables is None else variables
        self.calls = [] if calls is None else calls
        self.plugins = {}
        for name, files in (installed or {}).items():
            self._write(name, files)
        self.inner = fake_fish(self.variables)

    def _write(self, name, files):
        tops = set()
        for relative, data in files.items():
            path = self.config / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            tops.add("/".join(relative.split("/")[:2]))
        self.plugins[name] = sorted(tops)

    def _version(self, relative):
        path = self.config / relative
        if not path.is_file():
            return None
        match = self.VERSION.search(path.read_bytes())
        return match.group(1).decode() if match else ""

    def probe(self):
        fisher, tide = self._version("functions/fisher.fish"), self._version("functions/tide.fish")
        prompt = self.config / "functions" / "fish_prompt.fish"
        fields = ["fisher", f"fisher, version {fisher}"] if fisher is not None else ["no-fisher"]
        fields += ["tide", f"tide, version {tide}"] if tide is not None else ["no-tide"]
        fields.append(str(prompt) if prompt.is_file() else "n/a")
        for name, tops in self.plugins.items():
            fields += [name, str(len(tops)), *(str(self.config / top) for top in tops)]
        return fields

    def fisher(self, command, names):
        if not self.bootstrapping and not (self.config / "functions" / "fisher.fish").is_file():
            return 127, "", "fish: Unknown command: fisher\n"
        done, errors = 0, ""
        for name in names:
            key = name.lower()
            if command == "remove":
                if key not in self.plugins:
                    errors += f'fisher: Plugin not installed: "{key}"\n'
                    continue
                for top in self.plugins.pop(key):
                    path = self.config / top
                    shutil.rmtree(path) if path.is_dir() else path.unlink(missing_ok=True)
                if key.split("@")[0] == "ilancosman/tide":
                    for variable in [variable for variable in self.variables if variable.startswith("tide_")]:
                        del self.variables[variable]
                done += 1
                continue
            if key not in self.served:
                errors += f'fisher: Invalid plugin name or host unavailable: "{key}"\n'
                continue
            files = self.served[key]
            tops = sorted({"/".join(relative.split("/")[:2]) for relative in files})
            conflicts = [] if key in self.plugins else [top for top in tops if (self.config / top).exists()]
            if conflicts:
                errors += (f'fisher: Cannot install "{key}": please remove or move conflicting files first:\n'
                           + "".join(f"        {self.config / top}\n" for top in conflicts))
                continue
            self._write(key, files)
            done += 1
        return (0 if done else 1), f"fisher {command} version 4.4.5\n", errors

    def run(self, args, input=None, text=False, errors="strict", **kwargs):
        from witchy import fishprobe
        from witchy.components import tide

        args = list(args)
        self.calls.append(args)
        if self.missing:
            raise FileNotFoundError(2, "No such file or directory", "fish")
        if args == ["fish", "-c", fishprobe.PROBE_SCRIPT]:
            stdout = "".join(f"{field}\0" for field in [fishprobe.SENTINEL, *self.probe()]).encode("utf-8")
            return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr=b"")
        if args[:4] == ["fish", "-c", tide.FISHER_SCRIPT, "--"]:
            code, out, err = self.fisher(args[4], args[5:])
        elif args[:4] == ["fish", "-c", tide.BOOTSTRAP_SCRIPT, "--"]:
            if b"function fisher" not in Path(args[4]).read_bytes():
                code, out, err = 127, "", "fish: Unknown command: fisher\n"
            else:
                self.bootstrapping = True
                code, out, err = self.fisher("install", args[5:])
                self.bootstrapping = False
        elif args[:4] == ["fish", "-c", tide.SWAP_SCRIPT, "--"]:
            kept = {name: value for name, value in self.variables.items() if name.startswith("tide_")}
            if args[4]:
                self.fisher("remove", [args[4]])
            code, out, err = self.fisher("install", [args[5]])
            self.variables.update(kept)
        else:
            return self.inner(args, input=input, text=text, errors=errors, **kwargs)
        if not text:
            out, err = out.encode("utf-8"), err.encode("utf-8")
        return subprocess.CompletedProcess(args, code, stdout=out, stderr=err)
```

Create `tests/test_components_tide.py`:

```python
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.fakes import FISHER_FILE, RELEASES, TIDE_FILES, FakeFisher, fake_pins
from witchy import content, fishprobe, runner
from witchy.components import fish, tide
from witchy.components.base import run_command, sha
from witchy.context import Context

FISHER = RELEASES["jorgebucaran/fisher@4.4.5"]
REAL_FISH = shutil.which("fish")
ROOT = Path(__file__).resolve().parent.parent
OLD_TIDE = {**TIDE_FILES, "functions/tide.fish": b"function tide\n    echo 'tide, version 6.0.0'\nend\n"}


class TideTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.config = self.home / ".config" / "fish"
        self.config.mkdir(parents=True)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.bin / "curl").write_text("#!/bin/sh\n", encoding="utf-8")
        (self.bin / "curl").chmod(0o755)
        self.fetched = []
        self.variables = {}

    def fisher(self, installed=None, served=None, **kwargs):
        self.fake = FakeFisher(self.config, installed=installed, served=served, variables=self.variables, **kwargs)
        return self.fake

    def fetch(self, url):
        self.fetched.append(url)
        return FISHER_FILE

    def ctx(self, fake=None, dry_run=False, stamp="20261005-120000", fetch=None, path=None):
        self.out = io.StringIO()
        fake = fake or getattr(self, "fake", None) or self.fisher()
        return Context(home=self.home, env={"PATH": str(self.bin) if path is None else path}, out=self.out,
                       dry_run=dry_run, stamp=stamp, run=fake.run, dist=self.root / "dist",
                       lock_path=self.root / "witchy.lock", only=("tide",), fetch=fetch or self.fetch)

    def install(self, ctx=None, pins=None):
        ctx = ctx or self.ctx()
        return runner.install(ctx, [tide.TideComponent(fake_pins() if pins is None else pins)])

    def state(self):
        return json.loads((self.home / ".claude" / "witchy" / "state.json").read_text(encoding="utf-8"))

    def entry(self):
        return self.state()["components"]["tide"]

    def result(self):
        return self.state()["last_install"]["results"]["tide"]

    def fisher_calls(self):
        """Each fisher call: its script's kind and its arguments."""
        kinds = {tide.FISHER_SCRIPT: "fisher", tide.BOOTSTRAP_SCRIPT: "bootstrap", tide.SWAP_SCRIPT: "swap"}
        return [(kinds[args[2]], *args[4:]) for args in self.fake.calls if args[:2] == ["fish", "-c"]
                and args[2] in kinds]

    def log(self):
        return (self.home / ".cache" / "witchy" / "install.log").read_text(encoding="utf-8")


class BootstrapTest(TideTestCase):
    def test_a_pc_with_fish_only_gets_fisher_and_tide(self):
        self.fisher()
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fetched, ["https://example.invalid/fisher.fish"])
        cached = self.home / ".cache" / "witchy" / "fisher-4.4.5.fish"
        self.assertEqual(cached.read_bytes(), FISHER_FILE)
        self.assertEqual(self.fisher_calls(), [("bootstrap", str(cached), "jorgebucaran/fisher@4.4.5"),
                                               ("fisher", "install", "ilancosman/tide@v6.1.1")])
        self.assertEqual(sorted(self.fake.plugins), ["ilancosman/tide@v6.1.1", "jorgebucaran/fisher@4.4.5"])
        self.assertEqual(self.entry(), {"installed_fisher": True, "installed_tide": True,
                                        "previous_tide_plugin": None, "removed_plugins": [], "disabled_files": [],
                                        "moved_prompt": None})
        self.assertEqual(self.result(), "ok")

    def test_a_cached_bootstrap_file_with_the_pinned_hash_is_not_downloaded_again(self):
        cached = self.home / ".cache" / "witchy" / "fisher-4.4.5.fish"
        cached.parent.mkdir(parents=True)
        cached.write_bytes(FISHER_FILE)
        self.fisher()
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fetched, [])

    def test_a_bootstrap_file_that_does_not_match_its_pin_is_never_run(self):
        self.fisher()
        self.assertEqual(self.install(self.ctx(fetch=lambda url: b"function fisher\n    rm -rf ~\nend\n")), 2)
        self.assertEqual(self.result(), "failed: the downloaded fisher.fish does not match the pinned release")
        self.assertEqual(self.fisher_calls(), [])
        self.assertFalse((self.home / ".cache" / "witchy" / "fisher-4.4.5.fish").exists())
        self.assertNotIn("tide", self.state()["components"])

    def test_no_network_fails_with_the_reason(self):
        def offline(url):
            raise OSError("network is unreachable")

        self.fisher()
        self.assertEqual(self.install(self.ctx(fetch=offline)), 2)
        self.assertEqual(self.result(), "failed: could not download fisher (network is unreachable)")
        self.assertIn("--- download https://example.invalid/fisher.fish: network is unreachable", self.log())

    def test_tide_missing_installs_only_tide(self):
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("fisher", "install", "ilancosman/tide@v6.1.1")])
        self.assertEqual((self.entry()["installed_fisher"], self.entry()["installed_tide"]), (False, True))

    def test_another_tide_version_is_replaced_and_its_name_recorded(self):
        self.variables.update({"tide_pwd_icon": {"value": ["x"], "exported": False}})
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide": OLD_TIDE})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("swap", "ilancosman/tide", "ilancosman/tide@v6.1.1")])
        self.assertEqual(sorted(self.fake.plugins), ["ilancosman/tide@v6.1.1", "jorgebucaran/fisher"])
        self.assertEqual(self.entry()["previous_tide_plugin"], "ilancosman/tide")
        self.assertFalse(self.entry()["installed_tide"])
        self.assertEqual(self.variables, {"tide_pwd_icon": {"value": ["x"], "exported": False}})

    def test_tide_6_1_1_with_files_that_differ_from_the_release_is_replaced(self):
        # This PC: Tide's development branch, which also says 6.1.1.
        changed = {**TIDE_FILES, "functions/tide/configure/icons.fish": b"tide_bun_icon x\ntide_pwd_icon x\n"}
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide": changed})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("swap", "ilancosman/tide", "ilancosman/tide@v6.1.1")])

    def test_witchys_own_tide_with_a_changed_file_is_installed_again(self):
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide@v6.1.1": TIDE_FILES})
        (self.config / "functions" / "tide" / "configure" / "icons.fish").write_bytes(b"edited\n")
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("fisher", "install", "ilancosman/tide@v6.1.1")])
        self.assertEqual((self.config / "functions" / "tide" / "configure" / "icons.fish").read_bytes(),
                         TIDE_FILES["functions/tide/configure/icons.fish"])

    def test_pinned_tide_is_left_alone(self):
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide@v6.1.1": TIDE_FILES})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [])
        self.assertEqual(self.result(), "ok")

    def test_a_fisher_the_user_installed_is_never_pinned(self):
        older = {"functions/fisher.fish": b"function fisher\n    echo 'fisher, version 4.3.0'\nend\n"}
        self.fisher({"jorgebucaran/fisher": older, "ilancosman/tide@v6.1.1": TIDE_FILES})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [])

    def test_witchys_own_fisher_with_a_changed_file_is_installed_again(self):
        self.fisher({"jorgebucaran/fisher@4.4.5": FISHER, "ilancosman/tide@v6.1.1": TIDE_FILES})
        (self.config / "completions" / "fisher.fish").write_bytes(b"edited\n")
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("fisher", "install", "jorgebucaran/fisher@4.4.5")])

    def test_without_curl_nothing_is_downloaded(self):
        self.fisher()
        self.assertEqual(self.install(self.ctx(path=str(self.root / "empty"))), 2)
        self.assertEqual(self.result(), "failed: curl not found (sudo apt install curl)")
        self.assertEqual((self.fetched, self.fisher_calls()), ([], []))
        self.assertIn("tide: curl not found (sudo apt install curl); nothing was changed.", self.out.getvalue())

    def test_without_curl_a_ready_tide_is_fine(self):
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide@v6.1.1": TIDE_FILES})
        self.assertEqual(self.install(self.ctx(path=str(self.root / "empty"))), 0, self.out.getvalue())

    def test_files_that_do_not_match_the_pins_are_removed_again(self):
        served = {**RELEASES, "ilancosman/tide@v6.1.1": {**TIDE_FILES, "functions/tide.fish":
                                                         b"function tide\n    echo 'tide, version 6.1.1'; evil\nend\n"}}
        self.fisher({"jorgebucaran/fisher": FISHER}, served=served)
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "failed: ilancosman/tide files do not match the pinned release")
        self.assertEqual(self.fisher_calls(), [("fisher", "install", "ilancosman/tide@v6.1.1"),
                                               ("fisher", "remove", "ilancosman/tide@v6.1.1")])
        self.assertFalse((self.config / "functions" / "tide.fish").exists())
        self.assertNotIn("tide", self.state()["components"])

    def test_a_fisher_error_names_its_last_line_and_the_log(self):
        self.fisher({"jorgebucaran/fisher": FISHER}, served={})
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), 'failed: could not install Tide (exit 1): fisher: Invalid plugin name or host '
                                        'unavailable: "ilancosman/tide@v6.1.1" (details: ~/.cache/witchy/install.log)')
        self.assertIn("--- install Tide (exit 1)\nfisher install version 4.4.5\nfisher: Invalid plugin name",
                      self.log())

    def test_what_installed_before_a_failure_stays_recorded(self):
        self.fisher(served={"jorgebucaran/fisher@4.4.5": FISHER})
        self.assertEqual(self.install(), 2)
        self.assertTrue(self.result().startswith("failed: could not install Tide (exit 1)"))
        self.assertEqual((self.entry()["installed_fisher"], self.entry()["installed_tide"]), (True, False))

    def test_every_fisher_call_has_120_seconds_and_empty_standard_input(self):
        seen = []
        ctx = self.ctx()
        real = ctx.run

        def run(args, **kwargs):
            if args[2:3] in ([tide.FISHER_SCRIPT], [tide.BOOTSTRAP_SCRIPT]):
                seen.append((kwargs["timeout"], kwargs["input"]))
            return real(args, **kwargs)

        ctx.run = run
        self.assertEqual(self.install(ctx), 0, self.out.getvalue())
        self.assertEqual(seen, [(120, ""), (120, "")])

    def test_dry_run_lists_the_downloads_and_fisher_commands_and_runs_none(self):
        self.fisher()
        self.assertEqual(self.install(self.ctx(dry_run=True)), 0)
        self.assertIn("tide: download https://example.invalid/fisher.fish (sha256 ", self.out.getvalue())
        self.assertIn("tide: fisher install jorgebucaran/fisher@4.4.5\ntide: fisher install ilancosman/tide@v6.1.1\n",
                      self.out.getvalue())
        self.assertEqual((self.fetched, self.fisher_calls()), ([], []))
        self.assertFalse((self.home / ".claude").exists())
        self.assertFalse((self.home / ".cache").exists())

    def test_dry_run_of_a_replacement_names_both_tides(self):
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide": OLD_TIDE})
        self.install(self.ctx(dry_run=True))
        self.assertIn("tide: fisher remove ilancosman/tide, then fisher install ilancosman/tide@v6.1.1 "
                      "(Tide is 6.0.0); the Tide variables keep their values", self.out.getvalue())

    def test_a_reinstall_keeps_what_the_first_install_recorded(self):
        self.fisher()
        self.install()
        self.assertEqual(self.install(self.ctx(stamp="20261005-130000")), 0)
        self.assertEqual((self.entry()["installed_fisher"], self.entry()["installed_tide"]), (True, True))

    def test_without_fish_it_is_skipped(self):
        self.fisher(missing=True)
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "skipped: fish not found (sudo apt install fish)")

    def test_a_tide_fisher_does_not_know_is_not_touched(self):
        (self.config / "functions").mkdir()
        (self.config / "functions" / "tide.fish").write_bytes(TIDE_FILES["functions/tide.fish"])
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "failed: Tide is installed without fisher, so witchy can neither check nor "
                                        "replace it; remove it")
        self.assertEqual(self.fisher_calls(), [])


class PinsTest(unittest.TestCase):
    def test_the_installed_sources_are_the_pinned_ones(self):
        self.assertEqual(tuple(content.load_pins()["plugins"]), (tide.FISHER_SOURCE, tide.TIDE_SOURCE))
        self.assertEqual(tide.FISHER_SOURCE, f"{fishprobe.FISHER_PLUGIN}@{tide.FISHER_VERSION}")
        self.assertEqual(tide.TIDE_SOURCE, f"{fishprobe.TIDE_PLUGIN}@v{fishprobe.TIDE_VERSION}")

    def test_each_new_module_can_be_imported_first(self):
        for module in ("witchy.fishprobe", "witchy.takeover", "witchy.installlog", "witchy.components.tide"):
            done = subprocess.run([sys.executable, "-c", f"import {module}"], cwd=ROOT, capture_output=True,
                                  text=True, timeout=60)
            self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_listed_folder_counts_with_every_file_below_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            functions = Path(tmp) / "functions"
            (functions / "tide" / "configure").mkdir(parents=True)
            (functions / "tide" / "configure" / "icons.fish").write_bytes(b"a")
            (functions / "tide.fish").write_bytes(b"b")
            self.assertEqual(tide.file_hashes([str(functions / "tide"), str(functions / "tide.fish"),
                                               str(functions / "gone.fish")]),
                             {"functions/tide/configure/icons.fish": sha(b"a"), "functions/tide.fish": sha(b"b")})


# Stands in for fisher where only its effect on the variables matters: removing Tide erases every universal tide_
# variable and installing it sets Tide's defaults, as Tide's own uninstall and install handlers do.
FAKE_FISHER_FUNCTION = """\
function fisher
    switch $argv[1]
        case remove
            set -e -U (set -U --names | string match 'tide_*')
        case install
            set -U tide_pwd_icon lean
            test "$argv[2]" = ilancosman/tide@v6.1.1
    end
end
"""


@unittest.skipUnless(REAL_FISH, "fish is not installed")
class RealFishSwapTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        functions = Path(tmp.name) / "config" / "fish" / "functions"
        functions.mkdir(parents=True)
        self.home.mkdir()
        (functions / "fisher.fish").write_text(FAKE_FISHER_FUNCTION, encoding="utf-8")
        env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(functions.parent.parent), "PATH": "/usr/bin:/bin"}
        self.ctx = Context(home=self.home, env=env, out=io.StringIO())
        run_command(self.ctx, fish.set_command([("tide_pwd_icon", "set", ["x", "two words"]),
                                                ("tide_time_color", "exported", ["5F8787"]),
                                                ("tide_empty", "set", [])], "set three"))
        self.before = fish.snapshot(self.ctx, [])

    def test_a_swap_keeps_every_tide_variable(self):
        done = run_command(self.ctx, tide.swap_command("install Tide", "ilancosman/tide", "ilancosman/tide@v6.1.1"),
                           check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(fish.snapshot(self.ctx, []), self.before)

    def test_a_swap_whose_install_fails_still_keeps_them(self):
        done = run_command(self.ctx, tide.swap_command("install Tide", "ilancosman/tide", "ilancosman/tide@v9"),
                           check=False)
        self.assertEqual(done.returncode, 1)
        self.assertEqual(fish.snapshot(self.ctx, []), self.before)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_components_tide`
Expected:
```
ImportError: cannot import name 'tide' from 'witchy.components' (…/witchy/components/__init__.py)
FAILED (errors=1)
```

- [ ] **Step 3: Implement**

Create `witchy/components/tide.py`:

```python
"""tide: fisher and Tide 6.1.1, pinned file by file, with Tide as the only prompt (spec 5)."""
from __future__ import annotations

import http.client
import shutil
from pathlib import Path
from typing import Any

from .. import content, fishprobe, installlog, jsonio
from .base import Command, ComponentFailed, Plan, read, sha

FISH = "fish"
FISHER_VERSION = "4.4.5"
# What fisher installs, as content/pins.json names it. Spelled out: fishprobe may still be loading when this is.
FISHER_SOURCE = "jorgebucaran/fisher@4.4.5"
TIDE_SOURCE = "ilancosman/tide@v6.1.1"
FISHER_TIMEOUT = 120  # seconds for each fisher call, which downloads (spec D20)
FISH_MISSING = "fish not found (sudo apt install fish)"
CURL_MISSING = "curl not found (sudo apt install curl)"
NOT_PINNED = "its files do not match the pinned release"

# Sources the pinned fisher.fish, then lets it install itself as a plugin.
BOOTSTRAP_SCRIPT = "source $argv[1]; and fisher install $argv[2]"
FISHER_SCRIPT = "fisher $argv"
# Replaces one Tide with another and keeps every universal tide_ variable: Tide's uninstall erases them and its
# install sets its own defaults. argv: the plugin to remove ("" for none), then the one to install. The values
# are put back even when the install fails, so a later run still has them.
SWAP_SCRIPT = """\
set -l names (set -U --names | string match 'tide_*')
for name in $names
    set -g __witchy_saved_$name $$name
    set -q -U -x $name; and set -g __witchy_exported_$name
end
test -n "$argv[1]"; and fisher remove $argv[1]
fisher install $argv[2]
set -l code $status
for name in $names
    set -l saved __witchy_saved_$name
    if set -q __witchy_exported_$name
        set -U -x $name $$saved
    else
        set -U $name $$saved
    end
end
exit $code
"""


def fisher_command(label: str, *args: str) -> Command:
    """``fisher <args>``: 120 s, and empty standard input (fisher reads plugin names from a pipe)."""
    return Command((FISH, "-c", FISHER_SCRIPT, "--", *args), label, "", timeout=FISHER_TIMEOUT)


def swap_command(label: str, remove: str, install: str) -> Command:
    return Command((FISH, "-c", SWAP_SCRIPT, "--", remove, install), label, "", timeout=FISHER_TIMEOUT)


def installed_name(found: fishprobe.Probe, plugin: str) -> str | None:
    """The name fisher lists ``plugin`` under (``owner/repo``, maybe with ``@ref``), or None."""
    return next((name for name in found.plugins if name.lower().split("@", 1)[0] == plugin), None)


def file_hashes(paths: list[str]) -> dict[str, str]:
    """The SHA-256 of each file fisher lists, by path below fisher's folder (``functions/tide.fish``); a listed
    folder (``functions/tide``) counts with every file below it."""
    hashes = {}
    for listed in paths:
        path = Path(listed)
        key = "/".join(path.parts[-2:])
        if path.is_dir():
            for inner in sorted(path.rglob("*")):
                if inner.is_file():
                    hashes[f"{key}/{inner.relative_to(path).as_posix()}"] = sha(inner.read_bytes())
        elif path.is_file():
            hashes[key] = sha(path.read_bytes())
    return hashes


def mismatches(found: fishprobe.Probe, plugin: str, pinned: dict[str, str]) -> list[str]:
    """The files of ``plugin`` that differ from ``pinned``, are missing, or are not pinned at all."""
    hashes = file_hashes(fishprobe.plugin_files(found, plugin) or [])
    return sorted(name for name in pinned.keys() | hashes.keys() if pinned.get(name) != hashes.get(name))


class TideComponent:
    name = "tide"

    def __init__(self, pins: dict | None = None):
        self.pins = pins

    def _pins(self) -> dict:
        if self.pins is None:
            self.pins = content.load_pins()
        return self.pins

    def _pinned(self, source: str) -> dict[str, str]:
        return self._pins()["plugins"][source]

    def _bootstrap_file(self, ctx: Any) -> Path:
        return ctx.cache_dir / f"fisher-{FISHER_VERSION}.fish"

    def plan(self, ctx: Any, entry: dict | None) -> Plan:
        try:
            found = fishprobe.probe(ctx)
        except ComponentFailed as exc:
            if isinstance(exc.__cause__, FileNotFoundError):
                ctx.say(f"tide: {FISH_MISSING}")
                return Plan.skipped(FISH_MISSING)
            return Plan.skipped(str(exc))
        data: dict[str, Any] = {"entry": entry or {}, "error": None, "fisher": None, "tide": None, "replace": None}
        actions = []
        fisher_name = installed_name(found, fishprobe.FISHER_PLUGIN)
        if found.fisher is None:
            data["fisher"] = "install"
            cached = self._bootstrap_file(ctx)
            bootstrap = self._pins()["bootstrap"]
            source = (f"use {cached}" if sha(read(cached)) == bootstrap["sha256"]
                      else f"download {bootstrap['url']} (sha256 {bootstrap['sha256'][:12]}…)")
            actions += [f"tide: {source}", f"tide: fisher install {FISHER_SOURCE}"]
        elif fisher_name == FISHER_SOURCE and mismatches(found, fishprobe.FISHER_PLUGIN, self._pinned(FISHER_SOURCE)):
            # witchy's own fisher; a fisher the user installed is theirs and is left as it is.
            data["fisher"] = "update"
            actions.append(f"tide: fisher install {FISHER_SOURCE} ({NOT_PINNED})")
        tide_name = installed_name(found, fishprobe.TIDE_PLUGIN)
        if found.tide is not None and tide_name is None:
            data["error"] = "Tide is installed without fisher, so witchy can neither check nor replace it; remove it"
        elif tide_name is None:
            data["tide"] = "install"
            actions.append(f"tide: fisher install {TIDE_SOURCE}")
        else:
            reason = (f"Tide is {found.tide or 'of an unknown version'}" if found.tide != fishprobe.TIDE_VERSION
                      else NOT_PINNED if mismatches(found, fishprobe.TIDE_PLUGIN, self._pinned(TIDE_SOURCE))
                      else None)
            if reason and tide_name == TIDE_SOURCE:
                data["tide"] = "update"
                actions.append(f"tide: fisher install {TIDE_SOURCE} ({reason})")
            elif reason:
                data["tide"], data["replace"] = "replace", tide_name
                actions.append(f"tide: fisher remove {tide_name}, then fisher install {TIDE_SOURCE} ({reason}); "
                               "the Tide variables keep their values")
        installs = data["fisher"] is not None or data["tide"] is not None
        if data["error"] is None and installs and not shutil.which("curl", path=ctx.env.get("PATH")):
            data["error"] = CURL_MISSING  # fisher downloads with curl; nothing is downloaded without it
        if data["error"] is not None:
            actions = [f"tide: cannot go ahead: {data['error']}"]
        # fish plans again after this plan ran when it installs anything (spec D19: fish asks fish itself).
        data["installs"] = installs and data["error"] is None
        return Plan(actions=actions, data=data)

    def apply(self, ctx: Any, plan: Plan) -> dict:
        data = plan.data
        if data["error"] is not None:
            ctx.say(f"tide: {data['error']}; nothing was changed.")
            raise ComponentFailed(data["error"])
        earlier = data["entry"]
        entry = {"installed_fisher": earlier.get("installed_fisher", False),
                 "installed_tide": earlier.get("installed_tide", False),
                 "previous_tide_plugin": earlier.get("previous_tide_plugin"),
                 "removed_plugins": list(earlier.get("removed_plugins", [])),
                 "disabled_files": list(earlier.get("disabled_files", [])),
                 "moved_prompt": earlier.get("moved_prompt")}
        start = dict(entry)
        try:
            if data["fisher"] == "install":
                self._install_fisher(ctx)
            elif data["fisher"] == "update":
                self._run(ctx, fisher_command("update fisher", "install", FISHER_SOURCE))
            if data["fisher"] is not None:
                self._verify(ctx, fishprobe.FISHER_PLUGIN, FISHER_SOURCE, "fisher")
                entry["installed_fisher"] = entry["installed_fisher"] or data["fisher"] == "install"
            if data["tide"] == "replace":
                # Recorded first: from here on the user's Tide may be gone, and uninstall must bring it back.
                entry["previous_tide_plugin"] = entry["previous_tide_plugin"] or data["replace"]
                self._run(ctx, swap_command("install Tide", data["replace"], TIDE_SOURCE))
            elif data["tide"] is not None:
                self._run(ctx, fisher_command("install Tide", "install", TIDE_SOURCE))
            if data["tide"] is not None:
                found = self._verify(ctx, fishprobe.TIDE_PLUGIN, TIDE_SOURCE, "Tide")
                entry["installed_tide"] = entry["installed_tide"] or data["tide"] == "install"
                reason = fishprobe.tide_ready(found)
                if reason:
                    raise ComponentFailed(f"Tide is installed but not ready: {reason}")
        except ComponentFailed as exc:
            ctx.say(f"tide: {exc}")
            if entry == start and not earlier:
                raise
            plan.outcome = f"failed: {exc}"  # what was installed so far stays recorded (ritual 3.3)
        return entry

    def _run(self, ctx: Any, command: Command) -> None:
        done = installlog.run(ctx, command)
        if done.returncode != 0:
            raise ComponentFailed(installlog.failure(ctx, command.label, done))

    def _install_fisher(self, ctx: Any) -> None:
        bootstrap = self._pins()["bootstrap"]
        cached = self._bootstrap_file(ctx)
        data = read(cached)
        if sha(data) != bootstrap["sha256"]:
            try:
                data = ctx.fetch(bootstrap["url"])
            except (OSError, ValueError, http.client.HTTPException) as exc:
                installlog.append(ctx, f"--- download {bootstrap['url']}: {exc}")
                raise ComponentFailed(f"could not download fisher ({exc})") from exc
            installlog.append(ctx, f"--- download {bootstrap['url']}: {len(data)} bytes, "
                                   f"sha256 {sha(data)}")
            if sha(data) != bootstrap["sha256"]:
                raise ComponentFailed("the downloaded fisher.fish does not match the pinned release")
            try:
                jsonio.write_atomic_bytes(cached, data)
            except OSError as exc:
                raise ComponentFailed(f"could not keep fisher.fish in {cached.parent} ({exc})") from exc
        self._run(ctx, Command((FISH, "-c", BOOTSTRAP_SCRIPT, "--", str(cached), FISHER_SOURCE), "install fisher",
                               "", timeout=FISHER_TIMEOUT))

    def _verify(self, ctx: Any, plugin: str, source: str, what: str) -> fishprobe.Probe:
        """After a fisher install: the plugin is there, at the pinned version, file by file (spec D21)."""
        found = fishprobe.probe(ctx)
        version = found.fisher if plugin == fishprobe.FISHER_PLUGIN else found.tide
        wanted = FISHER_VERSION if plugin == fishprobe.FISHER_PLUGIN else fishprobe.TIDE_VERSION
        name = installed_name(found, plugin)
        if name is None or version is None:
            raise ComponentFailed(f"{what} is still not installed (details: {installlog.shown(ctx)})")
        if version != wanted or mismatches(found, plugin, self._pinned(source)):
            self._run(ctx, fisher_command(f"remove {name}", "remove", name))
            raise ComponentFailed(f"{plugin} files do not match the pinned release")
        return found
```

The component is not registered yet (Task 8): `runner.install` gets it from the tests.

In `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md`, section 5.1, replace:

```
| fish missing | `skipped: fish not found` (install fish: `sudo apt install fish`). |
```

with:

```
| fish missing | `skipped: fish not found (sudo apt install fish)`. |
```

replace:

```
| Tide present, version ≠ 6.1.1 | `fisher install ilancosman/tide@v6.1.1`; the previous `fish_plugins` line for Tide is recorded. |
| Tide 6.1.1 present | Nothing. |
```

with:

```
| Tide present, version ≠ 6.1.1, or files that differ from the pins (Tide's development branch, `ilancosman/tide`, also prints 6.1.1) | `fisher remove <its name>`, then `fisher install ilancosman/tide@v6.1.1` in the same fish call, which keeps every universal `tide_*` variable (Tide's uninstall erases them and its install sets its defaults); its name is recorded as `previous_tide_plugin`. A Tide witchy installed (`ilancosman/tide@v6.1.1`) with a changed file is installed again instead. |
| Tide 6.1.1 present, every file as pinned | Nothing. |
| A `tide` function that fisher did not install | `failed: Tide is installed without fisher, so witchy can neither check nor replace it; remove it`. |
```

and replace:

```
- fisher needs `curl`. Missing `curl` → `failed: curl not found (sudo apt install curl)` before anything is downloaded.
```

with:

```
- fisher needs `curl`. Missing `curl` → `failed: curl not found (sudo apt install curl)` before anything is downloaded (only when something must be installed).
- A fisher the user installed (any name but `jorgebucaran/fisher@4.4.5`) is used as it is and never pinned; witchy's own fisher with a changed file is installed again. Every fisher call gets empty standard input: fisher reads more plugin names from a pipe.
```

- [ ] **Step 4: Run the tests and the whole suite**

Run: `/usr/bin/python3 -m unittest tests.test_components_tide`
Expected: `Ran 27 tests … OK` (the two `RealFishSwapTest` tests run real fish, about 0.1 s each).

Run: `python3 -c "import witchy.fishprobe" && python3 -c "import witchy.components.tide" && echo ok`
Expected: `ok`

Run the suite on both interpreters and `python3 -m witchy validate`.
Expected: `Ran 695 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/components/tide.py tests/fakes.py tests/test_components_tide.py docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md
git commit -m "feat: the tide component installs fisher 4.4.5 and Tide 6.1.1 and checks every file against the pins" -m "fisher is bootstrapped from its pinned fisher.fish; Tide is installed, updated, or put in place of another Tide while every tide_ variable keeps its value. A file that does not match the pins is removed again." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: tide takes over other prompt owners: a hand-written fish_prompt, prompt plugins, init and global lines

**Items:** spec 5.2 in the component: the four takeover rows, one printed line per takeover, the edge cases at component level (second run, a line turned back on, `function fish_prompt`, symlink, continued line, CRLF and bytes, witchy's and fisher's files left alone), the dry run. Plan Decisions 6 and 15. The spec's fisher names are corrected (`_2F_`, Plan F Decision 12).

**Files:**
- Modify: `witchy/components/tide.py` (imports; `aside`, `owners`; `plan`; `apply` split into `apply` and `_apply`; `_move_prompt`, `_disable_lines`)
- Modify: `witchy/components/base.py` (`tilde`, `__all__`)
- Modify: `witchy/installlog.py` (`shown` uses `tilde`)
- Modify: `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (5.1, 5.2, 9.1)
- Test: `tests/test_components_tide.py`

**Interfaces:**
- Consumes: `takeover.scan`, `Scan`, `Line` (Task 2); `fish.config_dir(ctx)`; `build.fish_files(python, witchy_dir)` (only its keys); `jsonio.backup`, `jsonio.write_atomic_bytes`.
- Produces:
  - `base.tilde(ctx, path) -> str`.
  - `tide.aside(path, stamp) -> Path` (a free `<name>.bak-witchy-<stamp>[-N]`).
  - `tide.owners(ctx, found) -> (hand_written_prompt | None, [plugin names that ship fish_prompt.fish], takeover.Scan)`; the scan skips every file fisher lists and every file witchy ships.
  - `plan.data` gains `prompt`, `plugins`, `lines`; `installs` becomes `reprobe` (also true for a prompt moved or a plugin removed); `plan.changes` holds the files with lines disabled; a blocker sets `data["error"]` to the blockers joined with `"; "`.
  - The entry's `moved_prompt = {"path", "backup", "installed_sha256"}`, `removed_plugins = [names]`, `disabled_files = [{"path", "backup", "installed_sha256"}]` (the first backup of a file stays its record).
  - Printed lines: `tide: moved ~/… aside, a fish_prompt that was not Tide's (backup: ~/…)`, `tide: removed the fisher plugin <name>, which shipped its own fish_prompt`, `tide: disabled <what> in ~/… line N (backup: ~/…)`.

**Decisions:**
1. **Order (plan Decision 6):** fisher, then the prompt file and plugins, then Tide and its checks, then the lines. A blocker or a missing `curl` returns a plan whose only action is `tide: cannot go ahead: <reason>`; `apply` then prints `tide: <reason>; nothing was changed.` and fails.
2. **witchy's own files are found from `build.fish_files`'s keys,** not a hard-coded list, so Plan H's `set -g tide_character_color` in `conf.d/witchy.fish` is never disabled, whatever else Plan H adds.
3. **A moved prompt is recorded once:** a later run that finds another hand-written `fish_prompt.fish` moves it too but keeps the first record (the one uninstall gives back).
4. **The lines are written directly** (`jsonio.backup` then `write_atomic_bytes`) rather than through `apply_changes`, so each disabled line prints exactly one line, as spec 5.2 asks; the runner still checks `plan.changes` against the disk before `apply` (another writer in between fails the component).
5. **The deep copy of the entry** (`copy.deepcopy`) lets `apply` tell "nothing changed" from "something changed", now that lists in it are appended to.

- [ ] **Step 1: Write the failing tests**

In `tests/test_components_tide.py`, add before `class PinsTest`:

```python
PURE = {"functions/fish_prompt.fish": b"function fish_prompt\n    echo pure\nend\n",
        "conf.d/pure.fish": b"set -g pure_symbol x\n"}
PINNED = {"jorgebucaran/fisher": FISHER, "ilancosman/tide@v6.1.1": TIDE_FILES}


class TakeoverTest(TideTestCase):
    def write(self, name, data):
        path = self.config / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def backups(self):
        return sorted(path.name for path in self.config.rglob("*.bak-witchy-*"))

    def test_a_hand_written_prompt_is_moved_aside_before_tide_goes_in(self):
        prompt = self.write("functions/fish_prompt.fish", b"function fish_prompt\n    echo mine\nend\n")
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        moved = prompt.with_name("fish_prompt.fish.bak-witchy-20261005-120000")
        self.assertEqual(moved.read_bytes(), b"function fish_prompt\n    echo mine\nend\n")
        self.assertEqual(prompt.read_bytes(), TIDE_FILES["functions/fish_prompt.fish"])
        self.assertEqual(self.entry()["moved_prompt"], {"path": str(prompt), "backup": str(moved),
                                                        "installed_sha256": sha(moved.read_bytes())})
        self.assertIn("tide: moved ~/.config/fish/functions/fish_prompt.fish aside, a fish_prompt that was not "
                      "Tide's (backup: ~/.config/fish/functions/fish_prompt.fish.bak-witchy-20261005-120000)",
                      self.out.getvalue())

    def test_another_prompt_plugin_is_removed_before_tide_goes_in(self):
        self.fisher({"jorgebucaran/fisher": FISHER, "pure-fish/pure": PURE})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("fisher", "remove", "pure-fish/pure"),
                                               ("fisher", "install", "ilancosman/tide@v6.1.1")])
        self.assertEqual(self.entry()["removed_plugins"], ["pure-fish/pure"])
        self.assertIn("tide: removed the fisher plugin pure-fish/pure, which shipped its own fish_prompt",
                      self.out.getvalue())

    def test_a_starship_line_is_disabled_with_a_backup(self):
        config = self.write("config.fish", b"if status is-interactive\n    starship init fish | source\nend\n")
        self.fisher(PINNED)
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(config.read_bytes(),
                         b"if status is-interactive\n# witchy-disabled:     starship init fish | source\nend\n")
        backup = config.with_name("config.fish.bak-witchy-20261005-120000")
        self.assertEqual(backup.read_bytes(), b"if status is-interactive\n    starship init fish | source\nend\n")
        self.assertEqual(self.entry()["disabled_files"], [{"path": str(config), "backup": str(backup),
                                                           "installed_sha256": sha(config.read_bytes())}])
        self.assertIn("tide: disabled starship init in ~/.config/fish/config.fish line 2 "
                      "(backup: ~/.config/fish/config.fish.bak-witchy-20261005-120000)", self.out.getvalue())

    def test_lines_are_disabled_only_once_tide_is_in_place(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher({"jorgebucaran/fisher": FISHER}, served={})
        self.assertEqual(self.install(), 2)
        self.assertEqual(config.read_bytes(), b"starship init fish | source\n")

    def test_a_second_run_changes_nothing(self):
        self.write("config.fish", b"starship init fish | source\nset -gx tide_time_color 5F8787\n")
        self.fisher(PINNED)
        self.install()
        first = self.entry()
        self.assertEqual(self.install(self.ctx(stamp="20261005-130000")), 0)
        self.assertEqual(self.entry(), first)
        self.assertEqual(self.backups(), ["config.fish.bak-witchy-20261005-120000"])
        self.assertNotIn("disabled", self.out.getvalue())

    def test_a_line_turned_back_on_is_disabled_again_and_the_first_backup_stays(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher(PINNED)
        self.install()
        first = self.entry()["disabled_files"][0]["backup"]
        config.write_bytes(b"starship init fish | source\n")
        self.assertEqual(self.install(self.ctx(stamp="20261005-130000")), 0)
        self.assertEqual(config.read_bytes(), b"# witchy-disabled: starship init fish | source\n")
        self.assertEqual(self.entry()["disabled_files"][0]["backup"], first)

    def test_a_fish_prompt_function_fails_and_changes_nothing(self):
        config = self.write("config.fish", b"starship init fish | source\nfunction fish_prompt\n    echo x\nend\n")
        self.fisher()
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "failed: config.fish defines fish_prompt at line 2; remove that function")
        self.assertEqual((self.fetched, self.fisher_calls()), ([], []))
        self.assertEqual(config.read_bytes(), b"starship init fish | source\nfunction fish_prompt\n    echo x\nend\n")

    def test_a_symlinked_config_is_never_edited(self):
        dotfiles = self.root / "dotfiles" / "config.fish"
        dotfiles.parent.mkdir()
        dotfiles.write_bytes(b"starship init fish | source\n")
        (self.config / "config.fish").symlink_to(dotfiles)
        self.fisher(PINNED)
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(),
                         f"failed: config.fish is a symlink to {dotfiles}; disable line 1 there yourself")
        self.assertEqual(dotfiles.read_bytes(), b"starship init fish | source\n")

    def test_a_continued_line_fails_naming_file_and_line(self):
        self.write("conf.d/mine.fish", b"set -g tide_left_prompt_items pwd \\\n    git\n")
        self.fisher(PINNED)
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "failed: conf.d/mine.fish line 1 is continued over several lines; "
                                        "disable it yourself")

    def test_crlf_and_bytes_that_are_not_utf8_are_kept(self):
        config = self.write("config.fish", b"echo \xff\r\nstarship init fish | source\r\n")
        self.fisher(PINNED)
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(config.read_bytes(), b"echo \xff\r\n# witchy-disabled: starship init fish | source\r\n")

    def test_witchys_own_and_fishers_files_are_left_alone(self):
        ours = self.write("conf.d/witchy.fish", b"set -g tide_character_color FFB86B\n")
        self.fisher({**PINNED, "pure-fish/pure": {"conf.d/pure.fish": b"set -g tide_x y\n"}})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(ours.read_bytes(), b"set -g tide_character_color FFB86B\n")
        self.assertEqual((self.config / "conf.d" / "pure.fish").read_bytes(), b"set -g tide_x y\n")
        self.assertEqual(self.backups(), [])

    def test_dry_run_shows_the_takeover_and_changes_nothing(self):
        prompt = self.write("functions/fish_prompt.fish", b"function fish_prompt\nend\n")
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher({"jorgebucaran/fisher": FISHER, "pure-fish/pure": {"conf.d/pure.fish": b"x\n"}})
        self.assertEqual(self.install(self.ctx(dry_run=True)), 0)
        output = self.out.getvalue()
        self.assertIn(f"tide: move {prompt} to fish_prompt.fish.bak-witchy-20261005-120000 (a fish_prompt that is "
                      "not Tide's)", output)
        self.assertIn("+# witchy-disabled: starship init fish | source", output)
        self.assertEqual(prompt.read_bytes(), b"function fish_prompt\nend\n")
        self.assertEqual(config.read_bytes(), b"starship init fish | source\n")
        self.assertEqual(self.fisher_calls(), [])

    def test_fish_plans_again_only_after_a_plan_that_changes_which_prompt_runs(self):
        def reprobe(fake):
            return tide.TideComponent(fake_pins()).plan(self.ctx(fake=fake), None).data["reprobe"]

        self.assertTrue(reprobe(FakeFisher(self.config, {"jorgebucaran/fisher": FISHER})))
        self.write("config.fish", b"starship init fish | source\n")
        self.assertFalse(reprobe(FakeFisher(self.config, PINNED)))
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_components_tide`
Expected: `FAILED (failures=9, errors=2)`. fisher refuses Tide's file where the hand-written prompt or pure's is (`AssertionError: 2 != 0 : tide: could not install Tide (exit 1): …/functions/fish_prompt.fish (details: ~/.cache/witchy/install.log)`), the blockers do not fail (`AssertionError: 0 != 2`), no line is disabled, and `KeyError: 'reprobe'`.

- [ ] **Step 3: Implement**

In `witchy/components/base.py`, replace:

```python
           "file_change", "file_record", "applied_records", "restore_copy", "restore_json", "file_lock"]
```

with:

```python
           "file_change", "file_record", "applied_records", "restore_copy", "restore_json", "file_lock", "tilde"]
```

and add before `def fix_command(`:

```python
def tilde(ctx: Any, path: Path | str) -> str:
    """``path`` with ~ for HOME, as messages about the user's own files show it."""
    try:
        return "~/" + Path(path).relative_to(ctx.home).as_posix()
    except ValueError:
        return str(path)
```

In `witchy/installlog.py`, replace:

```python
from .components.base import Command, ComponentFailed, run_command
```

with:

```python
from .components.base import Command, ComponentFailed, run_command, tilde
```

and replace the body of `shown`:

```python
    target = path(ctx)
    try:
        return "~/" + target.relative_to(ctx.home).as_posix()
    except ValueError:
        return str(target)
```

with:

```python
    return tilde(ctx, path(ctx))
```

In `witchy/components/tide.py`, replace the imports:

```python
import http.client
import shutil
from pathlib import Path
from typing import Any

from .. import content, fishprobe, installlog, jsonio
from .base import Command, ComponentFailed, Plan, read, sha
```

with:

```python
import copy
import http.client
import shutil
from pathlib import Path
from typing import Any

from .. import build, content, fishprobe, installlog, jsonio, takeover
from .base import Command, ComponentFailed, Plan, read, sha, tilde
from .fish import config_dir
```

Add after `mismatches`, before `class TideComponent`:

```python
def aside(path: Path, stamp: str) -> Path:
    """A free ``<name>.bak-witchy-<stamp>`` beside ``path``."""
    target = path.with_name(f"{path.name}.bak-witchy-{stamp}")
    counter = 1
    while target.exists() or target.is_symlink():
        target = path.with_name(f"{path.name}.bak-witchy-{stamp}-{counter}")
        counter += 1
    return target


def owners(ctx: Any, found: fishprobe.Probe) -> tuple[Path | None, list[str], takeover.Scan]:
    """Every other prompt owner (spec 5.2): a fish_prompt.fish no plugin installed, the other fisher plugins that
    ship one, and the lines of config.fish and conf.d that start one or set a global tide_ variable."""
    folder = config_dir(ctx)
    prompt = folder / "functions" / "fish_prompt.fish"
    listed = {Path(path) for files in found.plugins.values() for path in files}
    ours = {folder / name for name in build.fish_files("", Path())}  # witchy's own fish files
    hand_written = prompt if (prompt.is_file() or prompt.is_symlink()) and prompt not in listed else None
    plugins = [name for name, files in found.plugins.items()
               if name.lower().split("@", 1)[0] != fishprobe.TIDE_PLUGIN and str(prompt) in files]
    return hand_written, plugins, takeover.scan(folder, listed | ours)
```

Replace the whole `plan` method with:

```python
    def plan(self, ctx: Any, entry: dict | None) -> Plan:
        try:
            found = fishprobe.probe(ctx)
        except ComponentFailed as exc:
            if isinstance(exc.__cause__, FileNotFoundError):
                ctx.say(f"tide: {FISH_MISSING}")
                return Plan.skipped(FISH_MISSING)
            return Plan.skipped(str(exc))
        prompt, plugins, scan = owners(ctx, found)
        data: dict[str, Any] = {"entry": entry or {}, "error": None, "fisher": None, "tide": None, "replace": None,
                                "prompt": prompt, "plugins": plugins, "lines": scan.lines}
        actions = []
        if prompt is not None:
            actions.append(f"tide: move {prompt} to {aside(prompt, ctx.stamp).name} (a fish_prompt that is not Tide's)")
        actions += [f"tide: fisher remove {name} (it ships its own fish_prompt)" for name in plugins]
        fisher_name = installed_name(found, fishprobe.FISHER_PLUGIN)
        if found.fisher is None:
            data["fisher"] = "install"
            cached = self._bootstrap_file(ctx)
            bootstrap = self._pins()["bootstrap"]
            source = (f"use {cached}" if sha(read(cached)) == bootstrap["sha256"]
                      else f"download {bootstrap['url']} (sha256 {bootstrap['sha256'][:12]}…)")
            actions += [f"tide: {source}", f"tide: fisher install {FISHER_SOURCE}"]
        elif fisher_name == FISHER_SOURCE and mismatches(found, fishprobe.FISHER_PLUGIN, self._pinned(FISHER_SOURCE)):
            # witchy's own fisher; a fisher the user installed is theirs and is left as it is.
            data["fisher"] = "update"
            actions.append(f"tide: fisher install {FISHER_SOURCE} ({NOT_PINNED})")
        tide_name = installed_name(found, fishprobe.TIDE_PLUGIN)
        if found.tide is not None and tide_name is None:
            data["error"] = "Tide is installed without fisher, so witchy can neither check nor replace it; remove it"
        elif tide_name is None:
            data["tide"] = "install"
            actions.append(f"tide: fisher install {TIDE_SOURCE}")
        else:
            reason = (f"Tide is {found.tide or 'of an unknown version'}" if found.tide != fishprobe.TIDE_VERSION
                      else NOT_PINNED if mismatches(found, fishprobe.TIDE_PLUGIN, self._pinned(TIDE_SOURCE))
                      else None)
            if reason and tide_name == TIDE_SOURCE:
                data["tide"] = "update"
                actions.append(f"tide: fisher install {TIDE_SOURCE} ({reason})")
            elif reason:
                data["tide"], data["replace"] = "replace", tide_name
                actions.append(f"tide: fisher remove {tide_name}, then fisher install {TIDE_SOURCE} ({reason}); "
                               "the Tide variables keep their values")
        installs = data["fisher"] is not None or data["tide"] is not None
        if scan.blockers:
            data["error"] = "; ".join(scan.blockers)
        elif data["error"] is None and installs and not shutil.which("curl", path=ctx.env.get("PATH")):
            data["error"] = CURL_MISSING  # fisher downloads with curl; nothing is downloaded without it
        if data["error"] is not None:
            return Plan(actions=[f"tide: cannot go ahead: {data['error']}"], data=data)
        # fish plans again once this plan ran when it changes which prompt fish runs (spec D19: fish asks fish).
        data["reprobe"] = installs or prompt is not None or bool(plugins)
        return Plan(changes=scan.changes, actions=actions, data=data)
```

Replace the whole `apply` method (up to `def _run`) with:

```python
    def apply(self, ctx: Any, plan: Plan) -> dict:
        data = plan.data
        if data["error"] is not None:
            ctx.say(f"tide: {data['error']}; nothing was changed.")
            raise ComponentFailed(data["error"])
        earlier = data["entry"]
        entry = {"installed_fisher": earlier.get("installed_fisher", False),
                 "installed_tide": earlier.get("installed_tide", False),
                 "previous_tide_plugin": earlier.get("previous_tide_plugin"),
                 "removed_plugins": list(earlier.get("removed_plugins", [])),
                 "disabled_files": list(earlier.get("disabled_files", [])),
                 "moved_prompt": earlier.get("moved_prompt")}
        start = copy.deepcopy(entry)
        try:
            self._apply(ctx, plan, entry)
        except ComponentFailed as exc:
            ctx.say(f"tide: {exc}")
            if entry == start and not earlier:
                raise
            plan.outcome = f"failed: {exc}"  # what was installed so far stays recorded (ritual 3.3)
        return entry

    def _apply(self, ctx: Any, plan: Plan, entry: dict) -> None:
        data = plan.data
        if data["fisher"] == "install":
            self._install_fisher(ctx)
        elif data["fisher"] == "update":
            self._run(ctx, fisher_command("update fisher", "install", FISHER_SOURCE))
        if data["fisher"] is not None:
            self._verify(ctx, fishprobe.FISHER_PLUGIN, FISHER_SOURCE, "fisher")
            entry["installed_fisher"] = entry["installed_fisher"] or data["fisher"] == "install"
        # Before Tide goes in: fisher refuses to put a file where another one already is.
        if data["prompt"] is not None:
            moved = self._move_prompt(ctx, data["prompt"])
            entry["moved_prompt"] = entry["moved_prompt"] or moved
        for name in data["plugins"]:
            self._run(ctx, fisher_command(f"remove {name}", "remove", name))
            ctx.say(f"tide: removed the fisher plugin {name}, which shipped its own fish_prompt")
            if name not in entry["removed_plugins"]:
                entry["removed_plugins"].append(name)
        if data["tide"] == "replace":
            # Recorded first: from here on the user's Tide may be gone, and uninstall must bring it back.
            entry["previous_tide_plugin"] = entry["previous_tide_plugin"] or data["replace"]
            self._run(ctx, swap_command("install Tide", data["replace"], TIDE_SOURCE))
        elif data["tide"] is not None:
            self._run(ctx, fisher_command("install Tide", "install", TIDE_SOURCE))
        if data["tide"] is not None:
            found = self._verify(ctx, fishprobe.TIDE_PLUGIN, TIDE_SOURCE, "Tide")
            entry["installed_tide"] = entry["installed_tide"] or data["tide"] == "install"
            reason = fishprobe.tide_ready(found)
            if reason:
                raise ComponentFailed(f"Tide is installed but not ready: {reason}")
        # Last: while Tide is not in place, the user's own prompt line keeps working.
        self._disable_lines(ctx, plan, entry)

    def _move_prompt(self, ctx: Any, prompt: Path) -> dict:
        target = aside(prompt, ctx.stamp)
        data = read(prompt)
        try:
            prompt.rename(target)
        except OSError as exc:
            raise ComponentFailed(f"could not move {tilde(ctx, prompt)} aside ({exc.strerror or exc})") from exc
        ctx.say(f"tide: moved {tilde(ctx, prompt)} aside, a fish_prompt that was not Tide's "
                f"(backup: {tilde(ctx, target)})")
        return {"path": str(prompt), "backup": str(target), "installed_sha256": sha(data)}

    def _disable_lines(self, ctx: Any, plan: Plan, entry: dict) -> None:
        """Comment out each line of another prompt owner; a file's first backup stays its record (spec 5.2)."""
        records = {record["path"]: record for record in entry["disabled_files"]}
        for change in plan.changes:
            try:
                backup = jsonio.backup(change.path, ctx.stamp)
                jsonio.write_atomic_bytes(change.path, change.after)
            except OSError as exc:
                raise ComponentFailed(f"could not write {tilde(ctx, change.path)} ({exc.strerror or exc})") from exc
            for line in plan.data["lines"]:
                if line.path == change.path:
                    ctx.say(f"tide: disabled {line.what} in {tilde(ctx, line.path)} line {line.number} "
                            f"(backup: {tilde(ctx, backup)})")
            earlier = records.get(str(change.path))
            records[str(change.path)] = {"path": str(change.path),
                                         "backup": earlier["backup"] if earlier else str(backup),
                                         "installed_sha256": sha(change.after)}
        entry["disabled_files"] = list(records.values())
```

In the spec, section 5.1, replace:

```
`functions --details fish_prompt`, and the universal list `_fisher_ilancosman_2f_tide_files`.
```

with:

```
`functions --details fish_prompt`, and each fisher plugin with its file list (`_fisher_ilancosman_2F_tide_files`; installed from a tag, `_fisher_ilancosman_2F_tide_40_v6_2E_31_2E_31__files`).
```

In section 5.2, replace:

```
Runs in `plan` (detection) and `apply` (changes), before the bootstrap in the same `apply`, because fisher refuses to overwrite files it does not own.
```

with:

```
Runs in `plan` (detection) and `apply` (changes). In `apply`, a hand-written `fish_prompt.fish` and other prompt plugins go after fisher is installed and before Tide, because fisher refuses to put a file where another one already is. The lines in `config.fish` and `conf.d` are disabled last, once Tide is in place, so a failed Tide install leaves the user's own prompt line working. Any case below that fails (a `fish_prompt` function, a continued line, a symlink) stops the whole component before it changes anything. witchy's own `conf.d/witchy.fish` and every file fisher lists for a plugin are never scanned.
```

replace:

```
| A hand-written `functions/fish_prompt.fish` | The file exists and is not in `_fisher_ilancosman_2f_tide_files`. | Moved to `fish_prompt.fish.bak-witchy-<stamp>`. |
```

with:

```
| A hand-written `functions/fish_prompt.fish` | The file exists and no fisher plugin lists it. | Moved to `fish_prompt.fish.bak-witchy-<stamp>` (a symlink is moved as a link; its target is not touched). |
```

append ` A file's first backup stays its record.` to the takeover cell of the `starship init fish` row (after `prefixed with `# witchy-disabled: `.`), replace:

```
Every takeover prints one line, for example `tide: disabled starship init in ~/.config/fish/config.fish (backup: …)`.
```

with:

```
Every takeover prints one line, for example `tide: disabled starship init in ~/.config/fish/config.fish line 2 (backup: …)`.
```

and replace:

```
- A matching line that ends in `\` (continued) fails like a `function fish_prompt` block, naming file and line.
```

with:

```
- A matching line that ends in `\`, or follows a line that does (continued), fails like a `function fish_prompt` block, naming file and line: `failed: config.fish line N is continued over several lines; disable it yourself`.
```

In section 9.1, replace `(`functions --details fish_prompt` is in `_fisher_ilancosman_2f_tide_files`)` with `(`functions --details fish_prompt` is in Tide's fisher file list)`.

- [ ] **Step 4: Run the tests and the whole suite**

Run: `/usr/bin/python3 -m unittest tests.test_components_tide`
Expected: `Ran 40 tests … OK`

Run the suite on both interpreters and `python3 -m witchy validate`.
Expected: `Ran 708 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/components/tide.py witchy/components/base.py witchy/installlog.py tests/test_components_tide.py docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md
git commit -m "feat: tide takes over other prompt owners: a hand-written fish_prompt, prompt plugins, init and global lines" -m "The fish_prompt file and prompt plugins go aside before Tide is installed; the lines in config.fish and conf.d are disabled once Tide is in place. A fish_prompt function, a continued line or a symlinked file fails the component before it changes anything." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Uninstall gives back the Tide, prompt plugins, lines and fish_prompt the tide component replaced

**Items:** spec 10, steps 1–5, in a corrected order (plan Decisions 7 and 8); acceptance 3 (the `starship` line comes back) and 6 (a PC whose Tide witchy installed loses it again; a PC whose Tide witchy replaced gets it back, with its variables).

**Files:**
- Modify: `witchy/components/tide.py` (`Change` import; `restore`, `_enable_lines`, `_prompt_back`)
- Modify: `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (section 10)
- Test: `tests/test_components_tide.py` (`write` and `backups` move to `TideTestCase`; `UninstallTest`)

**Interfaces:**
- Consumes: the runner's restore contract (`Plan.commands` run first, then `Plan.changes`, then `warnings` are printed; a failing command keeps the component installed and prints `<name>: <message>; run uninstall again.`); `takeover.enable`, `takeover.PREFIX`; `swap_command`, `fisher_command`, `installed_name` (Task 4).
- Produces: `TideComponent.restore(ctx, entry) -> Plan`:
  - commands, in order: the swap back to `previous_tide_plugin` (label `put back <name> in place of Tide 6.1.1`) or `fisher remove` witchy's Tide (`remove Tide (<name>)`); `fisher install <plugin>` for each removed plugin not installed now (`put back <plugin>`); `fisher remove` witchy's fisher (`remove fisher (<name>)`). Each is planned only when fish says it is still needed.
  - changes: each disabled file with its prefixes removed (backed up first when it changed since install); the moved `fish_prompt.fish` written back and its `.bak-witchy-…` removed.
  - warnings: `tide: fish not found, so fisher, Tide and the prompt plugins stay as they are.`, `tide: ~/… is a symlink now and is not edited; remove '# witchy-disabled: ' from its lines yourself.`, `tide: ~/…bak-witchy-… is gone, so your fish_prompt cannot come back.`, `tide: ~/…/fish_prompt.fish is not witchy's to replace; your fish_prompt stays at ~/….`

**Decisions:**
1. **Commands come from what fish reports now,** not from the entry alone: a retry after a failed `put back` runs only that; a Tide the user removed is not removed again; a previous Tide already back is left.
2. **The moved prompt goes back as two file changes** (write the original path, remove the `.bak-witchy-` copy), which the runner applies after the commands, so Tide's `fish_prompt.fish` is already gone. It is planned only when the place is free or holds Tide's file that this uninstall removes; otherwise it stays aside with a warning.
3. **Without fish** the commands are skipped with one warning and the component is still removed from `state.json`: the lines and the prompt file come back anyway. A fish that does not answer (not missing) keeps the component for a retry, like Plan F's `fish` restore.
4. **The swap back keeps the variables** `fish` restored a moment earlier in the same uninstall (reverse order: `fish` runs first), so the user's prompt survives Tide's own uninstall and install handlers.

- [ ] **Step 1: Write the failing tests**

In `tests/test_components_tide.py`, move `write` and `backups` from `TakeoverTest` up into `TideTestCase` (after `log`), unchanged:

```python
    def write(self, name, data):
        path = self.config / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def backups(self):
        return sorted(path.name for path in self.config.rglob("*.bak-witchy-*"))
```

and add before `class PinsTest`:

```python
class UninstallTest(TideTestCase):
    def uninstall(self, stamp="20261005-130000", dry_run=False):
        return runner.uninstall(self.ctx(stamp=stamp, dry_run=dry_run), [tide.TideComponent(fake_pins())])

    def test_removes_the_tide_and_fisher_it_installed_in_that_order(self):
        self.fisher()
        self.install()
        self.fake.calls.clear()
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("fisher", "remove", "ilancosman/tide@v6.1.1"),
                                               ("fisher", "remove", "jorgebucaran/fisher@4.4.5")])
        self.assertEqual(self.fake.plugins, {})
        self.assertFalse((self.home / ".claude" / "witchy" / "state.json").exists())

    def test_puts_back_the_tide_that_was_there_and_leaves_the_users_fisher(self):
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide": OLD_TIDE},
                    served={**RELEASES, "ilancosman/tide": OLD_TIDE})
        self.install()
        self.fake.calls.clear()
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("swap", "ilancosman/tide@v6.1.1", "ilancosman/tide")])
        self.assertEqual(sorted(self.fake.plugins), ["ilancosman/tide", "jorgebucaran/fisher"])

    def test_puts_back_a_removed_prompt_plugin_after_tide_is_gone(self):
        self.fisher({"jorgebucaran/fisher": FISHER, "pure-fish/pure": PURE},
                    served={**RELEASES, "pure-fish/pure": PURE})
        self.install()
        self.fake.calls.clear()
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("fisher", "remove", "ilancosman/tide@v6.1.1"),
                                               ("fisher", "install", "pure-fish/pure")])
        self.assertEqual((self.config / "functions" / "fish_prompt.fish").read_bytes(),
                         PURE["functions/fish_prompt.fish"])

    def test_a_retry_after_a_failed_command_does_not_repeat_what_worked(self):
        self.fisher({"jorgebucaran/fisher": FISHER, "pure-fish/pure": PURE},
                    served={**RELEASES, "pure-fish/pure": PURE})
        self.install()
        del self.fake.served["pure-fish/pure"]  # offline now
        self.assertEqual(self.uninstall(), 2)
        self.assertIn("tide: could not put back pure-fish/pure (exit 1); run uninstall again.", self.out.getvalue())
        self.assertIn("tide", self.state()["components"])
        self.fake.served["pure-fish/pure"] = PURE
        self.fake.calls.clear()
        self.assertEqual(self.uninstall("20261005-140000"), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("fisher", "install", "pure-fish/pure")])

    def test_disabled_lines_come_back_byte_for_byte(self):
        original = b"echo \xff\r\nstarship init fish | source\r\nset -g tide_x y\r\n"
        config = self.write("config.fish", original)
        self.fisher(PINNED)
        self.install()
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(config.read_bytes(), original)
        self.assertEqual(self.backups(), ["config.fish.bak-witchy-20261005-120000"])

    def test_the_users_later_edits_stay_and_the_edited_file_is_kept_as_a_backup(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher(PINNED)
        self.install()
        config.write_bytes(config.read_bytes() + b"alias ll 'ls -l'\n")
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(config.read_bytes(), b"starship init fish | source\nalias ll 'ls -l'\n")
        self.assertEqual(self.backups(), ["config.fish.bak-witchy-20261005-120000",
                                          "config.fish.bak-witchy-20261005-130000"])

    def test_a_file_that_became_a_symlink_is_left_with_a_warning(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher(PINNED)
        self.install()
        dotfiles = self.root / "dotfiles.fish"
        dotfiles.write_bytes(config.read_bytes())
        config.unlink()
        config.symlink_to(dotfiles)
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(dotfiles.read_bytes(), b"# witchy-disabled: starship init fish | source\n")
        self.assertIn("tide: ~/.config/fish/config.fish is a symlink now and is not edited; remove "
                      "'# witchy-disabled: ' from its lines yourself.", self.out.getvalue())

    def test_a_moved_prompt_comes_back_once_tide_is_gone(self):
        prompt = self.write("functions/fish_prompt.fish", b"function fish_prompt\n    echo mine\nend\n")
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.install()
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(prompt.read_bytes(), b"function fish_prompt\n    echo mine\nend\n")
        self.assertEqual(self.backups(), [])

    def test_a_moved_prompt_whose_place_is_taken_stays_aside(self):
        prompt = self.write("functions/fish_prompt.fish", b"function fish_prompt\n    echo mine\nend\n")
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.install()
        self.fake.run(["fish", "-c", tide.FISHER_SCRIPT, "--", "remove", "ilancosman/tide@v6.1.1"])
        prompt.write_bytes(b"function fish_prompt\n    echo newer\nend\n")
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(prompt.read_bytes(), b"function fish_prompt\n    echo newer\nend\n")
        self.assertIn("tide: ~/.config/fish/functions/fish_prompt.fish is not witchy's to replace; your fish_prompt "
                      "stays at ~/.config/fish/functions/fish_prompt.fish.bak-witchy-20261005-120000.",
                      self.out.getvalue())

    def test_a_moved_prompt_whose_backup_is_gone_is_a_warning(self):
        prompt = self.write("functions/fish_prompt.fish", b"function fish_prompt\nend\n")
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.install()
        prompt.with_name("fish_prompt.fish.bak-witchy-20261005-120000").unlink()
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertFalse(prompt.exists())
        self.assertIn("so your fish_prompt cannot come back.", self.out.getvalue())

    def test_a_tide_the_user_removed_is_not_removed_again(self):
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.install()
        self.fake.run(["fish", "-c", tide.FISHER_SCRIPT, "--", "remove", "ilancosman/tide@v6.1.1"])
        self.fake.calls.clear()
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [])

    def test_without_fish_the_lines_still_come_back(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.install()
        self.fake.missing = True
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(config.read_bytes(), b"starship init fish | source\n")
        self.assertIn("tide: fish not found, so fisher, Tide and the prompt plugins stay as they are.",
                      self.out.getvalue())

    def test_dry_run_lists_every_step_and_changes_nothing(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher({"pure-fish/pure": PURE}, served={**RELEASES, "pure-fish/pure": PURE})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.fake.calls.clear()
        self.assertEqual(self.uninstall(dry_run=True), 0)
        self.assertIn("tide: remove Tide (ilancosman/tide@v6.1.1)\ntide: put back pure-fish/pure\n"
                      "tide: remove fisher (jorgebucaran/fisher@4.4.5)\n", self.out.getvalue())
        self.assertIn("-# witchy-disabled: starship init fish | source", self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [])
        self.assertEqual(config.read_bytes(), b"# witchy-disabled: starship init fish | source\n")
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_components_tide`
Expected: `FAILED (errors=13)`, each with `AttributeError: 'TideComponent' object has no attribute 'restore'`.

- [ ] **Step 3: Implement**

In `witchy/components/tide.py`, replace:

```python
from .base import Command, ComponentFailed, Plan, read, sha, tilde
```

with:

```python
from .base import Change, Command, ComponentFailed, Plan, read, sha, tilde
```

and add at the end of `class TideComponent`, after `_verify`:

```python
    def restore(self, ctx: Any, entry: dict) -> Plan:
        """Uninstall (spec 10): Tide goes or the earlier Tide comes back, then the removed prompt plugins, then
        fisher if witchy installed it; after those commands, the disabled lines and a moved fish_prompt come back."""
        warnings: list[str] = []
        commands: list[Command] = []
        changes = self._enable_lines(ctx, entry, warnings)
        found = None
        if entry["installed_fisher"] or entry["installed_tide"] or entry["previous_tide_plugin"] or \
                entry["removed_plugins"]:
            try:
                found = fishprobe.probe(ctx)
            except ComponentFailed as exc:
                if not isinstance(exc.__cause__, FileNotFoundError):
                    raise  # fish is there but did not answer: keep the component and retry later
                warnings.append("tide: fish not found, so fisher, Tide and the prompt plugins stay as they are.")
        removes_tide = False
        if found is not None:
            tide_name = installed_name(found, fishprobe.TIDE_PLUGIN)
            previous = entry["previous_tide_plugin"]
            if previous and (tide_name or "").lower() != previous.lower():
                commands.append(swap_command(f"put back {previous} in place of Tide {fishprobe.TIDE_VERSION}",
                                             tide_name or "", previous))
            elif not previous and entry["installed_tide"] and tide_name:
                commands.append(fisher_command(f"remove Tide ({tide_name})", "remove", tide_name))
                removes_tide = True
            for plugin in entry["removed_plugins"]:
                if installed_name(found, plugin.lower().split("@", 1)[0]) is None:
                    commands.append(fisher_command(f"put back {plugin}", "install", plugin))
            fisher_name = installed_name(found, fishprobe.FISHER_PLUGIN)
            if entry["installed_fisher"] and fisher_name:
                commands.append(fisher_command(f"remove fisher ({fisher_name})", "remove", fisher_name))
        changes += self._prompt_back(ctx, entry.get("moved_prompt"), found, removes_tide, warnings)
        return Plan(changes=changes, commands=commands, warnings=warnings)

    def _enable_lines(self, ctx: Any, entry: dict, warnings: list[str]) -> list[Change]:
        """Each disabled line back as it was; the user's other edits to the file stay."""
        changes = []
        for record in entry["disabled_files"]:
            path = Path(record["path"])
            if path.is_symlink():
                warnings.append(f"tide: {tilde(ctx, path)} is a symlink now and is not edited; remove "
                                f"'{takeover.PREFIX.decode()}' from its lines yourself.")
                continue
            current = read(path)
            after = None if current is None else takeover.enable(current)
            if after != current:
                changes.append(Change(path, current, after, backup=sha(current) != record["installed_sha256"]))
        return changes

    def _prompt_back(self, ctx: Any, moved: dict | None, found: fishprobe.Probe | None, removes_tide: bool,
                     warnings: list[str]) -> list[Change]:
        """The fish_prompt.fish witchy moved aside, back in its place once Tide's is gone."""
        if not moved:
            return []
        path, backup = Path(moved["path"]), Path(moved["backup"])
        data, current = read(backup), read(path)
        tides = found is not None and str(path) in (fishprobe.plugin_files(found, fishprobe.TIDE_PLUGIN) or [])
        if data is None:
            warnings.append(f"tide: {tilde(ctx, backup)} is gone, so your fish_prompt cannot come back.")
            return []
        if current is not None and not (tides and removes_tide):
            warnings.append(f"tide: {tilde(ctx, path)} is not witchy's to replace; your fish_prompt stays at "
                            f"{tilde(ctx, backup)}.")
            return []
        # Runs after the commands: by then Tide's file is gone.
        return [Change(path, current, data, backup=False), Change(backup, data, None, backup=False)]
```

In the spec, section 10, replace everything from `Reverse order: ` up to (not including) `On this PC (Tide and fisher were already there)` with:

```
Reverse order: `fish` (variables, files), then `tide`. `tide` asks fish which plugins are installed now, so a retry after a failed step only runs what is left, in this order:

1. If `previous_tide_plugin` is set: `fisher remove` witchy's Tide and `fisher install <that>`, keeping every universal `tide_*` variable as `fish` just restored it (Tide's uninstall erases them and its install sets its defaults). Else if `installed_tide`: `fisher remove` witchy's Tide.
2. `fisher install <plugin>` for each prompt plugin it removed (after Tide is gone: both ship `fish_prompt.fish`).
3. If `installed_fisher`: `fisher remove` witchy's fisher.
4. Each file it commented out gets its `# witchy-disabled: ` prefixes taken away, which gives back the original bytes and keeps any later edit of the user's. A file the user changed since is backed up first; one that became a symlink is left, with a warning (D22).
5. A hand-written `fish_prompt.fish` it moved aside goes back, once Tide's is gone. If something else holds that place, or the moved file is gone, a warning says so.

Without fish, steps 1–3 are skipped with a warning; 4 and 5 still run.
```

(followed by one blank line).

- [ ] **Step 4: Run the tests and the whole suite**

Run: `/usr/bin/python3 -m unittest tests.test_components_tide`
Expected: `Ran 53 tests … OK`

Run the suite on both interpreters and `python3 -m witchy validate`.
Expected: `Ran 721 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/components/tide.py tests/test_components_tide.py docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md
git commit -m "feat: uninstall gives back the Tide, prompt plugins, lines and fish_prompt the tide component replaced" -m "Commands follow what fish reports now, so a retry runs only what is left; disabled lines lose their prefix, which keeps the user's later edits." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: doctor checks fisher, Tide 6.1.1, the pins, Tide's fish_prompt and other prompt owners

**Items:** spec 9.1, the `tide` component's checks: fisher found, Tide 6.1.1, every file matches the pins, the active `fish_prompt` is Tide's, no other prompt owner is active (a disabled line turned back on is drift, spec 5.2), and the glyph test line (D14). Plan Decision 13.

**Files:**
- Modify: `witchy/components/tide.py` (imports; `SHOWN_MAX`, `GLYPH_TEST`; `check`, `_pin_checks`, `_owner_checks`)
- Modify: `witchy/components/base.py` (`Check` docstring)
- Modify: `witchy/runner.py` (`SYMBOLS` gains `info`; `_print_check` prints a fix only for `warn` and `fail`)
- Modify: `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (9.1)
- Test: `tests/test_components_tide.py` (`CheckTest`), `tests/test_runner.py` (`test_an_info_line_is_never_a_problem`)

**Interfaces:**
- Consumes: `owners`, `mismatches`, `installed_name` (Tasks 4–5); `fishprobe.tide_ready`; `base.backup_checks`, `fix_command`; `palette.GLYPHS` (Plan F).
- Produces:
  - `TideComponent.check(ctx, entry) -> list[Check]`, in this order: fisher (`✓ fisher 4.4.5 found` / `✗ fisher not found` / `⚠ fisher is <v>; witchy was tested with 4.4.5`), Tide (`✓ Tide 6.1.1 found` / `✗ Tide not found` / `✗ Tide is <v>, not 6.1.1`), the pins (`✓ every <plugin> file matches the pinned release` / `✗ <plugin> files do not match the pinned release: <first 5> (and N more)`; fisher only when it is witchy's), the prompt (`✓ the active fish_prompt is Tide's` / `✗ fish_prompt is not Tide's (…)`), the owners (`✗ ~/… is a fish_prompt that is not Tide's`, `✗ the fisher plugin <name> ships its own fish_prompt`, `✗ <what> in ~/… line N is active`, a blocker split into problem and hand fix, or `✓ no other prompt owner is active`), `· glyph test: …`, then backup warnings. Without fish: one `⚠ cannot check fisher and Tide: fish not found (sudo apt install fish)` (and the backup warnings).
  - `tide.GLYPH_TEST = "glyph test: 🧹 🔮 🪦 🌿 🧪 💀 🔥 🐈 🦉 ❯ — each should be one clear symbol"`.
  - `runner.SYMBOLS["info"] = "·"`; `Check(level="info")` never prints a fix and never changes doctor's exit code.

**Decisions:**
1. **The glyph test is built from `palette.GLYPHS`** (`cwd home unwritable branch ok fail duration jobs time caret`), so it shows what the prompt really uses.
2. **The prompt line only appears when Tide is there:** without Tide, or at another version, the Tide line already carries the ✗; `tide_ready`'s reason is shown only when it is about `fish_prompt`.
3. **A blocker's fix is the step to take by hand** (`remove that function`, `disable line N there yourself`): the message is the text before the last `"; "`, the fix the text after it. `doctor --fix` (Task 10) runs only `install --only` fixes.
4. **The user's fisher at another version is a ⚠, not a ✗** (plan Decision 5), and its files are not pin-checked.

- [ ] **Step 1: Write the failing tests**

In `tests/test_components_tide.py`, add before `class PinsTest`:

```python
class CheckTest(TideTestCase):
    def doctor(self):
        ctx = self.ctx(stamp="20261005-130000")
        code = runner.doctor(ctx, [tide.TideComponent(fake_pins())])
        return code, [line for line in self.out.getvalue().splitlines()]

    def test_a_healthy_install(self):
        self.fisher()
        self.install()
        code, lines = self.doctor()
        self.assertEqual(code, 0)
        self.assertEqual(lines, [
            "✓ tide              fisher 4.4.5 found",
            "✓ tide              Tide 6.1.1 found",
            "✓ tide              every jorgebucaran/fisher file matches the pinned release",
            "✓ tide              every ilancosman/tide file matches the pinned release",
            "✓ tide              the active fish_prompt is Tide's",
            "✓ tide              no other prompt owner is active",
            "· tide              glyph test: 🧹 🔮 🪦 🌿 🧪 💀 🔥 🐈 🦉 ❯ — each should be one clear symbol"])

    def test_fisher_or_tide_missing_fails_with_the_fix(self):
        self.fisher()
        self.install()
        self.fake.fisher("remove", ["ilancosman/tide@v6.1.1", "jorgebucaran/fisher@4.4.5"])
        code, lines = self.doctor()
        self.assertEqual(code, 1)
        self.assertEqual(lines[:4], ["✗ tide              fisher not found",
                                     "    fix: python3 -m witchy install --only tide",
                                     "✗ tide              Tide not found",
                                     "    fix: python3 -m witchy install --only tide"])

    def test_another_tide_version_fails(self):
        self.fisher(PINNED)
        self.install()
        (self.config / "functions" / "tide.fish").write_bytes(OLD_TIDE["functions/tide.fish"])
        code, lines = self.doctor()
        self.assertIn("✗ tide              Tide is 6.0.0, not 6.1.1", lines)
        self.assertIn("✗ tide              ilancosman/tide files do not match the pinned release: functions/tide.fish",
                      lines)

    def test_a_long_list_of_changed_files_is_cut(self):
        self.fisher(PINNED)
        self.install()
        for number in range(7):
            self.write(f"functions/tide/extra{number}.fish", b"x\n")
        code, lines = self.doctor()
        self.assertIn("✗ tide              ilancosman/tide files do not match the pinned release: "
                      "functions/tide/extra0.fish, functions/tide/extra1.fish, functions/tide/extra2.fish, "
                      "functions/tide/extra3.fish, functions/tide/extra4.fish (and 2 more)", lines)

    def test_a_fish_prompt_that_is_not_tides_fails(self):
        self.fisher(PINNED)
        self.install()
        (self.config / "functions" / "fish_prompt.fish").unlink()
        code, lines = self.doctor()
        self.assertIn("✗ tide              fish_prompt is not Tide's (no fish_prompt)", lines)

    def test_a_disabled_line_turned_back_on_is_drift(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher(PINNED)
        self.install()
        config.write_bytes(b"starship init fish | source\n")
        code, lines = self.doctor()
        self.assertEqual(code, 1)
        self.assertIn("✗ tide              starship init in ~/.config/fish/config.fish line 1 is active", lines)
        self.assertIn("    fix: python3 -m witchy install --only tide", lines)

    def test_a_fish_prompt_function_names_what_to_do_by_hand(self):
        self.fisher(PINNED)
        self.install()
        self.write("config.fish", b"set -g fish_greeting\nfunction fish_prompt\nend\n")
        code, lines = self.doctor()
        self.assertIn("✗ tide              config.fish defines fish_prompt at line 2", lines)
        self.assertIn("    fix: remove that function", lines)

    def test_a_fisher_the_user_installed_at_another_version_is_a_warning(self):
        older = {"functions/fisher.fish": b"function fisher\n    echo 'fisher, version 4.3.0'\nend\n"}
        self.fisher({"jorgebucaran/fisher": older, "ilancosman/tide@v6.1.1": TIDE_FILES})
        self.install()
        code, lines = self.doctor()
        self.assertEqual(code, 0)
        self.assertIn("⚠ tide              fisher is 4.3.0; witchy was tested with 4.4.5", lines)
        self.assertNotIn("jorgebucaran/fisher file", "\n".join(lines))

    def test_without_fish_it_cannot_check(self):
        self.fisher()
        self.install()
        self.fake.missing = True
        code, lines = self.doctor()
        self.assertEqual((code, lines), (0, ["⚠ tide              cannot check fisher and Tide: fish not found "
                                             "(sudo apt install fish)"]))

    def test_a_missing_backup_is_a_warning(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher(PINNED)
        self.install()
        config.with_name("config.fish.bak-witchy-20261005-120000").unlink()
        code, lines = self.doctor()
        self.assertIn(f"⚠ tide              backup {config}.bak-witchy-20261005-120000 is missing; uninstall cannot "
                      "give back the original bytes", lines)
```

In `tests/test_runner.py`, in `DoctorTest`, add before `test_raising_check_is_reported_not_crashed`:

```python
    def test_an_info_line_is_never_a_problem(self):
        self.write_state({"a": {}})
        info = CheckingFake("a", self.log, checks=[Check("info", "a", "glyph test: 🧹", "never shown")])
        self.assertEqual(runner.doctor(self.ctx(), [info]), 0)
        self.assertEqual(self.out.getvalue(), "· a                 glyph test: 🧹\n")
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_components_tide tests.test_runner`
Expected: `FAILED (failures=10, errors=1)`: the tide checks are missing (doctor exits 0 with no lines; `AssertionError: 1 != 0` and missing lines) and `KeyError: 'info'` in the runner.

- [ ] **Step 3: Implement**

In `witchy/components/tide.py`, replace:

```python
from .. import build, content, fishprobe, installlog, jsonio, takeover
from .base import Change, Command, ComponentFailed, Plan, read, sha, tilde
```

with:

```python
from .. import build, content, fishprobe, installlog, jsonio, palette, takeover
from .base import Change, Check, Command, ComponentFailed, Plan, backup_checks, fix_command, read, sha, tilde
```

add after `NOT_PINNED = "its files do not match the pinned release"`:

```python
SHOWN_MAX = 5  # files listed by doctor
GLYPH_TEST = ("glyph test: " + " ".join(palette.GLYPHS[name] for name in (
    "cwd", "home", "unwritable", "branch", "ok", "fail", "duration", "jobs", "time", "caret"))
    + " — each should be one clear symbol")
```

and add at the end of `class TideComponent`, after `_prompt_back`:

```python
    def check(self, ctx: Any, entry: dict) -> list[Check]:
        """doctor (spec 9.1): fisher, Tide 6.1.1, the pins, Tide's fish_prompt, no other owner, a glyph test."""
        fix = fix_command(self.name)
        backups = [record.get("backup") for record in entry["disabled_files"]]
        backups += [entry["moved_prompt"]["backup"]] if entry.get("moved_prompt") else []
        try:
            found = fishprobe.probe(ctx)
        except ComponentFailed as exc:
            reason = FISH_MISSING if isinstance(exc.__cause__, FileNotFoundError) else str(exc)
            return [Check("warn", self.name, f"cannot check fisher and Tide: {reason}")] + \
                backup_checks(self.name, backups)
        checks = []
        if found.fisher is None:
            checks.append(Check("fail", self.name, "fisher not found", fix))
        elif found.fisher != FISHER_VERSION:
            checks.append(Check("warn", self.name, f"fisher is {found.fisher or 'of an unknown version'}; witchy "
                                                   f"was tested with {FISHER_VERSION}"))
        else:
            checks.append(Check("ok", self.name, f"fisher {FISHER_VERSION} found"))
        if found.tide is None:
            checks.append(Check("fail", self.name, "Tide not found", fix))
        elif found.tide != fishprobe.TIDE_VERSION:
            checks.append(Check("fail", self.name, f"Tide is {found.tide or 'of an unknown version'}, "
                                                   f"not {fishprobe.TIDE_VERSION}", fix))
        else:
            checks.append(Check("ok", self.name, f"Tide {fishprobe.TIDE_VERSION} found"))
        checks += self._pin_checks(found, fix)
        reason = fishprobe.tide_ready(found)
        if found.tide is not None and reason and reason.startswith("fish_prompt"):
            checks.append(Check("fail", self.name, reason, fix))
        elif not reason:
            checks.append(Check("ok", self.name, "the active fish_prompt is Tide's"))
        checks += self._owner_checks(ctx, found, fix)
        checks.append(Check("info", self.name, GLYPH_TEST))
        return checks + backup_checks(self.name, backups)

    def _pin_checks(self, found: fishprobe.Probe, fix: str) -> list[Check]:
        """Every file of Tide, and of fisher when witchy installed it, against content/pins.json (D21)."""
        checks = []
        plugins = [(fishprobe.TIDE_PLUGIN, TIDE_SOURCE)]
        if installed_name(found, fishprobe.FISHER_PLUGIN) == FISHER_SOURCE:
            plugins.insert(0, (fishprobe.FISHER_PLUGIN, FISHER_SOURCE))
        for plugin, source in plugins:
            if installed_name(found, plugin) is None:
                continue
            wrong = mismatches(found, plugin, self._pinned(source))
            if wrong:
                more = f" (and {len(wrong) - SHOWN_MAX} more)" if len(wrong) > SHOWN_MAX else ""
                checks.append(Check("fail", self.name, f"{plugin} files do not match the pinned release: "
                                                       + ", ".join(wrong[:SHOWN_MAX]) + more, fix))
            else:
                checks.append(Check("ok", self.name, f"every {plugin} file matches the pinned release"))
        return checks

    def _owner_checks(self, ctx: Any, found: fishprobe.Probe, fix: str) -> list[Check]:
        """Another prompt owner of spec 5.2 that is active, a disabled line turned back on included (drift)."""
        prompt, plugins, scan = owners(ctx, found)
        checks = []
        if prompt is not None:
            checks.append(Check("fail", self.name, f"{tilde(ctx, prompt)} is a fish_prompt that is not Tide's", fix))
        checks += [Check("fail", self.name, f"the fisher plugin {name} ships its own fish_prompt", fix)
                   for name in plugins]
        checks += [Check("fail", self.name, f"{line.what} in {tilde(ctx, line.path)} line {line.number} is active",
                         fix) for line in scan.lines]
        for blocker in scan.blockers:
            # Not something install can do: the fix is the instruction itself, which doctor --fix never runs.
            problem, _, instruction = blocker.rpartition("; ")
            checks.append(Check("fail", self.name, problem, instruction))
        return checks or [Check("ok", self.name, "no other prompt owner is active")]
```

In `witchy/components/base.py`, replace the `Check` docstring:

```python
    """One doctor line. ``level`` is "ok", "warn" or "fail"; ``fix`` is a command to run."""
```

with:

```python
    """One doctor line. ``level`` is "ok", "warn", "fail" or "info" (a line to read, never a problem); ``fix`` is a
    command to run, or what to do by hand when no witchy command can do it."""
```

In `witchy/runner.py`, replace:

```python
SYMBOLS = {"ok": "✓", "warn": "⚠", "fail": "✗"}
```

with:

```python
SYMBOLS = {"ok": "✓", "warn": "⚠", "fail": "✗", "info": "·"}
```

and in `_print_check` replace:

```python
    if check.fix and check.level != "ok":
```

with:

```python
    if check.fix and check.level in ("warn", "fail"):
```

In the spec, section 9.1, replace the five `tide` bullets:

```
- ✓/✗ fisher found; Tide is version 6.1.1.
- ✓/✗ every fisher and Tide file matches `content/pins.json` (D21).
- ✓/✗ the active `fish_prompt` is Tide's (`functions --details fish_prompt` is in Tide's fisher file list).
- ✓/✗ no other prompt owner from 5.2 is active.
- An info line: `glyph test: 🧹 🔮 🪦 🌿 🧪 💀 🔥 🐈 🦉 ❯ — each should be one clear symbol`.
```

with:

```
- ✓/✗ fisher found (⚠ when a fisher the user installed is not 4.4.5: witchy leaves the user's fisher alone); Tide is version 6.1.1.
- ✓/✗ every Tide file, and every fisher file when witchy installed fisher, matches `content/pins.json` (D21); ✗ lists the first 5 files, then a count.
- ✓/✗ the active `fish_prompt` is Tide's (`functions --details fish_prompt` is in Tide's fisher file list).
- ✓/✗ no other prompt owner from 5.2 is active; a disabled line turned back on is ✗ (drift). The ✗ of a `function fish_prompt` block, a continued line or a symlink gives the step to take by hand as its fix.
- An info line (`·`, never a problem): `glyph test: 🧹 🔮 🪦 🌿 🧪 💀 🔥 🐈 🦉 ❯ — each should be one clear symbol`.
```

- [ ] **Step 4: Run the tests and the whole suite**

Run: `/usr/bin/python3 -m unittest tests.test_components_tide tests.test_runner`
Expected: `Ran 113 tests … OK`

Run the suite on both interpreters and `python3 -m witchy validate`.
Expected: `Ran 732 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/components/tide.py witchy/components/base.py witchy/runner.py tests/test_components_tide.py tests/test_runner.py docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md
git commit -m "feat: doctor checks fisher, Tide 6.1.1, the pins, Tide's fish_prompt and other prompt owners" -m "A new info level prints the glyph test line without making it a problem. A fix that no witchy command can do is the step to take by hand." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: tide joins install before fish; fish plans again after tide; a banner names what did not install

**Items:** spec 5 (component order `claude`, `font`, `windows-terminal`, `tide`, `fish`), 9.2 (the banner after the summary line), D19 with the runner fix for a fresh PC (plan Decision 1), and the CLI accepting `--only tide` (the fix Plan F prints). Acceptance 1 and 4 at unit level.

**Files:**
- Modify: `witchy/components/__init__.py` (register `TideComponent` before `FishComponent`)
- Modify: `witchy/components/base.py` (`Plan.replan`)
- Modify: `witchy/components/fish.py` (`tide_goes_first`; `FishComponent.plan` defers)
- Modify: `witchy/runner.py` (`BANNER`, `BANNER_FIX`; re-plan in `_install`; the banner)
- Modify: `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (9.2, last paragraph)
- Test: `tests/test_runner.py` (`Replanning`, `ReplanTest`, `BannerTest`), `tests/test_components_tide.py` (`FreshPcTest`), `tests/test_components_fish.py` (component names), `tests/test_cli.py` (`--only tide`)

**Interfaces:**
- Consumes: `tide` plan `data["reprobe"]` (Task 5); `ctx.planned`, `ctx.results`, `ctx.entries` (the runner fills them); `fish.NOT_READY`, `desired` (Plan F).
- Produces:
  - `Plan.replan: bool = False`.
  - `runner._install`: before applying a plan with `replan`, calls `component.plan(ctx, ctx.entries.get(name))` again and uses that plan (and stores it in `ctx.planned`). A dry run never re-plans.
  - `runner.BANNER = "✗✗✗ witchy is NOT fully installed ✗✗✗"`, `runner.BANNER_FIX = "Fix the lines above, then run: python3 -m witchy install"`; printed right after the summary line, with one `  <name>: <result>` line per component that ended `skipped: …` or `failed: …`.
  - `fish.tide_goes_first(ctx) -> bool`; `FishComponent.plan` returns its file plan with `replan=True` and the single action `fish: set 159 prompt variables once tide has installed Tide (fish is asked again then)` when it is true.
  - `components.NAMES == ("claude", "font", "windows-terminal", "tide", "fish")`.

**Decisions:**
1. **The re-plan is generic** (`Plan.replan`), but only `fish` uses it, and only when `tide`'s plan will change which prompt fish runs (`reprobe`). A `tide` plan with nothing to do, or one that will fail, lets `fish` plan at once as before: two probes in a run where Tide is ready (`test_a_ready_tide_lets_fish_plan_once`).
2. **`"tide" not in ctx.results`** is how `fish` knows the re-plan is the second one; it reads only that `tide` has run, never how it ended (D19).
3. **The banner lists every skipped or failed component**, including `font` and `windows-terminal` on a PC without Windows; the spec asks for it whenever any selected component ends that way. It goes right after the summary line, before the headline and the notes.
4. **The files `fish` plans first are planned again too:** the second plan reads the disk afresh, and the runner re-checks its changes under the plan's lock, as for any plan.

- [ ] **Step 1: Write the failing tests**

In `tests/test_runner.py`, add before `class UninstallRunnerTest`:

```python
class Replanning(Fake):
    """A component whose first plan asks to be planned again right before it applies."""

    def plan(self, ctx, entry):
        self.log.append(("plan", self.name))
        if not any(step == ("apply", "a") for step in self.log):
            return Plan(replan=True, actions=["b: decided later"])
        return Plan(notes=["b planned after a"])


class ReplanTest(RunnerTestCase):
    def test_a_plan_can_ask_to_be_made_again_after_earlier_components_applied(self):
        self.assertEqual(runner.install(self.ctx(), [Fake("a", self.log), Replanning("b", self.log)]), 0)
        self.assertEqual(self.log, [("plan", "a"), ("plan", "b"), ("apply", "a"), ("plan", "b"), ("apply", "b")])
        self.assertIn("b planned after a", self.out.getvalue())

    def test_a_dry_run_shows_the_first_plan(self):
        self.assertEqual(runner.install(self.ctx(dry_run=True), [Fake("a", self.log), Replanning("b", self.log)]), 0)
        self.assertEqual(self.log, [("plan", "a"), ("plan", "b")])
        self.assertIn("b: decided later", self.out.getvalue())


class BannerTest(RunnerTestCase):
    def test_a_skipped_or_failed_component_gets_the_banner_after_the_summary(self):
        code = runner.install(self.ctx(), [Fake("a", self.log), Fake("b", self.log, skip="Tide not found"),
                                           Fake("c", self.log, fail=True)])
        self.assertEqual(code, 2)
        lines = self.out.getvalue().splitlines()
        start = lines.index("1/3 components installed · skipped: b (Tide not found) · failed: c (boom)")
        self.assertEqual(lines[start + 1:start + 5], ["✗✗✗ witchy is NOT fully installed ✗✗✗",
                                                      "  b: skipped: Tide not found",
                                                      "  c: failed: boom",
                                                      "Fix the lines above, then run: python3 -m witchy install"])

    def test_a_clean_run_has_no_banner(self):
        self.assertEqual(runner.install(self.ctx(), [Fake("a", self.log)]), 0)
        self.assertNotIn("NOT fully installed", self.out.getvalue())
```

In `tests/test_components_tide.py`, add before `class PinsTest`:

```python
class FreshPcTest(TideTestCase):
    """tide and fish in one run (acceptance criterion 1), through the runner as `install` runs them."""

    def run_install(self, only=("tide", "fish"), dry_run=False, fetch=None):
        ctx = self.ctx(dry_run=dry_run, fetch=fetch)
        ctx.only, ctx.python = only, "/usr/bin/python3"
        return runner.install(ctx, [tide.TideComponent(fake_pins()), fish.FishComponent()])

    def test_a_pc_with_fish_only_ends_with_the_witchy_prompt(self):
        self.fisher()
        self.assertEqual(self.run_install(), 0, self.out.getvalue())
        self.assertEqual(self.state()["last_install"]["results"], {"tide": "ok", "fish": "ok"})
        self.assertEqual(self.variables["tide_pwd_icon"]["value"], ["🧹"])
        self.assertEqual(len(self.state()["components"]["fish"]["variables"]), len(fish.desired("midnight")))

    def test_the_dry_run_says_fish_waits_for_tide(self):
        self.fisher()
        self.assertEqual(self.run_install(dry_run=True), 0)
        self.assertIn(f"fish: set {len(fish.desired('midnight'))} prompt variables once tide has installed Tide "
                      "(fish is asked again then)", self.out.getvalue())

    def test_when_tide_fails_fish_finds_tide_not_ready_by_itself(self):
        def offline(url):
            raise OSError("network is unreachable")

        self.fisher()
        self.assertEqual(self.run_install(fetch=offline), 2)
        self.assertEqual(self.state()["last_install"]["results"], {
            "tide": "failed: could not download fisher (network is unreachable)",
            "fish": "skipped: Tide not ready (run: python3 -m witchy install --only tide)"})
        self.assertIn("✗✗✗ witchy is NOT fully installed ✗✗✗\n"
                      "  tide: failed: could not download fisher (network is unreachable)\n"
                      "  fish: skipped: Tide not ready (run: python3 -m witchy install --only tide)\n",
                      self.out.getvalue())
        self.assertEqual(self.variables, {})

    def test_only_fish_never_waits_for_tide(self):
        self.fisher()
        self.assertEqual(self.run_install(only=("fish",)), 2)
        self.assertEqual(self.state()["last_install"]["results"]["fish"],
                         "skipped: Tide not ready (run: python3 -m witchy install --only tide)")
        self.assertEqual(self.fisher_calls(), [])

    def test_a_ready_tide_lets_fish_plan_once(self):
        self.fisher(PINNED)
        self.assertEqual(self.run_install(), 0, self.out.getvalue())
        probes = [args for args in self.fake.calls if args[2:3] == [fishprobe.PROBE_SCRIPT]]
        self.assertEqual(len(probes), 2)  # one for tide, one for fish
```

In `tests/test_components_fish.py`, replace:

```python
        self.assertEqual(components.NAMES, ("claude", "font", "windows-terminal", "fish"))
```

with:

```python
        self.assertEqual(components.NAMES, ("claude", "font", "windows-terminal", "tide", "fish"))
```

In `tests/test_cli.py`, add before `test_doctor_and_mood_run_on_an_empty_home`:

```python
    def test_only_accepts_tide_as_the_fixes_name_it(self):
        seen = []
        with mock.patch("witchy.runner.install", side_effect=lambda ctx: seen.append(ctx.only) or 0):
            self.assertEqual(main(["install", "--only", "tide", "--only", "fish"]), 0)
        self.assertEqual(seen, [("tide", "fish")])
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_cli tests.test_components_fish tests.test_components_tide tests.test_runner`
Expected: `FAILED (failures=5, errors=3)`. `test_a_pc_with_fish_only_ends_with_the_witchy_prompt` shows the problem Plan F raised: `AssertionError: 2 != 0 : fish: Tide not found; prompt not recoloured. Run: python3 -m witchy install --only tide`. The others: `TypeError: Plan.__init__() got an unexpected keyword argument 'replan'`, `argument --only: invalid choice: 'tide'`, the missing banner, the dry run without the `fish: set 159 …` line, and the old component names.

- [ ] **Step 3: Implement**

In `witchy/components/__init__.py`, replace:

```python
from .font import FontComponent
from .windows_terminal import WindowsTerminalComponent


def all_components() -> list:
    return [ClaudeComponent(), FontComponent(), WindowsTerminalComponent(), FishComponent()]
```

with:

```python
from .font import FontComponent
from .tide import TideComponent
from .windows_terminal import WindowsTerminalComponent


def all_components() -> list:
    return [ClaudeComponent(), FontComponent(), WindowsTerminalComponent(), TideComponent(), FishComponent()]
```

In `witchy/components/base.py`, in the `Plan` docstring replace:

```python
    in part (for example "skipped: Tide not found").
    """
```

with:

```python
    in part (for example "skipped: Tide not found"). ``replan`` makes the runner plan the component again right
    before applying it, because an earlier component of the same run changes what it finds.
    """
```

and after `    outcome: str | None = None` add:

```python
    replan: bool = False
```

In `witchy/components/fish.py`, add before `def config_dir(`:

```python
def tide_goes_first(ctx: Any) -> bool:
    """This run's tide plan changes which prompt fish runs and has not applied yet.

    fish then plans again once it has, and still asks fish itself whether Tide is ready, never how tide ended
    (spec D19). With ``--only fish`` there is no tide plan, so fish asks right away.
    """
    plan = ctx.planned.get("tide")
    return (plan is not None and plan.skip is None and bool(plan.data.get("reprobe"))
            and "tide" not in ctx.results)
```

and in `FishComponent.plan`, replace:

```python
        wanted = desired(variant)
        try:
            # Tide's readiness comes from fish itself, never from how the tide component ended (spec D19).
```

with:

```python
        wanted = desired(variant)
        if tide_goes_first(ctx):
            plan.replan = True
            plan.actions = [f"fish: set {len(wanted)} prompt variables once tide has installed Tide "
                            "(fish is asked again then)"]
            return plan
        try:
            # Tide's readiness comes from fish itself, never from how the tide component ended (spec D19).
```

In `witchy/runner.py`, after `NOTHING_INSTALLED = "Nothing was installed."` add:

```python
BANNER = "✗✗✗ witchy is NOT fully installed ✗✗✗"
BANNER_FIX = "Fix the lines above, then run: python3 -m witchy install"
```

in `_install`, replace:

```python
    for component, plan in plans:
        if plan.skip is not None:
            results[component.name] = f"skipped: {plan.skip}"
```

with:

```python
    for index, (component, plan) in enumerate(plans):
        if plan.replan:
            # An earlier component of this run changed what this one finds (fish after tide installed Tide).
            plan = component.plan(ctx, ctx.entries.get(component.name))
            plans[index] = (component, plan)
            ctx.planned[component.name] = plan
        if plan.skip is not None:
            results[component.name] = f"skipped: {plan.skip}"
```

and replace:

```python
    ok = all(result == "ok" for result in results.values())
    ctx.say(_summary(results))
```

with:

```python
    ok = all(result == "ok" for result in results.values())
    ctx.say(_summary(results))
    problems = {name: result for name, result in results.items() if result.startswith(("skipped: ", "failed: "))}
    if problems:  # spec 9.2: a summary line alone is too easy to miss
        ctx.say(BANNER)
        for name, result in problems.items():
            ctx.say(f"  {name}: {result}")
        ctx.say(BANNER_FIX)
```

In the spec, section 9.2, append to the paragraph that ends `This works the same with `--only fish` and with `doctor --fix`.`:

```
 The runner plans every component before it applies any, so when the same run's `tide` plan installs or replaces Tide, or moves a `fish_prompt` aside, `fish` asks to be planned again (`Plan.replan`) and the runner plans it once more right before applying it; that second plan asks fish again. A dry run shows `fish: set 159 prompt variables once tide has installed Tide (fish is asked again then)`. Without a `tide` plan in the run (`--only fish`), fish asks right away.
```

- [ ] **Step 4: Run the tests and the whole suite**

Run: `/usr/bin/python3 -m unittest tests.test_cli tests.test_components_fish tests.test_components_tide tests.test_runner`
Expected: `Ran 198 tests … OK`

Run: `python3 -c "import witchy.fishprobe" && python3 -c "import witchy.takeover" && python3 -c "import witchy.components" && echo ok`
Expected: `ok` (`tide.py` is now imported with the package; `test_each_new_module_can_be_imported_first` checks the same).

Run the suite on both interpreters and `python3 -m witchy validate`.
Expected: `Ran 742 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/components/__init__.py witchy/components/base.py witchy/components/fish.py witchy/runner.py tests/test_runner.py tests/test_components_tide.py tests/test_components_fish.py tests/test_cli.py docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md
git commit -m "feat: tide joins install before fish; fish plans again after tide; a banner names what did not install" -m "The runner plans a component again right before it applies when its first plan asks to (Plan.replan): fish does when this run's tide plan installs or replaces Tide, so a PC with only fish ends with the witchy prompt. fish still asks fish itself whether Tide is ready." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: tide and fish against real fish with a stand-in fisher and Tide; a weekly job runs the real download

**Items:** spec 12, "Integration": real fish with a local fake fisher and a fake Tide 6.1.1 tree served from a temporary folder, and one opt-in test (`WITCHY_NETWORK_TESTS=1`) that bootstraps the real fisher and Tide into a throwaway HOME and checks the pins; D24 and spec 12 "CI": `.github/workflows/network.yml` runs it weekly and on manual dispatch. Acceptance 1, 3 and 6 with real fish; acceptance 7 (the weekly job).

**Files:**
- Modify: `tests/fakes.py` (`FAKE_FISHER_FISH`, `FAKE_TIDE_INIT`, `fake_tide_tree`, `serve_plugins`)
- Create: `tests/test_tide_integration.py`, `tests/test_tide_network.py`
- Create: `.github/workflows/network.yml`

**Interfaces:**
- Consumes: `TideComponent(pins)`, `FishComponent`, `runner.install/doctor/uninstall`, `fake_pins` (Task 4), `scripts/pins.py` `pins()` and `download()` (Task 1).
- Produces:
  - `fakes.FAKE_FISHER_FISH`: a `fisher` function for real fish. `fisher --version` prints `fisher, version 4.4.5`; `fisher install <plugin>` copies `$WITCHY_FAKE_PLUGINS/<string escape --style=var plugin>/{functions,themes,conf.d,completions}/*` into fish's folder, refuses a file that is already there (unless it updates the plugin), records `_fisher_plugins` and `_fisher_<escaped>_files` (with `~` for HOME), sources the files and emits `<name>_install`; `fisher remove` emits `<name>_uninstall`, deletes the files, erases the functions and the records.
  - `fakes.FAKE_TIDE_INIT` (Tide's install handler sets `tide_pwd_icon` and `tide_character_icon`; its uninstall handler erases every universal `_?tide` variable, as Tide's does), `fake_tide_tree(version="6.1.1") -> dict[str, bytes]`, `serve_plugins(folder, releases, env)`.
  - `.github/workflows/network.yml`: Mondays 06:17 UTC and `workflow_dispatch`; Python 3.12, fish from apt; `WITCHY_NETWORK_TESTS=1 python -m unittest tests.test_tide_network -v`.

**Decisions:**
1. **A stand-in fisher, not the real one, for the offline suite:** the real `fisher.fish` is not in the repository and CI pushes must not download. The stand-in keeps exactly what witchy reads (the records, `~` in paths, the conflict refusal, the events), so the real probe, the pin check, the swap script and Tide's own variable handling all run in real fish. The real fisher runs in the network test and in Task 13.
2. **The plugin folders are named by fish** (`string escape --style=var`), in the test's temporary HOME, so the names match what the stand-in computes.
3. **The real-fish tests pin behaviour Tasks 4–8 built,** so they pass on the stage before; only `WorkflowTest` fails there. They run in about a second.
4. **The network test lives in the normal suite and skips itself** unless `WITCHY_NETWORK_TESTS=1`; it compares `scripts/pins.py`'s output for the real releases with `content/pins.json`, then installs, checks and uninstalls with the real fisher in a temporary HOME and `XDG_CONFIG_HOME`. In the prototype it passed in about 3 s.

- [ ] **Step 1: Write the stand-ins and the tests**

Add at the end of `tests/fakes.py`:

```python
# A stand-in for fisher 4.4.5 for real fish: it installs a plugin from $WITCHY_FAKE_PLUGINS/<escaped name> instead
# of downloading it, and otherwise keeps fisher's records the way fisher does (_fisher_plugins, and each plugin's
# files in _fisher_<escaped name>_files with ~ for HOME), refuses a file that is already there, sources what it
# installs and emits the conf.d install and uninstall events.
FAKE_FISHER_FISH = r"""function fisher --argument-names cmd
    switch "$cmd"
        case -v --version
            echo "fisher, version 4.4.5"
        case install remove
            set -l code 1
            for plugin in (string lower -- $argv[2..])
                set -l var _fisher_(string escape --style=var -- $plugin)_files
                set -l targets (string replace -- \~ ~ $$var)
                if test $cmd = remove
                    if not contains -- $plugin $_fisher_plugins
                        echo "fisher: Plugin not installed: \"$plugin\"" >&2
                        continue
                    end
                    for name in (string replace --filter --regex -- '.+/conf\.d/([^/]+)\.fish$' '$1' $targets)
                        emit {$name}_uninstall
                    end
                    command rm -rf $targets
                    functions --erase (string replace --filter --regex -- '.+/functions/([^/]+)\.fish$' '$1' $targets)
                    set -e -U _fisher_plugins[(contains --index -- $plugin $_fisher_plugins)]
                    set -e -U $var
                    set code 0
                    continue
                end
                set -l source $WITCHY_FAKE_PLUGINS/(string escape --style=var -- $plugin)
                if not test -d $source
                    echo "fisher: Invalid plugin name or host unavailable: \"$plugin\"" >&2
                    continue
                end
                set -l files $source/{functions,themes,conf.d,completions}/*
                set targets (string replace -- $source $__fish_config_dir $files)
                if not contains -- $plugin $_fisher_plugins
                    set -l conflicts
                    for target in $targets
                        test -e $target; and set -a conflicts $target
                    end
                    if set -q conflicts[1]
                        echo "fisher: Cannot install \"$plugin\": please remove or move conflicting files first:" >&2
                        printf '        %s\n' $conflicts >&2
                        continue
                    end
                end
                command mkdir -p $__fish_config_dir/{functions,themes,conf.d,completions}
                for file in $files
                    command cp -RLf $file (string replace -- $source $__fish_config_dir $file)
                end
                set -U $var (string replace -- ~ \~ $targets)
                contains -- $plugin $_fisher_plugins; or set -U -a _fisher_plugins $plugin
                for file in (string match --regex -- '.+/[^/]+\.fish$' $targets)
                    source $file
                    if set -l name (string replace --regex -- '.+conf\.d/([^/]+)\.fish$' '$1' $file)
                        emit {$name}_install
                    end
                end
                set code 0
            end
            return $code
    end
end
"""
# A stand-in for a Tide release: the version, a prompt, a nested folder (as functions/tide/ is), and Tide's own
# install and uninstall handlers, which set two of its variables and erase every universal tide_ variable.
FAKE_TIDE_INIT = """\
function _tide_init_install --on-event _tide_init_install
    set -U tide_pwd_icon lean
    set -U tide_character_icon '❯'
end
function _tide_init_uninstall --on-event _tide_init_uninstall
    set -e -U (set -U --names | string match --entire -r '^_?tide')
end
"""


def fake_tide_tree(version="6.1.1"):
    return {"functions/tide.fish": f"function tide\n    echo 'tide, version {version}'\nend\n".encode(),
            "functions/fish_prompt.fish": b"function fish_prompt\n    echo 'tide> '\nend\n",
            "functions/_tide_remove_unusable_items.fish": b"function _tide_remove_unusable_items\nend\n",
            "functions/tide/configure/icons.fish": b"tide_pwd_icon x\n",
            "conf.d/_tide_init.fish": FAKE_TIDE_INIT.encode()}


def serve_plugins(folder, releases, env):
    """Write each release (``owner/repo@ref`` -> files) where FAKE_FISHER_FISH looks for it, under ``folder``.

    ``env`` is the temporary HOME's environment: fish names the folders.
    """
    names = subprocess.run([shutil.which("fish"), "-c", "string escape --style=var -- $argv", "--", *releases],
                           capture_output=True, text=True, check=True, timeout=20, env=env).stdout.split()
    for escaped, files in zip(names, releases.values()):
        for relative, data in files.items():
            path = Path(folder) / escaped / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
```

Create `tests/test_tide_integration.py`:

```python
"""The tide and fish components with real fish, a stand-in fisher and a stand-in Tide served from a folder."""
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.fakes import FAKE_FISHER_FISH, fake_pins, fake_tide_tree, serve_plugins
from witchy import runner
from witchy.components import fish, tide
from witchy.context import Context

FISH = shutil.which("fish")
TOOL_DIRS = list(dict.fromkeys([str(Path(FISH).parent) if FISH else "/usr/bin", "/usr/bin", "/bin"]))
FISHER_TREE = {"functions/fisher.fish": FAKE_FISHER_FISH.encode()}
RELEASES = {"jorgebucaran/fisher@4.4.5": FISHER_TREE, "ilancosman/tide@v6.1.1": fake_tide_tree()}


@unittest.skipUnless(FISH, "fish is not installed")
class RealFishTideTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.config = self.root / "config" / "fish"
        self.config.mkdir(parents=True)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        (bin_dir / "curl").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")  # fisher's stand-in never calls it
        (bin_dir / "curl").chmod(0o755)
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config.parent),
                    "PATH": ":".join([str(bin_dir), *TOOL_DIRS]), "WITCHY_FAKE_PLUGINS": str(self.root / "served")}
        serve_plugins(self.root / "served", {**RELEASES, "ilancosman/tide": fake_tide_tree("6.0.0")}, self.env)

    def fish(self, script):
        done = subprocess.run([FISH, "-c", script], capture_output=True, text=True, env=self.env, timeout=20)
        self.assertEqual(done.stderr, "")
        return done.stdout

    def components(self):
        return [tide.TideComponent(fake_pins(RELEASES, bootstrap=FAKE_FISHER_FISH.encode())), fish.FishComponent()]

    def ctx(self, stamp):
        self.out = io.StringIO()
        return Context(home=self.home, env=self.env, out=self.out, python=sys.executable, stamp=stamp,
                       dist=self.root / "dist", lock_path=self.root / "witchy.lock", only=("tide", "fish"),
                       fetch=lambda url: FAKE_FISHER_FISH.encode())

    def test_a_pc_with_fish_only_gets_fisher_tide_and_the_witchy_prompt_and_gives_them_back(self):
        self.assertEqual(runner.install(self.ctx("20261005-120000"), self.components()), 0, self.out.getvalue())
        self.assertEqual(self.fish("tide --version; functions --details fish_prompt; printf '%s\\n' $tide_pwd_icon"),
                         f"tide, version 6.1.1\n{self.config}/functions/fish_prompt.fish\n🧹\n")
        self.assertEqual(self.fish("printf '%s\\n' $_fisher_plugins"),
                         "jorgebucaran/fisher@4.4.5\nilancosman/tide@v6.1.1\n")
        ctx = self.ctx("20261005-130000")
        self.assertEqual(runner.doctor(ctx, self.components()), 0, self.out.getvalue())
        self.assertNotIn("✗", self.out.getvalue())
        self.assertEqual(runner.uninstall(self.ctx("20261005-140000"), self.components()), 0, self.out.getvalue())
        self.assertEqual(self.fish("functions -q fisher tide; or echo gone; set -U --names | string match '*tide*'"),
                         "gone\n")
        self.assertEqual(sorted(path.name for path in (self.config / "functions").iterdir()), [])

    def test_a_starship_line_is_disabled_and_given_back(self):
        original = b"if type -q starship\r\n    starship init fish | source\r\nend\r\n"
        (self.config / "config.fish").write_bytes(original)
        self.assertEqual(runner.install(self.ctx("20261005-120000"), self.components()), 0, self.out.getvalue())
        self.assertEqual((self.config / "config.fish").read_bytes(),
                         b"if type -q starship\r\n# witchy-disabled:     starship init fish | source\r\nend\r\n")
        self.assertIn("tide: disabled starship init in", self.out.getvalue())
        self.assertEqual(runner.uninstall(self.ctx("20261005-130000"), self.components()), 0, self.out.getvalue())
        self.assertEqual((self.config / "config.fish").read_bytes(), original)

    def test_another_tide_is_replaced_and_comes_back_with_the_users_values(self):
        self.fish("source $WITCHY_FAKE_PLUGINS/jorgebucaran_2F_fisher_40_34_2E_34_2E_35_/functions/fisher.fish; "
                  "fisher install jorgebucaran/fisher@4.4.5 ilancosman/tide >/dev/null; "
                  "set -U tide_pwd_icon mine; set -Ux tide_time_color 5F8787")
        before = self.fish("set -U | string match 'tide_*'; set -U -x | string match 'tide_*'")
        self.assertEqual(runner.install(self.ctx("20261005-120000"), self.components()), 0, self.out.getvalue())
        self.assertEqual(self.fish("printf '%s\\n' $_fisher_plugins $tide_pwd_icon"),
                         "jorgebucaran/fisher@4.4.5\nilancosman/tide@v6.1.1\n🧹\n")
        self.assertEqual(runner.uninstall(self.ctx("20261005-130000"), self.components()), 0, self.out.getvalue())
        self.assertEqual(self.fish("printf '%s\\n' $_fisher_plugins; tide --version"),
                         "jorgebucaran/fisher@4.4.5\nilancosman/tide\ntide, version 6.0.0\n")
        self.assertEqual(self.fish("set -U | string match 'tide_*'; set -U -x | string match 'tide_*'"), before)


if __name__ == "__main__":
    unittest.main()
```

Create `tests/test_tide_network.py`:

```python
"""The real download path (spec 12, D24): opt in with WITCHY_NETWORK_TESTS=1. CI runs it weekly (network.yml)."""
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from witchy import content, runner
from witchy.components import tide
from witchy.context import Context

FISH = shutil.which("fish")
ROOT = Path(__file__).resolve().parent.parent
NETWORK = os.environ.get("WITCHY_NETWORK_TESTS") == "1"


@unittest.skipUnless(NETWORK, "set WITCHY_NETWORK_TESTS=1 to download fisher and Tide")
class RealReleasesTest(unittest.TestCase):
    def test_the_pins_match_the_real_releases(self):
        spec = importlib.util.spec_from_file_location("pins", ROOT / "scripts" / "pins.py")
        pins = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pins)
        self.assertEqual(pins.pins(pins.download), content.load_pins())

    @unittest.skipUnless(FISH and shutil.which("curl"), "fish and curl are needed")
    def test_bootstraps_the_real_fisher_and_tide_into_a_throwaway_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            env = {"HOME": str(home), "XDG_CONFIG_HOME": str(Path(tmp) / "config"), "PATH": os.environ["PATH"]}
            out = io.StringIO()

            def ctx(stamp):
                return Context(home=home, env=env, out=out, python=sys.executable, stamp=stamp,
                               dist=Path(tmp) / "dist", lock_path=Path(tmp) / "witchy.lock", only=("tide",))

            self.assertEqual(runner.install(ctx("20261005-120000"), [tide.TideComponent()]), 0, out.getvalue())
            done = subprocess.run([FISH, "-c", "fisher --version; tide --version; printf '%s\\n' $_fisher_plugins"],
                                  capture_output=True, text=True, env=env, timeout=30)
            self.assertEqual(done.stdout, "fisher, version 4.4.5\ntide, version 6.1.1\n"
                                          "jorgebucaran/fisher@4.4.5\nilancosman/tide@v6.1.1\n")
            self.assertEqual(runner.doctor(ctx("20261005-130000"), [tide.TideComponent()]), 0, out.getvalue())
            self.assertIn("every ilancosman/tide file matches the pinned release", out.getvalue())
            self.assertEqual(runner.uninstall(ctx("20261005-140000"), [tide.TideComponent()]), 0, out.getvalue())
            done = subprocess.run([FISH, "-c", "functions -q fisher tide; or echo gone"], capture_output=True,
                                  text=True, env=env, timeout=30)
            self.assertEqual(done.stdout, "gone\n")


class WorkflowTest(unittest.TestCase):
    def test_ci_runs_this_file_weekly_and_on_demand(self):
        text = (ROOT / ".github" / "workflows" / "network.yml").read_text(encoding="utf-8")
        for line in ("  schedule:", '    - cron: "17 6 * * 1"  # Mondays', "  workflow_dispatch:",
                     '          WITCHY_NETWORK_TESTS: "1"', "        run: python -m unittest tests.test_tide_network -v"):
            self.assertIn(line + "\n", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them**

Run: `/usr/bin/python3 -m unittest tests.test_tide_integration tests.test_tide_network`
Expected: `FAILED (errors=1, skipped=2)`: the three real-fish tests pass, the two network tests are skipped, and `WorkflowTest` fails with `FileNotFoundError: … .github/workflows/network.yml`.

- [ ] **Step 3: Add the workflow**

Create `.github/workflows/network.yml`:

```yaml
name: network

# The real download path: fisher's bootstrap file and the fisher and Tide releases from GitHub, checked against
# content/pins.json, installed into a throwaway HOME (spec 12, D24). Pushes run only the offline suite (tests.yml).
on:
  schedule:
    - cron: "17 6 * * 1"  # Mondays
  workflow_dispatch:

jobs:
  network:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install fish
        run: sudo apt-get update && sudo apt-get install -y fish
      - name: Bootstrap the real fisher and Tide
        env:
          WITCHY_NETWORK_TESTS: "1"
        run: python -m unittest tests.test_tide_network -v
```

- [ ] **Step 4: Run the tests, the network test, and the whole suite**

Run: `/usr/bin/python3 -m unittest tests.test_tide_integration tests.test_tide_network`
Expected: `Ran 6 tests … OK (skipped=2)`

Run (downloads fisher and Tide into a temporary HOME; allowed by the Global Constraints):
`WITCHY_NETWORK_TESTS=1 /usr/bin/python3 -m unittest tests.test_tide_network -v`
Expected:
```
test_bootstraps_the_real_fisher_and_tide_into_a_throwaway_home (…) ... ok
test_the_pins_match_the_real_releases (…) ... ok
test_ci_runs_this_file_weekly_and_on_demand (…) ... ok
Ran 3 tests … OK
```

Run the suite on both interpreters and `python3 -m witchy validate`.
Expected: `Ran 748 tests … OK (skipped=2)` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/fakes.py tests/test_tide_integration.py tests/test_tide_network.py .github/workflows/network.yml
git commit -m "test: tide and fish against real fish with a stand-in fisher and Tide; a weekly job runs the real download" -m "test_tide_integration installs, checks and uninstalls with real fish and plugins served from a folder. test_tide_network (opt in with WITCHY_NETWORK_TESTS=1) checks the pins against the real releases and bootstraps them into a throwaway HOME; network.yml runs it weekly." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: doctor --fix re-installs what doctor marks ✗ when a witchy command fixes it, then checks again

**Items:** spec 15.4 (D18): run doctor; collect the components with a ✗ whose fix is `python3 -m witchy install --only <component>`; run `install --only` those, in component order; run doctor again; never run a fix that is not a witchy command; exit 0 when the second doctor has no ✗, else 1. Acceptance 11 at unit level (Task 13 runs it for real).

**Files:**
- Modify: `witchy/runner.py` (`doctor(ctx, components=None, fix=False)`; the checks move into `_doctor`)
- Modify: `witchy/__main__.py` (`doctor --fix`)
- Test: `tests/test_runner.py` (`Drifting`, `DoctorFixTest`), `tests/test_cli.py` (`test_doctor_fix_reaches_the_runner`), `tests/test_components_tide.py` (`test_doctor_fix_after_tide_configure_ends_clean`)

**Interfaces:**
- Consumes: `base.fix_command`, `runner.install`, `runner._components`; the checks of every component (a ✗ on `fish` may carry `--only tide`, Plan F Decision 14).
- Produces:
  - `runner.doctor(ctx, components=None, fix=False) -> int`; `runner._doctor(ctx, components) -> list[Check] | None` (prints every line; `None` when `state.json` is damaged).
  - With `fix`: prints `doctor --fix: python3 -m witchy install --only a --only b`, runs `install` with `ctx.only` set to those names, prints `doctor --fix: checking again`, and checks again. With nothing a witchy command fixes: prints `doctor --fix: no witchy command fixes these; do the fixes above by hand.` and exits 1. With no ✗: behaves like `doctor`.
  - CLI: `python3 -m witchy doctor --fix`.

**Decisions:**
1. **A fix is picked by exact text,** `fix == fix_command(name)` for a component in the run; a ✗ on one component may name another (`fish`'s global shadow names `tide`), and the install then runs that one. ⚠ lines (`not installed`, `last install …`) are never fixed: spec 15.4 asks for ✗ only.
2. **The install's own exit code is not the result;** the second doctor is. The install prints its usual summary and banner in between.
3. **A damaged `state.json` stays a plain doctor failure** (exit 1, no install).

- [ ] **Step 1: Write the failing tests**

In `tests/test_runner.py`, add before `class MoodTest`:

```python
class Drifting(Fake):
    """A component whose check fails with ``fix`` until it is applied again; ``heals`` False keeps it failing."""

    def __init__(self, name, log, fix=None, heals=True):
        super().__init__(name, log)
        self.fix, self.heals, self.applied = fix, heals, False

    def apply(self, ctx, plan):
        self.applied = self.heals
        return super().apply(ctx, plan)

    def check(self, ctx, entry):
        if self.applied:
            return [Check("ok", self.name, "fine")]
        return [Check("fail", self.name, "drifted", self.fix or f"python3 -m witchy install --only {self.name}")]


class DoctorFixTest(RunnerTestCase):
    def test_installs_only_what_a_witchy_command_fixes_then_checks_again(self):
        self.write_state({"a": {}, "b": {}, "c": {}})
        a, b, c = Fake("a", self.log), Drifting("b", self.log), Drifting("c", self.log)
        self.assertEqual(runner.doctor(self.ctx(), [a, b, c], fix=True), 0, self.out.getvalue())
        self.assertEqual(self.log, [("plan", "b"), ("plan", "c"), ("apply", "b"), ("apply", "c")])
        output = self.out.getvalue()
        self.assertIn("doctor --fix: python3 -m witchy install --only b --only c\n", output)
        self.assertIn("doctor --fix: checking again\n✓ b                 fine\n✓ c                 fine\n", output)

    def test_a_fix_another_component_carries_installs_that_component_in_order(self):
        self.write_state({"tide": {}, "fish": {}})
        tide, fish = Drifting("tide", self.log), Drifting("fish", self.log, fix="python3 -m witchy install --only tide")
        runner.doctor(self.ctx(), [tide, fish], fix=True)
        self.assertEqual(self.log, [("plan", "tide"), ("apply", "tide")])

    def test_a_fix_by_hand_is_printed_and_never_run(self):
        self.write_state({"a": {}})
        by_hand = Drifting("a", self.log, fix="remove that function")
        self.assertEqual(runner.doctor(self.ctx(), [by_hand], fix=True), 1)
        self.assertEqual(self.log, [])
        self.assertIn("    fix: remove that function\ndoctor --fix: no witchy command fixes these; do the fixes "
                      "above by hand.\n", self.out.getvalue())

    def test_still_broken_after_the_install_exits_1(self):
        self.write_state({"a": {}})
        self.assertEqual(runner.doctor(self.ctx(), [Drifting("a", self.log, heals=False)], fix=True), 1)
        self.assertEqual(self.log, [("plan", "a"), ("apply", "a")])

    def test_nothing_failing_installs_nothing(self):
        self.write_state({"a": {}})
        fine = CheckingFake("a", self.log, checks=[Check("ok", "a", "fine")])
        self.assertEqual(runner.doctor(self.ctx(), [fine], fix=True), 0)
        self.assertEqual(self.log, [])
        self.assertNotIn("doctor --fix", self.out.getvalue())
```

In `tests/test_cli.py`, add before `test_doctor_and_mood_run_on_an_empty_home`:

```python
    def test_doctor_fix_reaches_the_runner(self):
        seen = []
        with mock.patch("witchy.runner.doctor", side_effect=lambda ctx, fix: seen.append(fix) or 0):
            self.assertEqual(main(["doctor", "--fix"]), 0)
            self.assertEqual(main(["doctor"]), 0)
        self.assertEqual(seen, [True, False])
```

In `tests/test_components_tide.py`, in `FreshPcTest`, add before `test_a_ready_tide_lets_fish_plan_once`:

```python
    def test_doctor_fix_after_tide_configure_ends_clean(self):
        self.fisher()
        self.run_install()
        self.variables["tide_pwd_icon"] = {"value": ["x"], "exported": False}  # what tide configure does
        ctx = self.ctx(stamp="20261005-130000")
        ctx.python = "/usr/bin/python3"
        self.assertEqual(runner.doctor(ctx, [tide.TideComponent(fake_pins()), fish.FishComponent()], fix=True), 0,
                         self.out.getvalue())
        self.assertIn("doctor --fix: python3 -m witchy install --only fish\n", self.out.getvalue())
        self.assertEqual(self.variables["tide_pwd_icon"]["value"], ["🧹"])
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_cli tests.test_components_tide tests.test_runner`
Expected: `FAILED (errors=7)`: six with `TypeError: doctor() got an unexpected keyword argument 'fix'`, and the CLI test with `python3 -m witchy: error: unrecognized arguments: --fix`.

- [ ] **Step 3: Implement**

In `witchy/runner.py`, replace the whole `doctor` function (up to `def mood(`) with `doctor` and `_doctor`; `_doctor`'s body is the old `doctor`'s, returning `None` instead of `1` for a damaged `state.json` and `checks` instead of the exit code at the end:

```python
def doctor(ctx: Any, components: Sequence[Component] | None = None, fix: bool = False) -> int:
    """Check every component; with ``fix``, re-install the ones a ✗ names in its fix, then check again (D18)."""
    checks = _doctor(ctx, components)
    failed = checks is None or any(check.level == "fail" for check in checks)
    if not fix or not failed or checks is None:
        return 1 if failed else 0
    # Only fixes that are witchy commands run; the others (sudo apt, editing config.fish) stay printed above.
    fixable = [component.name for component in _components(components)
               if any(check.level == "fail" and check.fix == fix_command(component.name) for check in checks)]
    if not fixable:
        ctx.say("doctor --fix: no witchy command fixes these; do the fixes above by hand.")
        return 1
    ctx.say("doctor --fix: python3 -m witchy install " + " ".join(f"--only {name}" for name in fixable))
    ctx.only = tuple(fixable)
    install(ctx, components)
    ctx.say("doctor --fix: checking again")
    checks = _doctor(ctx, components)
    return 1 if checks is None or any(check.level == "fail" for check in checks) else 0


def _doctor(ctx: Any, components: Sequence[Component] | None) -> list[Check] | None:
    """Print every check; None when state.json cannot be read."""
    try:
        state = statefile.load(ctx.state_path)
    except Abort as exc:
        _print_check(ctx, Check("fail", "state", " ".join(str(exc).split())))
        return None
    entries = (state or {}).get("components", {})
    ctx.variant = ctx.variant or (state or {}).get("variant")  # fish compares the prompt with this variant's
    checks: list[Check] = []
    for component in _components(components):
        entry = entries.get(component.name)
        if entry is None:
            checks.append(Check("warn", component.name, "not installed", fix_command(component.name)))
            continue
        try:
            checks.extend(component.check(ctx, entry))
        except Exception as exc:  # a broken check is reported as a failure line, never a traceback
            checks.append(Check("fail", component.name, f"check crashed: {exc!r}"))
    last = (state or {}).get("last_install") or {}
    for name, result in last.get("results", {}).items():
        if result != "ok":
            checks.append(Check("warn", name, f"last install ({last.get('at')}): {result}", fix_command(name)))
    for check in checks:
        _print_check(ctx, check)
    return checks
```

In `witchy/__main__.py`, replace:

```python
    commands.add_parser("doctor", help="check every installed piece and say how to fix it")
```

with:

```python
    doctor_parser = commands.add_parser("doctor", help="check every installed piece and say how to fix it")
    doctor_parser.add_argument("--fix", action="store_true",
                               help="re-install what doctor marks ✗ when a witchy command fixes it, then check again")
```

and replace:

```python
        return runner.doctor(ctx)
```

with:

```python
        return runner.doctor(ctx, fix=args.fix)
```

- [ ] **Step 4: Run the tests and the whole suite**

Run: `/usr/bin/python3 -m unittest tests.test_cli tests.test_components_tide tests.test_runner`
Expected: `Ran 138 tests … OK`

Run the suite on both interpreters and `python3 -m witchy validate`.
Expected: `Ran 755 tests … OK (skipped=2)` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/runner.py witchy/__main__.py tests/test_runner.py tests/test_cli.py tests/test_components_tide.py
git commit -m "feat: doctor --fix re-installs what doctor marks ✗ when a witchy command fixes it, then checks again" -m "Fixes that are not witchy commands stay printed and never run. Exit 0 when the second check has no ✗." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: install --fresh installs the apt packages a new WSL box lacks and offers fish as the login shell

**Items:** spec 15.1 (D15): before validation and the lock, list the missing `fish`, `curl`, `eza`; ask once before `sudo`; offer `chsh` when the login shell is not fish; a refusal of the install or a failed command exits 1; no terminal exits 1; `--fresh --dry-run` lists the questions and runs nothing. Acceptance 8. Plan Decision 14.

**Files:**
- Create: `witchy/fresh.py`
- Modify: `witchy/__main__.py` (`install --fresh`)
- Modify: `docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md` (15.1)
- Test: `tests/test_fresh.py` (new)

**Interfaces:**
- Consumes: `ctx.run` (with the terminal attached: no `capture_output`), `ctx.env["PATH"]`, `ctx.env["USER"]`, `ctx.dry_run`, `ctx.say`.
- Produces:
  - `fresh.PACKAGES = ("fish", "curl", "eza")`, `fresh.OPTIONAL = ("eza",)`, `fresh.NO_TERMINAL = "--fresh needs a terminal to ask before using sudo"`.
  - `fresh.login_shell(ctx) -> str | None` (`getent passwd <user>`, field 7).
  - `fresh.prepare(ctx, ask=input, interactive=None) -> int | None`: `None` means go on with the install, a number is the exit code. Questions: `sudo apt install <missing>? [y/N] ` and `make fish your login shell (chsh -s <path of fish>)? [y/N] `. Commands: `sudo apt-get update`, `sudo apt-get install -y <fish and curl if missing>`, `sudo apt-get install -y eza`, `chsh -s <fish>`. Notes: `fresh: nothing was installed.`, `fresh: <command> failed (exit N); nothing else ran.`, `fresh: eza could not be installed (exit N); ll and lt use ls.`, `fresh: chsh failed (exit N); your login shell stays as it was.`, and in a dry run `fresh: would ask: …`.
  - CLI: `python3 -m witchy install --fresh [--dry-run] [--only …]`; `main` calls `fresh.prepare(ctx)` before `runner.install(ctx)` and returns its code when it is not `None`.

**Decisions:**
1. **`apt-get update` first,** because a fresh WSL image has no package lists and `apt-get install` alone fails with "Unable to locate package". The question still names the packages, as the spec words it.
2. **`eza` is optional:** it is installed in its own `apt-get` call after `fish` and `curl`, and its failure is a note (Ubuntu 22.04 has no `eza` package; `ll` and `lt` fall back to `ls`). Refusing the question still exits 1, as the spec says.
3. **A terminal is needed only to ask:** with nothing missing and fish already the login shell, `--fresh` goes on without one. An `EOFError` from `input` counts as "no".
4. **`chsh` uses the `fish` found after apt ran** (`shutil.which` on `ctx.env["PATH"]`), and is offered when `getent` cannot tell the login shell too.
5. **Tests never run `sudo`, `apt-get` or `chsh`:** `ctx.run` is a fake that records the commands and puts a `fish` file on the temporary `PATH` when apt "installs" it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fresh.py`:

```python
import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import fresh
from witchy.__main__ import main
from witchy.context import Context


class FreshTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.bin = Path(tmp.name) / "bin"
        self.bin.mkdir()
        self.home = Path(tmp.name) / "home"
        self.calls, self.asked = [], []
        self.shell, self.codes = "/bin/bash", {}

    def tool(self, name):
        path = self.bin / name
        path.write_text("#!/bin/sh\n", encoding="utf-8")
        path.chmod(0o755)

    def fake_run(self, args, **kwargs):
        if args[:2] == ["getent", "passwd"]:
            return subprocess.CompletedProcess(args, 0, stdout=f"eimi:x:1000:1000::/home/eimi:{self.shell}\n")
        self.calls.append(args)
        if args[-1] == "fish" and "install" in args:
            self.tool("fish")  # apt put it on PATH
        return subprocess.CompletedProcess(args, self.codes.get(" ".join(args), 0))

    def prepare(self, answers=(), dry_run=False, interactive=True):
        replies = list(answers)

        def ask(question):
            self.asked.append(question)
            if not replies:
                raise EOFError
            return replies.pop(0)

        self.out = io.StringIO()
        ctx = Context(home=self.home, env={"PATH": str(self.bin), "USER": "eimi"}, out=self.out, dry_run=dry_run,
                      run=self.fake_run)
        return fresh.prepare(ctx, ask=ask, interactive=interactive)

    def test_nothing_missing_and_fish_already_the_login_shell_asks_nothing(self):
        for name in fresh.PACKAGES:
            self.tool(name)
        self.shell = "/usr/bin/fish"
        self.assertIsNone(self.prepare(interactive=False))
        self.assertEqual((self.asked, self.calls), ([], []))

    def test_asks_once_for_the_missing_packages_then_offers_chsh(self):
        self.tool("curl")
        self.assertIsNone(self.prepare(["y", "y"]))
        self.assertEqual(self.asked, ["sudo apt install fish eza? [y/N] ",
                                      f"make fish your login shell (chsh -s {self.bin / 'fish'})? [y/N] "])
        self.assertEqual(self.calls, [["sudo", "apt-get", "update"], ["sudo", "apt-get", "install", "-y", "fish"],
                                      ["sudo", "apt-get", "install", "-y", "eza"],
                                      ["chsh", "-s", str(self.bin / "fish")]])

    def test_a_refused_install_exits_1_and_runs_nothing(self):
        self.assertEqual(self.prepare(["n"]), 1)
        self.assertEqual(self.calls, [])
        self.assertIn("fresh: nothing was installed.", self.out.getvalue())

    def test_a_failed_apt_exits_1_and_asks_nothing_more(self):
        self.codes["sudo apt-get install -y fish curl"] = 100
        self.assertEqual(self.prepare(["y", "y"]), 1)
        self.assertEqual(len(self.asked), 1)
        self.assertIn("fresh: sudo apt-get install -y fish curl failed (exit 100); nothing else ran.",
                      self.out.getvalue())

    def test_eza_that_cannot_be_installed_is_only_a_note(self):
        self.tool("curl")
        self.tool("fish")
        self.codes["sudo apt-get install -y eza"] = 100
        self.shell = "/usr/bin/fish"
        self.assertIsNone(self.prepare(["y"]))
        self.assertIn("fresh: eza could not be installed (exit 100); ll and lt use ls.", self.out.getvalue())

    def test_chsh_is_offered_only_when_the_login_shell_is_not_fish(self):
        for name in fresh.PACKAGES:
            self.tool(name)
        self.assertIsNone(self.prepare(["n"]))
        self.assertEqual(self.asked, [f"make fish your login shell (chsh -s {self.bin / 'fish'})? [y/N] "])
        self.assertEqual(self.calls, [])  # a refusal is not an error

    def test_a_failed_chsh_is_reported_and_the_install_goes_on(self):
        for name in fresh.PACKAGES:
            self.tool(name)
        self.codes[f"chsh -s {self.bin / 'fish'}"] = 1
        self.assertIsNone(self.prepare(["y"]))
        self.assertIn("fresh: chsh failed (exit 1); your login shell stays as it was.", self.out.getvalue())

    def test_without_a_terminal_it_exits_1_before_asking(self):
        self.assertEqual(self.prepare(["y"], interactive=False), 1)
        self.assertEqual((self.asked, self.calls), ([], []))
        self.assertEqual(self.out.getvalue(), "--fresh needs a terminal to ask before using sudo\n")

    def test_dry_run_lists_the_questions_and_runs_nothing(self):
        self.assertIsNone(self.prepare(dry_run=True, interactive=False))
        self.assertEqual((self.asked, self.calls), ([], []))
        self.assertEqual(self.out.getvalue(), "fresh: would ask: sudo apt install fish curl eza? [y/N]\n"
                                              "fresh: would ask: make fish your login shell (chsh -s <fish>)? [y/N]\n")


class FreshCliTest(unittest.TestCase):
    def test_fresh_runs_before_the_install_and_can_stop_it(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp}), \
                mock.patch("witchy.fresh.prepare", return_value=1) as prepare, \
                mock.patch("witchy.runner.install") as install, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["install", "--fresh"]), 1)
            prepare.return_value = None
            install.return_value = 0
            self.assertEqual(main(["install", "--fresh", "--dry-run"]), 0)
            self.assertEqual(main(["install"]), 0)
        self.assertEqual(prepare.call_count, 2)
        self.assertEqual(install.call_count, 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_fresh`
Expected:
```
ImportError: cannot import name 'fresh' from 'witchy' (…/witchy/__init__.py)
FAILED (errors=1)
```

- [ ] **Step 3: Implement**

Create `witchy/fresh.py`:

```python
"""install --fresh: the apt packages a new WSL box lacks, and fish as the login shell (spec 15.1, D15).

It runs before validation and the lock, asks before each step, and runs sudo with the terminal attached so sudo
can ask for the password.
"""
from __future__ import annotations

import getpass
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

PACKAGES = ("fish", "curl", "eza")
OPTIONAL = ("eza",)  # ll and lt fall back to ls without it
NO_TERMINAL = "--fresh needs a terminal to ask before using sudo"


def login_shell(ctx: Any) -> str | None:
    """The login shell `getent passwd` names for the user, or None when it cannot be read."""
    user = ctx.env.get("USER") or getpass.getuser()
    try:
        done = ctx.run(["getent", "passwd", user], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    fields = done.stdout.strip().split(":")
    return fields[6] if done.returncode == 0 and len(fields) >= 7 else None


def _attached(ctx: Any, command: list[str]) -> int:
    """Run with the terminal attached (sudo asks for the password there); the exit code, 127 when it cannot start."""
    try:
        return ctx.run(command).returncode
    except OSError:
        return 127


def _yes(ask: Callable[[str], str], question: str) -> bool:
    try:
        return ask(question).strip().lower() in ("y", "yes")
    except EOFError:
        return False


def prepare(ctx: Any, ask: Callable[[str], str] = input, interactive: bool | None = None) -> int | None:
    """Install what is missing and offer chsh. None means go on with the install; a number is the exit code."""
    path = ctx.env.get("PATH")
    missing = [package for package in PACKAGES if shutil.which(package, path=path) is None]
    shell = login_shell(ctx)
    offer_shell = shell is None or Path(shell).name != "fish"
    install_question = f"sudo apt install {' '.join(missing)}? [y/N] "
    if ctx.dry_run:
        if missing:
            ctx.say(f"fresh: would ask: {install_question.strip()}")
        if offer_shell:
            ctx.say("fresh: would ask: make fish your login shell (chsh -s <fish>)? [y/N]")
        return None
    if not missing and not offer_shell:
        return None
    if not (sys.stdin.isatty() if interactive is None else interactive):
        ctx.say(NO_TERMINAL)
        return 1
    if missing:
        if not _yes(ask, install_question):
            ctx.say("fresh: nothing was installed.")
            return 1
        needed = [package for package in missing if package not in OPTIONAL]
        steps = [["sudo", "apt-get", "update"]] + ([["sudo", "apt-get", "install", "-y", *needed]] if needed else [])
        for command in steps:
            code = _attached(ctx, command)
            if code != 0:
                ctx.say(f"fresh: {' '.join(command)} failed (exit {code}); nothing else ran.")
                return 1
        for package in (package for package in missing if package in OPTIONAL):
            code = _attached(ctx, ["sudo", "apt-get", "install", "-y", package])
            if code != 0:
                ctx.say(f"fresh: {package} could not be installed (exit {code}); ll and lt use ls.")
    fish = shutil.which("fish", path=path)
    if offer_shell and fish and _yes(ask, f"make fish your login shell (chsh -s {fish})? [y/N] "):
        code = _attached(ctx, ["chsh", "-s", fish])
        if code != 0:
            ctx.say(f"fresh: chsh failed (exit {code}); your login shell stays as it was.")
    return None
```

In `witchy/__main__.py`, replace:

```python
from . import build, components, runner, validate
```

with:

```python
from . import build, components, fresh, runner, validate
```

after the `install_parser.add_argument("--only", …)` call add:

```python
    install_parser.add_argument("--fresh", action="store_true",
                                help="first install what a new WSL box lacks (fish, curl, eza) with sudo and offer "
                                     "fish as the login shell; asks before each")
```

and replace:

```python
    if args.command == "install":
        return runner.install(ctx)
```

with:

```python
    if args.command == "install":
        code = fresh.prepare(ctx) if args.fresh else None  # before validation and the lock (spec 15.1)
        return runner.install(ctx) if code is None else code
```

In the spec, section 15.1, replace items 2 and 3 and the paragraph after the list with:

```
2. If any are, asks once: `sudo apt install fish curl eza? [y/N]` (only the missing ones). Yes runs `sudo apt-get update`, then `sudo apt-get install -y` with the missing `fish` and `curl`, then the same for `eza` on its own, each with the terminal attached so sudo can ask for the password. A fresh WSL image has no package lists, so `install` alone would fail; `eza` is optional (`ll` and `lt` fall back to `ls`, and older Ubuntu releases do not package it), so its failure is a note. No, or a failed `update` or `fish`/`curl` install → exit 1, nothing else runs.
3. If the login shell (`getent passwd $USER`) is not fish, or cannot be read, asks `make fish your login shell (chsh -s <fish>)? [y/N]` and runs `chsh` on yes. A refusal is not an error; a failed `chsh` is a note.
4. Continues into the normal install.

Without a terminal on stdin, `--fresh` exits 1 with `--fresh needs a terminal to ask before using sudo`, unless it has nothing to ask. `--fresh --dry-run` lists what it would ask and runs nothing.
```

- [ ] **Step 4: Run the tests and the whole suite**

Run: `/usr/bin/python3 -m unittest tests.test_fresh`
Expected: `Ran 10 tests … OK`

Run the suite on both interpreters and `python3 -m witchy validate`.
Expected: `Ran 765 tests … OK (skipped=2)` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/fresh.py witchy/__main__.py tests/test_fresh.py docs/superpowers/specs/2026-10-05-witchy-prompt-takeover-design.md
git commit -m "feat: install --fresh installs the apt packages a new WSL box lacks and offers fish as the login shell" -m "It asks once before sudo, runs apt-get update first, treats eza as optional, and needs a terminal only when it has something to ask." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: The tide component, install --fresh, doctor --fix and the new doctor lines in the README

**Items:** README for the `tide` component (with the takeover and what is never edited), `install --fresh`, `doctor --fix`, the banner, and the doctor lines of Tasks 7 and Plan F that the troubleshooting table did not know (`prompt variables changed`, the global shadow, `Tide variables not checked`).

**Files:**
- Modify: `README.md`
- Test: `tests/test_cli.py` (`test_the_readme_names_every_component_in_order_and_every_flag`)

**Interfaces:**
- Consumes: `components.NAMES`.
- Produces: README text only.

**Decisions:**
1. **One small test keeps the README in step with the code:** it names every component in install order and shows `install --fresh` and `doctor --fix` in the usage block.
2. **Plan F's fish rows are corrected here,** because Plan F changed the messages (`prompt variables changed`, `Tide variables not checked`) without touching the README, and their fixes now point at `tide`.
3. **The "It installs" list keeps its order;** Plan H adds `preview` to the usage block next to these lines.

- [ ] **Step 1: Write the failing test**

In `tests/test_cli.py`, replace:

```python
from witchy import build
```

with:

```python
from witchy import build, components
```

and add before `test_doctor_and_mood_run_on_an_empty_home`:

```python
    def test_the_readme_names_every_component_in_order_and_every_flag(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Components, in install order: " + ", ".join(f"`{name}`" for name in components.NAMES) + ".",
                      readme)
        for usage in ("install --dry-run", "install --only claude", "install --fresh", "doctor --fix"):
            self.assertIn(f"/usr/bin/python3 -m witchy {usage} ", readme)
```

- [ ] **Step 2: Run it and watch it fail**

Run: `/usr/bin/python3 -m unittest tests.test_cli.CliTest.test_the_readme_names_every_component_in_order_and_every_flag`
Expected: `AssertionError: 'Components, in install order: `claude`, `font`, `windows-terminal`, `tide`, `fish`.' not found in '# Moonlit Candle…'`

- [ ] **Step 3: Update the README**

In `README.md`, replace the `- For fish:` bullet of "It installs" with:

```markdown
- For fish: fisher 4.4.5 and Tide 6.1.1 when they are missing, every file checked against the pinned release, and Tide as the only prompt; the Tide prompt recoloured, with tonight's moon phase as its first segment; a greeting on new Windows Terminal tabs (a moon drawn to tonight's phase, the Wheel of the Year, a tarot card of the day and a short system summary); `ll` and `lt` through eza
```

In the usage block, after the `install` line add:

```sh
/usr/bin/python3 -m witchy install --fresh               # on a new WSL box: apt install fish, curl, eza first (asks)
```

and after the `doctor` line add:

```sh
/usr/bin/python3 -m witchy doctor --fix                  # re-install what doctor marks ✗, then check again
```

Replace the paragraph that starts `Components, in install order:` with:

```markdown
Components, in install order: `claude`, `font`, `windows-terminal`, `tide`, `fish`.

- `tide` installs [fisher](https://github.com/jorgebucaran/fisher) 4.4.5 and [Tide](https://github.com/IlanCosman/tide) 6.1.1 when they are missing (fisher needs `curl`), replaces another Tide version, and checks every installed file against `content/pins.json`; a file that does not match is removed again. It makes Tide the only prompt: a hand-written `functions/fish_prompt.fish` is moved aside, another fisher prompt plugin (pure, hydro, …) is removed, and `starship init`, `oh-my-posh init` and `set -g tide_…` lines in `config.fish` and `conf.d` are commented out with `# witchy-disabled: `, after a backup. A `function fish_prompt` block, a line continued with `\` or a symlinked file is never edited: install fails and says what to change. Downloads and fisher's output go to `~/.cache/witchy/install.log`. `uninstall` gives all of it back and removes fisher and Tide only when witchy installed them.
- `fish` sets every Tide variable once Tide 6.1.1 is the active prompt. Without it, `fish` still installs the greeting and `ll`/`lt`, and the summary line says `skipped: Tide not ready (run: python3 -m witchy install --only tide)` (or `skipped: fish not found`).
- `install --fresh` first lists which of `fish`, `curl` and `eza` are missing, asks once before `sudo apt-get install`, and offers `chsh -s` to make fish the login shell. It needs a terminal to ask.
```

Replace the exit-code paragraph with:

```markdown
Exit codes for `install` and `uninstall`: `0` everything done, `1` nothing changed, `2` done with warnings (a component was skipped or failed: install names it in its summary line, `4/5 components installed · skipped: …`, and in a `✗✗✗ witchy is NOT fully installed ✗✗✗` banner below it with each reason; uninstall in its last line, `… still installed: …`).
```

Replace the first sentence under "Troubleshooting" with:

```markdown
Run `python3 -m witchy doctor`. Each `⚠` or `✗` line is followed by the command that fixes it; `doctor --fix` runs the ones that are witchy commands and checks again (exit 0 when no `✗` is left). A `·` line is information, never a problem.
```

In the table, replace the two rows

```markdown
| `✗ fish  Tide variables changed: …` | a Tide colour no longer holds the witchy value (for example after `tide configure`) | `python3 -m witchy install --only fish`, or keep your change |
| `⚠ fish  cannot check the Tide variables: …` | `fish` is not on PATH, or did not answer within 5 s | put `fish` on PATH, or run doctor again |
```

with:

```markdown
| `✗ fish  prompt variables changed: …` | a Tide variable no longer holds the witchy value (for example after `tide configure`) | `python3 -m witchy install --only fish`, or `doctor --fix` |
| `✗ fish  tide_… is overridden by a global in config.fish or conf.d` | a `set -g tide_…` line hides witchy's value in every new shell | `python3 -m witchy install --only tide` comments the line out |
| `⚠ fish  Tide variables not checked: …` | Tide is missing, not 6.1.1, or not the active prompt (the `tide` lines say which) | `python3 -m witchy install --only tide` |
| `✗ tide  fisher not found` or `Tide not found` | fisher or Tide is not installed | `python3 -m witchy install --only tide` |
| `✗ tide  Tide is …, not 6.1.1` or `ilancosman/tide files do not match the pinned release: …` | another Tide version, or a Tide file was edited | `python3 -m witchy install --only tide` puts Tide 6.1.1 back |
| `✗ tide  fish_prompt is not Tide's (…)` | another `fish_prompt` is the active one | `python3 -m witchy install --only tide` |
| `✗ tide  starship init in ~/.config/fish/config.fish line N is active` | a line witchy commented out was turned back on, or a new one appeared | `python3 -m witchy install --only tide` |
| `✗ tide  config.fish defines fish_prompt at line N` | a `function fish_prompt` block in `config.fish` or `conf.d` | remove that function by hand, then install |
| `✗ tide  config.fish is a symlink to …` | the line to disable lives in another file (a dotfiles repository) | comment out the named line there yourself |
| `⚠ tide  fisher is …; witchy was tested with 4.4.5` | your own fisher, another version; witchy leaves it alone | nothing to do |
| `· tide  glyph test: …` | each symbol should show as one clear glyph | if one shows as a box or two, check the font (Maple Mono NF) |
| `tide: failed: curl not found (sudo apt install curl)` (install) | fisher downloads with curl | `sudo apt install curl`, or `install --fresh` |
| `tide: failed: could not install Tide (exit 1): … (details: ~/.cache/witchy/install.log)` (install) | fisher could not download or install Tide | read the log, check the network, install again |
| `⚠ fish  cannot check the Tide variables: …` or `⚠ tide  cannot check fisher and Tide: …` | `fish` is not on PATH, or did not answer within 5 s | put `fish` on PATH (`install --fresh` installs it), or run doctor again |
```

- [ ] **Step 4: Run the test and the whole suite**

Run: `/usr/bin/python3 -m unittest tests.test_cli`
Expected: `Ran 11 tests … OK`

Run the suite on both interpreters and `python3 -m witchy validate`.
Expected: `Ran 766 tests … OK (skipped=2)` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_cli.py
git commit -m "docs: the tide component, install --fresh, doctor --fix and the new doctor lines in the README" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: End-to-end check in temporary HOMEs

**Items:** acceptance 1 (a PC with fish only: install exits 0, doctor has no ✗), 3 (a `starship` line is disabled and given back), 6 (uninstall removes what witchy installed; on this PC it puts back its Tide and every recorded variable), 11 (`doctor --fix` after drift), with the real fisher and the real Tide release. No commit: this task changes nothing in the repository.

**Files:** none.

**Interfaces:**
- Consumes: the CLI (`install`, `doctor`, `doctor --fix`, `uninstall`) run from the repo root.
- Produces: nothing.

**Decisions:**
1. **Everything runs under `env -i` with a temporary HOME,** `XDG_RUNTIME_DIR` (for the lock) in the same folder, and `PATH` without the user's own folders. Nothing reads or writes the real `~/.claude`, `~/.cache` or `~/.config/fish`; part B only *copies* the real fish folder.
2. **Part A downloads** fisher's bootstrap file and the two release tarballs (the only network use allowed). **Part B downloads nothing at uninstall:** this PC's Tide is the development branch, whose tarball is not a release, so a stand-in `curl` serves a tarball built from the installed files instead, plus the `v6.1.1` release tarball fetched once.

- [ ] **Step 1: Part A, a PC with fish only**

Run from the repo root:
```bash
E=$(mktemp -d); mkdir -p "$E/home/.config/fish"
run() { env -i HOME="$E/home" XDG_RUNTIME_DIR="$E" USER="$USER" LANG=C.UTF-8 PATH=/usr/bin:/bin "$@"; }
run python3 -m witchy install --only tide --only fish --dry-run | grep -E '^(tide|fish): '
```
Expected (the `fisher.fish` hash shortened as printed):
```
tide: download https://raw.githubusercontent.com/jorgebucaran/fisher/4.4.5/functions/fisher.fish (sha256 59640d07bda1…)
tide: fisher install jorgebucaran/fisher@4.4.5
tide: fisher install ilancosman/tide@v6.1.1
fish: set 159 prompt variables once tide has installed Tide (fish is asked again then)
```

Run: `run python3 -m witchy install --only tide --only fish | grep -v '^created '; echo "exit ${PIPESTATUS[0]}"`
Expected:
```
2/2 components installed
Moonlit Candle installed. Undo with: python3 -m witchy uninstall
Open a new terminal tab to see the new prompt and greeting; open shells keep the old ones.
The output style applies from your next message; restart Claude Code if the theme or status line do not update.
exit 0
```

Run: `run python3 -m witchy doctor | grep -E '^. (tide|fish) '`
Expected (no ✗):
```
✓ tide              fisher 4.4.5 found
✓ tide              Tide 6.1.1 found
✓ tide              every jorgebucaran/fisher file matches the pinned release
✓ tide              every ilancosman/tide file matches the pinned release
✓ tide              the active fish_prompt is Tide's
✓ tide              no other prompt owner is active
· tide              glyph test: 🧹 🔮 🪦 🌿 🧪 💀 🔥 🐈 🦉 ❯ — each should be one clear symbol
✓ fish              20 files match
✓ fish              159 prompt variables match
✓ fish              eza found
✓ fish              no greeting or sky errors in the last 7 days
```
(`⚠ fish  eza missing` instead of `eza found` on a PC without eza.)

- [ ] **Step 2: Drift and doctor --fix (acceptance 11)**

Run:
```bash
run fish -c 'set -U tide_pwd_icon X; set -U tide_character_color 00FF00'
run python3 -m witchy doctor --fix | grep -E 'doctor --fix|prompt variables'; echo "exit ${PIPESTATUS[0]}"
```
Expected:
```
✗ fish              prompt variables changed: tide_character_color, tide_pwd_icon
doctor --fix: python3 -m witchy install --only fish
doctor --fix: checking again
✓ fish              159 prompt variables match
exit 0
```

- [ ] **Step 3: A starship line and a global (acceptance 3), then uninstall (acceptance 6)**

Run:
```bash
printf 'if type -q starship\n    starship init fish | source\nend\nset -gx tide_time_color 5F8787\n' > "$E/home/.config/fish/config.fish"
run python3 -m witchy doctor | grep -A1 -E '^✗ (tide|fish) '
run python3 -m witchy install --only tide --only fish | grep -E '^tide:|components installed'
cat "$E/home/.config/fish/config.fish"
```
Expected:
```
✗ tide              starship init in ~/.config/fish/config.fish line 2 is active
    fix: python3 -m witchy install --only tide
✗ tide              set -g tide_time_color in ~/.config/fish/config.fish line 4 is active
    fix: python3 -m witchy install --only tide
--
✗ fish              tide_time_color is overridden by a global in config.fish or conf.d
    fix: python3 -m witchy install --only tide
tide: disabled starship init in ~/.config/fish/config.fish line 2 (backup: ~/.config/fish/config.fish.bak-witchy-<stamp>)
tide: disabled set -g tide_time_color in ~/.config/fish/config.fish line 4 (backup: ~/.config/fish/config.fish.bak-witchy-<stamp>)
2/2 components installed
if type -q starship
# witchy-disabled:     starship init fish | source
end
# witchy-disabled: set -gx tide_time_color 5F8787
```

Run:
```bash
run python3 -m witchy uninstall | grep -v '^removed '; echo "exit ${PIPESTATUS[0]}"
cat "$E/home/.config/fish/config.fish"
run fish -c 'functions -q fisher tide; or echo gone; set -U --names | string match "*tide*" | count'
```
Expected:
```
updated …/home/.config/fish/config.fish
Moonlit Candle uninstalled.
exit 0
if type -q starship
    starship init fish | source
end
set -gx tide_time_color 5F8787
gone
0
```

- [ ] **Step 4: Part B, a copy of this PC's fish folder**

Build a stand-in `curl` that serves the `v6.1.1` release (downloaded once) and a tarball of this PC's installed Tide files (read only), then copy the fish folder without witchy's own files:
```bash
B=$(mktemp -d); mkdir -p "$B/bin" "$B/served" "$B/dev/IlanCosman-tide-dev"
curl -sSL -o "$B/served/tide-v6.1.1.tgz" https://api.github.com/repos/ilancosman/tide/tarball/v6.1.1
fish -c 'printf "%s\n" $_fisher_ilancosman_2F_tide_files' | sed "s#^~#$HOME#" | while read -r f; do
  rel=${f#"$HOME/.config/fish/"}; mkdir -p "$B/dev/IlanCosman-tide-dev/$(dirname "$rel")"
  cp -R "$f" "$B/dev/IlanCosman-tide-dev/$rel"; done
tar czf "$B/served/tide-dev.tgz" -C "$B/dev" IlanCosman-tide-dev
cat > "$B/bin/curl" <<EOF
#!/bin/sh
for arg; do url=\$arg; done
echo "\$url" >> "$B/curl.log"
case "\$url" in
  https://api.github.com/repos/ilancosman/tide/tarball/v6.1.1) cat "$B/served/tide-v6.1.1.tgz" ;;
  https://api.github.com/repos/ilancosman/tide/tarball/HEAD) cat "$B/served/tide-dev.tgz" ;;
  *) exit 22 ;;
esac
EOF
chmod +x "$B/bin/curl"
mkdir -p "$B/home/.config"; cp -R ~/.config/fish "$B/home/.config/fish"
( cd "$B/home/.config/fish" && rm -f conf.d/witchy.fish conf.d/fnm.fish functions/ll.fish functions/lt.fish \
    functions/ritual.fish functions/fish_greeting.fish functions/_witchy_moon_bin.fish functions/_tide_item_moon.fish \
    *.bak-witchy-* functions/*.bak-witchy-* conf.d/*.bak-witchy-* )
runb() { env -i HOME="$B/home" XDG_RUNTIME_DIR="$B" USER="$USER" LANG=C.UTF-8 PATH="$B/bin:/usr/bin:/bin" "$@"; }
runb fish -c 'set -U | string match "tide_*"; echo exported:; set -U -x | string match "tide_*"' > "$B/before.txt"
runb fish -c 'printf "%s\n" $_fisher_plugins | string match "*tide*"; tide --version'
```
Expected: `ilancosman/tide` and `tide, version 6.1.1` (the development branch).

Run:
```bash
runb python3 -m witchy install --only tide --only fish --dry-run | grep -E '^tide: |^fish: set 1'
runb python3 -m witchy install --only tide --only fish | grep -v '^created \|^updated '; echo "exit ${PIPESTATUS[0]}"
runb fish -c 'printf "%s\n" $_fisher_plugins | string match "*tide*"; echo $tide_pwd_icon'
runb python3 -m witchy doctor | grep -E '^. (tide|fish) ' | grep -v '^✓'
```
Expected:
```
tide: fisher remove ilancosman/tide, then fisher install ilancosman/tide@v6.1.1 (its files do not match the pinned release); the Tide variables keep their values
fish: set 159 prompt variables once tide has installed Tide (fish is asked again then)
2/2 components installed
Moonlit Candle installed. Undo with: python3 -m witchy uninstall
…
exit 0
ilancosman/tide@v6.1.1
🧹
· tide              glyph test: 🧹 🔮 🪦 🌿 🧪 💀 🔥 🐈 🦉 ❯ — each should be one clear symbol
```

Run:
```bash
runb python3 -m witchy uninstall | grep -v '^removed \|^updated '; echo "exit ${PIPESTATUS[0]}"
cat "$B/curl.log"
runb fish -c 'set -U | string match "tide_*"; echo exported:; set -U -x | string match "tide_*"' > "$B/after.txt"
diff "$B/before.txt" "$B/after.txt" && echo same-variables
runb fish -c 'printf "%s\n" $_fisher_plugins | string match "*tide*"; tide --version'
```
Expected:
```
Moonlit Candle uninstalled.
exit 0
https://api.github.com/repos/ilancosman/tide/tarball/v6.1.1
https://api.github.com/repos/ilancosman/tide/tarball/HEAD
same-variables
ilancosman/tide
tide, version 6.1.1
```

- [ ] **Step 5: Clean up**

Run: `rm -rf "$E" "$B"`. Nothing to commit; `git status` shows a clean tree.

---

## Self-review against the spec

- 5 (component, order) → Tasks 4, 8; 5.1 (each table row, curl, pins, `tide --version`, timeouts and log, failures keep the record, entry fields, dry run) → Tasks 1, 3, 4; 5.2 (each owner row, the printed line, every edge case) → Tasks 2, 5, 7 (drift).
- 9.1 `tide` checks → Task 7; 9.2 banner and D19 → Task 8 (the `fish` side of 9.1 is Plan F).
- 10 (uninstall steps 1–5) → Task 6.
- 12: `test_components_tide.py` (bootstrap rows, takeover rows, uninstall steps, dry run, SHA mismatch) → Tasks 4–8 and 10; `test_runner.py` (banner) → Task 8; integration and the opt-in network test → Task 9; `network.yml` → Task 9; `test_fresh.py` → Task 11; `doctor --fix` → Task 10; takeover edge cases → Tasks 2 and 5.
- 15.1 → Task 11; 15.4 → Task 10.
- Acceptance 1, 3, 4, 6, 7, 8 (unit level), 11 → Tasks 4–11 and Task 13. Acceptance 2, 5, 9, 10 belong to Plans F and H.
