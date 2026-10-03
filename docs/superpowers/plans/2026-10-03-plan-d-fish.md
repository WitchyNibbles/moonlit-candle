# Plan D: fish, Tide, eza and Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install the greeting, the fish functions, the Tide prompt colours and the eza colours as a fourth installer component (`fish`), wire the sky job into new shells, add the fish doctor lines, finish the Plan A carry-overs, and take the whole shell ritual through acceptance on the real machine.

**Architecture:** A new component `witchy/components/fish.py` copies `build.ritual_package()` into `~/.claude/witchy/ritual/`, renders `content/fish/` templates into the fish config folder, and sets Tide's universal variables through two batched fish calls (one reads, one writes; values travel on standard input). Uninstall gives the variables back through `Plan.commands`, a runner feature this plan adds together with blocked-restore handling (R7) and partial outcomes. The fish templates check the greeting conditions themselves (spec 6.2) and start the sky job from `conf.d/witchy.fish` (spec 4.5).

**Tech Stack:** Python 3.10+ standard library only (`subprocess`, `dataclasses`, `difflib`, `re`, `shutil`, `unittest`); fish 3.7 and Tide 6.1.1 on the real machine; eza (optional, `sudo apt install eza`).

**Spec:** `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (revision 2). This plan covers sections 3.1 (commands), 3.6 (fish files), 4.5 (the fish half), 5, 6.2, 7, 8 (fish doctor lines, blocked restores), 9 (fish rows), 11.3–11.5, the `fish`, `doctor` and `round trip` rows of 12, and 14. Plans A–C are done; this plan is written against the code at `aeeb6b2`.

## Global Constraints

- Python 3.10 or newer, standard library only; every test passes on `/usr/bin/python3` (3.12) and `/home/eimi/.pyenv/versions/3.10.0/bin/python3`.
- Test command (from the repo root): `/usr/bin/python3 -m unittest discover -s tests -t .`, and the same with the 3.10 interpreter. `python3 -m witchy validate` must print `Moonlit Candle: all checks passed`.
- No test touches the real `~/.claude`, `~/.cache`, `~/.config/fish`, fish universal variables, Windows Terminal, the registry or the network. Unit tests use `tests.fakes.fake_fish`; tests that run real fish set `HOME` and `XDG_CONFIG_HOME` to a temporary folder and are skipped when fish is missing.
- Every fish call uses list arguments, a 5 s timeout and `ctx.env`, through the injectable `ctx.run` (spec 5.3, 10.2). Values never go into a script string.
- Tide variables and values exactly as spec 5.2 (colours without `#`); contrast rules exactly as spec 11.3 and 11.4.
- The greeting runs as `@PYTHON@ -I -B @WITCHY_DIR@/ritual` with `env FISH_VERSION=$FISH_VERSION`; the sky job as `… --sky >/dev/null 2>&1 &` then `disown` (spec 4.5, 6.1).
- `ll` runs `eza -la --icons --group-directories-first --git`, `lt` runs `eza --tree --level=2 --icons`; without eza, `ls -la` and `ls -R` (spec 7).
- Never run a real `install`, `uninstall` or `mood <variant>` without the user's go-ahead (Task 7 only). Dry runs and `doctor` are read-only and allowed.
- Messages, docstrings and comments are English and neutral in tone.
- Commit messages end with the `Co-Authored-By:` trailer of the model that wrote the commit.
- SDD workspaces go under `.superpowers/sdd/` (git-excluded).

## Decisions made while planning

1. **Prototype first.** Every change in this plan was made in a scratch copy of the repository and run on 3.12 and 3.10 (464 tests, `validate` clean). The tasks below were then replayed one by one on a fresh copy of `aeeb6b2`: each stage is green on both interpreters, each task's new tests fail on the stage before it (except Task 6, which pins behaviour), and the final stage is byte-identical to the prototype. A read-only `install --dry-run --only fish` on the real machine took 0.66 s and listed 20 files and 31 Tide changes.
2. **fish calls are batched; no `--no-config`.** `fish -c true` takes 0.43 s on this machine (its `config.fish` runs `pyenv init`), so one call per variable would take about 14 s. `fish --no-config` was tried: it also turns off universal variables (nothing is saved) and the user function path, so it cannot be used. One call reads Tide's presence and all 32 variables; one call sets the changed ones.
3. **Values travel on standard input** as NUL-terminated fields (name, mode, count, elements); fish values cannot hold NUL. Both scripts print a `witchy-fish` marker first, because `config.fish` may print to stdout (verified: it does run under `fish -c`). The reading script erases a global of the same name inside its own process so the universal value shows.
4. **`Plan.commands` run only for restore plans,** before the file changes. The install-side `set` runs inside `FishComponent.apply`, because a partial failure must record exactly the variables already set (spec 5.3).
5. **`Plan.outcome`** lets a plan that applied in part report `skipped: Tide not found`, `skipped: fish not found` or `failed: could not set <name>` while its entry (the installed files) is still recorded. Spec 5.3 asks for exactly that.
6. **A restore that cannot be planned raises `ComponentFailed`** (from `restore_json` when a `settings.json` is no longer plain JSON). The runner then keeps that whole component, files included, and exits 2. This is the Plan A R7 fix, and it covers Windows Terminal's sky images as well.
7. **`Plan.prune`** lists folders removed after a restore when empty (`~/.claude/witchy/ritual/`), so `~/.claude/witchy/` can go too.
8. **`file_change` / `file_record` move to `base.py`** (they were private in `windows_terminal.py`); the fish component records its files the same way.
9. **Templates live in `content/fish/functions/*.fish` and `content/fish/conf.d/witchy.fish`.** The placeholders `@PYTHON@`, `@WITCHY_DIR@` and `@EZA_COLORS@` are each rendered as one single-quoted fish word, so a path with spaces or quotes works (the fish tests use a HOME with a space). The fish config folder follows `$XDG_CONFIG_HOME`, as fish does.
10. **`_witchy_moon_bin` uses one `math` expression** (no rounding between steps) with the same operations as `moon.phase_bin`, and takes an optional Unix time for tests. It matches Python at 480 times over 60 days and ±60 s around 32 bin edges.
11. **`conf.d/witchy.fish` reads the stamps with `read`, not `cat`** (no extra processes on every shell). `exit` in a conf.d file stops only that file (verified on fish 3.7). Tide's prompt runs in a non-interactive background fish, which sources conf.d too; the snippet leaves at `status is-interactive; or exit`.
12. **`fish_greeting` guards twice:** `test -x @PYTHON@` and `test -f …/ritual/__main__.py`, plus `2>/dev/null` on the call. It sets `WITCHY_RITUAL_SHOWN` before those checks, so nested shells stay quiet even when the package is missing.
13. **`ritual` passes `--full $argv`,** so `ritual --date 2026-10-31` and `ritual --debug` work (acceptance 5 and 6). `ritual --omen` is an argument error (exit 2 with usage), which is fine for a typed command.
14. **eza:** `di`, `ex`, `ln`, `sn`/`sb`, `da`, and git `ga` `#FFD477`, `gm`/`gv`/`gt` `#FFB86B`, `gd` `#FF6B9F` (Tide's three git colours), in 24-bit `38;2;R;G;B`.
15. **Doctor log lines** (Plan C review): only the newest `greeting` and `sky` errors less than 7 days old, with their age (`today at 09:14`, `yesterday`, `3 days ago`), cut to 100 characters; a sky fail marker for today adds `(it retries tomorrow)`. The daily "changed by hand" sky line therefore shows once, with the fix `install --only windows-terminal`. Bad bytes and damaged lines in the log are skipped.
16. **Reinstall rules:** a variable that already holds the wanted value is recorded but not set again; the first previous value is kept (as for the Claude settings); variables recorded earlier stay recorded when fish cannot be asked this time; a file an earlier version shipped stays recorded so uninstall still removes it.
17. **Uninstall order inside `fish`:** read, restore the variables, rebuild Tide's item cache (`_tide_remove_unusable_items`, present in Tide 6.1.1), then remove the files. Without the rebuild, open shells keep `moon` in `_tide_left_items` and their background prompt prints "Unknown command" until a new shell starts.
18. **The install summary says `Nothing was installed.`** when no component applied (Plan A acceptance note). Exit codes are unchanged.
19. **Dry runs show each Tide change with its current value**, for example `fish: set -U tide_pwd_bg_color B99AFF (now: FFB7C5)`.

## Review Focus

1. **A `config.fish` that prints text or sets a global Tide variable** must not corrupt the snapshot: witchy must record and restore the universal values → Task 4 `test_what_config_fish_prints_is_ignored`, Task 6 `test_install_recolours_tide_and_uninstall_gives_every_variable_back` (real fish, noisy `config.fish` with a global).
2. **A HOME or Python path with spaces or quotes** must still run the greeting and the sky job → Task 3 `test_paths_are_quoted_for_fish` and every real-fish test in `tests/test_fish_files.py` (HOME is `…/my home`).
3. **An interrupted or failing uninstall** must lose nothing and retry cleanly: no file removed while variables could not be restored, no warning on the retry, recorded variables kept when fish does not answer at reinstall → Task 4 `test_a_failed_restore_keeps_everything_for_a_retry`, `test_a_fish_that_does_not_answer_keeps_the_component`, `test_a_reinstall_that_cannot_ask_fish_keeps_the_recorded_variables`.
4. **A `settings.json` hand-edited into JSON with comments before uninstall** must not leave Claude Code pointing at a deleted status line → Task 1 `test_claude_files_stay_while_its_settings_cannot_be_restored`.
5. **An old or damaged `ritual.log`** must neither warn for ever nor crash doctor → Task 5 `test_errors_older_than_a_week_are_history`, `test_damaged_log_lines_are_skipped`, `test_long_messages_are_cut`.

---

## File structure

| File | Status | Responsibility |
| :- | :- | :- |
| `witchy/components/base.py` | modify | `Command`, `run_command`, `Plan.commands/prune/outcome`, shared `file_change`/`file_record`, blocked `restore_json` |
| `witchy/components/windows_terminal.py` | modify | use the shared file helpers |
| `witchy/runner.py` | modify | restore commands, blocked restores, prune, outcomes, `NOTHING_INSTALLED` |
| `witchy/palette.py` | modify | `TIDE`, `EZA`, `Variant.tide`, `Variant.eza` |
| `witchy/validate.py` | modify | `validate_tide`, `validate_eza` (spec 11.3, 11.4) |
| `witchy/build.py` | modify | `EZA_CODES`, `eza_colors`, `fish_quote`, `fish_files` |
| `content/fish/functions/{fish_greeting,ritual,_witchy_moon_bin,_tide_item_moon,ll,lt}.fish`, `content/fish/conf.d/witchy.fish` | create | the fish templates |
| `witchy/components/fish.py` | create | the `fish` component and its doctor lines |
| `witchy/components/__init__.py` | modify | register `FishComponent` (so `--only fish` works) |
| `tests/fakes.py` | modify | `fake_fish` |
| `tests/test_base.py`, `tests/test_runner.py`, `tests/test_install.py` | modify | runner and R7 tests; the all-component round trip |
| `tests/test_prompt_palette.py`, `tests/test_fish_files.py`, `tests/test_components_fish.py`, `tests/test_fish_integration.py` | create | new tests |
| `README.md`, the spec, `.github/workflows/tests.yml` | modify | documentation and the CI step name |

---

### Task 1: Restore commands, blocked restores and partial outcomes (Plan A carry-overs)

**Files:**
- Modify: `witchy/components/base.py`, `witchy/components/windows_terminal.py`, `witchy/runner.py`
- Test: `tests/test_base.py`, `tests/test_runner.py`, `tests/test_install.py`

**Interfaces:**
- Consumes: the existing `Plan`, `Change`, `ComponentFailed`, `apply_changes`, `file_lock`, `restore_json`, `runner._uninstall`.
- Produces (later tasks rely on these exact names):
  - `base.COMMAND_TIMEOUT = 5`
  - `base.Command(args: tuple[str, ...], label: str, input: str | None = None)` — frozen dataclass
  - `Plan.commands: list[Command]`, `Plan.prune: list[Path]`, `Plan.outcome: str | None` (all default empty/None)
  - `base.run_command(ctx, command: Command, check: bool = True) -> subprocess.CompletedProcess` — calls `ctx.run(list(args), input=…, capture_output=True, text=True, errors="replace", timeout=5, env=dict(ctx.env))`; `OSError`/`ValueError`/`SubprocessError` → `ComponentFailed("could not <label> (<exc>)")` with the original as `__cause__`; a non-zero exit → `ComponentFailed("could not <label> (exit N)")` unless `check=False`
  - `base.file_change(path: Path, data: bytes, earlier: dict[Path, dict]) -> Change` and `base.file_record(change: Change, earlier: dict[Path, dict], backups: dict[Path, Path]) -> dict` (moved unchanged from `windows_terminal._file_change/_file_record`)
  - `base.restore_json` raises `ComponentFailed` when the file is no longer plain JSON or no longer an object
  - Runner: a `restore()` that raises `ComponentFailed` keeps that component (exit 2, `<name>: <reason>; run uninstall again.`; dry run: `<name>: <reason>; it would stay installed.`); a restore plan's commands run under its lock before its changes; its `prune` folders are removed afterwards when empty; install records `plan.outcome or "ok"`; `runner.NOTHING_INSTALLED = "Nothing was installed."`

- [ ] **Step 1: Write the failing tests**

In `tests/test_base.py` (edit 1 of 2), replace:

```python
from pathlib import Path

from witchy.components.base import Change, ComponentFailed, file_lock, show_changes

PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
```

with:

```python
from pathlib import Path

import subprocess

from witchy.components.base import Change, Command, ComponentFailed, file_lock, run_command, show_changes

PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
```

In `tests/test_base.py` (edit 2 of 2), replace:

```python
        show_changes(ctx, [Change(Path("/x/a.json"), b'{"a": 1}\n', b'{"a": 2}\n')])
        self.assertIn('+{"a": 2}', ctx.out.getvalue())
```

with:

```python
        show_changes(ctx, [Change(Path("/x/a.json"), b'{"a": 1}\n', b'{"a": 2}\n')])
        self.assertIn('+{"a": 2}', ctx.out.getvalue())


class RunCommandTest(unittest.TestCase):
    def ctx(self, run):
        ctx = Ctx()
        ctx.env, ctx.run = {"HOME": "/tmp/h"}, run
        return ctx

    def test_passes_list_arguments_input_env_and_a_timeout(self):
        seen = {}

        def run(args, **kwargs):
            seen.update(kwargs, args=args)
            return subprocess.CompletedProcess(args, 0, stdout="out", stderr="")

        done = run_command(self.ctx(run), Command(("fish", "-c", "x"), "do x", "in"))
        self.assertEqual(done.stdout, "out")
        self.assertEqual((seen["args"], seen["input"], seen["timeout"], seen["env"]),
                         (["fish", "-c", "x"], "in", 5, {"HOME": "/tmp/h"}))

    def test_a_non_zero_exit_fails_unless_unchecked(self):
        def run(args, **kwargs):
            return subprocess.CompletedProcess(args, 3, stdout="partial", stderr="")

        with self.assertRaisesRegex(ComponentFailed, r"^could not do x \(exit 3\)$"):
            run_command(self.ctx(run), Command(("x",), "do x"))
        self.assertEqual(run_command(self.ctx(run), Command(("x",), "do x"), check=False).stdout, "partial")

    def test_a_timeout_or_missing_program_fails_and_keeps_the_cause(self):
        for error in (subprocess.TimeoutExpired(["x"], 5), FileNotFoundError(2, "No such file", "x")):
            def run(args, **kwargs):
                raise error

            with self.assertRaises(ComponentFailed) as caught:
                run_command(self.ctx(run), Command(("x",), "do x"))
            self.assertIs(caught.exception.__cause__, error)
```

In `tests/test_runner.py` (edit 1 of 3), replace:

```python
import io
import json
import tempfile
import unittest
```

with:

```python
import io
import json
import subprocess
import tempfile
import unittest
```

In `tests/test_runner.py` (edit 2 of 3), replace:

```python
from witchy import palette, runner, state
from witchy.components.base import Abort, Change, Check, ComponentFailed, Plan
from witchy.context import Context
```

with:

```python
from witchy import palette, runner, state
from witchy.components.base import Abort, Change, Check, Command, ComponentFailed, Plan
from witchy.context import Context
```

In `tests/test_runner.py` (edit 3 of 3), replace:

```python
class UninstallRaceTest(RunnerTestCase):
    def test_a_rewrite_during_planning_leaves_only_that_component_installed(self):
```

with:

```python
class Restoring(Fake):
    """A component whose restore plan is ``make_plan(ctx)``."""

    def __init__(self, name, log, make_plan):
        super().__init__(name, log)
        self.make_plan = make_plan

    def restore(self, ctx, entry):
        super().restore(ctx, entry)
        return self.make_plan(ctx)


class RestoreCommandsTest(RunnerTestCase):
    def setUp(self):
        super().setUp()
        self.target = self.root / "ritual" / "cli.py"
        self.target.parent.mkdir()
        self.target.write_bytes(b"ours")
        self.calls = []

    def runs(self, code=0, error=None):
        def run(args, **kwargs):
            self.calls.append((args, kwargs, self.target.exists()))
            if error:
                raise error
            return subprocess.CompletedProcess(args, code, stdout="", stderr="")
        return run

    def plan(self, ctx):
        return Plan(commands=[Command(("fish", "-c", "restore"), "restore 2 Tide variables", "data")],
                    changes=[Change(self.target, b"ours", None, backup=False)], prune=[self.target.parent])

    def test_commands_run_before_the_changes_then_empty_folders_go(self):
        a = Restoring("a", self.log, self.plan)
        runner.install(self.ctx(), [a])
        self.assertEqual(runner.uninstall(self.ctx(run=self.runs()), [a]), 0)
        (args, kwargs, existed), = self.calls
        self.assertEqual((args, kwargs["input"], kwargs["timeout"], existed), (["fish", "-c", "restore"], "data", 5, True))
        self.assertFalse(self.target.parent.exists())

    def test_a_folder_that_is_not_empty_stays(self):
        (self.target.parent / "__pycache__").mkdir()
        a = Restoring("a", self.log, self.plan)
        runner.install(self.ctx(), [a])
        self.assertEqual(runner.uninstall(self.ctx(run=self.runs()), [a]), 0)
        self.assertTrue((self.target.parent / "__pycache__").is_dir())

    def test_a_failing_command_keeps_the_component_and_its_files(self):
        a = Restoring("a", self.log, self.plan)
        runner.install(self.ctx(), [a])
        self.assertEqual(runner.uninstall(self.ctx(run=self.runs(code=1)), [a]), 2)
        self.assertTrue(self.target.exists())
        self.assertEqual(self.state()["components"], {"a": {"installed": "a"}})
        self.assertIn("a: could not restore 2 Tide variables (exit 1); run uninstall again.", self.out.getvalue())

    def test_a_command_that_cannot_start_keeps_the_component(self):
        a = Restoring("a", self.log, self.plan)
        runner.install(self.ctx(), [a])
        missing = FileNotFoundError(2, "No such file or directory", "fish")
        self.assertEqual(runner.uninstall(self.ctx(run=self.runs(error=missing)), [a]), 2)
        self.assertTrue(self.target.exists())
        self.assertIn("could not restore 2 Tide variables", self.out.getvalue())

    def test_dry_run_lists_the_commands_and_runs_nothing(self):
        a = Restoring("a", self.log, self.plan)
        runner.install(self.ctx(), [a])
        self.assertEqual(runner.uninstall(self.ctx(dry_run=True, run=self.runs()), [a]), 0)
        self.assertEqual(self.calls, [])
        self.assertIn("a: restore 2 Tide variables", self.out.getvalue())
        self.assertTrue(self.target.exists())


class BlockedRestoreTest(RunnerTestCase):
    def blocked(self, ctx, entry):
        self.log.append(("restore", "a"))
        raise ComponentFailed("settings.json is no longer plain JSON; make it plain JSON again")

    def test_a_restore_that_cannot_be_planned_keeps_the_component_and_exits_2(self):
        a, b = Fake("a", self.log), Fake("b", self.log)
        a.restore = self.blocked
        runner.install(self.ctx(), [a, b])
        self.assertEqual(runner.uninstall(self.ctx(), [a, b]), 2)
        self.assertEqual(self.state()["components"], {"a": {"installed": "a"}})
        self.assertIn("a: settings.json is no longer plain JSON; make it plain JSON again; run uninstall again.",
                      self.out.getvalue())

    def test_dry_run_says_it_would_stay(self):
        a = Fake("a", self.log)
        a.restore = self.blocked
        runner.install(self.ctx(), [a])
        self.assertEqual(runner.uninstall(self.ctx(dry_run=True), [a]), 0)
        self.assertIn("a: settings.json is no longer plain JSON; make it plain JSON again; it would stay installed.",
                      self.out.getvalue())


class OutcomeTest(RunnerTestCase):
    def test_a_partial_outcome_is_recorded_and_its_entry_kept(self):
        class Partial(Fake):
            def plan(self, ctx, entry):
                super().plan(ctx, entry)
                return Plan(outcome="skipped: Tide not found", notes=["Open a new tab."])

        self.assertEqual(runner.install(self.ctx(), [Partial("fish", self.log)]), 2)
        self.assertEqual(self.state()["components"], {"fish": {"installed": "fish"}})
        self.assertEqual(self.state()["last_install"]["results"], {"fish": "skipped: Tide not found"})
        output = self.out.getvalue()
        self.assertIn("0/1 components installed · skipped: fish (Tide not found)", output)
        self.assertIn(runner.INSTALLED, output)
        self.assertIn("Open a new tab.", output)

    def test_nothing_applied_does_not_claim_an_install(self):
        self.assertEqual(runner.install(self.ctx(), [Fake("a", self.log, skip="no Windows Terminal")]), 2)
        output = self.out.getvalue()
        self.assertNotIn(runner.INSTALLED, output)
        self.assertIn(runner.NOTHING_INSTALLED, output)


class UninstallRaceTest(RunnerTestCase):
    def test_a_rewrite_during_planning_leaves_only_that_component_installed(self):
```

In `tests/test_install.py`, replace:

```python
        self.assertFalse((self.claude / "witchy" / "statusline.py").exists())

    def test_install_aborts_when_a_file_changes_while_planning(self):
        before = self.snapshot()
```

with:

```python
        self.assertFalse((self.claude / "witchy" / "statusline.py").exists())

    def test_claude_files_stay_while_its_settings_cannot_be_restored(self):
        before = self.snapshot()
        install.install(self.ctx())
        installed = self.settings.read_text(encoding="utf-8")
        self.settings.write_text("// a comment Claude Code does not write\n" + installed, encoding="utf-8")
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 2)
        self.assertIn("is no longer plain JSON; make it plain JSON again; run uninstall again.", self.out.getvalue())
        self.assertTrue((self.claude / "witchy" / "statusline.py").is_file())
        self.assertEqual(list(self.state()["components"]), ["claude"])
        self.assertEqual(self.ubuntu()["colorScheme"], "One Half Dark")
        self.settings.write_text(installed, encoding="utf-8")
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-131000")), 0)
        self.assertEqual(self.snapshot(), before)

    def test_install_aborts_when_a_file_changes_while_planning(self):
        before = self.snapshot()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_base tests.test_runner tests.test_install`
Expected: `FAILED (failures=1, errors=2)` — `ImportError: cannot import name 'Command' from 'witchy.components.base'` for `test_base` and `test_runner`, and `test_claude_files_stay_while_its_settings_cannot_be_restored` fails with `AssertionError: 0 != 2`.

- [ ] **Step 3: Implement**

In `witchy/components/base.py` (edit 1 of 5), replace:

```python
import difflib
import fcntl
import hashlib
import time
```

with:

```python
import difflib
import fcntl
import hashlib
import subprocess
import time
```

In `witchy/components/base.py` (edit 2 of 5), replace:

```python
__all__ = ["Abort", "ComponentFailed", "Change", "JsonPlan", "Plan", "Check", "Component", "sha", "read",
           "fix_command", "backup_checks", "check_unchanged", "show_changes", "apply_changes",
           "restore_copy", "restore_json", "file_lock"]
```

with:

```python
__all__ = ["Abort", "ComponentFailed", "Change", "Command", "JsonPlan", "Plan", "Check", "Component", "sha", "read",
           "fix_command", "backup_checks", "check_unchanged", "show_changes", "apply_changes", "run_command",
           "file_change", "file_record", "restore_copy", "restore_json", "file_lock"]

COMMAND_TIMEOUT = 5  # seconds for every fish call (spec 5.3)
```

In `witchy/components/base.py` (edit 3 of 5), replace:

```python
@dataclass
class Plan:
    """What a component will do. ``skip`` set means it will do nothing, and says why. ``actions`` describe work that is not a file change (a download, a reg.exe call) for dry runs. ``lock`` is held while the plan is applied."""

    changes: list[Change] = field(default_factory=list)
    skip: str | None = None
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    lock: Path | None = None
    data: dict[str, Any] = field(default_factory=dict)
```

with:

```python
@dataclass(frozen=True)
class Command:
    """A program to run: list arguments (never a shell string), optional standard input, and a label for messages."""

    args: tuple[str, ...]
    label: str
    input: str | None = None


@dataclass
class Plan:
    """What a component will do. ``skip`` set means it will do nothing, and says why. ``actions`` describe work that is not a file change (a download, a reg.exe call) for dry runs. ``lock`` is held while the plan is applied.

    For a restore plan the runner runs ``commands`` before writing ``changes``, then removes each ``prune``
    directory that is left empty. ``outcome`` replaces "ok" in the install results when a plan applied only
    in part (for example "skipped: Tide not found").
    """

    changes: list[Change] = field(default_factory=list)
    skip: str | None = None
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    lock: Path | None = None
    data: dict[str, Any] = field(default_factory=dict)
    commands: list[Command] = field(default_factory=list)
    prune: list[Path] = field(default_factory=list)
    outcome: str | None = None
```

In `witchy/components/base.py` (edit 4 of 5), replace:

```python
def restore_copy(entry: dict) -> Change | None:
```

with:

```python
def run_command(ctx: Any, command: Command, check: bool = True) -> subprocess.CompletedProcess:
    """Run ``command`` through ``ctx.run`` with ``ctx.env`` and a timeout.

    A command that cannot start or times out raises ComponentFailed (the cause is kept, so a caller can tell a
    missing program from a slow one); a non-zero exit raises it too unless ``check`` is false.
    """
    try:
        done = ctx.run(list(command.args), input=command.input, capture_output=True, text=True, errors="replace",
                       timeout=COMMAND_TIMEOUT, env=dict(ctx.env))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise ComponentFailed(f"could not {command.label} ({exc})") from exc
    if check and done.returncode != 0:
        raise ComponentFailed(f"could not {command.label} (exit {done.returncode})")
    return done


def file_change(path: Path, data: bytes, earlier: dict[Path, dict]) -> Change:
    """Copy ``data`` to ``path``; a file that still holds what witchy installed last time needs no backup."""
    before = read(path)
    previous = earlier.get(path)
    ours = previous is not None and sha(before) == previous["installed_sha256"]
    return Change(path, before, data, backup=not ours)


def file_record(change: Change, earlier: dict[Path, dict], backups: dict[Path, Path]) -> dict:
    """What state.json remembers about a copied file; the first backup ever made stays the restore target."""
    previous = earlier.get(change.path)
    backup = previous["backup"] if previous else (str(backups[change.path]) if change.path in backups else None)
    return {"path": str(change.path), "backup": backup, "installed_sha256": sha(read(change.path))}


def restore_copy(entry: dict) -> Change | None:
```

In `witchy/components/base.py` (edit 5 of 5), replace:

```python
    try:
        data, text = jsonio.read_json(path)
    except jsonio.StrictJsonError:
        warnings.append(f"{path} is no longer plain JSON; restore it by hand from {entry.get('backup')}.")
        return None
    if not isinstance(data, dict):
        warnings.append(f"{path} no longer holds a JSON object; restore it by hand from {entry.get('backup')}.")
        return None
```

with:

```python
    # A settings file that cannot be given back keeps the whole component installed: its other files
    # (the status line, the sky images) must stay while the settings still point at them.
    try:
        data, text = jsonio.read_json(path)
    except jsonio.StrictJsonError as exc:
        raise ComponentFailed(f"{path} is no longer plain JSON; make it plain JSON again") from exc
    if not isinstance(data, dict):
        raise ComponentFailed(f"{path} no longer holds a JSON object; fix it by hand")
```

In `witchy/components/windows_terminal.py` (edit 1 of 5), replace:

```python
from .base import (Change, Check, ComponentFailed, JsonPlan, Plan, apply_changes, backup_checks, fix_command, read,
                   restore_copy, restore_json, sha)
```

with:

```python
from .base import (Change, Check, ComponentFailed, JsonPlan, Plan, apply_changes, backup_checks, file_change,
                   file_record, fix_command, read, restore_copy, restore_json, sha)
```

In `witchy/components/windows_terminal.py` (edit 2 of 5), delete:

```python
def _file_change(path: Path, data: bytes, earlier: dict[Path, dict]) -> Change:
    before = read(path)
    previous = earlier.get(path)
    ours = previous is not None and sha(before) == previous["installed_sha256"]
    return Change(path, before, data, backup=not ours)


def _file_record(change: Change, earlier: dict[Path, dict], backups: dict[Path, Path]) -> dict:
    previous = earlier.get(change.path)
    backup = previous["backup"] if previous else (str(backups[change.path]) if change.path in backups else None)
    return {"path": str(change.path), "backup": backup, "installed_sha256": sha(read(change.path))}


```

In `witchy/components/windows_terminal.py` (edit 3 of 5), replace:

```python
        images = [_file_change(path.parent / wt.sky_file(bin_), image, earlier) for bin_, image in enumerate(renders)]
        config = _file_change(ctx.home / RITUAL_CONFIG, ritual_config(path, guid), earlier)
```

with:

```python
        images = [file_change(path.parent / wt.sky_file(bin_), image, earlier) for bin_, image in enumerate(renders)]
        config = file_change(ctx.home / RITUAL_CONFIG, ritual_config(path, guid), earlier)
```

In `witchy/components/windows_terminal.py` (edit 4 of 5), replace:

```python
        files = [_file_record(image, earlier, backups) for image in images if _still_ours(image, earlier)]
```

with:

```python
        files = [file_record(image, earlier, backups) for image in images if _still_ours(image, earlier)]
```

In `witchy/components/windows_terminal.py` (edit 5 of 5), replace:

```python
            files.append(_file_record(config, earlier, backups))
```

with:

```python
            files.append(file_record(config, earlier, backups))
```

In `witchy/runner.py` (edit 1 of 5), replace:

```python
from .components.base import Check, Component, apply_changes, check_unchanged, file_lock, fix_command, show_changes
```

with:

```python
from .components.base import (Check, Component, Plan, apply_changes, check_unchanged, file_lock, fix_command,
                              run_command, show_changes)
```

In `witchy/runner.py` (edit 2 of 5), replace:

```python
INSTALLED = "Moonlit Candle installed. Undo with: python3 -m witchy uninstall"
```

with:

```python
INSTALLED = "Moonlit Candle installed. Undo with: python3 -m witchy uninstall"
NOTHING_INSTALLED = "Nothing was installed."
```

In `witchy/runner.py` (edit 3 of 5), replace:

```python
    results: dict[str, str] = {}
    ctx.results = results
    for component, plan in plans:
        if plan.skip is not None:
            results[component.name] = f"skipped: {plan.skip}"
        else:
            try:
                with file_lock(plan.lock):
                    _recheck(plan.changes)
                    new_state["components"][component.name] = component.apply(ctx, plan)
                results[component.name] = "ok"
            except ComponentFailed as exc:
                results[component.name] = f"failed: {exc}"
```

with:

```python
    results: dict[str, str] = {}
    ctx.results = results
    applied = set()
    for component, plan in plans:
        if plan.skip is not None:
            results[component.name] = f"skipped: {plan.skip}"
        else:
            try:
                with file_lock(plan.lock):
                    _recheck(plan.changes)
                    new_state["components"][component.name] = component.apply(ctx, plan)
                applied.add(component.name)
                results[component.name] = plan.outcome or "ok"
            except ComponentFailed as exc:
                results[component.name] = f"failed: {exc}"
```

In `witchy/runner.py` (edit 4 of 5), replace:

```python
    ctx.say(_summary(results))
    ctx.say(INSTALLED)
    for component, plan in plans:
        if results[component.name] == "ok":
            for note in plan.notes:
                ctx.say(note)
```

with:

```python
    ctx.say(_summary(results))
    ctx.say(INSTALLED if applied else NOTHING_INSTALLED)
    for component, plan in plans:
        if component.name in applied:
            for note in plan.notes:
                ctx.say(note)
```

In `witchy/runner.py` (edit 5 of 5), replace:

```python
    entries = state["components"]
    # Reverse install order: the Windows side goes first and may refuse the write; local pieces follow.
    plans = [(component, component.restore(ctx, entries[component.name]))
             for component in reversed(_selected(ctx, components)) if component.name in entries]
    warnings = [warning for _, plan in plans for warning in plan.warnings]
    changes = [change for _, plan in plans for change in plan.changes]
    if ctx.dry_run:
        show_changes(ctx, changes)
        for warning in warnings:
            ctx.say(warning)
        ctx.say("Dry run: nothing was written.")
        return 0
    check_unchanged(_unlocked(plans))
    failed = []
    for component, plan in plans:
        try:
            with file_lock(plan.lock):
                _recheck(plan.changes)
                apply_changes(ctx, plan.changes)
        except (OSError, ComponentFailed) as exc:
            ctx.say(f"{component.name}: could not write ({exc}); run uninstall again.")
            failed.append(component.name)
            continue
        del entries[component.name]
        _save_or_remove(ctx, state)
```

with:

```python
    entries = state["components"]
    # Reverse install order: the Windows side goes first and may refuse the write; local pieces follow.
    plans = []
    for component in reversed(_selected(ctx, components)):
        if component.name not in entries:
            continue
        try:
            plan = component.restore(ctx, entries[component.name])
        except ComponentFailed as exc:
            plan = Plan.skipped(str(exc))  # nothing of it is touched; it stays installed
        plans.append((component, plan))
    warnings = [warning for _, plan in plans for warning in plan.warnings]
    changes = [change for _, plan in plans if plan.skip is None for change in plan.changes]
    if ctx.dry_run:
        for component, plan in plans:
            if plan.skip is not None:
                ctx.say(f"{component.name}: {plan.skip}; it would stay installed.")
        show_changes(ctx, changes)
        for component, plan in plans:
            for command in plan.commands:
                ctx.say(f"{component.name}: {command.label}")
        for warning in warnings:
            ctx.say(warning)
        ctx.say("Dry run: nothing was written.")
        return 0
    check_unchanged(_unlocked(plans))
    failed = []
    for component, plan in plans:
        try:
            if plan.skip is not None:
                raise ComponentFailed(plan.skip)
            with file_lock(plan.lock):
                _recheck(plan.changes)
                for command in plan.commands:
                    run_command(ctx, command)
                apply_changes(ctx, plan.changes)
        except (OSError, ComponentFailed) as exc:
            reason = f"could not write ({exc})" if isinstance(exc, OSError) else str(exc)
            ctx.say(f"{component.name}: {reason}; run uninstall again.")
            failed.append(component.name)
            continue
        for directory in plan.prune:
            try:
                directory.rmdir()
            except OSError:
                pass  # not empty (or already gone): only empty folders witchy made are removed
        del entries[component.name]
        _save_or_remove(ctx, state)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/usr/bin/python3 -m unittest tests.test_base tests.test_runner tests.test_install`
Expected: `OK`.

- [ ] **Step 5: Run the whole suite on both Pythons, and validate**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .`, `/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .` and `/usr/bin/python3 -m witchy validate`
Expected: `Ran 387 tests … OK` on both; `Moonlit Candle: all checks passed`.

- [ ] **Step 6: Commit**

```bash
git add witchy/components/base.py witchy/components/windows_terminal.py witchy/runner.py tests/test_base.py tests/test_runner.py tests/test_install.py
git commit -m "feat: run restore commands, keep components whose restore is blocked, record partial outcomes

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 2: Tide and eza colours, and their validation

**Files:**
- Modify: `witchy/palette.py`, `witchy/validate.py`
- Create: `tests/test_prompt_palette.py`

**Interfaces:**
- Consumes: `palette.Variant`, `validate.Failure`, `validate._contrast`, `validate.TEXT_MIN`, `validate.SECONDARY_MIN`, `validate.HEX`.
- Produces:
  - `palette.TIDE: dict[str, str | tuple[str, ...]]` — the 32 variables of spec 5.2; item lists are tuples
  - `palette.EZA: dict[str, str]` — roles `directory`, `executable`, `symlink`, `size`, `date`, `git_new`, `git_modified`, `git_renamed`, `git_typechange`, `git_deleted` → `#RRGGBB`
  - `Variant.tide`, `Variant.eza` (default empty; `midnight` gets `TIDE` and `EZA`)
  - `validate.TIDE_HEX`, `validate.GIT_PARTS`, `validate.GIT_BACKGROUNDS`, `validate.TIDE_TEXT_PAIRS`, `validate.TIDE_SECONDARY_PAIRS` — `(text, background)` pairs, `None` = the terminal background
  - `validate.validate_tide(tide, background=palette.BACKGROUND) -> list[Failure]`, `validate.validate_eza(eza, background=palette.BACKGROUND) -> list[Failure]`; both run for every variant in `validate_all`

- [ ] **Step 1: Write the failing tests**

The Tide name lists below were read from the real Tide 6.1.1 install (`fish -c 'set -U | string match -r "^tide_\S+"'` and the `_tide_item_*` function names), read-only.

Create `tests/test_prompt_palette.py`:

```python
import unittest
from unittest import mock

from witchy import palette, validate

# `fish -c 'set -U | string match -r "^tide_\S+"'` on Tide 6.1.1 (2026-10-03), the version the spec targets.
TIDE_6_1_1_VARIABLES = frozenset("""
tide_aws_bg_color tide_aws_color tide_aws_icon tide_bun_bg_color tide_bun_color tide_bun_icon tide_character_color
tide_character_color_failure tide_character_icon tide_character_vi_icon_default tide_character_vi_icon_replace
tide_character_vi_icon_visual tide_cmd_duration_bg_color tide_cmd_duration_color tide_cmd_duration_decimals
tide_cmd_duration_icon tide_cmd_duration_threshold tide_context_always_display tide_context_bg_color
tide_context_color_default tide_context_color_root tide_context_color_ssh tide_context_hostname_parts
tide_crystal_bg_color tide_crystal_color tide_crystal_icon tide_direnv_bg_color tide_direnv_bg_color_denied
tide_direnv_color tide_direnv_color_denied tide_direnv_icon tide_distrobox_bg_color tide_distrobox_color
tide_distrobox_icon tide_docker_bg_color tide_docker_color tide_docker_default_contexts tide_docker_icon
tide_elixir_bg_color tide_elixir_color tide_elixir_icon tide_gcloud_bg_color tide_gcloud_color tide_gcloud_icon
tide_git_bg_color tide_git_bg_color_unstable tide_git_bg_color_urgent tide_git_color_branch tide_git_color_conflicted
tide_git_color_dirty tide_git_color_operation tide_git_color_staged tide_git_color_stash tide_git_color_untracked
tide_git_color_upstream tide_git_icon tide_git_truncation_length tide_git_truncation_strategy tide_go_bg_color
tide_go_color tide_go_icon tide_java_bg_color tide_java_color tide_java_icon tide_jobs_bg_color tide_jobs_color
tide_jobs_icon tide_jobs_number_threshold tide_kubectl_bg_color tide_kubectl_color tide_kubectl_icon
tide_left_prompt_frame_enabled tide_left_prompt_items tide_left_prompt_prefix tide_left_prompt_separator_diff_color
tide_left_prompt_separator_same_color tide_left_prompt_suffix tide_nix_shell_bg_color tide_nix_shell_color
tide_nix_shell_icon tide_node_bg_color tide_node_color tide_node_icon tide_os_bg_color tide_os_color tide_os_icon
tide_php_bg_color tide_php_color tide_php_icon tide_private_mode_bg_color tide_private_mode_color
tide_private_mode_icon tide_prompt_add_newline_before tide_prompt_color_frame_and_connection
tide_prompt_color_separator_same_color tide_prompt_icon_connection tide_prompt_min_cols tide_prompt_pad_items
tide_prompt_transient_enabled tide_pulumi_bg_color tide_pulumi_color tide_pulumi_icon tide_pwd_bg_color
tide_pwd_color_anchors tide_pwd_color_dirs tide_pwd_color_truncated_dirs tide_pwd_icon tide_pwd_icon_home
tide_pwd_icon_unwritable tide_pwd_markers tide_python_bg_color tide_python_color tide_python_icon
tide_right_prompt_frame_enabled tide_right_prompt_items tide_right_prompt_prefix
tide_right_prompt_separator_diff_color tide_right_prompt_separator_same_color tide_right_prompt_suffix
tide_ruby_bg_color tide_ruby_color tide_ruby_icon tide_rustc_bg_color tide_rustc_color tide_rustc_icon
tide_shlvl_bg_color tide_shlvl_color tide_shlvl_icon tide_shlvl_threshold tide_status_bg_color
tide_status_bg_color_failure tide_status_color tide_status_color_failure tide_status_icon tide_status_icon_failure
tide_terraform_bg_color tide_terraform_color tide_terraform_icon tide_time_bg_color tide_time_color tide_time_format
tide_toolbox_bg_color tide_toolbox_color tide_toolbox_icon tide_vi_mode_bg_color_default tide_vi_mode_bg_color_insert
tide_vi_mode_bg_color_replace tide_vi_mode_bg_color_visual tide_vi_mode_color_default tide_vi_mode_color_insert
tide_vi_mode_color_replace tide_vi_mode_color_visual tide_vi_mode_icon_default tide_vi_mode_icon_insert
tide_vi_mode_icon_replace tide_vi_mode_icon_visual tide_zig_bg_color tide_zig_color tide_zig_icon
""".split())
# Tide 6.1.1's prompt items: its _tide_item_* functions, plus pwd and newline from _tide_2_line_prompt.
TIDE_6_1_1_ITEMS = frozenset("""
aws bun character cmd_duration context crystal direnv distrobox docker elixir gcloud git go java jobs kubectl
nix_shell node os php private_mode pulumi python ruby rustc shlvl status terraform time toolbox vi_mode zig pwd newline
""".split())
# The moon item is witchy's own; _tide_print_item reads tide_<item>_bg_color and tide_<item>_color.
MOON_VARIABLES = {"tide_moon_bg_color", "tide_moon_color"}


def pairs(failures):
    return {(f.rule, f.item) for f in failures}


class TideNamesTest(unittest.TestCase):
    def test_every_variable_exists_in_tide_6_1_1(self):
        self.assertEqual(set(palette.TIDE) - MOON_VARIABLES - TIDE_6_1_1_VARIABLES, set())
        self.assertTrue(MOON_VARIABLES <= set(palette.TIDE))

    def test_the_spec_variables_are_all_there(self):
        self.assertEqual(len(palette.TIDE), 32)
        self.assertEqual(palette.TIDE["tide_left_prompt_items"], ("moon", "pwd", "git", "newline", "character"))
        self.assertEqual(palette.TIDE["tide_right_prompt_items"], ("status", "cmd_duration", "time"))
        self.assertEqual(palette.TIDE["tide_cmd_duration_threshold"], "3000")

    def test_items_are_tide_items_or_the_moon(self):
        items = set(palette.TIDE["tide_left_prompt_items"]) | set(palette.TIDE["tide_right_prompt_items"])
        self.assertEqual(items - TIDE_6_1_1_ITEMS, {"moon"})

    def test_every_tide_colour_is_validated_for_contrast_or_exempt(self):
        checked = {name for pair in validate.TIDE_TEXT_PAIRS + validate.TIDE_SECONDARY_PAIRS for name in pair if name}
        colours = {key for key in palette.TIDE if "color" in key}
        self.assertEqual(colours - checked, {"tide_prompt_color_separator_same_color"})


class TideValidateTest(unittest.TestCase):
    def test_real_variables_pass(self):
        self.assertEqual(validate.validate_tide(palette.TIDE), [])

    def test_colours_need_six_hex_digits_without_a_hash(self):
        for bad in ("#B99AFF", "b99aff", "B99AF"):
            found = pairs(validate.validate_tide(dict(palette.TIDE, tide_pwd_bg_color=bad)))
            self.assertIn(("format", "tide.tide_pwd_bg_color"), found, bad)

    def test_segment_text_must_read_on_its_background(self):
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_time_color="2A1F3D")))
        self.assertIn(("text-contrast", "tide.tide_time_color on tide_time_bg_color"), found)

    def test_git_text_must_read_on_every_git_background(self):
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_git_bg_color_urgent="7A1F45")))
        self.assertIn(("text-contrast", "tide.tide_git_color_branch on tide_git_bg_color_urgent"), found)

    def test_the_character_reads_on_the_terminal_background(self):
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_character_color="2A1F3D")))
        self.assertIn(("text-contrast", "tide.tide_character_color on background"), found)

    def test_truncated_dirs_and_frame_need_3_to_1(self):
        lenient = dict(palette.TIDE, tide_pwd_color_truncated_dirs="5A4470")  # 3.66:1 on B99AFF
        self.assertEqual(validate.validate_tide(lenient), [])
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_prompt_color_frame_and_connection="3A2E47")))
        self.assertIn(("secondary-contrast", "tide.tide_prompt_color_frame_and_connection on background"), found)

    def test_a_missing_variable_is_reported(self):
        tide = {key: value for key, value in palette.TIDE.items() if key != "tide_moon_color"}
        self.assertIn(("missing-token", "tide.tide_moon_color"), pairs(validate.validate_tide(tide)))

    def test_items_must_be_strings(self):
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_left_prompt_items=("moon", 3))))
        self.assertIn(("format", "tide.tide_left_prompt_items"), found)


class EzaValidateTest(unittest.TestCase):
    def test_real_colours_pass(self):
        self.assertEqual(validate.validate_eza(palette.EZA), [])

    def test_format_contrast_and_presence(self):
        found = pairs(validate.validate_eza(dict(palette.EZA, directory="B99AFF", date="#2A1F3D")))
        self.assertIn(("format", "eza.directory"), found)
        self.assertIn(("text-contrast", "eza.date"), found)
        eza = {key: value for key, value in palette.EZA.items() if key != "symlink"}
        self.assertIn(("missing-token", "eza.symlink"), pairs(validate.validate_eza(eza)))


class VariantPromptTest(unittest.TestCase):
    def test_validate_all_checks_every_variant_prompt_and_eza(self):
        midnight = palette.VARIANTS["midnight"]
        broken = palette.Variant(**{**midnight.__dict__, "name": "broken",
                                    "tide": dict(midnight.tide, tide_moon_color="1D1230"),
                                    "eza": dict(midnight.eza, size="#1D1230")})
        with mock.patch.dict(palette.VARIANTS, {"broken": broken}):
            found = pairs(validate.validate_all())
        self.assertIn(("text-contrast", "tide.tide_moon_color on tide_moon_bg_color"), found)
        self.assertIn(("text-contrast", "eza.size"), found)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_prompt_palette`
Expected: `FAILED (errors=15)` — `AttributeError: module 'witchy.palette' has no attribute 'TIDE'` and `module 'witchy.validate' has no attribute 'validate_tide'` / `'validate_eza'`.

- [ ] **Step 3: Implement**

In `witchy/palette.py` (edit 1 of 3), replace:

```python
@dataclass(frozen=True)
class Variant:
```

with:

```python
# The Tide prompt (spec 5.2): fish universal variables. Colours are written without "#"; item lists are tuples
# (fish lists). Text on each segment reads at 4.5:1 on its background (spec 11.3).
TIDE: dict[str, str | tuple[str, ...]] = {
    "tide_left_prompt_items": ("moon", "pwd", "git", "newline", "character"),
    "tide_right_prompt_items": ("status", "cmd_duration", "time"),
    "tide_moon_bg_color": "1D1230",
    "tide_moon_color": "FFD477",
    "tide_pwd_bg_color": "B99AFF",
    "tide_pwd_color_anchors": "0D0916",
    "tide_pwd_color_dirs": "1D1230",
    "tide_pwd_color_truncated_dirs": "38234D",
    "tide_git_bg_color": "FFD477",
    "tide_git_bg_color_unstable": "FFB86B",
    "tide_git_bg_color_urgent": "FF6B9F",
    "tide_git_color_branch": "0D0916",
    "tide_git_color_conflicted": "0D0916",
    "tide_git_color_dirty": "0D0916",
    "tide_git_color_operation": "0D0916",
    "tide_git_color_staged": "0D0916",
    "tide_git_color_stash": "0D0916",
    "tide_git_color_untracked": "0D0916",
    "tide_git_color_upstream": "0D0916",
    "tide_character_color": "FF67B7",
    "tide_character_color_failure": "FF6B9F",
    "tide_prompt_color_frame_and_connection": "6E5A80",
    "tide_prompt_color_separator_same_color": "A99AB9",
    "tide_status_bg_color": "1D1230",
    "tide_status_color": "74E8B8",
    "tide_status_bg_color_failure": "1D1230",
    "tide_status_color_failure": "FF6B9F",
    "tide_cmd_duration_bg_color": "1D1230",
    "tide_cmd_duration_color": "A99AB9",
    "tide_cmd_duration_threshold": "3000",
    "tide_time_bg_color": "1D1230",
    "tide_time_color": "A99AB9",
}

# eza (spec 7): build.eza_colors turns these into EZA_COLORS. Git status uses Tide's three git colours.
EZA: dict[str, str] = {
    "directory": "#B99AFF",
    "executable": "#74E8B8",
    "symlink": "#77D9FF",
    "size": "#A99AB9",
    "date": "#A99AB9",
    "git_new": "#FFD477",
    "git_modified": "#FFB86B",
    "git_renamed": "#FFB86B",
    "git_typechange": "#FFB86B",
    "git_deleted": "#FF6B9F",
}


@dataclass(frozen=True)
class Variant:
```

In `witchy/palette.py` (edit 2 of 3), replace:

```python
    wt_profile: dict[str, Any] = field(default_factory=dict)
    ritual: dict[str, str] = field(default_factory=dict)
```

with:

```python
    wt_profile: dict[str, Any] = field(default_factory=dict)
    ritual: dict[str, str] = field(default_factory=dict)
    tide: dict[str, str | tuple[str, ...]] = field(default_factory=dict)
    eza: dict[str, str] = field(default_factory=dict)
```

In `witchy/palette.py` (edit 3 of 3), replace:

```python
VARIANTS: dict[str, Variant] = {
    "midnight": Variant("midnight", "dark", BACKGROUND, FOREGROUND, CLAUDE_OVERRIDES, WT_SCHEME, STATUSLINE,
                        sky=SKY, wt_profile=WT_PROFILE, ritual=RITUAL),
}
```

with:

```python
VARIANTS: dict[str, Variant] = {
    "midnight": Variant("midnight", "dark", BACKGROUND, FOREGROUND, CLAUDE_OVERRIDES, WT_SCHEME, STATUSLINE,
                        sky=SKY, wt_profile=WT_PROFILE, ritual=RITUAL, tide=TIDE, eza=EZA),
}
```

In `witchy/validate.py` (edit 1 of 4), replace:

```python
HEX = re.compile(r"^#[0-9A-F]{6}$")
TEXT_MIN = 4.5
SECONDARY_MIN = 3.0
```

with:

```python
HEX = re.compile(r"^#[0-9A-F]{6}$")
TIDE_HEX = re.compile(r"^[0-9A-F]{6}$")  # Tide colours carry no "#"
TEXT_MIN = 4.5
SECONDARY_MIN = 3.0
```

In `witchy/validate.py` (edit 2 of 4), replace:

```python
LINE_MAX = 48
MEANING_MAX = 60
```

with:

```python
LINE_MAX = 48
MEANING_MAX = 60


# Tide (spec 11.3): (text, background) pairs; None stands for the terminal background.
GIT_PARTS = ("branch", "conflicted", "dirty", "operation", "staged", "stash", "untracked", "upstream")
GIT_BACKGROUNDS = ("tide_git_bg_color", "tide_git_bg_color_unstable", "tide_git_bg_color_urgent")
TIDE_TEXT_PAIRS: tuple[tuple[str, str | None], ...] = (
    ("tide_moon_color", "tide_moon_bg_color"),
    ("tide_pwd_color_anchors", "tide_pwd_bg_color"),
    ("tide_pwd_color_dirs", "tide_pwd_bg_color"),
    *((f"tide_git_color_{part}", background) for part in GIT_PARTS for background in GIT_BACKGROUNDS),
    ("tide_status_color", "tide_status_bg_color"),
    ("tide_status_color_failure", "tide_status_bg_color_failure"),
    ("tide_cmd_duration_color", "tide_cmd_duration_bg_color"),
    ("tide_time_color", "tide_time_bg_color"),
    ("tide_character_color", None),
    ("tide_character_color_failure", None),
)
TIDE_SECONDARY_PAIRS: tuple[tuple[str, str | None], ...] = (
    ("tide_pwd_color_truncated_dirs", "tide_pwd_bg_color"),
    ("tide_prompt_color_frame_and_connection", None),
)
```

In `witchy/validate.py` (edit 3 of 4), replace:

```python
def validate_content(spinner: Mapping[str, Any], output_style: str) -> list[Failure]:
    failures: list[Failure] = []
```

with:

```python
def validate_tide(tide: Mapping[str, Any], background: str = palette.BACKGROUND) -> list[Failure]:
    """Every Tide variable is present; colours are RRGGBB without "#"; segment text reads on its background."""
    failures: list[Failure] = []
    for key in palette.TIDE:
        if key not in tide:
            failures.append(Failure("missing-token", f"tide.{key}", "-", "is missing from the Tide variables"))
    bad = set()
    for key, value in tide.items():
        if "color" in key and not (isinstance(value, str) and TIDE_HEX.match(value)):
            failures.append(Failure("format", f"tide.{key}", str(value), "is not RRGGBB in uppercase, without #"))
            bad.add(key)
        elif "color" not in key and not (isinstance(value, str) or
                                         (isinstance(value, tuple) and all(isinstance(v, str) for v in value))):
            failures.append(Failure("format", f"tide.{key}", str(value), "must be a string or a tuple of strings"))
    for pairs, rule, minimum in ((TIDE_TEXT_PAIRS, "text-contrast", TEXT_MIN),
                                 (TIDE_SECONDARY_PAIRS, "secondary-contrast", SECONDARY_MIN)):
        for text, on in pairs:
            if text not in tide or text in bad or (on is not None and (on not in tide or on in bad)):
                continue
            behind = background if on is None else "#" + tide[on]
            _contrast(failures, rule, f"tide.{text} on {on or 'background'}", "#" + tide[text], behind, minimum,
                      tide[text])
    return failures


def validate_eza(eza: Mapping[str, Any], background: str = palette.BACKGROUND) -> list[Failure]:
    """Every eza colour is present, #RRGGBB, and reads at 4.5:1 on the background (spec 11.4)."""
    failures: list[Failure] = []
    for key in palette.EZA:
        if key not in eza:
            failures.append(Failure("missing-token", f"eza.{key}", "-", "is missing from the eza colours"))
    for key, value in eza.items():
        if not isinstance(value, str) or not HEX.match(value):
            failures.append(Failure("format", f"eza.{key}", str(value), "is not #RRGGBB in uppercase"))
        else:
            _contrast(failures, "text-contrast", f"eza.{key}", value, background, TEXT_MIN, value)
    return failures


def validate_content(spinner: Mapping[str, Any], output_style: str) -> list[Failure]:
    failures: list[Failure] = []
```

In `witchy/validate.py` (edit 4 of 4), replace:

```python
                     for key, value in variant.sky.items() if not isinstance(value, str) or not HEX.match(value)]
        failures += validate_ritual_palette(variant.ritual, variant.background)
    try:
        spinner = content.load_spinner(content_dir)
```

with:

```python
                     for key, value in variant.sky.items() if not isinstance(value, str) or not HEX.match(value)]
        failures += validate_ritual_palette(variant.ritual, variant.background)
        failures += validate_tide(variant.tide, variant.background)
        failures += validate_eza(variant.eza, variant.background)
    try:
        spinner = content.load_spinner(content_dir)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/usr/bin/python3 -m unittest tests.test_prompt_palette` and `/usr/bin/python3 -m witchy validate`
Expected: `OK`; `Moonlit Candle: all checks passed` (the lowest ratios are the frame colour at 3.22:1 and the failure status at 6.65:1).

- [ ] **Step 5: Run the whole suite on both Pythons**

Expected: `Ran 402 tests … OK` on both.

- [ ] **Step 6: Commit**

```bash
git add witchy/palette.py witchy/validate.py tests/test_prompt_palette.py
git commit -m "feat: add the Tide and eza colours with their contrast rules

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 3: The fish templates and their rendering

**Files:**
- Create: `content/fish/functions/fish_greeting.fish`, `content/fish/functions/ritual.fish`, `content/fish/functions/_witchy_moon_bin.fish`, `content/fish/functions/_tide_item_moon.fish`, `content/fish/functions/ll.fish`, `content/fish/functions/lt.fish`, `content/fish/conf.d/witchy.fish`
- Modify: `witchy/build.py`
- Create: `tests/test_fish_files.py`

**Interfaces:**
- Consumes: `palette.EZA` / `Variant.eza` (Task 2); `content.CONTENT_DIR`; `moon.phase_bin`, `moon.EPOCH`, `moon.SYNODIC_DAYS`, `moon.GLYPHS` (Plan C).
- Produces:
  - `build.FISH_SOURCE = content.CONTENT_DIR / "fish"`
  - `build.EZA_CODES: dict[str, tuple[str, ...]]`, `build.eza_colors(colours: dict[str, str]) -> str`
  - `build.fish_quote(text: str) -> str`
  - `build.fish_files(python: str, witchy_dir: Path, variant: str = palette.DEFAULT_VARIANT, source: Path = FISH_SOURCE) -> dict[str, bytes]` — keys are paths inside the fish config folder: `functions/<name>.fish`, `conf.d/witchy.fish`
  - fish: `_witchy_moon_bin [UNIX_SECONDS]` prints 0–7; `_tide_item_moon` calls `_tide_print_item moon <glyph>`; `fish_greeting`, `ritual`, `ll`, `lt`; `conf.d/witchy.fish` exports `EZA_COLORS` and starts the sky job

- [ ] **Step 1: Write the failing tests**

These tests run the rendered files in a real fish inside a temporary HOME (with a space in it) and `XDG_CONFIG_HOME`, with a stub `python3` that records its arguments. They are skipped when fish is missing; this machine has fish 3.7.0, so here they must run.

Create `tests/test_fish_files.py`:

```python
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from witchy import build, palette
from witchy.ritual import moon

FISH = shutil.which("fish")
NAMES = {"functions/fish_greeting.fish", "functions/ritual.fish", "functions/_witchy_moon_bin.fish",
         "functions/_tide_item_moon.fish", "functions/ll.fish", "functions/lt.fish", "conf.d/witchy.fish"}
# Stands in for Python: records its arguments and FISH_VERSION, and prints a line so callers can be heard.
STUB_PYTHON = """#!/bin/sh
printf '%s\\n' "$@" "FISH_VERSION=$FISH_VERSION" > "$HOME/python-args"
echo "python ran"
"""


class RenderTest(unittest.TestCase):
    def test_every_template_is_rendered_without_placeholders(self):
        files = build.fish_files("/usr/bin/python3", Path("/home/eimi/.claude/witchy"))
        self.assertEqual(set(files), NAMES)
        for name, data in files.items():
            self.assertNotIn("@", data.decode("utf-8").replace("@PWD@", ""), name)

    def test_paths_are_quoted_for_fish(self):
        files = build.fish_files("/opt/py thon/bin/python3", Path("/home/o'neil/.claude/witchy"))
        greeting = files["functions/fish_greeting.fish"].decode("utf-8")
        self.assertIn("env FISH_VERSION=$FISH_VERSION '/opt/py thon/bin/python3' -I -B "
                      "'/home/o\\'neil/.claude/witchy'/ritual 2>/dev/null", greeting)

    def test_eza_colours_come_from_the_variant(self):
        self.assertEqual(build.eza_colors({**palette.EZA, "directory": "#B99AFF"}).split(":")[0], "di=38;2;185;154;255")
        codes = [part.split("=")[0] for part in build.eza_colors(palette.EZA).split(":")]
        self.assertEqual(codes, ["di", "ex", "ln", "sn", "sb", "da", "ga", "gm", "gv", "gt", "gd"])
        conf = build.fish_files("/usr/bin/python3", Path("/w"))["conf.d/witchy.fish"].decode("utf-8")
        self.assertIn(f"set -gx EZA_COLORS '{build.eza_colors(palette.EZA)}'", conf)

    def test_fish_quote(self):
        self.assertEqual(build.fish_quote("a b"), "'a b'")
        self.assertEqual(build.fish_quote("it's \\ here"), "'it\\'s \\\\ here'")


@unittest.skipUnless(FISH, "fish is not installed")
class FishTestCase(unittest.TestCase):
    """Runs the rendered files in a real fish, inside a throwaway HOME and XDG_CONFIG_HOME."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "my home"  # a space, so the quoting is exercised for real
        self.config = Path(tmp.name) / "config" / "fish"
        self.witchy = self.home / ".claude" / "witchy"
        self.cache = self.home / ".cache" / "witchy"
        (self.witchy / "ritual").mkdir(parents=True)
        (self.witchy / "ritual" / "__main__.py").write_text("", encoding="utf-8")
        self.python = Path(tmp.name) / "bin" / "python3"
        self.python.parent.mkdir()
        self.python.write_text(STUB_PYTHON, encoding="utf-8")
        self.python.chmod(0o755)
        for name, data in build.fish_files(str(self.python), self.witchy).items():
            path = self.config / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config.parent), "TERM": "dumb",
                    "PATH": f"{self.python.parent}:/usr/bin:/bin"}

    def fish(self, script, *args, interactive=False, env=None):
        command = [FISH, *(["-i"] if interactive else []), "-c", script, "--", *args]
        return subprocess.run(command, capture_output=True, text=True, timeout=20, env={**self.env, **(env or {})},
                              stdin=subprocess.DEVNULL)

    def python_args(self):
        path = self.home / "python-args"
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else None


class SyntaxTest(FishTestCase):
    def test_every_file_parses(self):
        for name in NAMES:
            done = subprocess.run([FISH, "--no-execute", str(self.config / name)], capture_output=True, text=True,
                                  timeout=10)
            self.assertEqual((done.returncode, done.stderr), (0, ""), name)


class MoonBinTest(FishTestCase):
    def test_matches_the_python_moon_over_60_days_and_at_every_bin_edge(self):
        start = datetime(2026, 10, 3, tzinfo=timezone.utc)
        times = [start + timedelta(hours=3 * step) for step in range(60 * 8)]
        for edge in range(1, 33):
            middle = moon.EPOCH + timedelta(days=moon.SYNODIC_DAYS * (edge / 16) + moon.SYNODIC_DAYS * 324)
            times += [middle - timedelta(seconds=60), middle + timedelta(seconds=60)]
        seconds = [str(int(when.timestamp())) for when in times]
        done = self.fish("for t in $argv; _witchy_moon_bin $t; end", *seconds)
        self.assertEqual(done.stderr, "")
        expected = [str(moon.phase_bin(datetime.fromtimestamp(int(s), timezone.utc))) for s in seconds]
        self.assertEqual(done.stdout.split(), expected)

    def test_without_an_argument_it_uses_now(self):
        done = self.fish("_witchy_moon_bin")
        self.assertIn(done.stdout.strip(), {str(moon.phase_bin(datetime.now(timezone.utc) + timedelta(seconds=s)))
                                           for s in (-5, 5)})

    def test_the_tide_item_prints_the_glyph(self):
        done = self.fish("function _tide_print_item; echo $argv; end; _tide_item_moon")
        self.assertEqual(done.stdout.split(), ["moon", moon.GLYPHS[moon.phase_bin(datetime.now(timezone.utc))]])


class GreetingTest(FishTestCase):
    WT = {"WT_SESSION": "f00d"}

    def greet(self):
        return self.fish("fish_greeting; echo shown=$WITCHY_RITUAL_SHOWN", interactive=True, env=self.WT)

    def test_a_top_level_windows_terminal_shell_runs_the_package(self):
        done = self.greet()
        self.assertEqual(done.stdout, "python ran\nshown=1\n")
        args = self.python_args()
        self.assertEqual(args[:3], ["-I", "-B", f"{self.witchy}/ritual"])
        self.assertTrue(args[3].startswith("FISH_VERSION=3"), args)

    def test_quiet_unless_every_condition_holds(self):
        cases = {"not interactive": (self.WT, False), "no WT_SESSION": ({}, True),
                 "tmux": ({**self.WT, "TMUX": "/tmp/tmux"}, True), "Claude Code": ({**self.WT, "CLAUDECODE": "1"}, True),
                 "nested": ({**self.WT, "WITCHY_RITUAL_SHOWN": "1"}, True),
                 "VS Code": ({**self.WT, "TERM_PROGRAM": "vscode"}, True)}
        for label, (env, interactive) in cases.items():
            done = self.fish("fish_greeting", interactive=interactive, env=env)
            self.assertEqual((done.stdout, done.stderr), ("", ""), label)
            self.assertIsNone(self.python_args(), label)

    def test_a_missing_package_prints_nothing_but_still_marks_the_shell(self):
        (self.witchy / "ritual" / "__main__.py").unlink()
        done = self.greet()
        self.assertEqual((done.stdout, done.stderr), ("shown=1\n", ""))

    def test_a_missing_python_prints_nothing(self):
        self.python.unlink()
        done = self.greet()
        self.assertEqual((done.stdout, done.stderr), ("shown=1\n", ""))

    def test_ritual_always_runs_the_full_ritual_with_its_arguments(self):
        done = self.fish("ritual --date 2026-10-31", env={"TMUX": "/tmp/tmux"})
        self.assertEqual(done.stdout, "python ran\n")
        self.assertEqual(self.python_args()[:5], ["-I", "-B", f"{self.witchy}/ritual", "--full", "--date"])


class ListingTest(FishTestCase):
    def setUp(self):
        super().setUp()
        self.folder = self.home / "folder"
        (self.folder / "inner").mkdir(parents=True)
        (self.folder / "inner" / "deep.txt").write_text("", encoding="utf-8")

    def test_without_eza_they_fall_back_to_ls(self):
        long = self.fish("ll $argv[1]", str(self.folder))
        self.assertIn("inner", long.stdout)
        self.assertRegex(long.stdout, r"(?m)^d")  # ls -la: one line per entry, directories start with d
        tree = self.fish("lt $argv[1]", str(self.folder))
        self.assertIn("deep.txt", tree.stdout)

    def test_with_eza_they_run_it(self):
        eza = self.python.parent / "eza"
        eza.write_text('#!/bin/sh\necho "eza $*"\n', encoding="utf-8")
        eza.chmod(0o755)
        self.assertEqual(self.fish("ll x").stdout, "eza -la --icons --group-directories-first --git x\n")
        self.assertEqual(self.fish("lt").stdout, "eza --tree --level=2 --icons\n")

    def test_eza_colours_are_exported(self):
        done = self.fish("printenv EZA_COLORS")
        self.assertEqual(done.stdout.strip(), build.eza_colors(palette.EZA))


class SkyJobStartTest(FishTestCase):
    WT = {"WT_SESSION": "f00d"}

    def setUp(self):
        super().setUp()
        (self.witchy / "ritual-config.json").write_text("{}", encoding="utf-8")
        self.cache.mkdir(parents=True)
        self.bin = moon.phase_bin(datetime.now(timezone.utc))

    def start_shell(self, env=None, interactive=True):
        return self.fish("true", interactive=interactive, env={**self.WT, **(env or {})})

    def wait_for_python(self):
        deadline = time.monotonic() + 5
        while self.python_args() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        return self.python_args()

    def test_starts_the_job_when_the_phase_moved(self):
        (self.cache / "sky-bin").write_text(f"{(self.bin + 1) % 8}\n", encoding="utf-8")
        done = self.start_shell()
        self.assertEqual((done.stdout, done.stderr), ("", ""))
        self.assertEqual(self.wait_for_python()[:4], ["-I", "-B", f"{self.witchy}/ritual", "--sky"])

    def test_starts_the_job_when_there_is_no_stamp_yet(self):
        self.start_shell()
        self.assertEqual(self.wait_for_python()[3], "--sky")

    def test_does_nothing_when_the_stamp_is_current(self):
        (self.cache / "sky-bin").write_text(f"{self.bin}\n", encoding="utf-8")
        self.start_shell()
        time.sleep(0.3)
        self.assertIsNone(self.python_args())

    def test_does_nothing_after_a_failure_today(self):
        (self.cache / "sky-fail").write_text(date.today().isoformat() + "\n", encoding="utf-8")
        self.start_shell()
        time.sleep(0.3)
        self.assertIsNone(self.python_args())

    def test_retries_the_day_after_a_failure(self):
        (self.cache / "sky-fail").write_text((date.today() - timedelta(days=1)).isoformat() + "\n", encoding="utf-8")
        self.start_shell()
        self.assertEqual(self.wait_for_python()[3], "--sky")

    def test_needs_an_interactive_windows_terminal_shell_and_the_config(self):
        self.start_shell(interactive=False)
        self.fish("true", interactive=True)  # no WT_SESSION
        (self.witchy / "ritual-config.json").unlink()
        self.start_shell()
        time.sleep(0.3)
        self.assertIsNone(self.python_args())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_fish_files`
Expected: `FAILED (errors=22)` — `AttributeError: module 'witchy.build' has no attribute 'fish_files'` (and `fish_quote`, `eza_colors`).

- [ ] **Step 3: Write the templates**

Create `content/fish/functions/fish_greeting.fish`:

```fish
# Moonlit Candle (witchy): the greeting, on top-level Windows Terminal shells only (spec 6.2).
function fish_greeting --description 'Moonlit Candle greeting'
    status is-interactive; or return
    set -q WT_SESSION; or return
    for name in TMUX CLAUDECODE WITCHY_RITUAL_SHOWN
        set -q $name; and return
    end
    test "$TERM_PROGRAM" = vscode; and return
    # Exported, so nested shells and everything they start stay quiet.
    set -gx WITCHY_RITUAL_SHOWN 1
    test -x @PYTHON@; and test -f @WITCHY_DIR@/ritual/__main__.py; or return
    env FISH_VERSION=$FISH_VERSION @PYTHON@ -I -B @WITCHY_DIR@/ritual 2>/dev/null
end
```

Create `content/fish/functions/ritual.fish`:

```fish
# Moonlit Candle (witchy): the full ritual on demand, anywhere; `ritual --date 2026-10-31` previews a day.
function ritual --description 'Moonlit Candle: show the full ritual'
    env FISH_VERSION=$FISH_VERSION @PYTHON@ -I -B @WITCHY_DIR@/ritual --full $argv
end
```

Create `content/fish/functions/_witchy_moon_bin.fish`:

```fish
# Moonlit Candle (witchy): the moon phase bin, 0 (new) to 7 (waning crescent), as ritual/moon.py computes it:
# days since the new moon of 2000-01-06 18:14 UTC (Unix time 947182440), modulo 29.530588853, in eighths
# centred on each phase. An optional argument gives the time in Unix seconds instead of now.
function _witchy_moon_bin --description 'Moon phase bin, 0-7'
    set -l now $argv[1]
    set -q now[1]; or set now (date +%s)
    math "floor(((($now - 947182440) / 86400) % 29.530588853) / 29.530588853 * 8 + 0.5) % 8"
end
```

Create `content/fish/functions/_tide_item_moon.fish`:

```fish
# Moonlit Candle (witchy): the Tide prompt item "moon", today's phase. Tide renders items asynchronously,
# so working it out on every prompt costs nothing visible and a shell left open for days stays right.
function _tide_item_moon
    set -l glyphs 🌑 🌒 🌓 🌔 🌕 🌖 🌗 🌘
    _tide_print_item moon $glyphs[(math (_witchy_moon_bin) + 1)]
end
```

Create `content/fish/functions/ll.fish`:

```fish
# Moonlit Candle (witchy): a long listing through eza, or ls without it (spec 7).
function ll --description 'List all files in long format (eza)'
    if command -q eza
        eza -la --icons --group-directories-first --git $argv
    else
        ls -la $argv
    end
end
```

Create `content/fish/functions/lt.fish`:

```fish
# Moonlit Candle (witchy): a two-level tree through eza, or ls -R without it (spec 7).
function lt --description 'Tree of a folder, two levels deep (eza)'
    if command -q eza
        eza --tree --level=2 --icons $argv
    else
        ls -R $argv
    end
end
```

Create `content/fish/conf.d/witchy.fish`:

```fish
# Moonlit Candle (witchy): eza colours, and the sky job that keeps the Windows Terminal moon on tonight's
# phase (spec 4.5, 7). The job starts only when the phase bin differs from the last one it set, and at
# most once a day after a failure.
set -gx EZA_COLORS @EZA_COLORS@

status is-interactive; or exit
set -q WT_SESSION; or exit
test -f @WITCHY_DIR@/ritual-config.json; and test -x @PYTHON@; or exit

set -l cache $HOME/.cache/witchy
set -l stamp
test -r $cache/sky-bin; and read stamp <$cache/sky-bin
test "$stamp" = (_witchy_moon_bin); and exit
set -l failed
test -r $cache/sky-fail; and read failed <$cache/sky-fail
test "$failed" = (date +%F); and exit
@PYTHON@ -I -B @WITCHY_DIR@/ritual --sky >/dev/null 2>&1 &
disown
```

- [ ] **Step 4: Render them**

In `witchy/build.py` (edit 1 of 2), replace:

```python
STATUSLINE_SOURCE = Path(__file__).resolve().parent / "statusline.py"
RITUAL_SOURCE = Path(__file__).resolve().parent / "ritual"
PALETTE_BLOCK = re.compile(r"(# BEGIN PALETTE\n)(.*?)(# END PALETTE\n)", re.DOTALL)
```

with:

```python
STATUSLINE_SOURCE = Path(__file__).resolve().parent / "statusline.py"
RITUAL_SOURCE = Path(__file__).resolve().parent / "ritual"
FISH_SOURCE = content.CONTENT_DIR / "fish"
PALETTE_BLOCK = re.compile(r"(# BEGIN PALETTE\n)(.*?)(# END PALETTE\n)", re.DOTALL)
```

In `witchy/build.py` (edit 2 of 2), replace:

```python
def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
```

with:

```python
# Each eza colour role and the EZA_COLORS codes it sets (eza's colour codes: di directories, ex executables,
# ln symlinks, sn/sb size number/unit, da date, ga/gm/gv/gt/gd git new/modified/renamed/typechange/deleted).
EZA_CODES = {
    "directory": ("di",),
    "executable": ("ex",),
    "symlink": ("ln",),
    "size": ("sn", "sb"),
    "date": ("da",),
    "git_new": ("ga",),
    "git_modified": ("gm",),
    "git_renamed": ("gv",),
    "git_typechange": ("gt",),
    "git_deleted": ("gd",),
}


def eza_colors(colours: dict[str, str]) -> str:
    """EZA_COLORS for ``colours``, in 24-bit colour: ``di=38;2;185;154;255:ex=…``."""
    parts = []
    for role, codes in EZA_CODES.items():
        red, green, blue = (int(colours[role][i:i + 2], 16) for i in (1, 3, 5))
        parts += [f"{code}=38;2;{red};{green};{blue}" for code in codes]
    return ":".join(parts)


def fish_quote(text: str) -> str:
    """``text`` as one fish word: single quotes, with backslashes and single quotes escaped."""
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def fish_files(python: str, witchy_dir: Path, variant: str = palette.DEFAULT_VARIANT,
               source: Path = FISH_SOURCE) -> dict[str, bytes]:
    """The fish functions and conf.d snippet as installed, keyed by their path inside the fish config folder."""
    values = {"@PYTHON@": fish_quote(python), "@WITCHY_DIR@": fish_quote(str(witchy_dir)),
              "@EZA_COLORS@": fish_quote(eza_colors(palette.VARIANTS[variant].eza))}
    files = {}
    for path in sorted(source.rglob("*.fish")):
        text = path.read_text(encoding="utf-8")
        for placeholder, value in values.items():
            text = text.replace(placeholder, value)
        files[path.relative_to(source).as_posix()] = text.encode("utf-8")
    return files


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `/usr/bin/python3 -m unittest tests.test_fish_files -v 2>&1 | tail -5`
Expected: `Ran 22 tests … OK`, with no `skipped`.

- [ ] **Step 6: Run the whole suite on both Pythons, and validate**

Expected: `Ran 424 tests … OK` on both; `Moonlit Candle: all checks passed`.

- [ ] **Step 7: Commit**

```bash
git add content/fish witchy/build.py tests/test_fish_files.py
git commit -m "feat: add the fish greeting, ritual, moon item, ll/lt and sky-job templates

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 4: The `fish` component

**Files:**
- Create: `witchy/components/fish.py`
- Modify: `witchy/components/__init__.py`, `tests/fakes.py`
- Create: `tests/test_components_fish.py`

**Interfaces:**
- Consumes: `Command`, `run_command`, `file_change`, `file_record`, `Plan.commands/prune/outcome`, the runner behaviour (Task 1); `palette.TIDE` / `Variant.tide` (Task 2); `build.fish_files`, `build.ritual_package` (Task 3, Plan C); `claude.python_for`.
- Produces:
  - `fish.FISH = "fish"`, `fish.RITUAL_DIR = Path(".claude/witchy/ritual")`, `fish.NEW_TAB_NOTE`, `fish.NO_EZA_NOTE`, `fish.SENTINEL = "witchy-fish"`
  - `fish.SNAPSHOT_SCRIPT`, `fish.SET_SCRIPT`, `fish.REFRESH_SCRIPT` (fish source strings; `tests.fakes.fake_fish` recognises them by identity)
  - `fish.config_dir(ctx) -> Path`
  - `fish.snapshot(ctx, names: list[str]) -> tuple[bool, dict[str, dict]]` — Tide present, and each variable as `{"absent": True}` or `{"value": [str, …], "exported": bool}`; raises `ComponentFailed` (cause kept)
  - `fish.set_command(updates: list[tuple[str, str, list[str]]], label: str) -> Command` — mode `"set"`, `"exported"` or `"erase"`
  - `fish._fields(stdout: str) -> list[str]` — the NUL-separated fields after the marker
  - `FishComponent` with `name = "fish"`; state entry `{"files": [{"path", "backup", "installed_sha256"}, …], "variables": {name: {"previous": <snapshot>, "installed": [str, …]}}}`; `check()` returns `[]` until Task 5
  - `tests.fakes.fake_fish(variables=None, tide=True, fail_at=None, missing=False, noise="", calls=None)`
  - `components.NAMES == ("claude", "font", "windows-terminal", "fish")`

- [ ] **Step 1: Write the failing tests**

In `tests/fakes.py`, replace:

```python
            archive.writestr(name, data)
    return buffer.getvalue()
```

with:

```python
            archive.writestr(name, data)
    return buffer.getvalue()


def fake_fish(variables=None, tide=True, fail_at=None, missing=False, noise="", calls=None):
    """A ``run`` that answers witchy's two fish scripts the way fish would.

    ``variables`` maps names to ``{"value": [...], "exported": bool}`` and is changed in place by the set
    script. ``fail_at`` names a variable whose set fails (the script stops there, exit 1); ``missing`` makes
    fish absent; ``noise`` is what config.fish prints first. Every call is appended to ``calls``.
    """
    from witchy.components import fish

    store = {} if variables is None else variables

    def answer(args, fields, code=0):
        stdout = noise + "".join(f"{field}\0" for field in [fish.SENTINEL, *fields])
        return subprocess.CompletedProcess(args, code, stdout=stdout, stderr="")

    def run(args, input=None, **kwargs):
        args = list(args)
        if calls is not None:
            calls.append((args, input))
        if missing:
            raise FileNotFoundError(2, "No such file or directory", "fish")
        if args[:3] == ["fish", "-c", fish.SNAPSHOT_SCRIPT] and args[3] == "--":
            fields = ["tide" if tide else "no-tide"]
            for name in args[4:]:
                if name in store:
                    value = store[name]
                    fields += [name, "exported" if value["exported"] else "unexported", str(len(value["value"])),
                               *value["value"]]
                else:
                    fields += [name, "absent"]
            return answer(args, fields)
        if args == ["fish", "-c", fish.SET_SCRIPT]:
            items, done = input.split("\0")[:-1], []
            while items:
                name, mode, count = items[:3]
                values, items = items[3:3 + int(count)], items[3 + int(count):]
                if name == fail_at:
                    return answer(args, done, code=1)
                if mode == "erase":
                    store.pop(name, None)
                else:
                    exported = mode == "exported" or store.get(name, {}).get("exported", False)
                    store[name] = {"value": values, "exported": exported}
                done.append(name)
            return answer(args, done)
        if args == ["fish", "-c", fish.REFRESH_SCRIPT]:
            return subprocess.CompletedProcess(args, 0, stdout=noise, stderr="")
        raise AssertionError(f"unexpected command in a test: {args}")
    return run
```

Create `tests/test_components_fish.py`:

```python
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.fakes import fake_fish
from witchy import build, components, palette, runner
from witchy.components import fish
from witchy.context import Context

# The prompt as Tide's own "lean" setup and the user left it: a pink pwd, an exported variable, no moon.
USER_TIDE = {
    "tide_left_prompt_items": {"value": ["os", "pwd", "git", "newline", "character"], "exported": False},
    "tide_pwd_bg_color": {"value": ["FFB7C5"], "exported": False},
    "tide_time_color": {"value": ["5F8787"], "exported": True},
    "tide_cmd_duration_threshold": {"value": ["3000"], "exported": False},
}


class FishTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.variables = json.loads(json.dumps(USER_TIDE))
        self.calls = []

    def ctx(self, run=None, dry_run=False, env=None, stamp="20261003-120000"):
        self.out = io.StringIO()
        return Context(home=self.home, env={"PATH": "/nowhere"} if env is None else env, out=self.out,
                       dry_run=dry_run, python="/usr/bin/python3", stamp=stamp, dist=self.root / "dist",
                       lock_path=self.root / "witchy.lock", only=("fish",),
                       run=run or fake_fish(self.variables, calls=self.calls))

    def state(self):
        return json.loads((self.home / ".claude" / "witchy" / "state.json").read_text(encoding="utf-8"))

    def entry(self):
        return self.state()["components"]["fish"]

    def files(self):
        config = self.home / ".config" / "fish"
        ritual = self.home / ".claude" / "witchy" / "ritual"
        return {**{config / name: data for name, data in build.fish_files("/usr/bin/python3",
                                                                           self.home / ".claude" / "witchy").items()},
                **{ritual / name: data for name, data in build.ritual_package().items()}}

    def set_calls(self):
        return [input for args, input in self.calls if args == ["fish", "-c", fish.SET_SCRIPT]]

    def value(self, name):
        return self.variables.get(name, {}).get("value")


class InstallTest(FishTestCase):
    def test_installs_the_files_and_recolours_tide(self):
        self.assertEqual(runner.install(self.ctx()), 0)
        for path, data in self.files().items():
            self.assertEqual(path.read_bytes(), data, path)
        self.assertEqual(self.value("tide_left_prompt_items"), ["moon", "pwd", "git", "newline", "character"])
        self.assertEqual(self.value("tide_moon_color"), ["FFD477"])
        self.assertEqual(self.variables["tide_time_color"], {"value": ["A99AB9"], "exported": True})
        self.assertEqual(len(self.set_calls()), 1)
        self.assertIn(fish.NEW_TAB_NOTE, self.out.getvalue())

    def test_records_what_each_variable_held_before(self):
        runner.install(self.ctx())
        variables = self.entry()["variables"]
        self.assertEqual(set(variables), set(palette.TIDE))
        self.assertEqual(variables["tide_pwd_bg_color"], {"previous": {"value": ["FFB7C5"], "exported": False},
                                                          "installed": ["B99AFF"]})
        self.assertEqual(variables["tide_moon_color"]["previous"], {"absent": True})
        self.assertEqual(variables["tide_time_color"]["previous"]["exported"], True)
        self.assertEqual(len(self.entry()["files"]), len(self.files()))

    def test_a_variable_that_already_holds_the_value_is_not_set_again(self):
        runner.install(self.ctx())
        sent = self.set_calls()[0].split("\0")
        self.assertNotIn("tide_cmd_duration_threshold", sent)
        self.assertEqual(self.entry()["variables"]["tide_cmd_duration_threshold"]["installed"], ["3000"])

    def test_values_are_sent_on_standard_input_never_in_a_shell_string(self):
        runner.install(self.ctx())
        args = [args for args, _ in self.calls]
        self.assertTrue(all(arg[:2] == ["fish", "-c"] for arg in args))
        self.assertTrue(all("B99AFF" not in " ".join(arg) for arg in args))
        self.assertIn("tide_pwd_bg_color\0set\0" "1\0B99AFF\0", self.set_calls()[0])

    def test_without_tide_the_files_still_install(self):
        code = runner.install(self.ctx(run=fake_fish(self.variables, tide=False, calls=self.calls)))
        self.assertEqual(code, 2)
        self.assertEqual(self.set_calls(), [])
        self.assertEqual(self.entry()["variables"], {})
        self.assertTrue((self.home / ".config" / "fish" / "functions" / "fish_greeting.fish").is_file())
        self.assertEqual(self.state()["last_install"]["results"], {"fish": "skipped: Tide not found"})
        self.assertIn("fish: Tide not found; prompt not recoloured.", self.out.getvalue())

    def test_without_fish_the_files_still_install(self):
        self.assertEqual(runner.install(self.ctx(run=fake_fish(missing=True))), 2)
        self.assertEqual(self.state()["last_install"]["results"], {"fish": "skipped: fish not found"})
        self.assertTrue((self.home / ".claude" / "witchy" / "ritual" / "cli.py").is_file())

    def test_a_failed_set_stops_and_records_only_what_was_set(self):
        run = fake_fish(self.variables, fail_at="tide_pwd_bg_color", calls=self.calls)
        self.assertEqual(runner.install(self.ctx(run=run)), 2)
        variables = self.entry()["variables"]
        self.assertIn("tide_moon_color", variables)  # set before the failure
        self.assertNotIn("tide_pwd_bg_color", variables)
        self.assertNotIn("tide_time_color", variables)  # never reached
        self.assertIn("tide_cmd_duration_threshold", variables)  # needed no change
        self.assertEqual(self.value("tide_pwd_bg_color"), ["FFB7C5"])
        self.assertEqual(self.state()["last_install"]["results"], {"fish": "failed: could not set tide_pwd_bg_color"})

    def test_a_fish_that_times_out_while_setting_keeps_the_files_recorded(self):
        answers = fake_fish(self.variables)

        def run(args, **kwargs):
            if args == ["fish", "-c", fish.SET_SCRIPT]:
                raise subprocess.TimeoutExpired(args, 5)
            return answers(args, **kwargs)

        self.assertEqual(runner.install(self.ctx(run=run)), 2)
        self.assertEqual(len(self.entry()["files"]), len(self.files()))
        self.assertEqual(self.state()["last_install"]["results"]["fish"], "failed: could not set tide_left_prompt_items")

    def test_what_config_fish_prints_is_ignored(self):
        run = fake_fish(self.variables, noise="Welcome!\n\0stray\0", calls=self.calls)
        self.assertEqual(runner.install(self.ctx(run=run)), 0)
        self.assertEqual(self.entry()["variables"]["tide_pwd_bg_color"]["previous"]["value"], ["FFB7C5"])

    def test_reinstall_keeps_the_first_previous_value(self):
        runner.install(self.ctx())
        with mock.patch.dict(palette.TIDE, {"tide_pwd_bg_color": "D0B8FF"}):
            self.assertEqual(runner.install(self.ctx(stamp="20261003-130000")), 0)
        record = self.entry()["variables"]["tide_pwd_bg_color"]
        self.assertEqual(record, {"previous": {"value": ["FFB7C5"], "exported": False}, "installed": ["D0B8FF"]})
        self.assertEqual(self.value("tide_pwd_bg_color"), ["D0B8FF"])

    def test_a_reinstall_that_cannot_ask_fish_keeps_the_recorded_variables(self):
        runner.install(self.ctx())
        recorded = self.entry()["variables"]
        self.assertEqual(runner.install(self.ctx(run=fake_fish(missing=True), stamp="20261003-130000")), 2)
        self.assertEqual(self.entry()["variables"], recorded)
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-140000")), 0)
        self.assertEqual(self.variables, USER_TIDE)

    def test_reinstall_without_changes_sets_nothing(self):
        runner.install(self.ctx())
        self.calls.clear()
        self.assertEqual(runner.install(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.set_calls(), [])

    def test_dry_run_reads_but_never_writes(self):
        self.assertEqual(runner.install(self.ctx(dry_run=True)), 0)
        self.assertEqual(self.set_calls(), [])
        self.assertFalse((self.home / ".config").exists())
        self.assertEqual(self.variables, USER_TIDE)
        self.assertIn("fish: set -U tide_pwd_bg_color B99AFF (now: FFB7C5)", self.out.getvalue())
        self.assertIn("fish: set -Ux tide_time_color A99AB9 (now: 5F8787)", self.out.getvalue())
        self.assertIn("fish: set -U tide_moon_color FFD477 (now: unset)", self.out.getvalue())

    def test_fish_config_follows_xdg_config_home(self):
        env = {"PATH": "/nowhere", "XDG_CONFIG_HOME": str(self.root / "xdg")}
        self.assertEqual(runner.install(self.ctx(env=env)), 0)
        self.assertTrue((self.root / "xdg" / "fish" / "conf.d" / "witchy.fish").is_file())
        self.assertFalse((self.home / ".config").exists())

    def test_eza_missing_is_noted(self):
        runner.install(self.ctx())
        self.assertIn(fish.NO_EZA_NOTE, self.out.getvalue())
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        (bin_dir / "eza").write_text("#!/bin/sh\n", encoding="utf-8")
        (bin_dir / "eza").chmod(0o755)
        runner.install(self.ctx(env={"PATH": str(bin_dir)}, stamp="20261003-130000"))
        self.assertNotIn(fish.NO_EZA_NOTE, self.out.getvalue())

    def test_fish_is_a_component_name(self):
        self.assertEqual(components.NAMES, ("claude", "font", "windows-terminal", "fish"))


class UninstallTest(FishTestCase):
    def test_gives_back_every_variable_and_removes_the_files(self):
        runner.install(self.ctx())
        self.calls.clear()
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.variables, USER_TIDE)
        # Read, restore, then rebuild Tide's item cache, all before any file goes.
        self.assertEqual([args[2] for args, _ in self.calls],
                         [fish.SNAPSHOT_SCRIPT, fish.SET_SCRIPT, fish.REFRESH_SCRIPT])
        for path in self.files():
            self.assertFalse(path.exists(), path)
        self.assertFalse((self.home / ".claude" / "witchy").exists())

    def test_a_users_own_function_comes_back(self):
        mine = self.home / ".config" / "fish" / "functions" / "ll.fish"
        mine.parent.mkdir(parents=True)
        mine.write_text("function ll; ls -lh $argv; end\n", encoding="utf-8")
        runner.install(self.ctx())
        self.assertIn(b"eza -la", mine.read_bytes())
        runner.uninstall(self.ctx(stamp="20261003-130000"))
        self.assertEqual(mine.read_text(encoding="utf-8"), "function ll; ls -lh $argv; end\n")

    def test_a_variable_the_user_changed_is_left_with_a_warning(self):
        runner.install(self.ctx())
        self.variables["tide_pwd_bg_color"] = {"value": ["123456"], "exported": False}
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.value("tide_pwd_bg_color"), ["123456"])
        self.assertIn("tide_pwd_bg_color was changed after install; leaving it as it is.", self.out.getvalue())
        self.assertEqual(self.value("tide_time_color"), ["5F8787"])

    def test_a_retry_after_a_partial_restore_is_silent(self):
        runner.install(self.ctx())
        self.variables["tide_pwd_bg_color"] = USER_TIDE["tide_pwd_bg_color"]  # already given back
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        self.assertNotIn("changed after install", self.out.getvalue())
        self.assertEqual(self.variables, USER_TIDE)

    def test_a_failed_restore_keeps_everything_for_a_retry(self):
        runner.install(self.ctx())
        failing = fake_fish(self.variables, fail_at="tide_moon_color")
        self.assertEqual(runner.uninstall(self.ctx(run=failing, stamp="20261003-130000")), 2)
        self.assertIn("fish: could not restore", self.out.getvalue())
        self.assertTrue((self.home / ".config" / "fish" / "functions" / "_tide_item_moon.fish").is_file())
        self.assertIn("fish", self.state()["components"])
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-131000")), 0)
        self.assertEqual(self.variables, USER_TIDE)

    def test_a_fish_that_does_not_answer_keeps_the_component(self):
        runner.install(self.ctx())

        def run(args, **kwargs):
            raise subprocess.TimeoutExpired(args, 5)

        self.assertEqual(runner.uninstall(self.ctx(run=run, stamp="20261003-130000")), 2)
        self.assertIn("fish: could not read the Tide variables", self.out.getvalue())
        self.assertTrue((self.home / ".claude" / "witchy" / "ritual" / "cli.py").is_file())

    def test_without_fish_the_files_still_go(self):
        runner.install(self.ctx())
        self.assertEqual(runner.uninstall(self.ctx(run=fake_fish(missing=True), stamp="20261003-130000")), 0)
        self.assertIn("fish not found; the Tide variables were left as they are.", self.out.getvalue())
        self.assertFalse((self.home / ".claude" / "witchy" / "ritual").exists())

    def test_installed_without_tide_uninstalls_without_fish_calls(self):
        runner.install(self.ctx(run=fake_fish(self.variables, tide=False)))
        self.calls.clear()
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.calls, [])

    def test_dry_run_lists_the_restore_and_changes_nothing(self):
        runner.install(self.ctx())
        installed = json.loads(json.dumps(self.variables))
        self.assertEqual(runner.uninstall(self.ctx(dry_run=True, stamp="20261003-130000")), 0)
        self.assertIn(f"fish: restore {len(palette.TIDE) - 1} Tide variables", self.out.getvalue())
        self.assertEqual(self.variables, installed)
        self.assertTrue((self.home / ".claude" / "witchy" / "ritual" / "cli.py").is_file())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_components_fish`
Expected: `FAILED (errors=1)` — `ImportError: cannot import name 'fish' from 'witchy.components'`.

- [ ] **Step 3: Implement**

Create `witchy/components/fish.py`:

```python
"""fish: the greeting package, the fish functions and conf.d snippet, and the Tide prompt colours (spec 5, 6, 7)."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .. import build, palette
from .base import (Check, Command, ComponentFailed, Plan, apply_changes, file_change, file_record, restore_copy,
                   run_command)
from .claude import python_for

FISH = "fish"
RITUAL_DIR = Path(".claude/witchy/ritual")
NEW_TAB_NOTE = "Open a new terminal tab to see the new prompt and greeting; open shells keep the old ones."
NO_EZA_NOTE = "eza is not installed, so ll and lt use ls; install it with: sudo apt install eza"
SENTINEL = "witchy-fish"  # whatever config.fish prints comes before it

# Prints the sentinel, whether Tide is installed, then each name's universal value: the name, "absent" or
# "exported"/"unexported", the element count and the elements. Every field ends in NUL, which no fish
# value can hold.
SNAPSHOT_SCRIPT = """\
printf '%s\\0' witchy-fish
functions -q tide; and printf 'tide\\0'; or printf 'no-tide\\0'
for name in $argv
    set -e -g $name  # a global set by config.fish would hide the universal value
    if set -q -U $name
        set -l flag unexported
        set -q -U -x $name; and set flag exported
        printf '%s\\0' $name $flag (count $$name) $$name
    else
        printf '%s\\0' $name absent
    end
end
"""

# Reads records from standard input (name, mode, element count, elements; NUL-terminated fields), sets or
# erases each universal variable, and prints each name once it is done. It stops at the first failure.
SET_SCRIPT = """\
printf '%s\\0' witchy-fish
while read -z -l name
    read -z -l mode
    read -z -l count
    set -l values
    while test $count -gt 0
        read -z -l value
        set -a values $value
        set count (math $count - 1)
    end
    switch $mode
        case erase
            if set -q -U $name
                set -e -U $name
            end
        case exported
            set -U -x $name $values
        case '*'
            set -U $name $values
    end
    or exit 1
    printf '%s\\0' $name
end
"""


# Tide caches the usable items (_tide_left_items, _tide_right_items) when a shell starts. Rebuilding that cache
# right after a restore stops open shells from calling the moon item once its function is gone.
REFRESH_SCRIPT = """\
if functions -q _tide_remove_unusable_items
    _tide_remove_unusable_items
end
"""


def config_dir(ctx: Any) -> Path:
    """fish's own rule: $XDG_CONFIG_HOME/fish, else ~/.config/fish."""
    base = ctx.env.get("XDG_CONFIG_HOME")
    return Path(base) / "fish" if base else ctx.home / ".config" / "fish"


def _fields(stdout: str) -> list[str]:
    head, found, rest = stdout.partition(SENTINEL + "\0")
    if not found:
        raise ValueError("fish printed no answer")
    return rest.split("\0")[:-1]


def snapshot(ctx: Any, names: list[str]) -> tuple[bool, dict[str, dict]]:
    """Whether Tide is installed, and each variable as ``{"absent": True}`` or ``{"value": [...], "exported": bool}``."""
    done = run_command(ctx, Command((FISH, "-c", SNAPSHOT_SCRIPT, "--", *names), "read the Tide variables"))
    try:
        fields = _fields(done.stdout)
        tide, index, found = fields[0] == "tide", 1, {}
        while index < len(fields):
            name, flag = fields[index], fields[index + 1]
            if flag == "absent":
                found[name], index = {"absent": True}, index + 2
                continue
            count = int(fields[index + 2])
            found[name] = {"value": fields[index + 3:index + 3 + count], "exported": flag == "exported"}
            index += 3 + count
        return tide, {name: found[name] for name in names}
    except (ValueError, IndexError, KeyError) as exc:
        raise ComponentFailed(f"could not read the Tide variables ({exc})") from exc


def set_command(updates: list[tuple[str, str, list[str]]], label: str) -> Command:
    """One fish call that applies each (name, mode, values); mode is "set", "exported" or "erase"."""
    fields = [field for name, mode, values in updates for field in (name, mode, str(len(values)), *values)]
    return Command((FISH, "-c", SET_SCRIPT), label, "".join(f"{field}\0" for field in fields))


def _values(value: str | tuple[str, ...]) -> list[str]:
    return [value] if isinstance(value, str) else list(value)


class FishComponent:
    name = "fish"

    def plan(self, ctx: Any, entry: dict | None) -> Plan:
        variant = ctx.variant or palette.DEFAULT_VARIANT
        witchy_dir = ctx.claude_dir / "witchy"
        targets = {ctx.home / RITUAL_DIR / name: data for name, data in build.ritual_package(variant).items()}
        folder = config_dir(ctx)
        targets.update({folder / name: data for name, data in build.fish_files(python_for(ctx), witchy_dir,
                                                                               variant).items()})
        earlier = {Path(record["path"]): record for record in (entry or {}).get("files", [])}
        changes = [file_change(path, data, earlier) for path, data in targets.items()]
        notes = [NEW_TAB_NOTE] + ([] if shutil.which("eza", path=ctx.env.get("PATH")) else [NO_EZA_NOTE])
        # What earlier installs recorded stays recorded even when fish cannot be asked this time.
        recorded = (entry or {}).get("variables", {})
        plan = Plan(changes=changes, notes=notes, data={"earlier": earlier, "recorded": recorded, "records": {},
                                                        "updates": []})
        desired = {name: _values(value) for name, value in palette.VARIANTS[variant].tide.items()}
        try:
            tide, current = snapshot(ctx, list(desired))
        except ComponentFailed as exc:
            missing = isinstance(exc.__cause__, FileNotFoundError)
            plan.outcome = "skipped: fish not found" if missing else f"skipped: {exc}"
            ctx.say(f"fish: {'fish not found' if missing else exc}; prompt not recoloured.")
            return plan
        if not tide:
            plan.outcome = "skipped: Tide not found"
            ctx.say("fish: Tide not found; prompt not recoloured.")
            return plan
        records, updates = {}, []
        for name, values in desired.items():
            # A reinstall keeps the value from before the first install, not witchy's own.
            previous = recorded[name]["previous"] if name in recorded else current[name]
            records[name] = {"previous": previous, "installed": values}
            if current[name].get("value") != values:
                updates.append((name, "exported" if previous.get("exported") else "set", values))
        plan.data.update(records=records, updates=updates)
        plan.actions = [f"fish: set -U{'x' if mode == 'exported' else ''} {name} {' '.join(values)} "
                        f"(now: {' '.join(current[name]['value']) if 'value' in current[name] else 'unset'})"
                        for name, mode, values in updates]
        return plan

    def apply(self, ctx: Any, plan: Plan) -> dict:
        try:
            backups = apply_changes(ctx, plan.changes)
        except OSError as exc:
            raise ComponentFailed(f"could not write the fish files ({exc})") from exc
        earlier = plan.data["earlier"]
        files = [file_record(change, earlier, backups) for change in plan.changes]
        shipped = {change.path for change in plan.changes}
        # A file an earlier version shipped stays recorded, so uninstall still removes it.
        files += [record for path, record in earlier.items() if path not in shipped]
        variables = dict(plan.data["recorded"])
        updates = plan.data["updates"]
        done: set[str] = set()
        if updates:
            # After the files: the moon item must exist before Tide is told to show it (spec 5.3).
            try:
                result = run_command(ctx, set_command(updates, f"set {len(updates)} Tide variables"), check=False)
                done = set(_fields(result.stdout))
                ok = result.returncode == 0
            except (ComponentFailed, ValueError):
                ok = False
            if not ok:
                stopped = next((name for name, _, _ in updates if name not in done), updates[-1][0])
                plan.outcome = f"failed: could not set {stopped}"
                ctx.say(f"fish: could not set {stopped}; the Tide variables after it were not set.")
        pending = {name for name, _, _ in updates} - done
        variables.update({name: record for name, record in plan.data["records"].items() if name not in pending})
        return {"files": files, "variables": variables}

    def restore(self, ctx: Any, entry: dict) -> Plan:
        warnings: list[str] = []
        commands: list[Command] = []
        variables = entry.get("variables") or {}
        if variables:
            try:
                _, current = snapshot(ctx, list(variables))
            except ComponentFailed as exc:
                if not isinstance(exc.__cause__, FileNotFoundError):
                    raise  # fish is there but did not answer: keep the component and retry later
                warnings.append("fish: fish not found; the Tide variables were left as they are.")
                current = {}
            undo = []
            for name, record in variables.items():
                if name not in current or current[name] == record["previous"]:
                    continue  # fish is gone, or this one was already given back by an earlier attempt
                if current[name].get("value") != record["installed"]:
                    warnings.append(f"{name} was changed after install; leaving it as it is.")
                    continue
                previous = record["previous"]
                if previous.get("absent"):
                    undo.append((name, "erase", []))
                else:
                    undo.append((name, "exported" if previous["exported"] else "set", previous["value"]))
            if undo:
                commands += [set_command(undo, f"restore {len(undo)} Tide variables"),
                             Command((FISH, "-c", REFRESH_SCRIPT), "refresh Tide's prompt items")]
        changes = [change for change in (restore_copy(record) for record in entry["files"]) if change is not None]
        # The variables go back first, so no prompt asks for the moon item once its function is gone.
        return Plan(changes=changes, commands=commands, warnings=warnings, prune=[ctx.home / RITUAL_DIR])

    def check(self, ctx: Any, entry: dict) -> list[Check]:
        return []  # the doctor lines come with Task 5
```

In `witchy/components/__init__.py` (edit 1 of 2), replace:

```python
from .claude import ClaudeComponent
from .font import FontComponent
from .windows_terminal import WindowsTerminalComponent
```

with:

```python
from .claude import ClaudeComponent
from .fish import FishComponent
from .font import FontComponent
from .windows_terminal import WindowsTerminalComponent
```

In `witchy/components/__init__.py` (edit 2 of 2), replace:

```python
def all_components() -> list:
    return [ClaudeComponent(), FontComponent(), WindowsTerminalComponent()]
```

with:

```python
def all_components() -> list:
    return [ClaudeComponent(), FontComponent(), WindowsTerminalComponent(), FishComponent()]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/usr/bin/python3 -m unittest tests.test_components_fish`
Expected: `Ran 25 tests … OK`.

- [ ] **Step 5: Run the whole suite on both Pythons, and validate**

Expected: `Ran 449 tests … OK` on both; `Moonlit Candle: all checks passed`.

- [ ] **Step 6: A read-only dry run on the real machine**

Run: `/usr/bin/python3 -m witchy install --dry-run --only fish | grep -v '^[-+ @]' | tail -40`
Expected: `create` lines for the 13 files under `~/.claude/witchy/ritual/` and the 7 fish files, 31 lines like `fish: set -U tide_pwd_bg_color B99AFF (now: FFB7C5)` (`tide_cmd_duration_threshold` already holds `3000`), then `Dry run: nothing was written.`; exit 0. Paste the output into the task report. This reads fish variables and writes nothing.

- [ ] **Step 7: Commit**

```bash
git add witchy/components/fish.py witchy/components/__init__.py tests/fakes.py tests/test_components_fish.py
git commit -m "feat: add the fish component: greeting package, fish files and Tide colours

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 5: The fish doctor lines

**Files:**
- Modify: `witchy/components/fish.py`, `tests/test_components_fish.py`

**Interfaces:**
- Consumes: `FishComponent`, `snapshot` (Task 4); `ritual.log.NAME`, `ritual.sky.FAIL` (Plan C); `base.backup_checks`, `fix_command`, `read`, `sha`; `ctx.now`, `ctx.cache_dir`.
- Produces:
  - `fish.EZA_FIX = "sudo apt install eza"`, `fish.RECENT = timedelta(days=7)`, `fish.MESSAGE_MAX = 100`, `fish.LOG_LINE`
  - `fish.log_checks(ctx) -> list[Check]`
  - `FishComponent.check(ctx, entry)` — in order: files match / changed; Tide variables match / changed (warn when fish does not answer); eza found / missing; the greeting and sky lines; missing backups. Lines use the component name `fish`, messages starting `greeting:` and `sky:` (spec 9).

- [ ] **Step 1: Write the failing tests**

In `tests/test_components_fish.py` (edit 1 of 2), replace:

```python
import json
import subprocess
import tempfile
import unittest
```

with:

```python
import json
import subprocess
from datetime import datetime
import tempfile
import unittest
```

In `tests/test_components_fish.py` (edit 2 of 2), replace:

```python
if __name__ == "__main__":
    unittest.main()
```

with:

```python
class DoctorTest(FishTestCase):
    NOW = datetime(2026, 10, 3, 21, 0)

    def doctor(self, run=None, env=None):
        ctx = self.ctx(run=run, env=env)
        ctx.now = lambda: self.NOW
        code = runner.doctor(ctx, [fish.FishComponent()])
        return code, self.out.getvalue()

    def log(self, *lines):
        path = self.home / ".cache" / "witchy" / "ritual.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")

    def test_a_healthy_install(self):
        runner.install(self.ctx())
        code, output = self.doctor()
        self.assertEqual(code, 0)
        self.assertIn(f"✓ fish              {len(self.files())} files match", output)
        self.assertIn(f"✓ fish              {len(palette.TIDE)} Tide variables match", output)
        self.assertIn("✓ fish              no greeting or sky errors in the last 7 days", output)

    def test_a_changed_file_and_a_changed_variable_fail(self):
        runner.install(self.ctx())
        (self.home / ".config" / "fish" / "functions" / "ll.fish").write_text("function ll; end\n", encoding="utf-8")
        self.variables["tide_pwd_bg_color"]["value"] = ["123456"]
        code, output = self.doctor()
        self.assertEqual(code, 1)
        self.assertIn("✗ fish              changed or missing: ", output)
        self.assertIn("ll.fish", output)
        self.assertIn("✗ fish              Tide variables changed: tide_pwd_bg_color", output)
        self.assertIn("fix: python3 -m witchy install --only fish", output)

    def test_fish_that_does_not_answer_is_a_warning(self):
        runner.install(self.ctx())
        code, output = self.doctor(run=fake_fish(missing=True))
        self.assertEqual(code, 0)
        self.assertIn("⚠ fish              cannot check the Tide variables: could not read the Tide variables", output)

    def test_eza(self):
        runner.install(self.ctx())
        self.assertIn("⚠ fish              eza missing — sudo apt install eza", self.doctor()[1])
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        (bin_dir / "eza").write_text("#!/bin/sh\n", encoding="utf-8")
        (bin_dir / "eza").chmod(0o755)
        self.assertIn("✓ fish              eza found", self.doctor(env={"PATH": str(bin_dir)})[1])

    def test_the_newest_greeting_error_of_the_week(self):
        runner.install(self.ctx())
        self.log("2026-10-01T08:00:00 greeting: OldError()",
                 "2026-10-03T09:14:00 greeting: KeyError('name')",
                 "2026-10-02T23:59:00 sky: older than the greeting line but still recent")
        output = self.doctor()[1]
        self.assertIn("⚠ fish              greeting: last run failed today at 09:14: KeyError('name')", output)
        self.assertIn("⚠ fish              sky: last run failed yesterday: older than the greeting line", output)
        self.assertNotIn("OldError", output)

    def test_errors_older_than_a_week_are_history(self):
        runner.install(self.ctx())
        self.log("2026-09-20T09:14:00 greeting: KeyError('name')", "2026-09-26T21:00:00 sky: boom")
        output = self.doctor()[1]
        self.assertNotIn("KeyError", output)
        self.assertIn("no greeting or sky errors in the last 7 days", output)

    def test_long_messages_are_cut(self):
        runner.install(self.ctx())
        self.log("2026-10-03T09:14:00 greeting: UnicodeEncodeError(" + "x" * 300 + ")")
        line = next(line for line in self.doctor()[1].splitlines() if "greeting:" in line)
        self.assertTrue(line.endswith("…"))
        self.assertLess(len(line), 170)

    def test_the_sky_fail_marker(self):
        runner.install(self.ctx())
        self.log("2026-10-03T08:00:00 sky: backgroundImage was changed by hand ('C:/me.png'); leaving it")
        (self.home / ".cache" / "witchy" / "sky-fail").write_text("2026-10-03\n", encoding="utf-8")
        output = self.doctor()[1]
        self.assertIn("sky: last run failed today at 08:00: backgroundImage was changed by hand ('C:/me.png'); "
                      "leaving it (it retries tomorrow)", output)
        self.assertIn("fix: python3 -m witchy install --only windows-terminal", output)
        (self.home / ".cache" / "witchy" / "ritual.log").unlink()
        self.assertIn("⚠ fish              sky: the sky job failed today (it retries tomorrow)", self.doctor()[1])

    def test_damaged_log_lines_are_skipped(self):
        runner.install(self.ctx())
        self.log("2026-10-03T09:14:00 greeting: KeyError('name')", "2026-13-03T09:15:00 greeting: bad month",
                 "not a log line")
        path = self.home / ".cache" / "witchy" / "ritual.log"
        path.write_bytes(path.read_bytes() + b"\xff\xfe broken bytes\n")
        output = self.doctor()[1]
        self.assertNotIn("check crashed", output)
        self.assertIn("greeting: last run failed today at 09:14: KeyError('name')", output)

    def test_an_aware_now_compares_with_the_local_log(self):
        runner.install(self.ctx())
        self.log("2026-10-03T09:14:00 greeting: KeyError('name')")
        ctx = self.ctx()
        ctx.now = lambda: self.NOW.astimezone()
        runner.doctor(ctx, [fish.FishComponent()])
        self.assertIn("greeting: last run failed today at 09:14", self.out.getvalue())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_components_fish`
Expected: `FAILED (failures=9, errors=1)` — all ten `DoctorTest` tests, because `check()` still returns `[]` (`test_long_messages_are_cut` errors with `StopIteration`); the 25 Task 4 tests still pass.

- [ ] **Step 3: Implement**

In `witchy/components/fish.py` (edit 1 of 4), replace:

```python
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .. import build, palette
from .base import (Check, Command, ComponentFailed, Plan, apply_changes, file_change, file_record, restore_copy,
                   run_command)
from .claude import python_for
```

with:

```python
from __future__ import annotations

import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .. import build, palette
from ..ritual import log, sky
from .base import (Check, Command, ComponentFailed, Plan, apply_changes, backup_checks, file_change, file_record,
                   fix_command, read, restore_copy, run_command, sha)
from .claude import python_for
```

In `witchy/components/fish.py` (edit 2 of 4), replace:

```python
NO_EZA_NOTE = "eza is not installed, so ll and lt use ls; install it with: sudo apt install eza"
SENTINEL = "witchy-fish"  # whatever config.fish prints comes before it

# Prints the sentinel, whether Tide is installed, then each name's universal value: the name, "absent" or
```

with:

```python
NO_EZA_NOTE = "eza is not installed, so ll and lt use ls; install it with: sudo apt install eza"
SENTINEL = "witchy-fish"  # whatever config.fish prints comes before it
EZA_FIX = "sudo apt install eza"
RECENT = timedelta(days=7)  # older greeting and sky errors are history, not a warning
MESSAGE_MAX = 100
LOG_LINE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d) (greeting|sky): (.*)$")

# Prints the sentinel, whether Tide is installed, then each name's universal value: the name, "absent" or
```

In `witchy/components/fish.py` (edit 3 of 4), replace:

```python
def _values(value: str | tuple[str, ...]) -> list[str]:
    return [value] if isinstance(value, str) else list(value)
```

with:

```python
def _values(value: str | tuple[str, ...]) -> list[str]:
    return [value] if isinstance(value, str) else list(value)


def _last_errors(path: Path) -> dict[str, tuple[datetime, str]]:
    """The newest "greeting" and "sky" lines of ritual.log: when, and what."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    found = {}
    for line in lines:
        match = LOG_LINE.match(line)
        try:
            if match:
                found[match.group(2)] = (datetime.fromisoformat(match.group(1)), match.group(3))
        except ValueError:
            continue  # a damaged line (say, month 13) is skipped, not a doctor crash
    return found


def _when(stamp: datetime, now: datetime) -> str:
    days = (now.date() - stamp.date()).days
    return f"today at {stamp:%H:%M}" if days <= 0 else "yesterday" if days == 1 else f"{days} days ago"


def _short(message: str) -> str:
    return message if len(message) <= MESSAGE_MAX else message[:MESSAGE_MAX - 1] + "…"


def log_checks(ctx: Any) -> list[Check]:
    """Doctor lines for the greeting and the sky job: their newest error from the last week, and the fail marker."""
    path = ctx.cache_dir / log.NAME
    now = ctx.now()
    if now.tzinfo is not None:
        now = now.astimezone().replace(tzinfo=None)  # the log holds local wall-clock times
    errors = {kind: found for kind, found in _last_errors(path).items() if now - found[0] < RECENT}
    checks = []
    if "greeting" in errors:
        stamp, message = errors["greeting"]
        checks.append(Check("warn", "fish", f"greeting: last run failed {_when(stamp, now)}: {_short(message)}",
                            f"see {path}"))
    try:
        failed_today = (ctx.cache_dir / sky.FAIL).read_text(encoding="utf-8").strip() == now.date().isoformat()
    except (OSError, ValueError):
        failed_today = False
    retry = " (it retries tomorrow)" if failed_today else ""
    if "sky" in errors:
        stamp, message = errors["sky"]
        checks.append(Check("warn", "fish", f"sky: last run failed {_when(stamp, now)}: {_short(message)}{retry}",
                            fix_command("windows-terminal")))
    elif failed_today:
        checks.append(Check("warn", "fish", f"sky: the sky job failed today{retry}", f"see {path}"))
    if not checks:
        checks.append(Check("ok", "fish", "no greeting or sky errors in the last 7 days"))
    return checks
```

In `witchy/components/fish.py` (edit 4 of 4), replace:

```python
    def check(self, ctx: Any, entry: dict) -> list[Check]:
        return []  # the doctor lines come with Task 5
```

with:

```python
    def check(self, ctx: Any, entry: dict) -> list[Check]:
        fix = fix_command(self.name)
        changed = [record["path"] for record in entry["files"]
                   if sha(read(Path(record["path"]))) != record["installed_sha256"]]
        checks = [Check("fail", self.name, "changed or missing: " + ", ".join(changed), fix) if changed
                  else Check("ok", self.name, f"{len(entry['files'])} files match")]
        variables = entry.get("variables") or {}
        if variables:
            try:
                _, current = snapshot(ctx, list(variables))
            except ComponentFailed as exc:
                checks.append(Check("warn", self.name, f"cannot check the Tide variables: {exc}"))
            else:
                drift = [name for name, record in variables.items() if current[name].get("value") != record["installed"]]
                checks.append(Check("fail", self.name, "Tide variables changed: " + ", ".join(drift), fix) if drift
                              else Check("ok", self.name, f"{len(variables)} Tide variables match"))
        if shutil.which("eza", path=ctx.env.get("PATH")):
            checks.append(Check("ok", self.name, "eza found"))
        else:
            checks.append(Check("warn", self.name, f"eza missing — {EZA_FIX}", EZA_FIX))
        checks += log_checks(ctx)
        return checks + backup_checks(self.name, [record.get("backup") for record in entry["files"]])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/usr/bin/python3 -m unittest tests.test_components_fish`
Expected: `Ran 35 tests … OK`.

- [ ] **Step 5: Run the whole suite on both Pythons, and doctor (read-only)**

Run both suites, then `/usr/bin/python3 -m witchy doctor`.
Expected: `Ran 459 tests … OK` on both. Doctor on the real machine (fish not installed yet) prints `⚠ fish              not installed` with `fix: python3 -m witchy install --only fish`, besides the lines it printed before this plan.

- [ ] **Step 6: Commit**

```bash
git add witchy/components/fish.py tests/test_components_fish.py
git commit -m "feat: doctor checks the fish files, Tide colours, eza and the last greeting and sky errors

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 6: Real-fish round trip, the all-component round trip, and the docs

**Files:**
- Create: `tests/test_fish_integration.py`
- Modify: `tests/test_install.py`, `README.md`, `docs/superpowers/specs/2026-10-02-shell-ritual-design.md`, `.github/workflows/tests.yml`

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces: no new code. These tests pin behaviour the earlier tasks built (spec 12 `fish` integration and `round trip` rows); they pass as soon as they are written. A failure means a bug in Tasks 1–5: debug it with superpowers:systematic-debugging, do not loosen the test. They were checked against four deliberate breakages of `fish.py` (no global erase, no prune, no export, no marker), each of which they catch.

- [ ] **Step 1: Write the tests**

Create `tests/test_fish_integration.py`:

```python
import io
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from witchy import palette, runner
from witchy.components import fish
from witchy.components.base import run_command
from witchy.context import Context

FISH = shutil.which("fish")
# What a user's Tide set-up looks like before witchy: a few colours of their own, one exported variable,
# a config.fish that prints something and sets a global that would hide a universal value.
BEFORE = """\
set -U tide_left_prompt_items os pwd git newline character
set -U tide_pwd_bg_color FFB7C5
set -Ux tide_time_color 5F8787
set -U tide_cmd_duration_threshold 3000
"""
CONFIG = """\
echo "hello from config.fish"
set -g tide_pwd_bg_color 000000
"""


@unittest.skipUnless(FISH, "fish is not installed")
class RealFishRoundTripTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.config = self.root / "config" / "fish"
        (self.config / "functions").mkdir(parents=True)
        (self.config / "functions" / "tide.fish").write_text("function tide\nend\n", encoding="utf-8")
        # Tide's own cache of usable items, rebuilt when a shell starts (a stand-in with the same effect).
        (self.config / "functions" / "_tide_remove_unusable_items.fish").write_text(
            "function _tide_remove_unusable_items\n    set -U _tide_left_items $tide_left_prompt_items\nend\n",
            encoding="utf-8")
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config.parent), "PATH": "/usr/bin:/bin"}
        self.fish(BEFORE)
        (self.config / "config.fish").write_text(CONFIG, encoding="utf-8")

    def fish(self, script):
        done = subprocess.run([FISH, "-c", script], capture_output=True, text=True, env=self.env, timeout=20)
        self.assertEqual(done.stderr, "")
        return done.stdout.replace("hello from config.fish\n", "", 1)

    def universal(self):
        """Every universal tide_ variable with its value, and the exported ones, as fish lists them."""
        listing = self.fish("set -U; echo exported:; set -U -x")
        return [line for line in listing.splitlines() if line.startswith(("tide_", "exported:"))]

    def ctx(self, stamp):
        self.out = io.StringIO()
        return Context(home=self.home, env=self.env, out=self.out, python="/usr/bin/python3", stamp=stamp,
                       dist=self.root / "dist", lock_path=self.root / "witchy.lock", only=("fish",))

    def test_install_recolours_tide_and_uninstall_gives_every_variable_back(self):
        before = self.universal()
        self.assertEqual(runner.install(self.ctx("20261003-120000")), 0, self.out.getvalue())
        self.assertEqual(self.fish("set -e -g tide_pwd_bg_color; printf '%s\\n' $tide_pwd_bg_color"), "B99AFF\n")
        self.assertEqual(self.fish("printf '%s\\n' $tide_left_prompt_items").split(),
                         list(palette.TIDE["tide_left_prompt_items"]))
        self.assertIn("tide_time_color A99AB9", self.fish("set -U -x"))
        self.assertEqual(self.fish("printf '%s\\n' $tide_moon_bg_color"), "1D1230\n")
        self.fish("_tide_remove_unusable_items")  # a new shell starts and caches the moon item
        self.assertEqual(runner.uninstall(self.ctx("20261003-130000")), 0, self.out.getvalue())
        self.assertEqual(self.universal(), before)
        self.assertEqual(self.fish("printf '%s\\n' $_tide_left_items").split(), ["os", "pwd", "git", "newline",
                                                                                 "character"])
        self.assertFalse((self.home / ".claude" / "witchy").exists())
        self.assertEqual(sorted(path.name for path in (self.config / "functions").iterdir()),
                         ["_tide_remove_unusable_items.fish", "tide.fish"])
        self.assertEqual(sorted(path.name for path in (self.config / "conf.d").iterdir()), [])

    def test_snapshot_reads_values_with_spaces_and_empty_lists(self):
        self.fish("set -U tide_a 'two words' ''; set -U tide_b; set -Ux tide_c x")
        tide, found = fish.snapshot(self.ctx("20261003-120000"), ["tide_a", "tide_b", "tide_c", "tide_none"])
        self.assertTrue(tide)
        self.assertEqual(found, {"tide_a": {"value": ["two words", ""], "exported": False},
                                 "tide_b": {"value": [], "exported": False},
                                 "tide_c": {"value": ["x"], "exported": True},
                                 "tide_none": {"absent": True}})

    def test_the_set_script_sets_exports_and_erases(self):
        ctx = self.ctx("20261003-120000")
        done = run_command(ctx, fish.set_command([("tide_a", "set", ["a b", ""]), ("tide_c", "exported", ["x"]),
                                                    ("tide_pwd_bg_color", "erase", [])], "set three"))
        self.assertEqual(done.returncode, 0)
        _, found = fish.snapshot(ctx, ["tide_a", "tide_c", "tide_pwd_bg_color"])
        self.assertEqual(found, {"tide_a": {"value": ["a b", ""], "exported": False},
                                 "tide_c": {"value": ["x"], "exported": True},
                                 "tide_pwd_bg_color": {"absent": True}})

    def test_the_set_script_stops_at_the_first_failure(self):
        ctx = self.ctx("20261003-120000")
        done = run_command(ctx, fish.set_command([("tide_a", "set", ["1"]), ("status", "set", ["read-only"]),
                                                    ("tide_b", "set", ["2"])], "set three"), check=False)
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(fish._fields(done.stdout), ["tide_a"])
        self.assertEqual(fish.snapshot(ctx, ["tide_b"])[1], {"tide_b": {"absent": True}})


if __name__ == "__main__":
    unittest.main()
```

In `tests/test_install.py` (edit 1 of 2), replace:

```python
from unittest import mock

from witchy import content, install, jsonio, validate
from witchy.components import base
```

with:

```python
from unittest import mock

from tests.fakes import fake_fish
from witchy import content, install, jsonio, palette, validate
from witchy.components import base
```

In `tests/test_install.py` (edit 2 of 2), replace:

```python
        self.assertEqual(self.snapshot(), before)

    def test_install_aborts_when_a_file_changes_while_planning(self):
        before = self.snapshot()
```

with:

```python
        self.assertEqual(self.snapshot(), before)

    def test_every_local_component_round_trips_bytes_and_fish_variables(self):
        mine = self.home / ".config" / "fish" / "functions" / "ll.fish"
        mine.parent.mkdir(parents=True)
        mine.write_text("function ll; ls -lh $argv; end\n", encoding="utf-8")
        variables = {"tide_pwd_bg_color": {"value": ["FFB7C5"], "exported": False},
                     "tide_time_color": {"value": ["5F8787"], "exported": True}}
        original = json.loads(json.dumps(variables))
        before = self.snapshot()

        def ctx(stamp):
            ctx = self.ctx(stamp=stamp)
            ctx.run, ctx.only = fake_fish(variables), ("claude", "windows-terminal", "fish")
            return ctx

        self.assertEqual(install.install(ctx("20260930-120000")), 0)
        self.assertEqual(variables["tide_pwd_bg_color"]["value"], [palette.TIDE["tide_pwd_bg_color"]])
        self.assertTrue((self.claude / "witchy" / "ritual" / "__main__.py").is_file())
        self.assertEqual(install.uninstall(ctx("20260930-130000")), 0)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(variables, original)

    def test_install_aborts_when_a_file_changes_while_planning(self):
        before = self.snapshot()
```

- [ ] **Step 2: Run them**

Run: `/usr/bin/python3 -m unittest tests.test_fish_integration tests.test_install -v 2>&1 | tail -4`
Expected: `Ran 34 tests … OK`, no `skipped`.

- [ ] **Step 3: Update the README, the spec and the CI step name**

In `README.md` (edit 1 of 4), replace:

```markdown
- The "WitchyNibbles" output style, which only changes the tone of chat replies
- A status line with moon phases for context used, 5 h / 7 d limits, and git

## Usage
```

with:

```markdown
- The "WitchyNibbles" output style, which only changes the tone of chat replies
- A status line with moon phases for context used, 5 h / 7 d limits, and git
- For fish: the Tide prompt recoloured, with tonight's moon phase as its first segment; a greeting on new Windows Terminal tabs (a moon drawn to tonight's phase, the Wheel of the Year, a tarot card of the day and a short system summary); `ll` and `lt` through eza

## Usage
```

In `README.md` (edit 2 of 4), replace:

````markdown
```

Components, in install order: `claude`, `font`, `windows-terminal`.

`install` backs up every file it changes as `*.bak-witchy-<date>` and records the previous values in `~/.claude/witchy/state.json`; `uninstall` restores them. A `settings.json` that is not strict JSON (comments, trailing commas) is never rewritten: for Windows Terminal you get a snippet to paste by hand and the rest continues; for `~/.claude/settings.json` the install stops without changing anything.
````

with:

````markdown
```

Components, in install order: `claude`, `font`, `windows-terminal`, `fish`. The `fish` component needs [Tide](https://github.com/IlanCosman/tide) for the prompt colours; without Tide (or fish) it still installs the greeting and `ll`/`lt`, and the last line says `skipped: Tide not found`.

`install` backs up every file it changes as `*.bak-witchy-<date>` and records the previous values in `~/.claude/witchy/state.json`; `uninstall` restores them. A `settings.json` that is not strict JSON (comments, trailing commas) is never rewritten: for Windows Terminal you get a snippet to paste by hand and the rest continues; for `~/.claude/settings.json` the install stops without changing anything.
````

In `README.md` (edit 3 of 4), replace:

```markdown
Exit codes for `install` and `uninstall`: `0` everything done, `1` nothing changed, `2` done with warnings (a component was skipped or failed; the last line says which).

Restart Claude Code and Windows Terminal after installing.

## Troubleshooting
```

with:

````markdown
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
````

In `README.md` (edit 4 of 4), replace:

```markdown
| `✗ windows-terminal  changed or missing: …` | a sky image or `ritual-config.json` was edited or deleted | `python3 -m witchy install --only windows-terminal` |
| `⚠ …  backup … is missing` | a backup was deleted | uninstall still works, key by key |
| `⚠ …  last install (…): skipped: …` | a component was skipped at the last install | read the reason, then install `--only` that component |
| `✗ state  … damaged` | `state.json` is not readable | fix or remove the file by hand |
```

with:

```markdown
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
```

In `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (edit 1 of 5), replace:

````markdown
```

`Plan` holds file `Change`s (the existing dataclass), commands to run (fish, `reg.exe`), notes and warnings. `--dry-run` prints every plan and runs nothing.

### 3.2 Runner (`witchy/runner.py`)
````

with:

````markdown
```

`Plan` holds file `Change`s (the existing dataclass), commands to run (fish, `reg.exe`), notes and warnings. `--dry-run` prints every plan and runs nothing. A restore plan's `commands` run before its file changes, and its `prune` folders are removed afterwards when empty. A plan that applies only in part sets `outcome` (for example `skipped: Tide not found`), which the runner records instead of `ok`. A `restore` that cannot be planned (its `settings.json` is no longer plain JSON) raises `ComponentFailed`: nothing of that component is touched and it stays in state.

### 3.2 Runner (`witchy/runner.py`)
````

In `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (edit 2 of 5), replace:

```markdown
| `fish` | `~/.claude/witchy/ritual/` (greeting package); `~/.config/fish/functions/{fish_greeting,ritual,_tide_item_moon,_witchy_moon_bin,ll,lt}.fish`; `~/.config/fish/conf.d/witchy.fish`; the Tide universal variables (5.2) |

fish files are rendered at install time from `content/fish/*.fish` templates (placeholders `@PYTHON@`, `@WITCHY_DIR@`).

## 4. Windows Terminal
```

with:

```markdown
| `fish` | `~/.claude/witchy/ritual/` (greeting package); `~/.config/fish/functions/{fish_greeting,ritual,_tide_item_moon,_witchy_moon_bin,ll,lt}.fish`; `~/.config/fish/conf.d/witchy.fish`; the Tide universal variables (5.2) |

fish files are rendered at install time from `content/fish/functions/*.fish` and `content/fish/conf.d/witchy.fish` (placeholders `@PYTHON@`, `@WITCHY_DIR@`, `@EZA_COLORS@`, each written as a single-quoted fish word). They go to `$XDG_CONFIG_HOME/fish` when it is set, as fish itself does.

## 4. Windows Terminal
```

In `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (edit 3 of 5), replace:

```markdown
- Every `fish` call uses list arguments and a 5 s timeout through the injectable `ctx.run`.
- Running shells keep their old prompt; the summary says to open a new tab.

## 6. Greeting (the ritual)
```

with:

```markdown
- Every `fish` call uses list arguments and a 5 s timeout through the injectable `ctx.run`.
- Running shells keep their old prompt; the summary says to open a new tab.
- `fish -c` runs the user's `config.fish` (0.4 s on this machine) and `--no-config` also turns off universal variables, so the calls are batched: one call reads Tide's presence and every variable, one call sets them all. Values travel on standard input as NUL-terminated fields, never in the script; the scripts print a `witchy-fish` marker first, so whatever `config.fish` prints is ignored. A global that `config.fish` sets is erased inside the reading call so the universal value shows.
- When fish or Tide is missing, the files still install and the result is `skipped: fish not found` or `skipped: Tide not found`. A failed set records the files and the variables already set, and the result is `failed: could not set <name>`.
- Uninstall restores the variables before it removes the files. A variable that already holds its previous value is skipped silently (a retry after a partial restore). When fish no longer exists, the variables are left with a warning and the files still go; when fish exists but does not answer, the component stays installed.

## 6. Greeting (the ritual)
```

In `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (edit 4 of 5), replace:

```markdown
- `ll` runs `eza -la --icons --group-directories-first --git`; `lt` runs `eza --tree --level=2 --icons`. Without eza they fall back to `ls -la` and `ls -R`.
- `ls` itself is not aliased.
- Doctor shows `⚠ eza missing — sudo apt install eza` when eza is absent.
```

with:

```markdown
- `ll` runs `eza -la --icons --group-directories-first --git`; `lt` runs `eza --tree --level=2 --icons`. Without eza they fall back to `ls -la` and `ls -R`.
- `ls` itself is not aliased.
- Codes: `di`, `ex`, `ln`, `sn` and `sb`, `da`, and git `ga` `#FFD477`, `gm`/`gv`/`gt` `#FFB86B`, `gd` `#FF6B9F` (Tide's three git colours), all as 24-bit `38;2;R;G;B`.
- Doctor shows `⚠ eza missing — sudo apt install eza` when eza is absent.
```

In `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (edit 5 of 5), replace:

```markdown
- `--only` accepts `claude`, `font`, `windows-terminal`, `fish` (repeatable). Components not named keep their state untouched.
- Install and uninstall exit 0 (all ok), 1 (nothing changed: validation, lock, abort), 2 (done with warnings).
- An uninstall whose restore cannot be written keeps that component in state and exits 2; running uninstall again retries it.
- `doctor` prints one line per check, `✓`, `⚠` or `✗`, each `✗`/`⚠` with its fix (often `python3 -m witchy install --only <name>`). It uses the paths recorded in state (no `cmd.exe` lookup) and finishes under 2 s. Exit 1 on any `✗`, else 0. A `check()` that raises is reported as `✗` with the exception text.
- Doctor checks: installed files match their recorded hashes; settings keys and profile keys hold installed values; the theme is active; the font is registered; the sky images and `ritual-config.json` exist; Tide variables match; eza is present; the backups state relies on still exist; the last `ritual.log` error; the sky fail marker; components skipped at the last install.
- `mood` without an argument prints the active and available variants. With a variant it records it in state and re-runs install; an unknown variant exits 1 with `available: midnight`.
```

with:

```markdown
- `--only` accepts `claude`, `font`, `windows-terminal`, `fish` (repeatable). Components not named keep their state untouched.
- Install and uninstall exit 0 (all ok), 1 (nothing changed: validation, lock, abort), 2 (done with warnings).
- An uninstall whose restore cannot be written, or cannot be planned, keeps that component in state and exits 2; running uninstall again retries it. A Claude or Windows Terminal `settings.json` that is no longer plain JSON keeps the whole component, files included, because the settings still point at them.
- The end summary says `Nothing was installed.` instead of the install line when no component applied.
- `doctor` prints one line per check, `✓`, `⚠` or `✗`, each `✗`/`⚠` with its fix (often `python3 -m witchy install --only <name>`). It uses the paths recorded in state (no `cmd.exe` lookup) and finishes under 2 s. Exit 1 on any `✗`, else 0. A `check()` that raises is reported as `✗` with the exception text.
- Doctor checks: installed files match their recorded hashes; settings keys and profile keys hold installed values; the theme is active; the font is registered; the sky images and `ritual-config.json` exist; Tide variables match; eza is present; the backups state relies on still exist; the last `ritual.log` error; the sky fail marker; components skipped at the last install.
- The newest `greeting` and `sky` errors are shown only when they are less than 7 days old, with their age (`today at 09:14`, `yesterday`, `3 days ago`) and cut to 100 characters. A sky fail marker for today adds `(it retries tomorrow)`. The log holds errors only, so an old error would otherwise warn for ever.
- `mood` without an argument prints the active and available variants. With a variant it records it in state and re-runs install; an unknown variant exits 1 with `available: midnight`.
```

In `.github/workflows/tests.yml`, replace:

```yaml
        with:
          python-version: ${{ matrix.python }}
      - name: Install fish (used by the shell tests in Plan C)
        run: sudo apt-get update && sudo apt-get install -y fish
      - name: Run tests
```

with:

```yaml
        with:
          python-version: ${{ matrix.python }}
      - name: Install fish (for the fish integration tests)
        run: sudo apt-get update && sudo apt-get install -y fish
      - name: Run tests
```

- [ ] **Step 4: Run the whole suite on both Pythons, and validate**

Expected: `Ran 464 tests … OK` on both; `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_fish_integration.py tests/test_install.py README.md docs/superpowers/specs/2026-10-02-shell-ritual-design.md .github/workflows/tests.yml
git commit -m "test: real-fish and all-component round trips; document the fish component and record plan D decisions

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 7: Acceptance on the real machine, screenshot and PR

This task is run by the controller with the user, not by a subagent. It starts after the whole-branch review, the `code-simplifier` pass and superpowers:verification-before-completion. Every step that changes the real machine waits for the user's explicit go-ahead. Report real-machine output verbatim.

**Files:** possibly `docs/screenshots/shell-ritual.png` (only if the user chooses to commit the screenshot).

- [ ] **Step 1: Pre-flight (read-only)**

Run: `git status --short`, both test suites, `/usr/bin/python3 -m witchy validate`, `/usr/bin/python3 -m witchy install --dry-run` (save the full output to the scratchpad), `/usr/bin/python3 -m witchy doctor`.
Expected: clean tree; 464 OK on both; validation passes; the dry run shows only the changes of spec sections 3–7 (criterion 2): the output-style diff, 8 sky PNGs, the Ubuntu profile hunk, `ritual-config.json`, the font actions, 20 fish files and 31 `fish: set -U` lines.

- [ ] **Step 2: Ask for the go-ahead (AskUserQuestion)**

Tell the user, before they decide:
1. `~/.claude/output-styles/witchynibbles.md` (their hand-edited copy) is replaced with the repo's neutral wording; the dry-run diff shows the hunk.
2. The Ubuntu profile's whole `font` object is replaced, dropping `"features": {"aalt": 0}` until uninstall.
3. The Maple Mono NF download is about 21 MB from GitHub.
4. The pink Tide prompt is recoloured (31 variables); uninstall gives it back.
5. eza is not installed: `ll`/`lt` fall back to `ls` until they run `! sudo apt install eza` (needed for criterion 3's coloured `ll`).
6. Afterwards: restart Windows Terminal (font, profile) and Claude Code (theme).

Options: (a) install everything now (recommended), (b) install without `font`, (c) not yet.

- [ ] **Step 3: Install**

Run: `time /usr/bin/python3 -m witchy install` (or with the `--only` set the user chose).
Expected: exit 0 (2 only for a reason the summary names); the summary line, `Moonlit Candle installed…`, the restart notes and `Open a new terminal tab…`. Then `time /usr/bin/python3 -m witchy doctor`: no `✗` (criterion 7), under 2 s.

- [ ] **Step 4: Criterion 3 — a new tab (the user)**

The user restarts Windows Terminal and opens a new Ubuntu tab. Check together: Maple Mono NF; the starfield with tonight's moon phase; the pink box cursor; 🌙 and "witchyterm" on the tab; the side-by-side greeting; the prompt starting with today's moon glyph; a coloured `ll` (after eza is installed). The user takes the screenshot (Win+Shift+S). Ask whether to commit it as `docs/screenshots/shell-ritual.png` (GitHub shows it in the PR body) or to attach it to the PR by hand.

- [ ] **Step 5: Criterion 4 — when the greeting stays quiet (the user)**

Within 10 minutes: a second tab and a split pane (Alt+Shift+D) show the one-line omen; `tmux` and a nested `fish` show nothing; `ritual` shows the full ritual in any of them. For Claude Code's shells, run from this session `! env -u WITCHY_RITUAL_SHOWN fish -i -c fish_greeting` (`fish -c` never calls the greeting by itself, and the variable would hide the check): it prints nothing, because Claude Code sets `CLAUDECODE`.

- [ ] **Step 6: Criteria 5 and 6 — previews and timing**

Run in fish: `ritual --date 2026-10-31` (the Samhain line, in the Samhain accent) and `ritual --date 2026-10-26` (`⋆ Samhain in 5 days`). Then `for i in (seq 10); ritual --debug | tail -1; end`: the median `total` must be under 200 ms. `--debug` excludes interpreter start-up and imports, so also run `time fish -c 'for i in (seq 10); ritual >/dev/null; end'` and report the wall-clock average per run next to it.

- [ ] **Step 7: Criterion 9 — uninstall, then reinstall if the user wants (go-ahead first)**

Run: `/usr/bin/python3 -m witchy uninstall`, then open a new tab: the pink 🌸 Tide prompt, the previous profile settings, fish's default greeting; Maple Mono stays installed. Run `doctor` (every component `not installed`) and `git status`. Ask whether to reinstall (`python3 -m witchy install`).

- [ ] **Step 8: Finish the branch**

Use superpowers:finishing-a-development-branch. Before any push: ask whether to rebase the non-Opus `Co-Authored-By:` trailers (Plans A–D have Haiku and Sonnet trailers). Push `feat/shell-ritual` and open the PR against `main` only after the user says yes (the repository is public). The PR body summarises Plans A–D, lists the acceptance results with their receipts, and shows the screenshot.

---

## For the final review

Deferred minors found while planning (none blocks; carry them into the handoff):

- `fish` apply: a write that fails part-way leaves the files already written unrecorded (the same holds for the `claude` component); a fish that times out while setting may have set variables that are not recorded.
- Uninstall's `_tide_remove_unusable_items` refresh is skipped when every variable was already given back (a retry); a new tab rebuilds the cache anyway.
- The `fish` component reads Tide's presence with `functions -q tide`, which only sees an autoloaded or sourced `tide`; Tide installed by fisher qualifies.
- Doctor's sky line suggests `install --only windows-terminal` for every sky error, not only "changed by hand".
- Plan B and Plan C deferred minors in `~/.claude/handoffs/witchyterm-2026-10-03-0347.md` and `~/.claude/handoffs/witchyterm-2026-10-03-0500.md` still apply.
