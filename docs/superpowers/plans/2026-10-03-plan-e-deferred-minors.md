# Plan E: Deferred Minors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the minor issues deferred by the Plan B, C and D reviews (51 items; one, the font backup in the Windows Fonts folder, is kept by decision) without changing what a healthy install, doctor run or uninstall does on the real machine.

**Architecture:** Fifteen small, test-first tasks in five areas: the runner and the shared component helpers (Tasks 1–3), windows-terminal and font (4–5), fish (6–8), the installer helpers (9–11) and the greeting package (12–15). Task 2 adds two shared helpers that Tasks 4 and 6 use: `apply_changes(…, backups)` keeps the backups made before a failed write, and `applied_records(…)` records exactly what a run wrote, so a component that fails part-way can record its partial work (Plan D decision 5's `Plan.outcome`) or put its files back. Task 16 checks the result read-only against the real installed state.

**Tech Stack:** Python 3.10+ standard library only (`subprocess`, `argparse`, `fcntl`, `importlib`, `unittest`); fish 3.7 and Tide 6.1.1 for the real-fish tests.

**Spec:** `docs/superpowers/specs/2026-10-02-shell-ritual-design.md`. Tasks that change behaviour update their spec section in the same commit (3.1, 3.2, 3.3, 4.4, 4.5, 5.3, 6.1, 6.7, 8, 9, 11). Sources of the items: the "Deferred minors" lists in the Plan B, C and D handoffs (`~/.claude/handoffs/witchyterm-2026-10-03-{0347,0500,1128}.md`). Item ids below (B1…, C1…, D1…) are the position in those lists. This plan is written against `main` at `0df90e9`.

## Global Constraints

- Python 3.10 or newer, standard library only. Every test passes on `/usr/bin/python3` (3.12) and `/home/eimi/.pyenv/versions/3.10.0/bin/python3`.
- Test command, from the repo root: `/usr/bin/python3 -m unittest discover -s tests -t .`, and the same with the 3.10 interpreter. `python3 -m witchy validate` must print `Moonlit Candle: all checks passed`.
- No test touches the real `~/.claude`, `~/.cache`, `~/.config/fish`, fish universal variables, Windows Terminal, `cmd.exe`, `reg.exe`, the registry or the network. Use `tests/fakes.py` and temporary folders. Tests that run real fish set `HOME` and `XDG_CONFIG_HOME` to a temporary folder and are skipped when fish is missing.
- **Every manual run of witchy code uses a temporary HOME** (`HOME=$(mktemp -d)`), including the CLI, the greeting, `--sky` and the fish templates. During prototyping one run of `ritual` with a bad `--date` against the real HOME wrote `~/.cache/witchy/ritual.log` (Task 12's C6 logs argument errors when stderr is not a terminal). Never use `fish --no-config` for Tide work.
- Never run a real `install`, `uninstall` or `mood <variant>` without the user's go-ahead. `doctor` and `--dry-run` are read-only and allowed (Task 16).
- Exit codes do not change anywhere.
- Messages, docstrings and comments are English and neutral in tone.
- Commit messages end with the `Co-Authored-By:` trailer of the model that wrote the commit. The commit blocks below show the prototype's message; keep the subject and body, and put your own trailer.
- SDD workspaces go under `.superpowers/sdd/` (git-excluded).

## Decisions

Made by the user during triage:

1. **Headline:** when components applied but the install did not fully succeed, the summary says `Moonlit Candle partly installed.` (Task 1). `Nothing was installed.` stays for "nothing applied".
2. **Uninstall without fish on PATH** still completes. The warning now says that Tide's colours and the `moon` item stay, and that `tide configure` resets them (Task 6, D16).
3. **Font backup kept (B6, won't fix):** a differing, unregistered `MapleMono-NF-*.ttf` still gets a `.bak-witchy-*` beside it in the Windows Fonts folder. Without it, the user's own font would be overwritten with no way back.
4. **Fix the items first proposed as won't-fix:** D13 (byte-exact fish values), D19 (no sleeps in the negative fish tests), D23 (partial-apply state), C6 (argument errors logged when nobody sees them), C8 (`--date` across DST), C10 (`sky-bin` under the lock), C13 (atomic, serialised log).

Made while prototyping (each task's **Decisions** block has the details):

5. **Prototype first.** Every task was built and tested in a scratch clone. The 15 commits were then replayed in this plan's order on a fresh `0df90e9`: every stage is green on both interpreters with `validate` clean. Each fixing task's new tests fail on the stage before it. Tasks 3, 5, 8 and 15 only pin behaviour, so they have no RED. The final tree is byte-identical to the merged prototype (557 tests). A read-only `doctor`, `install --dry-run` and `uninstall --dry-run` of that tree against the real installed state exited 0, and no file changed on disk.
6. **The headline follows the exit code (Task 1):** exit 0 means "installed"; exit 2 with something applied means "partly installed", including some ok plus one skipped. Under the old rule, fish without Tide read "installed" next to claude but "partly installed" alone. The user chose "partly installed" for the none-ok case; this extends it to every exit-2 install so the wording no longer depends on which other components ran. **Review this one.**
7. **Partial work is recorded, not rolled back, for claude and fish (Tasks 2, 6).** The entry gets `outcome = "failed: could not write (…)"` and lists only the files that hold this run's bytes. windows-terminal cannot record an entry without its settings record, so when `settings.json` refuses the write it puts back the images it wrote instead, best effort. It never touches a file this run did not write (Task 4).
8. **`claude`'s `settings` record is optional:** it is absent only when witchy has never written `settings.json` (a first install that stopped part-way). An empty placeholder record would turn off the byte-exact restore of the user's settings for good (Task 2).
9. **Byte-exact fish values (Task 6):** commands carry an `exact` flag (bytes in and out; text decoded with `surrogateescape`), and `state.save` writes undecodable bytes as `\udcXX` escapes. Real fish 3.7 cannot store invalid UTF-8 in a universal variable, so the real-fish test covers `\r` and the fake-based test covers invalid bytes.
10. **The greeting package imports itself by path (Task 13, C14):** `__main__.py` loads its own folder with `importlib.util.spec_from_file_location` instead of `sys.path.append`. With append, another top-level `ritual` package on the path would win.
11. **The ritual log (Task 13):** each message has its whitespace collapsed and is cut to 300 characters, the same limit as the entry point's fallback. Writers take `ritual.log.lock`, wait at most 1 s, then drop the line silently. Each write goes to a temp file that replaces the log. A newly created log has mode 0600.
12. **`--date` (Task 12):** exactly `YYYY-MM-DD` (ASCII digits, a real date) on both interpreters. A preview takes the local offset valid on that day, keeping today's wall-clock time.
13. **C10 narrows the race but cannot close it:** `conf.d/witchy.fish` reads `sky-bin` without the lock (Task 14).
14. **C2 needed nothing:** the Meeus worked-example tests (49.a, 27.a) were already at 1 s, the tightest the 5-decimal JDEs allow.

## Review Focus

1. **A write that fails part-way, then a reinstall after witchy's output changed, then uninstall,** must give back the user's original file, or remove the file when there was none. It must never "restore" witchy's own older bytes. Tests: Task 2 `test_a_retry_after_a_failed_copy_gives_back_the_users_original`, Task 6 `test_a_retry_after_a_failed_write_gives_back_the_users_function`, Task 4 `test_a_failed_settings_write_on_reinstall_puts_back_the_earlier_images`.
2. **The failure paths that write into the real Windows Terminal folder** must leave alone every file this run did not write: a PNG someone else rewrote, or the user's PNG whose copy failed. Tests: Task 4 `test_the_put_back_leaves_an_image_someone_else_rewrote`, `test_backups_made_before_a_failed_image_copy_are_recorded`, `test_a_put_back_that_fails_still_reports_the_settings_write`.
3. **A Tide variable holding `\r` or bytes that are not UTF-8** comes back byte for byte, and saving it in state does not crash. Tests: Task 6 `test_a_value_with_carriage_returns_comes_back_byte_for_byte` (real fish), `test_a_fish_value_that_is_not_utf8_round_trips`, `test_an_exact_command_sends_and_reads_every_byte_unchanged`.
4. **The greeting and the sky job logging at the same moment** lose no line and never leave a half-written log. A held lock never blocks a shell for more than 1 s. Tests: Task 13 `test_two_writers_at_once_lose_no_line`, `test_two_writers_at_once_keep_the_last_twenty`, `test_a_held_lock_gives_up_quietly`.
5. **The state written by the code on `main` (the user's real install)** still loads, passes doctor and plans both an install and an uninstall with the new code, without writing anything. Check: Task 16 (read-only, real machine).

## Items → tasks

| Task | Items |
|---|---|
| 1 | D1 `Plan.skip` docstring · D2 prune folders in the uninstall dry run · D3 partial headline · B4 actions after their own diff |
| 2 | B11 (`apply_changes` keeps backups) · D22 explicit file selection in claude · D23 partial claude apply |
| 3 | B1 claude+font+windows-terminal through the runner · D5 `restore_json` "no longer holds a JSON object" · D21 duplicate import |
| 4 | B11 (caller) · B12 doctor checks image backups · B14 + D23 put back images on a failed settings write · D6 blocked windows-terminal restore |
| 5 | B2 font: copy `OSError`, unreadable TTF name, unreadable registry |
| 6 | D23 partial fish apply · D4 new-tab note · D13 byte-exact values · D14 `moon` still listed · D15 one warning when Tide is gone · D16 clearer no-fish warning |
| 7 | D7 exact 100-character cut · D8 yesterday's sky marker · D9 a time zone the code must convert · D17 retry only after today's error · D18 a command as the log fix · README exit-code sentence |
| 8 | D19 `fish_trace` instead of sleeps · D20 no hard-coded PATH or Python |
| 9 | B7 unreadable cache file · B8 PNG check · B9 prune old cache keys |
| 10 | B10 required sky colours · D10 Tide colour keys by name · D11 separator exemption comment · D12 eza git colours from Tide |
| 11 | B5 `%` in a profile path · B3 `USERNAME` never queried · B15 README "skipped or failed" |
| 12 | C3 `--sky` dispatch tests · C6 log argument errors nobody sees · C7 strict `--date` · C8 the preview day's offset |
| 13 | C9 cap log messages · C13 atomic, serialised log · C14 stdlib cannot be shadowed |
| 14 | C4 CRLF · C5 duplicate sky value · C10 stamp under the lock · C11 config that is not an object |
| 15 | C1 a time zone moves a season date · C12 no art row wider than the column (C2: nothing to add) |
| 16 | Read-only check against the real install |

Already fixed before this plan: B13 (commit `2d17019`), C12 (by construction; Task 15 adds the guard test).

## File structure

No new modules. Files each task touches:

| Task | Source | Tests | Docs |
|---|---|---|---|
| 1 | `witchy/runner.py`, `witchy/components/base.py` | `tests/test_runner.py` | spec 3.1, 3.2, 8 |
| 2 | `witchy/components/base.py`, `witchy/components/claude.py` | `tests/test_base.py`, `tests/test_components_claude.py`, `tests/test_install.py` | spec 3.3, 9 |
| 3 | n/a | `tests/test_base.py`, `tests/test_install.py` | n/a |
| 4 | `witchy/components/windows_terminal.py` | `tests/test_components_wt.py`, `tests/test_install.py` | spec 3.3, 9 |
| 5 | n/a | `tests/fakes.py` (`fake_windows(reg_query_code=0)`), `tests/test_components_font.py` | n/a |
| 6 | `witchy/components/base.py`, `witchy/components/fish.py`, `witchy/state.py` | `tests/fakes.py` (`fake_fish`), `tests/test_base.py`, `tests/test_components_fish.py`, `tests/test_state.py` | spec 5.3, 9 |
| 7 | `witchy/components/fish.py` | `tests/test_components_fish.py` | spec 8, `README.md` |
| 8 | n/a | `tests/test_fish_files.py`, `tests/test_fish_integration.py` | n/a |
| 9 | `witchy/sky_render.py` | `tests/test_sky_render.py` | spec 4.4 |
| 10 | `witchy/validate.py`, `witchy/palette.py`, `witchy/sky_render.py` | `tests/test_validate.py`, `tests/test_prompt_palette.py` | spec 11 |
| 11 | `witchy/windows.py` | `tests/test_windows.py`, `tests/test_wt.py` | `README.md` |
| 12 | `witchy/ritual/cli.py` | `tests/test_ritual_cli.py` | spec 6.1, 6.7 |
| 13 | `witchy/ritual/log.py`, `witchy/ritual/__main__.py` | `tests/test_ritual_log.py`, `tests/test_ritual_package.py` | spec 6.1 |
| 14 | `witchy/ritual/sky.py` | `tests/test_sky_job.py` | spec 4.5 |
| 15 | n/a | `tests/test_art.py`, `tests/test_wheel.py` | n/a |

Order: Tasks 4 and 6 need Task 2. Everything else is independent but was replayed in this order, so keep it. Test counts in each Step 4 assume this order.

---

### Task 1: Runner output (headline, dry-run order, prune folders)

**Items:**
- D1: the `Plan` docstring says a skipped plan "will do nothing", but a skipped restore plan means "blocked, the component stays installed".
- D2: the uninstall dry run never lists `plan.prune`.
- D3: `Moonlit Candle installed.` is printed next to `0/1 components installed`; it must say `Moonlit Candle partly installed.` when not every component ended ok.
- B4: the install dry run prints every plan's actions after all file diffs (font actions after the windows-terminal diff).

**Files:**
- Modify: `witchy/runner.py` (`PARTLY_INSTALLED`, the headline choice, dry-run order, prune lines)
- Modify: `witchy/components/base.py` (`Plan` docstring only)
- Modify: `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (sections 3.1, 3.2 item 7, 8)
- Test: `tests/test_runner.py`

**Interfaces:**
- Consumes: `runner.INSTALLED`, `runner.NOTHING_INSTALLED`, `Plan.prune`, `Plan.actions`, `base.show_changes(ctx, changes)`.
- Produces:
  - `runner.PARTLY_INSTALLED = "Moonlit Candle partly installed. Undo with: python3 -m witchy uninstall"`
  - Install headline: `NOTHING_INSTALLED` when no component applied, `INSTALLED` when every result is `"ok"`, otherwise `PARTLY_INSTALLED`. Exit codes unchanged (0 all ok, 2 otherwise).
  - Install dry run: for each non-skipped plan in order, its file changes (`show_changes`) then its `actions`, then `Dry run: nothing was written.`
  - Uninstall dry run: after each component's command labels, one line per `plan.prune` folder: `<name>: remove <folder> if empty` (full path, like the `remove <path>` lines above it).

**Decisions:**
1. **Some ok, others skipped/failed/partial → `Moonlit Candle partly installed.`** Today that case prints `Moonlit Candle installed.`. It is wrong for the same reason as the 0-ok case: with the old rule, fish without Tide gets "partly installed" when installed alone (`--only fish`) but "installed" when claude is also selected, so the headline depended on which other components ran. The new rule follows the exit code: exit 0 → `installed`, exit 2 with something applied → `partly installed`, nothing applied → `Nothing was installed.`. This matches uninstall, which says `partly uninstalled` whenever it exits 2. A Linux machine without Windows Terminal now always reads "partly installed", which is true, and the summary line just above names what was skipped.
2. **The headline keeps `Undo with: python3 -m witchy uninstall`.** Something was written, so the undo hint still applies; the text starts with the exact words the user chose (`Moonlit Candle partly installed.`).
3. **Prune lines use the full path, not `~`.** No dry-run line shows `~` today: `show_changes` prints `remove /home/…/ritual/cli.py` right above. A `~` only on the prune line would mix two styles in four lines. `tests/test_components_fish.py:293` uses `assertIn` on the command line only, so it keeps passing unchanged.
4. **README:** it does not quote the headline (line 31 only says "the last line says which"), so it is not changed here.

- [ ] **Step 1: Write the failing tests**

In `tests/test_runner.py`:

In `InstallRunnerTest.test_installs_in_order_and_records_results`, replace:

```python
        self.assertIn("2/2 components installed", self.out.getvalue())
        self.assertIn("a note", self.out.getvalue())
```

with:

```python
        self.assertIn("2/2 components installed", self.out.getvalue())
        self.assertIn(runner.INSTALLED, self.out.getvalue())
        self.assertIn("a note", self.out.getvalue())
```

In `InstallRunnerTest.test_skipped_component_exits_2_and_keeps_its_old_entry`, replace:

```python
        self.assertIn("1/2 components installed · skipped: b (nope)", self.out.getvalue())
```

with:

```python
        self.assertIn("1/2 components installed · skipped: b (nope)", self.out.getvalue())
        self.assertIn(runner.PARTLY_INSTALLED, self.out.getvalue())
        self.assertNotIn(runner.INSTALLED, self.out.getvalue())
```

In `InstallRunnerTest`, after `test_dry_run_lists_planned_actions` (replacing the two blank lines after it with one blank line, the new test and one blank line), add:

```python
    def test_dry_run_prints_each_plans_actions_after_its_own_changes(self):
        class Acting(Fake):
            def plan(self, ctx, entry):
                super().plan(ctx, entry)
                return Plan(changes=[Change(ctx.home / f"{self.name}.txt", None, b"x\n")],
                            actions=[f"{self.name}: act"])

        self.assertEqual(runner.install(self.ctx(dry_run=True), [Acting("a", self.log), Acting("b", self.log)]), 0)
        self.assertEqual(self.out.getvalue().splitlines(),
                         [f"create {self.home / 'a.txt'} (1 lines)", "a: act",
                          f"create {self.home / 'b.txt'} (1 lines)", "b: act", "Dry run: nothing was written."])
```

In `RestoreCommandsTest`, after `test_dry_run_lists_the_commands_and_runs_nothing`, add:

```python
    def test_dry_run_lists_the_folders_it_would_remove_if_empty(self):
        a = Restoring("a", self.log, self.plan)
        runner.install(self.ctx(), [a])
        self.assertEqual(runner.uninstall(self.ctx(dry_run=True, run=self.runs()), [a]), 0)
        self.assertEqual(self.out.getvalue().splitlines(),
                         [f"remove {self.target}", "a: restore 2 Tide variables",
                          f"a: remove {self.target.parent} if empty", "Dry run: nothing was written."])
        self.assertTrue(self.target.parent.is_dir())
```

In `OutcomeTest.test_a_partial_outcome_is_recorded_and_its_entry_kept`, replace:

```python
        self.assertIn(runner.INSTALLED, output)
        self.assertIn("Open a new tab.", output)
```

with:

```python
        self.assertIn(runner.PARTLY_INSTALLED, output)
        self.assertNotIn(runner.INSTALLED, output)
        self.assertIn("Open a new tab.", output)
```

Replace the whole `OutcomeTest.test_nothing_applied_does_not_claim_an_install` with it plus a new test:

```python
    def test_nothing_applied_does_not_claim_an_install(self):
        self.assertEqual(runner.install(self.ctx(), [Fake("a", self.log, skip="no Windows Terminal")]), 2)
        output = self.out.getvalue()
        self.assertNotIn(runner.INSTALLED, output)
        self.assertNotIn(runner.PARTLY_INSTALLED, output)
        self.assertIn(runner.NOTHING_INSTALLED, output)

    def test_some_ok_and_some_failed_is_a_partial_install(self):
        code = runner.install(self.ctx(), [Fake("a", self.log), Fake("b", self.log, fail=True)])
        self.assertEqual(code, 2)
        output = self.out.getvalue()
        self.assertIn("1/2 components installed · failed: b (boom)", output)
        self.assertIn(runner.PARTLY_INSTALLED, output)
        self.assertNotIn(runner.INSTALLED, output)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_runner.InstallRunnerTest.test_skipped_component_exits_2_and_keeps_its_old_entry tests.test_runner.InstallRunnerTest.test_dry_run_prints_each_plans_actions_after_its_own_changes tests.test_runner.RestoreCommandsTest.test_dry_run_lists_the_folders_it_would_remove_if_empty tests.test_runner.OutcomeTest`
Expected (real output from the prototype):
```
ERROR: test_skipped_component_exits_2_and_keeps_its_old_entry (...)
AttributeError: module 'witchy.runner' has no attribute 'PARTLY_INSTALLED'
(same AttributeError for the three OutcomeTest tests)
FAIL: test_dry_run_prints_each_plans_actions_after_its_own_changes (...)
First differing element 1:
'create /tmp/tmpm037efc7/home/b.txt (1 lines)'
'a: act'
FAIL: test_dry_run_lists_the_folders_it_would_remove_if_empty (...)
First differing element 2:
'Dry run: nothing was written.'
'a: remove /tmp/tmpcc0_sdpf/ritual if empty'
FAILED (failures=2, errors=4)
```

- [ ] **Step 3: Implement**

In `witchy/components/base.py`, replace the `Plan` docstring paragraph:

```python
    For a restore plan the runner runs ``commands`` before writing ``changes``, then removes each ``prune``
    directory that is left empty. ``outcome`` replaces "ok" in the install results when a plan applied only
    in part (for example "skipped: Tide not found").
```

with:

```python
    For a restore plan the runner runs ``commands`` before writing ``changes``, then removes each ``prune``
    directory that is left empty. A skipped restore plan means the restore is blocked: nothing of the component
    is touched and it stays installed. ``outcome`` replaces "ok" in the install results when a plan applied only
    in part (for example "skipped: Tide not found").
```

In `witchy/runner.py`:

Replace:

```python
INSTALLED = "Moonlit Candle installed. Undo with: python3 -m witchy uninstall"
```

with:

```python
INSTALLED = "Moonlit Candle installed. Undo with: python3 -m witchy uninstall"
PARTLY_INSTALLED = "Moonlit Candle partly installed. Undo with: python3 -m witchy uninstall"
```

In `_install`, replace:

```python
    changes = [change for _, plan in plans if plan.skip is None for change in plan.changes]
    if ctx.dry_run:
        show_changes(ctx, changes)
        for _, plan in plans:
            if plan.skip is None:
                for action in plan.actions:
                    ctx.say(action)
        ctx.say("Dry run: nothing was written.")
        return 0
```

with:

```python
    if ctx.dry_run:
        for _, plan in plans:
            if plan.skip is None:
                show_changes(ctx, plan.changes)
                for action in plan.actions:
                    ctx.say(action)
        ctx.say("Dry run: nothing was written.")
        return 0
```

Replace:

```python
    ctx.say(_summary(results))
    ctx.say(INSTALLED if applied else NOTHING_INSTALLED)
```

with:

```python
    ok = all(result == "ok" for result in results.values())
    ctx.say(_summary(results))
    # Exit 2 with something applied is a partial install, whichever components were selected.
    ctx.say(NOTHING_INSTALLED if not applied else INSTALLED if ok else PARTLY_INSTALLED)
```

Replace:

```python
    ctx.say(NEW_SESSION_NOTE)
    return 0 if all(result == "ok" for result in results.values()) else 2
```

with:

```python
    ctx.say(NEW_SESSION_NOTE)
    return 0 if ok else 2
```

In `_uninstall`, replace:

```python
        for component, plan in plans:
            for command in plan.commands:
                ctx.say(f"{component.name}: {command.label}")
        for warning in warnings:
```

with:

```python
        for component, plan in plans:
            for command in plan.commands:
                ctx.say(f"{component.name}: {command.label}")
            for directory in plan.prune:
                ctx.say(f"{component.name}: remove {directory} if empty")
        for warning in warnings:
```

In `docs/superpowers/specs/2026-10-02-shell-ritual-design.md`:

Section 3.1, replace:

```
`--dry-run` prints every plan and runs nothing. A restore plan's `commands` run before its file changes, and its `prune` folders are removed afterwards when empty.
```

with:

```
`--dry-run` prints every plan (each plan's file changes, then its actions) and runs nothing. A restore plan's `commands` run before its file changes, and its `prune` folders are removed afterwards when empty (an uninstall dry run lists them as `<name>: remove <folder> if empty`).
```

Section 3.2, replace item 7:

```
7. Print an end summary, e.g. `3/4 components installed · failed: font (download failed (…))`, and exit 0 (all ok), 1 (nothing changed) or 2 (installed with warnings).
```

with:

```
7. Print an end summary, e.g. `3/4 components installed · failed: font (download failed (…))`, and exit 0 (all ok), 1 (nothing changed) or 2 (installed with warnings). The line after it is `Moonlit Candle installed.` (exit 0), `Moonlit Candle partly installed.` (exit 2, something applied) or `Nothing was installed.` (exit 2, nothing applied).
```

Section 8, replace:

```
- The end summary says `Nothing was installed.` instead of the install line when no component applied.
```

with:

```
- The line after the end summary says `Moonlit Candle installed.` only when every selected component ended `ok`. When at least one applied but not all ended `ok` (skipped, failed, or applied only in part, such as fish without Tide) it says `Moonlit Candle partly installed.`, and when no component applied it says `Nothing was installed.`
```

- [ ] **Step 4: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 476 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/runner.py witchy/components/base.py tests/test_runner.py docs/superpowers/specs/2026-10-02-shell-ritual-design.md
git commit -m "fix: partial install headline, prune folders and per-plan actions in dry runs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Base contracts (backups kept on failure, explicit file selection, partial claude apply)

**Items:**
- B11 (base part): `apply_changes` loses the backups it already made when a later write raises.
- D22: `ClaudeComponent.apply` builds file records from `plan.changes[:-1]`, which depends on `plan()` putting the settings change last.
- D23: a claude apply that fails part-way (an `OSError` after some files were written) records nothing; the retry then backs up witchy's own bytes and uninstall "restores" them instead of removing the file or giving back the user's original.

**Files:**
- Modify: `witchy/components/base.py` (`apply_changes` gains `backups`; new `applied_records`)
- Modify: `witchy/components/claude.py` (`apply`, new `_partial`, `restore` and `check` accept an entry without `settings`, new `_check_settings`)
- Modify: `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (section 3.3 bullet, section 9 row)
- Test: `tests/test_base.py`, `tests/test_components_claude.py`, `tests/test_install.py`

**Interfaces:**
- Consumes: `base.file_record(change, earlier, backups)`, `base.read`, `JsonPlan.previous`, `JsonPlan.entry(backup)`, `Plan.outcome` (Plan D decision 5), `jsonio.write_atomic_bytes`.
- Produces (the fish and windows-terminal tasks rely on these exact names):
  - `base.apply_changes(ctx, changes: list[Change], backups: dict[Path, Path] | None = None) -> dict[Path, Path]`. It writes `changes` in order. Each backup goes into `backups` as soon as it is made: when a dict is given, that same dict is filled in place and returned; without one, a new dict is returned. If a write raises, the caller's dict still holds every backup made before the exception, including the backup of the change whose write failed (that backup is made before the write). Keys already in the dict are kept.
  - `base.applied_records(changes: list[Change], earlier: dict[Path, dict], backups: dict[Path, Path]) -> list[dict]`. For each change, in order: a file that now holds `change.after` gets `file_record(change, earlier, backups)`; otherwise a path in `earlier` keeps `earlier[path]` unchanged (the same dict); otherwise nothing. It is safe to call after a successful apply too: it then gives the same records as `file_record` on every change. Exported in `base.__all__`.
  - Claude state entry: `"settings"` is now optional. It is absent only when witchy has never written `settings.json` (a first install that stopped part-way). `ClaudeComponent.restore` then restores only the copies, and `check` reports `fail` with `settings keys not installed in <claude_dir>/settings.json`. `tests/fixtures/state-v1.json` is unaffected (the v1 migration always has `claude_settings`).
  - Claude partial apply: `plan.outcome = "failed: could not write (<OSError text>)"`, prints `claude: could not write (<OSError text>); run install again.`, and returns the partial entry. When there is nothing to record (no file holds this run's bytes, nothing recorded earlier, no settings), it raises `ComponentFailed("could not write (<OSError text>)")` instead.

**Decisions:**
1. **Record, don't roll back.** This reuses Plan D decision 5 (`Plan.outcome` plus a returned entry): the runner already records an entry for a plan whose outcome is not "ok". A rollback would need more writes on a disk that just refused one, and a rollback that fails part-way would bring the same hole back.
2. **`applied_records` lives in `base`** because the same hole exists in fish and windows-terminal (see the report). It decides by the bytes on disk, not by the position of the failing change, so it does not depend on the order of the changes or on which write failed. A file the run did not write keeps its earlier record as it was, so a user-edited file keeps its first backup as the restore target. Today windows-terminal's `_still_ours` drops that record.
3. **`settings` is optional instead of being recorded as an empty record.** A placeholder record (`keys: {}`, no backup) would carry into the retry (`JsonPlan.entry` keeps `previous`), turn `byte_restore_ok` off for good and lose the byte-exact restore of the user's `settings.json`. With no record, the retry plans settings exactly as a first install does.
4. **`_partial` checks the settings file's bytes** (`read(path) == change.after`) instead of assuming the settings change is last. This is the same order independence as D22, and it is pinned by `test_settings_written_before_a_failure_are_recorded`.
5. **The runner is unchanged.** A component's entry shape is its own, so only the component can build a partial entry. With this task every component catches its own write `OSError`, so the runner still catches only `ComponentFailed`.
6. **Proof the end-to-end tests catch the real bug, not only the crash:** with `apply` changed to raise `ComponentFailed` on `OSError` (crash fixed, nothing recorded) and the state assertion left out, all three `test_install.py` tests fail on the final `snapshot()` comparison: uninstall leaves witchy's first theme bytes in place.

- [ ] **Step 1: Write the failing tests**

`tests/test_base.py`. Replace the import:

```python
from witchy.components.base import (Change, Command, ComponentFailed, file_lock, file_record, run_command, sha,
                                    show_changes)
```

with:

```python
from witchy.components.base import (Change, Command, ComponentFailed, applied_records, apply_changes, file_lock,
                                    file_record, run_command, sha, show_changes)
```

In `class Ctx`, replace:

```python
    def __init__(self):
        self.out = io.StringIO()
```

with:

```python
    def __init__(self):
        self.out = io.StringIO()
        self.stamp = "20261003-120000"
```

Between `FileRecordTest` and `ShowChangesTest`, add:

```python
class AppliedRecordsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_a_file_holding_this_runs_bytes_gets_a_new_record(self):
        path = self.root / "theme.json"
        path.write_bytes(b"new")
        backups = {path: self.root / "theme.json.bak"}
        self.assertEqual(applied_records([Change(path, b"mine", b"new")], {}, backups),
                         [{"path": str(path), "backup": str(backups[path]), "installed_sha256": sha(b"new")}])

    def test_a_file_the_run_did_not_write_keeps_its_earlier_record(self):
        path = self.root / "style.md"
        path.write_bytes(b"edited by the user")
        earlier = {path: {"path": str(path), "backup": "/x/style.md.bak", "installed_sha256": sha(b"old")}}
        self.assertEqual(applied_records([Change(path, b"edited by the user", b"new")], earlier, {}), [earlier[path]])

    def test_a_file_witchy_never_wrote_is_left_out(self):
        path = self.root / "tips.json"
        self.assertEqual(applied_records([Change(path, None, b"new")], {}, {}), [])
        path.write_bytes(b"the user's own")
        self.assertEqual(applied_records([Change(path, b"the user's own", b"new")], {}, {}), [])


class ApplyChangesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.first = self.root / "a.json"
        self.first.write_bytes(b"mine")

    def test_the_backups_made_before_a_failure_stay_with_the_caller(self):
        blocker = self.root / "blocker"
        blocker.write_bytes(b"a file, so nothing can be created inside it")
        backups = {}
        with self.assertRaises(OSError):
            apply_changes(Ctx(), [Change(self.first, b"mine", b"ours"), Change(blocker / "b.json", None, b"ours")],
                          backups)
        self.assertEqual(list(backups), [self.first])
        self.assertEqual(backups[self.first].read_bytes(), b"mine")
        self.assertEqual(self.first.read_bytes(), b"ours")

    def test_the_given_dict_is_filled_and_returned(self):
        backups = {Path("/x/earlier.json"): Path("/x/earlier.json.bak")}
        self.assertIs(apply_changes(Ctx(), [Change(self.first, b"mine", b"ours")], backups), backups)
        self.assertEqual(list(backups), [Path("/x/earlier.json"), self.first])

    def test_without_a_dict_a_new_one_is_returned(self):
        backups = apply_changes(Ctx(), [Change(self.first, b"mine", b"ours")])
        self.assertEqual(backups, {self.first: self.root / "a.json.bak-witchy-20261003-120000"})
```

`tests/test_components_claude.py`. Replace the imports:

```python
from pathlib import Path

from witchy import build
from witchy.components.base import Abort, apply_changes
from witchy.components.claude import RESTART_NOTE, ClaudeComponent
```

with:

```python
from pathlib import Path
from unittest import mock

from witchy import build, jsonio
from witchy.components.base import Abort, ComponentFailed, apply_changes, sha
from witchy.components.claude import COPIES, RESTART_NOTE, ClaudeComponent
```

After the `data` method, add:

```python
    def write_fails(self, target):
        real = jsonio.write_atomic_bytes

        def write(path, data):
            if Path(path) == target:
                raise PermissionError(13, "Permission denied", str(path))
            return real(path, data)

        return mock.patch.object(jsonio, "write_atomic_bytes", side_effect=write)
```

After `test_check_warns_when_the_settings_backup_is_gone`, add:

```python
    def test_file_records_do_not_depend_on_the_order_of_the_changes(self):
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        plan.changes.reverse()
        entry = self.component.apply(ctx, plan)
        self.assertEqual(sorted(record["path"] for record in entry["files"]),
                         sorted(str(self.home / target) for target in COPIES.values()))
        self.assertEqual(entry["settings"]["path"], str(self.settings))

    def test_a_write_that_fails_part_way_records_what_was_written(self):
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        with self.write_fails(self.claude / "output-styles" / "witchynibbles.md"):
            entry = self.component.apply(ctx, plan)
        theme = self.claude / "themes" / "moonlit-candle.json"
        self.assertEqual(entry["files"],
                         [{"path": str(theme), "backup": None, "installed_sha256": sha(theme.read_bytes())}])
        self.assertNotIn("settings", entry)
        self.assertRegex(plan.outcome,
                         r"^failed: could not write \(\[Errno 13\] Permission denied: '.*witchynibbles\.md'\)$")
        self.assertIn("claude: could not write (", self.out.getvalue())
        self.assertEqual(self.data(), {"theme": "dark", "model": "opus"})

    def test_settings_written_before_a_failure_are_recorded(self):
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        plan.changes.reverse()
        with self.write_fails(self.claude / "output-styles" / "witchynibbles.md"):
            entry = self.component.apply(ctx, plan)
        self.assertEqual(entry["settings"]["keys"]["theme"]["previous"], {"value": "dark"})
        self.assertEqual([record["path"] for record in entry["files"]],
                         [str(self.claude / "witchy" / "tips.json"), str(self.claude / "witchy" / "statusline.py")])

    def test_a_first_write_that_fails_records_nothing(self):
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        with self.write_fails(self.claude / "themes" / "moonlit-candle.json"):
            with self.assertRaisesRegex(ComponentFailed, r"^could not write \("):
                self.component.apply(ctx, plan)

    def test_a_failed_reinstall_keeps_the_earlier_records_it_did_not_replace(self):
        _, _, first = self.install()
        ctx = self.ctx(stamp="20261002-120500")
        ctx.outputs[build.THEME] += "\n"
        ctx.outputs[build.OUTPUT_STYLE] += "\n"
        plan = self.component.plan(ctx, first)
        with self.write_fails(self.claude / "output-styles" / "witchynibbles.md"):
            entry = self.component.apply(ctx, plan)
        self.assertTrue(plan.outcome.startswith("failed: could not write ("))
        self.assertEqual(entry["settings"], first["settings"])
        theme, *others = entry["files"]
        self.assertEqual(theme["installed_sha256"], sha(ctx.outputs[build.THEME].encode("utf-8")))
        self.assertEqual(others, first["files"][1:])

    def test_without_a_settings_record_restore_and_check_handle_the_copies(self):
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        with self.write_fails(self.claude / "output-styles" / "witchynibbles.md"):
            entry = self.component.apply(ctx, plan)
        fails = [check.message for check in self.component.check(ctx, entry) if check.level == "fail"]
        self.assertEqual(fails, [f"settings keys not installed in {self.settings}"])
        restore = self.component.restore(self.ctx(stamp="20261002-130000"), entry)
        self.assertEqual([change.path for change in restore.changes], [self.claude / "themes" / "moonlit-candle.json"])
        apply_changes(ctx, restore.changes)
        self.assertFalse((self.claude / "themes" / "moonlit-candle.json").exists())
        self.assertEqual(self.data(), {"theme": "dark", "model": "opus"})
```

`tests/test_install.py`. In `InstallTestCase`, replace the whole `wt_write_fails` method with:

```python
    def wt_write_fails(self):
        """Windows Terminal's settings.json cannot be replaced (it holds the file open); everything else writes."""
        return self.write_fails(self.wt)

    def write_fails(self, target):
        """``target`` cannot be written; everything else writes."""
        real = jsonio.write_atomic_bytes

        def write(path, data):
            if Path(path) == target:
                raise PermissionError(13, "Permission denied", str(path))
            return real(path, data)

        return mock.patch("witchy.install.jsonio.write_atomic_bytes", side_effect=write)

    def theme_changes(self):
        """A later witchy version that ships a different theme file."""
        real = install.build.render_outputs

        def render(**kwargs):
            outputs = real(**kwargs)
            return {**outputs, install.build.THEME: outputs[install.build.THEME] + "\n"}

        return mock.patch("witchy.install.build.render_outputs", side_effect=render)
```

In `InstallTest`, before `test_no_windows_terminal_is_skipped_with_exit_2`, add:

```python
    def install_after_a_failed_copy(self):
        """The output style cannot be written (after the theme was); then a later version reinstalls."""
        theme = self.claude / "themes" / "moonlit-candle.json"
        with self.write_fails(self.claude / "output-styles" / "witchynibbles.md"):
            self.assertEqual(install.install(self.ctx()), 2)
        self.assertIn("claude: could not write (", self.out.getvalue())
        self.assertIn("1/2 components installed · failed: claude (could not write (", self.out.getvalue())
        self.assertEqual([record["path"] for record in self.state()["components"]["claude"]["files"]], [str(theme)])
        self.assertEqual(self.claude_settings(), CLAUDE_ORIGINAL)
        with self.theme_changes():
            self.assertEqual(install.install(self.ctx(stamp="20260930-120500")), 0)
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 0)

    def test_a_retry_after_a_failed_copy_still_removes_what_witchy_wrote(self):
        before = self.snapshot()
        self.install_after_a_failed_copy()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.claude / "themes" / "moonlit-candle.json").exists())

    def test_a_retry_after_a_failed_copy_gives_back_the_users_original(self):
        theme = self.claude / "themes" / "moonlit-candle.json"
        theme.parent.mkdir()
        theme.write_bytes(b'{"name": "my own theme"}\n')
        before = self.snapshot()
        self.install_after_a_failed_copy()
        self.assertEqual(self.snapshot(), before)

    def test_uninstall_after_a_failed_copy_removes_what_witchy_wrote(self):
        before = self.snapshot()
        with self.write_fails(self.claude / "output-styles" / "witchynibbles.md"):
            self.assertEqual(install.install(self.ctx()), 2)
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 0)
        self.assertEqual(self.snapshot(), before)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_base tests.test_components_claude tests.test_install`
Expected (real output from the prototype, trimmed):
```
ImportError: cannot import name 'applied_records' from 'witchy.components.base' (…)
ERROR: test_a_failed_reinstall_keeps_the_earlier_records_it_did_not_replace (…)
PermissionError: [Errno 13] Permission denied: '/tmp/…/home/.claude/output-styles/witchynibbles.md'
(the same PermissionError for the other four new claude tests and the three new test_install tests)
FAIL: test_file_records_do_not_depend_on_the_order_of_the_changes (…)
'/tmp/tmppi7uz4fw/home/.claude/settings.json'   (listed as a copied file; the theme is missing)
FAILED (failures=1, errors=9)
```

- [ ] **Step 3: Implement**

`witchy/components/base.py`. Replace `__all__` with:

```python
__all__ = ["Abort", "ComponentFailed", "Change", "Command", "JsonPlan", "Plan", "Check", "Component", "sha", "read",
           "fix_command", "backup_checks", "check_unchanged", "show_changes", "apply_changes", "run_command",
           "file_change", "file_record", "applied_records", "restore_copy", "restore_json", "file_lock"]
```

Replace the first two lines of `apply_changes`:

```python
def apply_changes(ctx: Any, changes: list[Change]) -> dict[Path, Path]:
    backups: dict[Path, Path] = {}
```

with:

```python
def apply_changes(ctx: Any, changes: list[Change], backups: dict[Path, Path] | None = None) -> dict[Path, Path]:
    """Write ``changes`` in order and return the backups made, by path.

    Each backup goes into ``backups`` (when given) as soon as it is made, so a caller still has the ones made
    before a write that raises.
    """
    backups = {} if backups is None else backups
```

(the rest of the function is unchanged). After `file_record`, add:

```python
def applied_records(changes: list[Change], earlier: dict[Path, dict], backups: dict[Path, Path]) -> list[dict]:
    """The file records after an apply that may have stopped part-way.

    A file that holds this run's bytes gets a new record. One the run did not write keeps its earlier record,
    so its first backup stays the restore target; one witchy never wrote is left out.
    """
    records = []
    for change in changes:
        if change.after is not None and read(change.path) == change.after:
            records.append(file_record(change, earlier, backups))
        elif change.path in earlier:
            records.append(earlier[change.path])
    return records
```

`witchy/components/claude.py`. Replace the base import with:

```python
from .base import (Abort, Change, Check, ComponentFailed, JsonPlan, Plan, applied_records, apply_changes,
                   backup_checks, file_change, file_record, fix_command, read, restore_copy, restore_json, sha)
```

Replace the methods `apply`, `restore` and `check` with:

```python
    def apply(self, ctx: Any, plan: Plan) -> dict:
        settings: JsonPlan = plan.data["settings"]
        copies = [change for change in plan.changes if change is not settings.change]
        backups: dict[Path, Path] = {}
        try:
            apply_changes(ctx, plan.changes, backups)
        except OSError as exc:
            return self._partial(ctx, plan, copies, backups, exc)
        return {
            "files": [file_record(change, plan.data["earlier"], backups) for change in copies],
            "settings": settings.entry(backups.get(settings.change.path)),
        }

    def _partial(self, ctx: Any, plan: Plan, copies: list[Change], backups: dict[Path, Path], exc: OSError) -> dict:
        """Record what a write that failed part-way left in place.

        Without a record, the next install would back up witchy's own bytes and uninstall would give those back.
        The entry has no "settings" until witchy has written settings.json.
        """
        settings: JsonPlan = plan.data["settings"]
        ctx.say(f"claude: could not write ({exc}); run install again.")
        entry: dict[str, Any] = {"files": applied_records(copies, plan.data["earlier"], backups)}
        if read(settings.change.path) == settings.change.after:
            entry["settings"] = settings.entry(backups.get(settings.change.path))
        elif settings.previous:
            entry["settings"] = settings.previous
        if not entry["files"] and "settings" not in entry:
            raise ComponentFailed(f"could not write ({exc})") from exc
        plan.outcome = f"failed: could not write ({exc})"
        return entry

    def restore(self, ctx: Any, entry: dict) -> Plan:
        warnings: list[str] = []
        record = entry.get("settings")
        settings = None
        if record is not None:
            settings = restore_json(record, lambda data: claude_settings.restore_keys(data, record["keys"]), warnings)
        copies = [restore_copy(file_record) for file_record in entry["files"]]
        # Settings first, so they never point at files that are already gone.
        return Plan(changes=[change for change in [settings, *copies] if change is not None], warnings=warnings)

    def check(self, ctx: Any, entry: dict) -> list[Check]:
        fix = fix_command(self.name)
        checks = []
        changed = [record["path"] for record in entry["files"]
                   if sha(read(Path(record["path"]))) != record["installed_sha256"]]
        if changed:
            checks.append(Check("fail", self.name, "changed or missing: " + ", ".join(changed), fix))
        else:
            checks.append(Check("ok", self.name, f"{len(entry['files'])} files match"))
        record = entry.get("settings")
        if record is None:
            missing = ctx.claude_dir / "settings.json"
            checks.append(Check("fail", self.name, f"settings keys not installed in {missing}", fix))
        else:
            checks.append(self._check_settings(record, fix))
        backups = [(record or {}).get("backup"), *(f.get("backup") for f in entry["files"])]
        checks.extend(backup_checks(self.name, backups))
        return checks

    def _check_settings(self, record: dict, fix: str) -> Check:
        try:
            data, _ = jsonio.read_json(Path(record["path"]))
        except (OSError, jsonio.StrictJsonError) as exc:
            return Check("fail", self.name, f"cannot read {record['path']}: {exc}", fix)
        data = data if isinstance(data, dict) else {}
        drift = [key for key, key_record in record["keys"].items()
                 if snapshot(data, key) != {"value": key_record["installed"]}]
        if drift:
            return Check("fail", self.name, "settings changed: " + ", ".join(drift), fix)
        return Check("ok", self.name, f"theme {claude_settings.THEME} active, "
                                      f"{len(record['keys'])} settings keys match")
```

`docs/superpowers/specs/2026-10-02-shell-ritual-design.md`. In section 3.3, after the bullet that starts `- A copied file that someone edited after witchy wrote it`, add:

```
- An apply that stops part-way (a file write fails) still records the files witchy already wrote and reports `failed: <reason>`, so the next install does not mistake witchy's bytes for the user's and uninstall still removes them or gives back the original. A file the run did not write keeps its earlier record. A `claude` entry has no `settings` record until witchy has written `settings.json`; doctor then reports `settings keys not installed`.
```

In section 9, after the row `| claude | \`settings.json\` not plain JSON | …`, add:

```
| claude | a file write `OSError` | `failed: could not write (…)`, exit 2; the files already written stay recorded (nothing is recorded when none was) | `claude: could not write (…); run install again.` |
```

- [ ] **Step 4: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 491 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/components/base.py witchy/components/claude.py tests/test_base.py tests/test_components_claude.py tests/test_install.py docs/superpowers/specs/2026-10-02-shell-ritual-design.md
git commit -m "fix: a claude install that fails part-way records what it wrote; apply_changes keeps earlier backups" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

**Follow-up for later tasks (not in this task):**
- windows-terminal: replace `backups.update(apply_changes(ctx, images))` with `apply_changes(ctx, images, backups)`, and do the same for the settings and config calls, so the image backups made before an `OSError` stay recorded (B11). The same hole as D23 is still there: when the settings write fails, `apply` unlinks only the images that did not exist before (`image.before is None`) and raises `ComponentFailed`. An image that existed before (witchy's earlier render) and was overwritten keeps the new bytes, with either no record (first install) or a stale record holding the old `installed_sha256` (the runner keeps the old entry). At the next install `file_change` sees bytes that match no record, backs them up, and `file_record` makes that backup the restore target, so uninstall gives back witchy's image. Fix: in that `except OSError` branch, also put back every image with `image.before is not None` whose file now holds `image.after` (`jsonio.write_atomic_bytes(image.path, image.before)`, inside its own `try/except OSError: pass`). WT cannot record a partial entry without its settings record, so a rollback fits here. Optionally, `files` can use `applied_records(images, earlier, backups)` and `applied_records([config], earlier, backups)` in place of `_still_ours` + `file_record`; unlike `_still_ours`, it keeps the earlier record of an image the user edited, so its first backup is not orphaned.
- fish: `FishComponent.apply` turns an `OSError` from `apply_changes` into `ComponentFailed("could not write the fish files …")` and records nothing: the same hole as D23. Fix: `backups = {}`; `apply_changes(ctx, plan.changes, backups)` in `try`; on `OSError`, set `plan.outcome = f"failed: could not write the fish files ({exc})"`, print `fish: could not write the fish files (…); run install again.`, skip the Tide `set` call, and return `{"files": applied_records(plan.changes, earlier, backups) + [earlier records of paths no longer shipped], "variables": dict(plan.data["recorded"])}`. Raise `ComponentFailed` only when that entry would hold no files and no variables.
- font: not affected. Its records hold no backups and uninstall keeps the fonts, so no restore target can go wrong.

---

### Task 3: Runner-level tests (claude + font + windows-terminal, a settings file that is no longer an object)

**Items:**
- B1: no test runs claude, font and windows-terminal together through the runner; add an install + uninstall round trip, plus an offline case where the font fails and the others still install.
- D5: the `restore_json` branch for "no longer holds a JSON object" has no test.
- D21: `tests/test_base.py` imports `tempfile` twice.

**Files:**
- Test: `tests/test_install.py` (new test in `InstallTest`, new class `WindowsComponentsTest`)
- Test: `tests/test_base.py` (remove the duplicate import)

**Interfaces:**
- Consumes: `tests.fakes.fake_windows`, `make_ttf`, `make_zip`, `reg_listing`; `fonts.SHA256`, `fonts.MEMBERS`, `fonts.STYLES`, `fonts.FAMILY`; `font.KEPT_WARNING`; `windows_terminal.NO_FONT_NOTE`; `runner.PARTLY_INSTALLED` (Task 1); `InstallTestCase.ctx/snapshot/ubuntu/state/claude_settings`.
- Produces: nothing new.

**Decisions:**
1. **The round trip lives in `tests/test_install.py`** as `WindowsComponentsTest(InstallTestCase)`. It reuses that file's Claude and Windows Terminal fixtures, and its setUp follows `tests/test_components_font.py`: a fake `/mnt/c` user Fonts folder, a zip of four tiny TrueType files, and `fonts.SHA256` patched to that zip's digest. `fake_windows` answers `cmd.exe /c echo %USERPROFILE%`, `reg.exe query` (empty) and `reg.exe add`. Any other command fails the test, so no real Windows call can slip in.
2. **The offline case asserts the font-dependent path end to end.** windows-terminal planned the font key (the font plan was not skipped), but at apply time `ctx.results["font"]` is `failed: …`, so it rebuilds the profile without `font` and adds `NO_FONT_NOTE`. Uninstall still gives back every byte.
3. **Font files stay after uninstall** (spec 4.3, `KEPT_WARNING`). The snapshot covers HOME and the Windows Terminal folder, not the fake `/mnt/c`, so `snapshot() == before` holds, and the fonts are checked separately.

- [ ] **Step 1: Write the failing tests**

`tests/test_base.py`, replace:

```python
import tempfile
import tempfile
```

with:

```python
import tempfile
```

`tests/test_install.py`, replace the imports at the top:

```python
import io
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from tests.fakes import fake_fish
from witchy import content, install, jsonio, palette, validate
from witchy.components import base
```

with:

```python
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from tests.fakes import fake_fish, fake_windows, make_ttf, make_zip, reg_listing
from witchy import content, fonts, install, jsonio, palette, runner, validate
from witchy.components import base
from witchy.components.font import KEPT_WARNING
from witchy.components.windows_terminal import NO_FONT_NOTE
```

In `InstallTest`, after `test_claude_files_stay_while_its_settings_cannot_be_restored`, add:

```python
    def test_claude_stays_while_its_settings_no_longer_hold_an_object(self):
        install.install(self.ctx())
        installed = self.settings.read_text(encoding="utf-8")
        self.settings.write_text("[]\n", encoding="utf-8")
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 2)
        self.assertIn(f"claude: {self.settings} no longer holds a JSON object; fix it by hand; run uninstall again.",
                      self.out.getvalue())
        self.assertEqual(list(self.state()["components"]), ["claude"])
        self.assertTrue((self.claude / "witchy" / "statusline.py").is_file())
        self.assertEqual(self.settings.read_text(encoding="utf-8"), "[]\n")
        self.settings.write_text(installed, encoding="utf-8")
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-131000")), 0)
        self.assertEqual(self.claude_settings(), CLAUDE_ORIGINAL)
```

At the end of the file, before `if __name__ == "__main__":`, add:

```python
class WindowsComponentsTest(InstallTestCase):
    """claude, font and windows-terminal together through the runner, with a fake Windows host."""

    def setUp(self):
        super().setUp()
        self.mnt = self.root / "mnt"
        self.fonts = self.mnt / "c" / "Users" / "user" / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"
        self.fonts.mkdir(parents=True)
        self.archive = make_zip({name: make_ttf(f"{fonts.FAMILY} {style}")
                                 for name, style in zip(fonts.MEMBERS, fonts.STYLES)})
        patcher = mock.patch.object(fonts, "SHA256", hashlib.sha256(self.archive).hexdigest())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.calls = []

    def windows_ctx(self, stamp, fetch=None):
        ctx = self.ctx(stamp=stamp)
        ctx.run = fake_windows(echo={"USERPROFILE": "C:\\Users\\user\r\n"}, reg_query=reg_listing({}),
                               calls=self.calls)
        ctx.mount_root, ctx.fetch = self.mnt, fetch or (lambda url: self.archive)
        ctx.only = ("claude", "font", "windows-terminal")
        return ctx

    def test_claude_font_and_windows_terminal_install_and_uninstall_together(self):
        before = self.snapshot()
        self.assertEqual(install.install(self.windows_ctx("20260930-120000")), 0)
        self.assertIn("3/3 components installed", self.out.getvalue())
        self.assertEqual(sorted(path.name for path in self.fonts.iterdir()), sorted(fonts.MEMBERS))
        self.assertEqual(len([call for call in self.calls if call[:2] == ["reg.exe", "add"]]), len(fonts.MEMBERS))
        self.assertEqual(self.ubuntu()["font"], palette.VARIANTS["midnight"].wt_profile["font"])
        self.assertEqual(sorted(self.state()["components"]), ["claude", "font", "windows-terminal"])
        self.assertEqual(install.uninstall(self.windows_ctx("20260930-130000")), 0)
        self.assertIn(KEPT_WARNING, self.out.getvalue())
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(sorted(path.name for path in self.fonts.iterdir()), sorted(fonts.MEMBERS))

    def test_offline_the_font_fails_and_the_others_still_install(self):
        def offline(url):
            raise urllib.error.URLError("offline")

        before = self.snapshot()
        self.assertEqual(install.install(self.windows_ctx("20260930-120000", fetch=offline)), 2)
        output = self.out.getvalue()
        self.assertIn("2/3 components installed · failed: font (download failed (<urlopen error offline>))", output)
        self.assertIn(runner.PARTLY_INSTALLED, output)
        self.assertIn(NO_FONT_NOTE, output)
        self.assertEqual(list(self.fonts.iterdir()), [])
        self.assertNotIn("font", self.ubuntu())
        self.assertEqual(self.ubuntu()["colorScheme"], "Moonlit Candle")
        self.assertEqual(self.claude_settings()["theme"], "custom:moonlit-candle")
        self.assertEqual(sorted(self.state()["components"]), ["claude", "windows-terminal"])
        self.assertEqual(install.uninstall(self.windows_ctx("20260930-130000")), 0)
        self.assertEqual(self.snapshot(), before)
```

(Keep two blank lines before the class and before `if __name__ == "__main__":`.)

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_install.WindowsComponentsTest tests.test_install.InstallTest.test_claude_stays_while_its_settings_no_longer_hold_an_object tests.test_base`
Expected: these tests pin behaviour that already works (Task 1 is in place), so there is **no RED**. Real output from the prototype:
```
Ran 22 tests in …s

OK
```

- [ ] **Step 3: Implement**

No source changes. This task adds tests only.

- [ ] **Step 4: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 494 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_base.py tests/test_install.py
git commit -m "test: claude, font and windows-terminal through the runner; a settings file that is no longer an object" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: windows-terminal keeps image backups, puts back its images when settings.json refuses the write, checks every backup

**Items:**
- B11 (caller part): `apply` runs `backups.update(apply_changes(ctx, images))`; when a later image write raises, the backups already made are lost, so uninstall deletes the user's original image instead of giving it back.
- B14 + the D23 hole: when the `settings.json` write fails after the images were written, `apply` removes only the images that did not exist before and raises `ComponentFailed`. An image that held witchy's earlier render (or the user's own file) keeps this run's bytes with no record or a stale one: doctor fails, and the next install backs up witchy's image and makes it the restore target.
- B12: doctor's `backup_checks` for windows-terminal checks only the `settings.json` backup, not the image and `ritual-config.json` backups in `entry["files"]`.
- D6: no windows-terminal test for a blocked restore (`settings.json` no longer plain JSON, or no longer an object).

**Files:**
- Modify: `witchy/components/windows_terminal.py` (`_still_ours` replaced by `_put_back`; `apply` keeps backups in one dict, puts back images on a settings failure, records files with `applied_records`; `check` checks every backup)
- Modify: `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (section 3.3 bullet, section 9 windows-terminal rows)
- Test: `tests/test_components_wt.py`, `tests/test_install.py`

**Interfaces:**
- Consumes: `base.apply_changes(ctx, changes, backups)` and `base.applied_records(changes, earlier, backups)` (Task 2), `base.read`, `base.backup_checks`, `jsonio.write_atomic_bytes`, `runner.doctor`, the `InstallTestCase.wt_write_fails` helper (Task 2) and the `runner` import in `tests/test_install.py` (Task 3).
- Produces: nothing new. The windows-terminal entry shape is unchanged; `WindowsTerminalComponent.apply` still raises `ComponentFailed("could not write <settings path>")` when `settings.json` cannot be written.

**Decisions:**
1. **Put back, don't record, when `settings.json` fails.** A windows-terminal entry cannot exist without its settings record (`restore` needs `path`, `existed`, `backup`, the profile keys), so a partial entry like claude's (Task 2) is not possible. The runner keeps the earlier entry on `ComponentFailed`, so putting each image back as it was makes the files match that entry again (or match "nothing installed" on a first install).
2. **`_put_back` touches only a file that still holds this run's bytes, and each one is best effort.** It skips unchanged images, restores `before` when the file existed and removes it when this run created it. The old code removed every image with `before is None` without looking, so it deleted a file someone else wrote meanwhile, and an `OSError` from `unlink` escaped as a crash (the runner catches only `ComponentFailed`). The backups made before the writes are left in place: if a put-back fails, the backup is the only copy of the user's file.
3. **`applied_records` replaces `_still_ours` + `file_record`.** Both give the same record for a file that holds this run's bytes or the recorded bytes. They differ for a file the run did not write and someone changed or deleted: `_still_ours` dropped its record silently (doctor said every file matched, and the first backup was orphaned), while `applied_records` keeps the earlier record as the spec (section 3.3, Task 2) now says, so doctor reports `changed or missing` and the first backup stays the restore target. Pinned by `test_a_failed_image_copy_keeps_the_record_of_an_image_someone_changed`.
4. **What a failed image copy records (B11).** No `ComponentFailed` there: the settings are written without the background keys and an entry is recorded. With eight user PNGs and the third write failing, images 0 and 1 are recorded with this run's backups; image 2 gets no record, because nothing replaced it (it still holds the user's bytes; its backup was made just before the failed write and stays on disk unused). The triage note asked for "that PNG's backup" to be recorded; recording a backup for a file witchy never wrote would make uninstall rewrite the user's file, so the test asserts that image 2 is untouched and unrecorded instead.
5. **B12 uses claude's expression** (`[entry backup, *each file record's backup]`), with the `records` list `check` already builds.
6. **D6 tests pin existing behaviour (no RED).** Task 3 covered claude's blocked restore only. The component test checks both `restore_json` refusals; the runner test checks exit 2, the entry kept in state, the sky files and `ritual-config.json` still present, and a clean retry once the comment is gone.
7. **`test_a_put_back_that_fails_still_reports_the_settings_write` has no RED.** Today's code never touches an image that existed before, so it passes before and after; it pins that a failing put-back still ends in `ComponentFailed`, not an `OSError`.

- [ ] **Step 1: Write the failing tests**

`tests/test_components_wt.py`. Replace the import:

```python
from witchy.components.base import ComponentFailed, Plan, apply_changes
```

with:

```python
from witchy.components.base import ComponentFailed, Plan, apply_changes, read, sha
```

After the `install` method of `WindowsTerminalComponentTest`, add:

```python
    def write_fails(self, fails):
        """Writing a path for which ``fails(path)`` is true raises PermissionError; everything else writes."""
        real = jsonio.write_atomic_bytes

        def write(path, data):
            if fails(Path(path)):
                raise PermissionError(13, "Permission denied", str(path))
            return real(path, data)

        return mock.patch("witchy.jsonio.write_atomic_bytes", side_effect=write)

    def sky(self):
        """The bytes of each sky image beside settings.json, or None for one that is not there."""
        return [read(self.root / wt.sky_file(bin_)) for bin_ in range(8)]

    def later_plan(self, entry):
        """A reinstall by a later witchy version: another cursor colour and other sky images."""
        again = self.ctx(stamp="20261002-130000")
        again.sky_size = (128, 72)
        with mock.patch.dict(palette.WT_SCHEME, {"cursorColor": "#FF9BD7"}):
            return again, self.component.plan(again, entry)

    def user_sky(self, bins):
        """Sky images that are already there and are not witchy's (a copy the user made)."""
        for bin_ in bins:
            (self.root / wt.sky_file(bin_)).write_bytes(b"my own sky %d" % bin_)
        return self.sky()
```

After `test_restore_writes_settings_first_under_the_lock` (the last test of the class), add:

```python
    def test_backups_made_before_a_failed_image_copy_are_recorded(self):
        originals = self.user_sky(range(8))
        with self.write_fails(lambda path: path.name == wt.sky_file(2)):
            ctx, entry = self.install()
        self.assertIn("sky images not copied", self.out.getvalue())
        self.assertEqual(entry["files"], [
            {"path": str(self.root / wt.sky_file(bin_)),
             "backup": str(self.root / f"{wt.sky_file(bin_)}.bak-witchy-20261002-120000"),
             "installed_sha256": sha(read(self.root / wt.sky_file(bin_)))} for bin_ in (0, 1)])
        self.assertEqual(self.sky()[2:], originals[2:])
        apply_changes(ctx, self.component.restore(self.ctx(stamp="20261002-130000"), entry).changes)
        self.assertEqual(self.sky(), originals)

    def test_a_failed_settings_write_puts_back_the_images_it_wrote(self):
        originals = self.user_sky(range(4))
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        with self.write_fails(lambda path: path == self.wt):
            with self.assertRaisesRegex(ComponentFailed, "^could not write "):
                self.component.apply(ctx, plan)
        self.assertEqual(self.sky(), originals)
        self.assertFalse(self.config().exists())

    def test_a_failed_settings_write_on_reinstall_puts_back_the_earlier_images(self):
        _, entry = self.install()
        earlier = self.sky()
        again, plan = self.later_plan(entry)
        with self.write_fails(lambda path: path == self.wt):
            with self.assertRaises(ComponentFailed):
                self.component.apply(again, plan)
        self.assertEqual(self.sky(), earlier)
        self.assertEqual({check.level for check in self.component.check(again, entry)}, {"ok"})

    def test_the_put_back_leaves_an_image_someone_else_rewrote(self):
        image = self.root / wt.sky_file(0)

        def fails(path):
            if path == self.wt:
                image.write_bytes(b"written meanwhile")
                return True
            return False

        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        with self.write_fails(fails):
            with self.assertRaises(ComponentFailed):
                self.component.apply(ctx, plan)
        self.assertEqual(self.sky(), [b"written meanwhile"] + [None] * 7)

    def test_a_put_back_that_fails_still_reports_the_settings_write(self):
        _, entry = self.install()
        again, plan = self.later_plan(entry)
        refused = []

        def fails(path):
            if path == self.wt:
                refused.append(path)
            return bool(refused)  # the settings write fails, and every write after it

        with self.write_fails(fails):
            with self.assertRaisesRegex(ComponentFailed, "^could not write "):
                self.component.apply(again, plan)
        self.assertEqual(self.sky(), [image.after for image in plan.data["images"]])

    def test_a_failed_image_copy_keeps_the_record_of_an_image_someone_changed(self):
        _, entry = self.install()
        changed = self.root / wt.sky_file(3)
        changed.write_bytes(b"edited")
        again, plan = self.later_plan(entry)
        with self.write_fails(lambda path: path.suffix == ".png"):
            entry2 = self.component.apply(again, plan)
        self.assertEqual(entry2["files"], entry["files"])
        fails = [check.message for check in self.component.check(again, entry2) if check.level == "fail"]
        self.assertEqual(fails, [f"changed or missing: {changed}"])

    def test_check_warns_when_an_image_backup_is_gone(self):
        self.user_sky([0])
        ctx, entry = self.install()
        backup = Path(entry["files"][0]["backup"])
        backup.unlink()
        warnings = [check.message for check in self.component.check(ctx, entry) if check.level == "warn"]
        self.assertEqual(warnings, [f"backup {backup} is missing; uninstall cannot give back the original bytes"])

    def test_restore_is_blocked_while_settings_cannot_be_read_back(self):
        _, entry = self.install()
        installed = self.wt.read_text(encoding="utf-8")
        for text, reason in [("// mine\n" + installed, "is no longer plain JSON; make it plain JSON again"),
                             ("[]\n", "no longer holds a JSON object; fix it by hand")]:
            with self.subTest(reason=reason):
                self.wt.write_text(text, encoding="utf-8")
                with self.assertRaises(ComponentFailed) as caught:
                    self.component.restore(self.ctx(stamp="20261002-130000"), entry)
                self.assertEqual(str(caught.exception), f"{self.wt} {reason}")
```

`tests/test_install.py`. In `InstallTest`, after `test_retry_after_a_failed_windows_terminal_write_keeps_the_originals`, add:

```python
    def test_a_failed_windows_terminal_write_gives_back_the_sky_images_it_replaced(self):
        for bin_ in range(4):
            (self.wt.parent / install.wt.sky_file(bin_)).write_bytes(b"my own sky %d" % bin_)
        before = self.snapshot()
        with self.wt_write_fails():
            self.assertEqual(install.install(self.ctx()), 2)
        self.assertNotIn("windows-terminal", self.state()["components"])
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 0)
        self.assertEqual(self.snapshot(), before)

    def test_a_failed_windows_terminal_rewrite_keeps_the_sky_images_state_records(self):
        before = self.snapshot()
        install.install(self.ctx())
        later = self.ctx(stamp="20260930-120500")
        later.sky_size = (128, 72)
        with self.wt_write_fails(), mock.patch.dict(install.palette.WT_SCHEME, {"cursorColor": "#FF9BD7"}):
            self.assertEqual(install.install(later), 2)
        self.assertEqual(runner.doctor(self.ctx()), 0)
        self.assertEqual(install.install(self.ctx(stamp="20260930-120600")), 0)
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 0)
        self.assertEqual(self.snapshot(), before)
```

After `test_claude_stays_while_its_settings_no_longer_hold_an_object`, add:

```python
    def test_windows_terminal_stays_while_its_settings_have_comments(self):
        before = self.snapshot()
        install.install(self.ctx())
        installed = self.wt.read_text(encoding="utf-8")
        self.wt.write_text("// a comment\n" + installed, encoding="utf-8")
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 2)
        self.assertIn(f"windows-terminal: {self.wt} is no longer plain JSON; make it plain JSON again; "
                      "run uninstall again.", self.out.getvalue())
        self.assertEqual(list(self.state()["components"]), ["windows-terminal"])
        self.assertEqual(sorted(path.name for path in self.wt.parent.glob("moonlit-candle-sky-*.png")),
                         [install.wt.sky_file(bin_) for bin_ in range(8)])
        self.assertTrue((self.claude / "witchy" / "ritual-config.json").is_file())
        self.assertEqual(self.claude_settings(), CLAUDE_ORIGINAL)
        self.wt.write_text(installed, encoding="utf-8")
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-131000")), 0)
        self.assertEqual(self.snapshot(), before)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_components_wt tests.test_install`
Expected (real output from the prototype, trimmed):
```
FAIL: test_a_failed_image_copy_keeps_the_record_of_an_image_someone_changed (…)
AssertionError: Lists differ: [{'pa[514 chars]-sky-4.png', 'backup': None, … != [{'pa[514 chars]-sky-3.png', 'backup': None, …
FAIL: test_a_failed_settings_write_on_reinstall_puts_back_the_earlier_images (…)
AssertionError: Lists differ: [b'\x[39 chars]00\x00\x80\x00\x00\x00H\x08… != [b'\x[39 chars]00\x01\x00\x00\x00\x00\x90\x08…
FAIL: test_a_failed_settings_write_puts_back_the_images_it_wrote (…)
AssertionError: Lists differ: [b'\x89PNG\r\n\x1a\n…None] != [b'my own sky 0', b'my own sky 1', …None]
FAIL: test_backups_made_before_a_failed_image_copy_are_recorded (…)
AssertionError: Lists differ: [{'pa[55 chars]up': None, … != [{'pa[55 chars]up': '/tmp/…/moonlit-candle-sky-0.pn…
FAIL: test_check_warns_when_an_image_backup_is_gone (…)
AssertionError: Lists differ: [] != ['backup /tmp/…/moonlit-candle-s[90 chars]tes']
FAIL: test_the_put_back_leaves_an_image_someone_else_rewrote (…)
AssertionError: Lists differ: [None, None, None, None, None, None, None, None] != [b'written meanwhile', None, …]
FAIL: test_a_failed_windows_terminal_rewrite_keeps_the_sky_images_state_records (tests.test_install.InstallTest…)
AssertionError: 1 != 0
FAIL: test_a_failed_windows_terminal_write_gives_back_the_sky_images_it_replaced (tests.test_install.InstallTest…)
AssertionError: {'/tm…': b'\x89PNG\r\n…'} != {'/tm…': b'my own sky 0', …}
Ran 70 tests in 8.772s
FAILED (failures=8)
```
`test_a_put_back_that_fails_still_reports_the_settings_write`, `test_restore_is_blocked_while_settings_cannot_be_read_back` and `test_windows_terminal_stays_while_its_settings_have_comments` pass already (decisions 6 and 7). Without its `runner.doctor` line, `test_a_failed_windows_terminal_rewrite_keeps_the_sky_images_state_records` still fails on the final `snapshot()` comparison: uninstall gives back witchy's second render instead of removing the images.

- [ ] **Step 3: Implement**

`witchy/components/windows_terminal.py`. Replace the base import:

```python
from .base import (Change, Check, ComponentFailed, JsonPlan, Plan, apply_changes, backup_checks, file_change,
                   file_record, fix_command, read, restore_copy, restore_json, sha)
```

with:

```python
from .base import (Change, Check, ComponentFailed, JsonPlan, Plan, applied_records, apply_changes, backup_checks,
                   file_change, fix_command, read, restore_copy, restore_json, sha)
```

Replace the whole function `_still_ours` with:

```python
def _put_back(images: list[Change]) -> None:
    """Undo this run's image writes once settings.json refused the write: no entry will describe them.

    Only a file that still holds this run's bytes is touched, and each one is best effort.
    """
    for image in images:
        if image.before == image.after:
            continue
        try:
            if read(image.path) != image.after:
                continue
            if image.before is None:
                image.path.unlink()
            else:
                jsonio.write_atomic_bytes(image.path, image.before)
        except OSError:
            pass  # best effort: the settings write is the failure that gets reported
```

Replace the method `apply` with:

```python
    def apply(self, ctx: Any, plan: Plan) -> dict:
        json_plan: JsonPlan = plan.data["json"]
        settings, images, config, earlier = json_plan.change, plan.data["images"], plan.data["config"], plan.data["earlier"]
        backups: dict[Path, Path] = {}
        try:
            apply_changes(ctx, images, backups)
            background = True
        except OSError as exc:
            ctx.say(f"windows-terminal: sky images not copied ({exc})")
            background = False
        font = plan.data["font"] == "installed" or (plan.data["font"] == "planned" and ctx.results.get("font") == "ok")
        if plan.data["font"] == "planned" and not font and NO_FONT_NOTE not in plan.notes:
            plan.notes.append(NO_FONT_NOTE)
        if (font, background) != (plan.data["font"] is not None, True):
            settings.after, json_plan.extra = plan.data["build"](font, background)
        try:
            apply_changes(ctx, [settings], backups)
        except OSError as exc:
            _put_back(images)
            ctx.say(f"Windows Terminal: could not write {settings.path} ({exc}); {WT_SKIP}.")
            raise ComponentFailed(f"could not write {settings.path}") from exc
        entry = json_plan.entry(backups.get(settings.path))
        if background:
            try:
                apply_changes(ctx, [config], backups)
            except OSError as exc:
                ctx.say(f"windows-terminal: could not write {config.path} ({exc}); the sky keeps tonight's phase.")
        entry["files"] = applied_records([*images, config], earlier, backups)
        return entry
```

In `check`, replace the last line:

```python
        return checks + backup_checks(self.name, [entry.get("backup")])
```

with:

```python
        return checks + backup_checks(self.name, [entry.get("backup"), *(record.get("backup") for record in records)])
```

`docs/superpowers/specs/2026-10-02-shell-ritual-design.md`. In section 3.3, after the bullet that starts `- An apply that stops part-way (a file write fails)`, add:

```
- `windows-terminal` cannot keep an entry without its `settings.json` record, so when that write fails it puts back the sky images it wrote (removing the ones it created) and the state keeps the earlier entry, if any. An image someone else changed in the meantime is left alone.
```

In section 9, replace the two windows-terminal rows:

```
| windows-terminal | sky image copy `OSError` | set no background keys; the rest applies | `windows-terminal: sky images not copied (…)` |
| windows-terminal | `StrictJsonError`, profile not found, write `OSError` | existing handling | existing messages |
```

with:

```
| windows-terminal | sky image copy `OSError` | set no background keys; the rest applies; the images already copied stay recorded | `windows-terminal: sky images not copied (…)` |
| windows-terminal | `StrictJsonError`, profile not found | existing handling | existing messages |
| windows-terminal | `settings.json` write `OSError` | `failed: could not write <path>`, exit 2; the sky images this run wrote are put back (best effort); state keeps the earlier entry | `Windows Terminal: could not write <path> (…); skipping the terminal colour scheme.` |
```

- [ ] **Step 4: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 505 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/components/windows_terminal.py tests/test_components_wt.py tests/test_install.py docs/superpowers/specs/2026-10-02-shell-ritual-design.md
git commit -m "fix: windows-terminal keeps image backups on a failed copy, puts back its images when settings.json refuses the write" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: font tests for an unreadable registry, an unreadable font name and a failed copy

**Items:**
- B2: untested paths in `witchy/components/font.py`: the registry-unreadable skip in `plan` (and the matching doctor warning in `check`), the unreadable TTF name in `apply`, and the copy `OSError` in `apply`.

**Files:**
- Modify: `tests/fakes.py` (`fake_windows` gains `reg_query_code`, default 0)
- Test: `tests/test_components_font.py`

**Interfaces:**
- Consumes: `fonts.MEMBERS`, `fonts.SHA256`, `make_zip`, `make_ttf`, `jsonio.write_atomic_bytes`.
- Produces: `tests.fakes.fake_windows(echo=None, reg_query="", reg_query_code=0, reg_add_code=0, calls=None)`. `reg.exe query` exits with `reg_query_code`; with the default, every existing caller behaves as before (all of them pass keyword arguments).

**Decisions:**
1. **Test only; no RED.** Every path already works; these tests pin the user-visible outcome. No bug turned up, so `font.py` is unchanged.
2. **The doctor warning for an unreadable registry is covered too** (`test_check_warns_when_the_registry_cannot_be_read`). It is the same B2 gap (`check`, lines 116-118) and needs the same new fake argument.
3. **"Nothing half-recorded"** is checked as: `apply` raises `ComponentFailed` (the runner records no `font` entry for it) and no `reg.exe add` ran. For the copy failure the two fonts copied before it stay, as spec section 9 says ("files already copied stay"). For the bad name, nothing is copied, because every name is read before the first copy.
4. **The garbage TTF is the third member**, so the test also shows that the names are checked for every member before anything is copied. `release()` re-patches `fonts.SHA256` for the new archive; `addCleanup` stops it before the `setUp` patcher, so the original value comes back.

- [ ] **Step 1: Write the failing tests**

`tests/fakes.py`. Replace the head of `fake_windows`, from the `def` line to the end of its docstring:

```python
def fake_windows(echo=None, reg_query="", reg_add_code=0, calls=None):
    """A ``run`` that answers like a Windows host.

    ``cmd.exe /c echo %VAR%`` prints ``echo[VAR]`` (cmd.exe prints ``%VAR%`` back when a variable is unset),
    ``reg.exe query`` prints ``reg_query`` and ``reg.exe add`` exits with ``reg_add_code``. Any other command
    fails the test. Every call is appended to ``calls`` when it is a list.
    """
```

with:

```python
def fake_windows(echo=None, reg_query="", reg_query_code=0, reg_add_code=0, calls=None):
    """A ``run`` that answers like a Windows host.

    ``cmd.exe /c echo %VAR%`` prints ``echo[VAR]`` (cmd.exe prints ``%VAR%`` back when a variable is unset),
    ``reg.exe query`` prints ``reg_query`` and exits with ``reg_query_code``, and ``reg.exe add`` exits with
    ``reg_add_code``. Any other command fails the test. Every call is appended to ``calls`` when it is a list.
    """
```

and replace:

```python
            return subprocess.CompletedProcess(args, 0, stdout=reg_query, stderr="")
```

with:

```python
            return subprocess.CompletedProcess(args, reg_query_code, stdout=reg_query, stderr="")
```

`tests/test_components_font.py`. Replace the import:

```python
from witchy import fonts
```

with:

```python
from witchy import fonts, jsonio
```

Replace the method `ctx` with:

```python
    def ctx(self, reg=None, reg_query_code=0, reg_add_code=0, fetch=None, echo=None):
        self.out = io.StringIO()
        run = fake_windows(echo={"USERPROFILE": "C:\\Users\\user\r\n"} if echo is None else echo,
                           reg_query=reg_listing(OTHER_FONT if reg is None else reg), reg_query_code=reg_query_code,
                           reg_add_code=reg_add_code, calls=self.calls)
        return Context(home=self.root / "home", env={}, out=self.out, run=run, mount_root=self.mnt,
                       fetch=fetch or self.fetch)
```

Between `ctx` and `install`, add:

```python
    def release(self, members):
        """Serve ``members`` as the release archive, with a matching checksum."""
        self.archive = make_zip(members)
        patcher = mock.patch.object(fonts, "SHA256", hashlib.sha256(self.archive).hexdigest())
        patcher.start()
        self.addCleanup(patcher.stop)

    def adds(self):
        return [call for call in self.calls if call[:2] == ["reg.exe", "add"]]
```

After `test_registry_failure_fails`, add:

```python
    def test_unreadable_registry_is_skipped(self):
        plan = self.component.plan(self.ctx(reg_query_code=1), None)
        self.assertEqual(plan.skip, "cannot read the font registry")
        self.assertIn("font: cannot read the font registry (reg.exe); keeping the current font.", self.out.getvalue())
        self.assertEqual(self.fetched, [])

    def test_check_warns_when_the_registry_cannot_be_read(self):
        _, _, entry = self.install()
        checks = self.component.check(self.ctx(reg_query_code=1), entry)
        self.assertEqual([(check.level, check.message) for check in checks],
                         [("warn", "cannot read the font registry (reg.exe)")])

    def test_an_unreadable_font_name_fails_before_anything_is_copied(self):
        members = {name: make_ttf(f"Maple Mono NF {style}") for name, style in zip(fonts.MEMBERS, STYLES)}
        self.release({**members, fonts.MEMBERS[2]: b"not a font"})
        with self.assertRaisesRegex(ComponentFailed, r"^the font's name table is not readable \("):
            self.install()
        self.assertIn("font: the font's name table is not readable (", self.out.getvalue())
        self.assertEqual(list(self.folder.iterdir()), [])
        self.assertEqual(self.adds(), [])

    def test_a_failed_copy_fails_and_registers_nothing(self):
        real = jsonio.write_atomic_bytes
        target = self.folder / fonts.MEMBERS[2]

        def write(path, data):
            if Path(path) == target:
                raise PermissionError(13, "Permission denied", str(path))
            return real(path, data)

        with mock.patch("witchy.jsonio.write_atomic_bytes", side_effect=write):
            with self.assertRaisesRegex(ComponentFailed, r"^could not copy the font files \(\[Errno 13\] "):
                self.install()
        self.assertIn(f"font: could not copy the font files ([Errno 13] Permission denied: '{target}'); "
                      "keeping the current font.", self.out.getvalue())
        self.assertEqual(sorted(path.name for path in self.folder.iterdir()), sorted(fonts.MEMBERS[:2]))
        self.assertEqual(self.adds(), [])
```

- [ ] **Step 2: Run them (no RED: they pin existing behaviour)**

Run: `/usr/bin/python3 -m unittest tests.test_components_font.FontComponentTest.test_unreadable_registry_is_skipped tests.test_components_font.FontComponentTest.test_check_warns_when_the_registry_cannot_be_read tests.test_components_font.FontComponentTest.test_an_unreadable_font_name_fails_before_anything_is_copied tests.test_components_font.FontComponentTest.test_a_failed_copy_fails_and_registers_nothing`
Expected (real output from the prototype):
```
Ran 4 tests in 0.043s

OK
```
(Without the `tests/fakes.py` change, the two registry tests error with `TypeError: fake_windows() got an unexpected keyword argument 'reg_query_code'`.)

- [ ] **Step 3: Implement**

Nothing to implement: `witchy/components/font.py` already behaves as the tests expect.

- [ ] **Step 4: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 509 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/fakes.py tests/test_components_font.py
git commit -m "test: font skips an unreadable registry, fails on an unreadable font name or a failed copy" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: fish install and uninstall (partial write, new-tab note, byte-exact values, uninstall warnings)

**Items:**
- D23-fish: `FishComponent.apply` turns a file-write `OSError` into `ComponentFailed` and records nothing; the retry then backs up witchy's own bytes and uninstall gives those back.
- D4: `NEW_TAB_NOTE` ("…see the new prompt and greeting…") is added before it is known whether Tide is there.
- D13: Tide values are read and written in text mode (`\r` becomes `\n`, invalid UTF-8 becomes U+FFFD), so a restore can write back altered values.
- D14: after uninstall, a prompt-item list the user changed but that still lists `moon` gets only the generic "was changed" warning.
- D15: when Tide was removed before uninstall, every recorded variable gives its own warning.
- D16: when fish is not on PATH at uninstall, the warning does not say that Tide keeps witchy's colours and the `moon` item, or how to undo them.

**Files:**
- Modify: `witchy/components/base.py` (`Command.exact`; `run_command` passes bytes for an exact command)
- Modify: `witchy/components/fish.py` (`GREETING_NOTE`, `PROMPT_ITEMS`, `_shown`, `_changed_warning`, exact snapshot and set commands, notes in `plan`, `apply` + new `_partial`, warnings in `restore`)
- Modify: `witchy/state.py` (`save` writes a lone surrogate as a `\udcXX` escape)
- Modify: `tests/fakes.py` (`fake_fish` handles bytes and text the way `subprocess.run` does)
- Modify: `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (section 5.3 bullets, section 9 row)
- Test: `tests/test_components_fish.py`, `tests/test_base.py`, `tests/test_state.py`

**Interfaces:**
- Consumes: `base.apply_changes(ctx, changes, backups)` and `base.applied_records(changes, earlier, backups)` from Task 2; `Plan.outcome`, `Plan.notes`; `jsonio.write_atomic_bytes`; `build.fish_files`.
- Produces:
  - `base.Command(args, label, input=None, exact=False)`. With `exact=True`, `run_command` sends `input` as `input.encode("utf-8", "surrogateescape")`, calls `ctx.run` without `text`/`errors`, and returns the `CompletedProcess` with `stdout` and `stderr` decoded as `bytes.decode("utf-8", "surrogateescape")`. A `ctx.run` stand-in for an exact command must return bytes. Commands without `exact` are unchanged (`text=True, errors="replace"`).
  - `fish.snapshot` and `fish.set_command` build exact commands; `REFRESH_SCRIPT`'s command is not exact.
  - `fish.GREETING_NOTE = "Open a new terminal tab to see the greeting."`; `fish.PROMPT_ITEMS = ("tide_left_prompt_items", "tide_right_prompt_items")`.
  - fish plan notes: `[NEW_TAB_NOTE]` with Tide, `[GREETING_NOTE]` without Tide or when fish does not answer, `[]` when fish is not found; then `NO_EZA_NOTE` when eza is missing.
  - fish partial apply: `plan.outcome = "failed: could not write the fish files (<OSError text>)"`, prints `fish: could not write the fish files (<OSError text>); run install again.`, no Tide `set` call, the new-tab notes are dropped, and the entry is `{"files": applied_records(...) + <earlier records of paths no longer shipped>, "variables": <variables recorded earlier>}`. When that entry has no files and no variables it raises `ComponentFailed("could not write the fish files (<OSError text>)")`.
  - `tests.fakes.fake_fish(...)` now takes `text`/`errors` like `subprocess.run`: without `text` it reads bytes and returns bytes; with `text` it emulates the decode and newline translation. `calls` still holds `(args, input as str)`.

**Decisions:**
1. **D23 follows Task 2's claude fix exactly** (record, don't roll back): the files that hold this run's bytes are recorded with their backups, the Tide variables are not set (the moon item's function may be missing), and the runner records the entry with the `failed: …` outcome. The new-tab notes are dropped on that path because nothing new is ready to see.
2. **The failing file in the end-to-end tests is `functions/lt.fish`**, the file written right after `functions/ll.fish`, so the "user's original comes back" case has a user file that was overwritten before the failure. The component-level test fails the second write of the plan (`plan.changes[1]`), as the triage asked. Proof that the end-to-end tests catch the real bug and not only the crash: with `_partial` changed to always raise `ComponentFailed` (crash fixed, nothing recorded), all three `PartialWriteTest` end-to-end tests fail on the final `snapshot()` comparison (uninstall leaves witchy's first `conf.d/witchy.fish` bytes in place).
3. **D4 without fish: no new-tab note at all.** Without fish there is no greeting to see. When fish is there but does not answer (a timeout), the greeting still shows, so it gets `GREETING_NOTE`.
4. **D13 uses an `exact` flag on `Command`**, not on `run_command`, because the restore's set command is run by the runner (`run_command(ctx, command)`), so the flag has to travel with the command. Values stay `str` in memory and in state, with surrogate escapes for bytes that are not UTF-8; `_fields` and the rest of the code are unchanged.
5. **`state.save` encodes with `backslashreplace`.** A lone surrogate cannot be encoded as UTF-8, so the first install with such a value would have crashed while saving state. `backslashreplace` turns only lone surrogates into `\udcXX`, which is a valid JSON escape that `json.loads` reads back as the same surrogate; every other character is written as before (`ensure_ascii=False` keeps `é`).
6. **Dry-run actions show such bytes as U+FFFD (`_shown`)**: printing a lone surrogate to a strict UTF-8 stdout would crash `install --dry-run`. That test pins the new code only; it passes on the old code too (which had U+FFFD already).
7. **The real-fish test checks `\r` and a non-ASCII character, not invalid UTF-8.** Verified on fish 3.7.0 in a temporary HOME: a universal variable holding byte `0xFF` is written to `fish_variables` as `` and fish then fails to parse it ("Unable to parse universal variable message"), and `read -z` inside a `while` loop drops invalid bytes. So fish itself cannot keep such a value; the Python side is still byte-exact (the fake-based test proves it).
8. **D14 gives the exact fish command**: `set -U <name> (string match -v moon $<name>)` (checked in a temporary fish 3.7.0: it removes every `moon` item and keeps the export flag). Tide 6.1.1's `_tide_remove_unusable_items` only prunes tool items, so a `moon` item whose function is gone stays in the prompt.
9. **D15: one warning when every recorded variable is absent**, then the records are dropped (the component uninstalls). Tide's own uninstall erases every `tide_` universal variable.
10. **D16 points at `tide configure`**: in Tide 6.1.1 its last step (`_tide_finish`) sets every `tide_` variable, prompt items included, from the chosen style. The previous values are not printed: they would be up to 32 `set -U` lines.

- [ ] **Step 1: Write the failing tests**

`tests/fakes.py`. Replace the whole `fake_fish` function with:

```python
def fake_fish(variables=None, tide=True, fail_at=None, missing=False, noise="", calls=None):
    """A ``run`` that answers witchy's fish scripts the way fish would, byte for byte.

    ``variables`` maps names to ``{"value": [...], "exported": bool}`` and is changed in place by the set
    script. A value stands for its UTF-8 bytes with surrogate escapes, so it can hold any byte but NUL.
    Standard input and output are handled as ``subprocess.run`` handles them: bytes, or text that is decoded
    with ``errors`` and has its newlines translated. ``fail_at`` names a variable whose set fails (the script
    stops there, exit 1); ``missing`` makes fish absent; ``noise`` is what config.fish prints first. Every
    call is appended to ``calls``, with its input as a string.
    """
    from witchy.components import fish

    store = {} if variables is None else variables

    def answer(args, received):
        if args[:3] == ["fish", "-c", fish.SNAPSHOT_SCRIPT] and args[3] == "--":
            fields = ["tide" if tide else "no-tide"]
            for name in args[4:]:
                if name in store:
                    value = store[name]
                    fields += [name, "exported" if value["exported"] else "unexported", str(len(value["value"])),
                               *value["value"]]
                else:
                    fields += [name, "absent"]
            return 0, fields
        if args == ["fish", "-c", fish.SET_SCRIPT]:
            items, done = received.split("\0")[:-1], []
            while items:
                name, mode, count = items[:3]
                values, items = items[3:3 + int(count)], items[3 + int(count):]
                if name == fail_at:
                    return 1, done
                if mode == "erase":
                    store.pop(name, None)
                else:
                    exported = mode == "exported" or store.get(name, {}).get("exported", False)
                    store[name] = {"value": values, "exported": exported}
                done.append(name)
            return 0, done
        if args == ["fish", "-c", fish.REFRESH_SCRIPT]:
            return 0, None
        raise AssertionError(f"unexpected command in a test: {args}")

    def run(args, input=None, text=False, errors="strict", **kwargs):
        args = list(args)
        if text and input is not None:
            input = input.encode("utf-8", errors)
        received = None if input is None else input.decode("utf-8", "surrogateescape")
        if calls is not None:
            calls.append((args, received))
        if missing:
            raise FileNotFoundError(2, "No such file or directory", "fish")
        code, fields = answer(args, received)
        printed = noise + ("" if fields is None else "".join(f"{field}\0" for field in [fish.SENTINEL, *fields]))
        stdout = printed.encode("utf-8", "surrogateescape")
        if text:
            stdout = stdout.decode("utf-8", errors).replace("\r\n", "\n").replace("\r", "\n")
            return subprocess.CompletedProcess(args, code, stdout=stdout, stderr="")
        return subprocess.CompletedProcess(args, code, stdout=stdout, stderr=b"")
    return run
```

(The suite stays green with this fake alone: it emulates the text mode the current code uses.)

`tests/test_base.py`. In `RunCommandTest`, after `test_passes_list_arguments_input_env_and_a_timeout`, add:

```python
    def test_an_exact_command_sends_and_reads_every_byte_unchanged(self):
        seen = {}

        def run(args, **kwargs):
            seen.update(kwargs)
            return subprocess.CompletedProcess(args, 0, stdout=b"a\r\nb\xff\0", stderr=b"")

        done = run_command(self.ctx(run), Command(("fish", "-c", "x"), "do x", "c\r\udcff", exact=True))
        self.assertEqual(seen["input"], b"c\r\xff")
        self.assertNotIn("text", seen)
        self.assertEqual(done.stdout, "a\r\nb\udcff\0")
```

`tests/test_state.py`. In `LoadSaveTest`, after `test_save_then_load_round_trips`, add:

```python
    def test_a_fish_value_that_is_not_utf8_round_trips(self):
        # A byte that is not UTF-8 is held as a lone surrogate; the file stays valid UTF-8 JSON.
        value = {"value": ["FF\udcff", "é\r"], "exported": False}
        data = dict(state.empty("midnight"), components={"fish": {"files": [], "variables": {"v": value}}})
        state.save(self.path, data)
        self.path.read_bytes().decode("utf-8")
        self.assertEqual(state.load(self.path), data)
        self.assertIn('"é\\r"', self.path.read_text(encoding="utf-8"))
```

`tests/test_components_fish.py`. Replace the imports:

```python
import io
import json
import subprocess
from datetime import datetime
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.fakes import fake_fish
from witchy import build, components, palette, runner
from witchy.components import fish
from witchy.context import Context
```

with:

```python
import io
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.fakes import fake_fish
from witchy import build, components, jsonio, palette, runner
from witchy.components import fish
from witchy.components.base import ComponentFailed, sha
from witchy.context import Context

FISH = shutil.which("fish")
```

In `FishTestCase`, after the `value` method, add:

```python
    def write_fails(self, target):
        """``target`` cannot be written; everything else writes."""
        real = jsonio.write_atomic_bytes

        def write(path, data):
            if Path(path) == target:
                raise PermissionError(13, "Permission denied", str(path))
            return real(path, data)

        return mock.patch.object(jsonio, "write_atomic_bytes", side_effect=write)

    def fish_files_change(self):
        """A later witchy version that ships different fish files."""
        real = build.fish_files

        def render(*args, **kwargs):
            return {name: data + b"\n" for name, data in real(*args, **kwargs).items()}

        return mock.patch.object(build, "fish_files", side_effect=render)
```

In `InstallTest`, before `test_without_fish_the_files_still_install`, add:

```python
    def test_the_new_tab_note_promises_only_what_this_install_changes(self):
        def slow(args, **kwargs):
            raise subprocess.TimeoutExpired(args, 5)

        cases = ((fake_fish(self.variables), [fish.NEW_TAB_NOTE]),
                 (fake_fish(self.variables, tide=False), [fish.GREETING_NOTE]),
                 (slow, [fish.GREETING_NOTE]),
                 (fake_fish(missing=True), []))
        for run, notes in cases:
            with self.subTest(notes=notes):
                plan = fish.FishComponent().plan(self.ctx(run=run), None)
                self.assertEqual(plan.notes, notes + [fish.NO_EZA_NOTE])
```

In `InstallTest`, the set call is now exact, so its stand-ins answer in bytes. In `test_a_set_call_killed_by_a_signal_is_an_unknown_outcome`, replace:

```python
            args, -9, stdout=f"{fish.SENTINEL}\0{name}\0", stderr=""))
```

with:

```python
            args, -9, stdout=f"{fish.SENTINEL}\0{name}\0".encode(), stderr=b""))
```

and in `test_a_set_call_with_no_marker_is_an_unknown_outcome`, replace:

```python
        self.unknown_outcome(lambda args: subprocess.CompletedProcess(args, 0, stdout="garbage", stderr=""))
```

with:

```python
        self.unknown_outcome(lambda args: subprocess.CompletedProcess(args, 0, stdout=b"garbage", stderr=b""))
```

In `InstallTest`, before `test_reinstall_keeps_the_first_previous_value`, add:

```python
    def test_a_value_comes_back_byte_for_byte(self):
        # A carriage return, a line break and a byte that is not UTF-8 (0xFF, held as the surrogate U+DCFF).
        odd = {"value": ["FF\rB7\udcffC5", "two\r\nlines"], "exported": False}
        self.variables["tide_pwd_bg_color"] = odd
        self.assertEqual(runner.install(self.ctx()), 0)
        self.assertEqual(self.entry()["variables"]["tide_pwd_bg_color"]["previous"], odd)
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.variables["tide_pwd_bg_color"], odd)
        self.assertIn("tide_pwd_bg_color\0set\0" "2\0FF\rB7\udcffC5\0two\r\nlines\0", self.set_calls()[-1])

    def test_a_dry_run_shows_bytes_that_are_not_utf8_as_replacement_characters(self):
        self.variables["tide_pwd_bg_color"] = {"value": ["FF\udcff"], "exported": False}
        self.assertEqual(runner.install(self.ctx(dry_run=True)), 0)
        self.assertIn("fish: set -U tide_pwd_bg_color B99AFF (now: FF�)", self.out.getvalue())
        self.out.getvalue().encode("utf-8")  # printable on a strict UTF-8 terminal
```

In `UninstallTest`, after `test_a_variable_the_user_changed_is_left_with_a_warning`, add:

```python
    def test_a_prompt_item_list_that_still_lists_moon_says_how_to_remove_it(self):
        runner.install(self.ctx())
        self.variables["tide_left_prompt_items"]["value"] = ["moon", "pwd", "time"]
        self.variables["tide_right_prompt_items"]["value"] = ["status", "time"]
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.value("tide_left_prompt_items"), ["moon", "pwd", "time"])
        self.assertIn("tide_left_prompt_items was changed after install; leaving it as it is, but it still lists "
                      "moon. Remove it with: set -U tide_left_prompt_items "
                      "(string match -v moon $tide_left_prompt_items)", self.out.getvalue())
        self.assertIn("tide_right_prompt_items was changed after install; leaving it as it is.", self.out.getvalue())

    def test_tide_removed_before_uninstall_gives_one_warning(self):
        runner.install(self.ctx())
        self.variables.clear()  # Tide's own uninstall erases every tide_ variable
        self.calls.clear()
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        output = self.out.getvalue()
        self.assertIn("fish: Tide's variables are gone (was Tide removed?); nothing to restore.", output)
        self.assertNotIn("changed after install", output)
        self.assertEqual(self.set_calls(), [])
        self.assertFalse((self.home / ".claude" / "witchy").exists())
```

In `UninstallTest.test_without_fish_the_files_still_go`, replace:

```python
        self.assertIn("fish not found; the Tide variables were left as they are.", self.out.getvalue())
```

with:

```python
        self.assertIn("fish: fish not found, so Tide keeps witchy's colours and the moon item; to reset them, run "
                      "tide configure in fish.", self.out.getvalue())
```

Between `UninstallTest` and `DoctorTest`, add:

```python
class PartialWriteTest(FishTestCase):
    """A fish file that cannot be written: what was written stays recorded, so uninstall still undoes it."""

    def setUp(self):
        super().setUp()
        self.functions = self.home / ".config" / "fish" / "functions"

    def snapshot(self):
        return {str(path): path.read_bytes() for path in sorted(self.home.rglob("*"))
                if path.is_file() and ".bak-witchy-" not in path.name}

    def test_a_write_that_fails_part_way_records_what_was_written(self):
        ctx = self.ctx()
        component = fish.FishComponent()
        plan = component.plan(ctx, None)
        first, second = plan.changes[0].path, plan.changes[1].path
        with self.write_fails(second):
            entry = component.apply(ctx, plan)
        self.assertEqual(entry, {"files": [{"path": str(first), "backup": None,
                                            "installed_sha256": sha(first.read_bytes())}], "variables": {}})
        self.assertRegex(plan.outcome, r"^failed: could not write the fish files "
                                       r"\(\[Errno 13\] Permission denied: '.*'\)$")
        self.assertIn("fish: could not write the fish files (", self.out.getvalue())
        self.assertEqual(self.set_calls(), [])
        self.assertEqual(self.variables, USER_TIDE)
        self.assertEqual(plan.notes, [fish.NO_EZA_NOTE])

    def test_a_first_write_that_fails_records_nothing(self):
        ctx = self.ctx()
        component = fish.FishComponent()
        plan = component.plan(ctx, None)
        with self.write_fails(plan.changes[0].path):
            with self.assertRaisesRegex(ComponentFailed, r"^could not write the fish files \("):
                component.apply(ctx, plan)

    def test_a_failed_reinstall_keeps_the_variables_and_the_records_it_did_not_replace(self):
        runner.install(self.ctx())
        first = self.entry()
        ctx = self.ctx(stamp="20261003-130000")
        component = fish.FishComponent()
        with self.fish_files_change():
            plan = component.plan(ctx, first)
        with self.write_fails(self.functions / "lt.fish"):
            entry = component.apply(ctx, plan)
        self.assertEqual(entry["variables"], first["variables"])
        earlier = {record["path"]: record for record in first["files"]}
        records = {record["path"]: record for record in entry["files"]}
        self.assertEqual(list(records), list(earlier))
        for name in ("lt.fish", "ritual.fish"):
            self.assertEqual(records[str(self.functions / name)], earlier[str(self.functions / name)])
        ll = str(self.functions / "ll.fish")
        self.assertEqual(records[ll]["installed_sha256"], sha(Path(ll).read_bytes()))
        self.assertNotEqual(records[ll]["installed_sha256"], earlier[ll]["installed_sha256"])

    def install_after_a_failed_write(self):
        """lt.fish cannot be written (ll.fish just was); then a later version reinstalls, then uninstall."""
        with self.write_fails(self.functions / "lt.fish"):
            self.assertEqual(runner.install(self.ctx()), 2)
        self.assertIn("fish: could not write the fish files (", self.out.getvalue())
        self.assertRegex(self.state()["last_install"]["results"]["fish"],
                         r"^failed: could not write the fish files \(.*lt\.fish'\)$")
        self.assertEqual(self.variables, USER_TIDE)
        with self.fish_files_change():
            self.assertEqual(runner.install(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-140000")), 0)

    def test_a_retry_after_a_failed_write_still_removes_what_witchy_wrote(self):
        before = self.snapshot()
        self.install_after_a_failed_write()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.variables, USER_TIDE)

    def test_a_retry_after_a_failed_write_gives_back_the_users_function(self):
        mine = self.functions / "ll.fish"
        mine.parent.mkdir(parents=True)
        mine.write_text("function ll; ls -lh $argv; end\n", encoding="utf-8")
        before = self.snapshot()
        self.install_after_a_failed_write()
        self.assertEqual(self.snapshot(), before)

    def test_uninstall_after_a_failed_write_removes_what_witchy_wrote(self):
        before = self.snapshot()
        with self.write_fails(self.functions / "lt.fish"):
            self.assertEqual(runner.install(self.ctx()), 2)
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.snapshot(), before)
```

After `DoctorTest` (before `if __name__ == "__main__":`), add:

```python
@unittest.skipUnless(FISH, "fish is not installed")
class RealFishBytesTest(unittest.TestCase):
    """Real fish with a temporary HOME and config folder, never the user's own."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        config = self.root / "config"
        (config / "fish" / "functions").mkdir(parents=True)
        (config / "fish" / "functions" / "tide.fish").write_text("function tide\nend\n", encoding="utf-8")
        tools = dict.fromkeys([str(Path(FISH).parent), "/usr/bin", "/bin"])
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(config), "PATH": os.pathsep.join(tools)}

    def fish(self, script):
        return subprocess.run([FISH, "-c", script], capture_output=True, env=self.env, timeout=20, check=True).stdout

    def ctx(self, stamp):
        return Context(home=self.home, env=self.env, out=io.StringIO(), python=sys.executable, stamp=stamp,
                       dist=self.root / "dist", lock_path=self.root / "witchy.lock", only=("fish",))

    def test_a_value_with_carriage_returns_comes_back_byte_for_byte(self):
        self.fish("set -U tide_pwd_bg_color (printf 'FF\\rB7C5\\r\\0two\\r ❯\\0' | string split0)")
        read = "printf '%s\\0' $tide_pwd_bg_color"
        before = self.fish(read)
        self.assertEqual(before, "FF\rB7C5\r\0two\r ❯\0".encode())
        self.assertEqual(runner.install(self.ctx("20261003-120000")), 0)
        self.assertEqual(self.fish(read), b"B99AFF\0")
        self.assertEqual(runner.uninstall(self.ctx("20261003-130000")), 0)
        self.assertEqual(self.fish(read), before)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_components_fish tests.test_state tests.test_base`
Expected (real output from the prototype, trimmed):
```
ERROR: test_a_set_call_killed_by_a_signal_is_an_unknown_outcome (…)
TypeError: a bytes-like object is required, not 'str'
(the same TypeError for test_a_set_call_with_no_marker_is_an_unknown_outcome)
ERROR: test_the_new_tab_note_promises_only_what_this_install_changes (…)
AttributeError: module 'witchy.components.fish' has no attribute 'GREETING_NOTE'
ERROR: test_a_write_that_fails_part_way_records_what_was_written (…)
PermissionError: [Errno 13] Permission denied: '/tmp/…/home/.claude/witchy/ritual/__main__.py'
(the same PermissionError for test_a_failed_reinstall_keeps_the_variables_and_the_records_it_did_not_replace)
ERROR: test_a_fish_value_that_is_not_utf8_round_trips (…)
UnicodeEncodeError: 'utf-8' codec can't encode character '\udcff' in position 190: surrogates not allowed
ERROR: test_an_exact_command_sends_and_reads_every_byte_unchanged (…)
TypeError: Command.__init__() got an unexpected keyword argument 'exact'
FAIL: test_a_value_comes_back_byte_for_byte (…)
AssertionError: {'value': ['FF\nB7�C5', 'two\nlines'], 'exported': False} != {'value': ['FF\rB7\udcffC5', 'two\r\nlines'], 'exported': False}
FAIL: test_a_retry_after_a_failed_write_gives_back_the_users_function (…)
AssertionError: 'fish: could not write the fish files (' not found in "created …"
(the same for test_a_retry_after_a_failed_write_still_removes_what_witchy_wrote)
FAIL: test_uninstall_after_a_failed_write_removes_what_witchy_wrote (…)
AssertionError: {'/tmp/…/home/.claude/witchy/rit[41933 chars]d\n"} != {}
FAIL: test_a_value_with_carriage_returns_comes_back_byte_for_byte (…)
AssertionError: b'FF\nB7C5\n\x00two\n \xe2\x9d\xaf\x00' != b'FF\rB7C5\r\x00two\r \xe2\x9d\xaf\x00'
FAIL: test_a_prompt_item_list_that_still_lists_moon_says_how_to_remove_it (…)
FAIL: test_tide_removed_before_uninstall_gives_one_warning (…)
(output holds four "… was changed after install; leaving it as it is." lines instead of the one warning)
FAIL: test_without_fish_the_files_still_go (…)
FAILED (failures=8, errors=7)
```
(`test_a_dry_run_shows_bytes_that_are_not_utf8_as_replacement_characters` passes here: the old code already shows U+FFFD. It guards the new byte-exact read. `test_a_first_write_that_fails_records_nothing` also passes here: it pins that nothing is recorded when nothing was written.)

- [ ] **Step 3: Implement**

`witchy/components/base.py`. Replace the `Command` class with:

```python
@dataclass(frozen=True)
class Command:
    """A program to run: list arguments (never a shell string), optional standard input, and a label for messages.

    An ``exact`` command's input and output travel as UTF-8 bytes with surrogate escapes and no newline
    translation, so every byte comes back as it was (a fish value can hold any byte but NUL).
    """

    args: tuple[str, ...]
    label: str
    input: str | None = None
    exact: bool = False
```

Replace the function `run_command` with:

```python
def run_command(ctx: Any, command: Command, check: bool = True) -> subprocess.CompletedProcess:
    """Run ``command`` through ``ctx.run`` with ``ctx.env`` and a timeout.

    A command that cannot start or times out raises ComponentFailed (the cause is kept, so a caller can tell a
    missing program from a slow one); a non-zero exit raises it too unless ``check`` is false.
    """
    if command.exact:
        data = None if command.input is None else command.input.encode("utf-8", "surrogateescape")
        text: dict[str, Any] = {}
    else:
        data, text = command.input, {"text": True, "errors": "replace"}
    try:
        done = ctx.run(list(command.args), input=data, capture_output=True, timeout=COMMAND_TIMEOUT,
                       env=dict(ctx.env), **text)
    except subprocess.TimeoutExpired as exc:  # its text would hold the whole argument list
        raise ComponentFailed(f"could not {command.label} (timed out after {COMMAND_TIMEOUT} s)") from exc
    except OSError as exc:
        raise ComponentFailed(f"could not {command.label} ({exc.strerror or type(exc).__name__})") from exc
    except (ValueError, subprocess.SubprocessError) as exc:
        raise ComponentFailed(f"could not {command.label} ({str(exc)[:100]})") from exc
    if command.exact:
        done.stdout = done.stdout.decode("utf-8", "surrogateescape")
        done.stderr = done.stderr.decode("utf-8", "surrogateescape")
    if check and done.returncode != 0:
        raise ComponentFailed(f"could not {command.label} (exit {done.returncode})")
    return done
```

`witchy/state.py`. Replace the function `save` with:

```python
def save(path: Path, data: dict) -> None:
    # A fish value byte that is not UTF-8 is held as a lone surrogate; it is written as a \udcXX escape,
    # which json reads back as the same surrogate.
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    jsonio.write_atomic_bytes(path, text.encode("utf-8", "backslashreplace"))
```

`witchy/components/fish.py`. Replace the base import:

```python
from .base import (Check, Command, ComponentFailed, Plan, apply_changes, backup_checks, file_change, file_record,
                   fix_command, read, restore_copy, run_command, sha)
```

with:

```python
from .base import (Check, Command, ComponentFailed, Plan, applied_records, apply_changes, backup_checks,
                   file_change, file_record, fix_command, read, restore_copy, run_command, sha)
```

After `NEW_TAB_NOTE = …`, add:

```python
GREETING_NOTE = "Open a new terminal tab to see the greeting."
```

After `MESSAGE_MAX = 100`, add:

```python
PROMPT_ITEMS = ("tide_left_prompt_items", "tide_right_prompt_items")
```

In `snapshot`, replace:

```python
    done = run_command(ctx, Command((FISH, "-c", SNAPSHOT_SCRIPT, "--", *names), "read the Tide variables"))
```

with:

```python
    done = run_command(ctx, Command((FISH, "-c", SNAPSHOT_SCRIPT, "--", *names), "read the Tide variables",
                                    exact=True))
```

In `set_command`, replace:

```python
    return Command((FISH, "-c", SET_SCRIPT), label, "".join(f"{field}\0" for field in fields))
```

with:

```python
    return Command((FISH, "-c", SET_SCRIPT), label, "".join(f"{field}\0" for field in fields), exact=True)
```

After the function `_values`, add:

```python
def _shown(values: list[str]) -> str:
    """Values as printable text: a byte that is not UTF-8 shows as U+FFFD."""
    return " ".join(values).encode("utf-8", "surrogateescape").decode("utf-8", "replace")


def _changed_warning(name: str, current: dict) -> str:
    if name in PROMPT_ITEMS and "moon" in current.get("value", []):
        # The moon item's function goes with the files, and Tide would report it on every prompt.
        return (f"{name} was changed after install; leaving it as it is, but it still lists moon. "
                f"Remove it with: set -U {name} (string match -v moon ${name})")
    return f"{name} was changed after install; leaving it as it is."
```

In `FishComponent.plan`, replace:

```python
        notes = [NEW_TAB_NOTE] + ([] if shutil.which("eza", path=ctx.env.get("PATH")) else [NO_EZA_NOTE])
```

with:

```python
        notes = [] if shutil.which("eza", path=ctx.env.get("PATH")) else [NO_EZA_NOTE]
```

replace:

```python
            missing = isinstance(exc.__cause__, FileNotFoundError)
            plan.outcome = "skipped: fish not found" if missing else f"skipped: {exc}"
```

with:

```python
            missing = isinstance(exc.__cause__, FileNotFoundError)
            if not missing:  # fish is there but did not answer: its greeting still shows
                plan.notes.insert(0, GREETING_NOTE)
            plan.outcome = "skipped: fish not found" if missing else f"skipped: {exc}"
```

replace:

```python
        if not tide:
            plan.outcome = "skipped: Tide not found"
```

with:

```python
        if not tide:
            plan.notes.insert(0, GREETING_NOTE)
            plan.outcome = "skipped: Tide not found"
```

and replace:

```python
        plan.data.update(records=records, updates=updates)
        plan.actions = [f"fish: set -U{'x' if mode == 'exported' else ''} {name} {' '.join(values)} "
                        f"(now: {' '.join(current[name]['value']) if 'value' in current[name] else 'unset'})"
                        for name, mode, values in updates]
```

with:

```python
        plan.data.update(records=records, updates=updates)
        plan.notes.insert(0, NEW_TAB_NOTE)
        plan.actions = [f"fish: set -U{'x' if mode == 'exported' else ''} {name} {' '.join(values)} "
                        f"(now: {_shown(current[name]['value']) if 'value' in current[name] else 'unset'})"
                        for name, mode, values in updates]
```

In `FishComponent.apply`, replace the start of the method:

```python
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
```

with:

```python
    def apply(self, ctx: Any, plan: Plan) -> dict:
        earlier = plan.data["earlier"]
        shipped = {change.path for change in plan.changes}
        # A file an earlier version shipped stays recorded, so uninstall still removes it.
        unshipped = [record for path, record in earlier.items() if path not in shipped]
        backups: dict[Path, Path] = {}
        try:
            apply_changes(ctx, plan.changes, backups)
        except OSError as exc:
            return self._partial(ctx, plan, backups, unshipped, exc)
        files = [file_record(change, earlier, backups) for change in plan.changes] + unshipped
        variables = dict(plan.data["recorded"])
```

(the rest of `apply` is unchanged). Between `apply` and `restore`, add:

```python
    def _partial(self, ctx: Any, plan: Plan, backups: dict[Path, Path], unshipped: list[dict], exc: OSError) -> dict:
        """Record what a write that failed part-way left in place; the Tide variables are not set.

        Without a record, the next install would back up witchy's own bytes and uninstall would give those back.
        """
        ctx.say(f"fish: could not write the fish files ({exc}); run install again.")
        entry = {"files": applied_records(plan.changes, plan.data["earlier"], backups) + unshipped,
                 "variables": dict(plan.data["recorded"])}
        if not entry["files"] and not entry["variables"]:
            raise ComponentFailed(f"could not write the fish files ({exc})") from exc
        plan.outcome = f"failed: could not write the fish files ({exc})"
        plan.notes = [note for note in plan.notes if note not in (NEW_TAB_NOTE, GREETING_NOTE)]
        return entry
```

In `FishComponent.restore`, replace:

```python
                warnings.append("fish: fish not found; the Tide variables were left as they are.")
                current = {}
            undo = []
            for name, record in variables.items():
                if name not in current or current[name] == record["previous"]:
                    continue  # fish is gone, or this one was already given back by an earlier attempt
                if current[name].get("value") != record["installed"]:
                    warnings.append(f"{name} was changed after install; leaving it as it is.")
                    continue
```

with:

```python
                warnings.append("fish: fish not found, so Tide keeps witchy's colours and the moon item; to reset "
                                "them, run tide configure in fish.")
                current = {}
            if current and all(found.get("absent") for found in current.values()):
                warnings.append("fish: Tide's variables are gone (was Tide removed?); nothing to restore.")
                current = {}
            undo = []
            for name, record in variables.items():
                if name not in current or current[name] == record["previous"]:
                    continue  # fish or Tide is gone, or this one was already given back by an earlier attempt
                if current[name].get("value") != record["installed"]:
                    warnings.append(_changed_warning(name, current[name]))
                    continue
```

`docs/superpowers/specs/2026-10-02-shell-ritual-design.md`, section 5.3. Replace the bullet:

```
- Snapshot each variable before the first install: its values (read NUL-separated), its export flag, or `{"absent": true}`.
```

with:

```
- Snapshot each variable before the first install: its values (read NUL-separated, byte for byte: a carriage return or a byte that is not UTF-8 is written back as it was), its export flag, or `{"absent": true}`.
```

Replace the bullet:

```
- Uninstall restores a variable (or erases it with `set -e -U`) only if it still holds the installed value; otherwise it warns and leaves it.
```

with:

```
- Uninstall restores a variable (or erases it with `set -e -U`) only if it still holds the installed value; otherwise it warns and leaves it. When a changed `tide_left_prompt_items` or `tide_right_prompt_items` still lists `moon`, the warning gives the command that removes it (`set -U <name> (string match -v moon $<name>)`), because the moon item's function goes with the files.
```

Replace the bullet:

```
- Running shells keep their old prompt; the summary says to open a new tab.
```

with:

```
- Running shells keep their old prompt; the summary says to open a new tab for the new prompt and greeting. Without Tide (or when fish does not answer) it names only the greeting; without fish it says nothing about a new tab.
```

In the bullet that starts `- When fish or Tide is missing, the files still install`, replace its first sentence:

```
- When fish or Tide is missing, the files still install and the result is `skipped: fish not found` or `skipped: Tide not found`.
```

with:

```
- When fish or Tide is missing, the files still install and the result is `skipped: fish not found` or `skipped: Tide not found`. When a file write fails part-way, the files already written stay recorded (with the variables recorded earlier), the Tide variables are not set, and the result is `failed: could not write the fish files (…)`; nothing is recorded when nothing was written.
```

In the bullet that starts `- Uninstall restores the variables before it removes the files.`, replace:

```
When fish no longer exists, the variables are left with a warning and the files still go; when fish exists but does not answer, the component stays installed.
```

with:

```
When fish no longer exists, the variables are left and the files still go, with the warning `fish: fish not found, so Tide keeps witchy's colours and the moon item; to reset them, run tide configure in fish.`; when fish exists but does not answer, the component stays installed. When every recorded variable is gone (Tide was removed), uninstall gives one warning, `fish: Tide's variables are gone (was Tide removed?); nothing to restore.`, instead of one per variable.
```

In section 9, after the row `| fish | \`set -U\` non-zero (\`CalledProcessError\`) | …`, add:

```
| fish | a file write `OSError` | `failed: could not write the fish files (…)`, exit 2; the Tide variables are not set; the files already written stay recorded (nothing is recorded when none was) | `fish: could not write the fish files (…); run install again.` |
```

- [ ] **Step 4: Run the whole suite on both interpreters**

Run (any manual witchy run uses a temporary HOME):
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
H=$(mktemp -d); HOME=$H XDG_CONFIG_HOME=$H/.config python3 -m witchy validate; rm -rf $H
```
Expected: `Ran 523 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/components/fish.py witchy/components/base.py witchy/state.py tests/fakes.py tests/test_components_fish.py tests/test_base.py tests/test_state.py docs/superpowers/specs/2026-10-02-shell-ritual-design.md
git commit -m "fix: a fish install that fails part-way records what it wrote; byte-exact Tide values; clearer uninstall warnings" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: fish doctor lines (retry only after a failure today, a command as the log fix, sharper tests)

**Items:**
- D7: the long-message doctor test checks `len(line) < 170`, not the 100-character cut itself (test only).
- D8: no doctor test with a stale (yesterday) `sky-fail` marker (test only).
- D9: the aware-now doctor test uses `self.NOW.astimezone()`, a no-op on a UTC machine, so it proves nothing there.
- D17: `(it retries tomorrow)` is attached to a sky error of any age in the 7-day window.
- D18: the greeting and fail-marker lines give `see <path>` as their fix, but `Check.fix` is a command to run.
- README line 31 says "the last line says which" about the install summary, but the summary is not install's last line.

**Files:**
- Modify: `witchy/components/fish.py` (`import shlex`; `log_checks`)
- Modify: `README.md` (exit-code sentence; two troubleshooting rows)
- Modify: `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (section 8, the doctor log bullet)
- Test: `tests/test_components_fish.py`

**Interfaces:**
- Consumes: `log.NAME`, `log.MAX_LINES` (20, unchanged on the ritual branch), `sky.FAIL`, `fix_command`, `MESSAGE_MAX`.
- Produces:
  - Greeting line and fail-marker line fix: `tail -n 20 <shlex.quote(str(ctx.cache_dir / "ritual.log"))>`. The sky error line's fix stays `python3 -m witchy install --only windows-terminal`.
  - `(it retries tomorrow)` is added to the sky error line only when the `sky-fail` marker holds today's date and the newest sky error is from today. A marker for today without a sky error from today gives the line `sky: the sky job failed today (it retries tomorrow)`, also when an older sky error is shown.

**Decisions:**
1. **D17, marker today but the newest sky error is older:** the older error is shown without `(it retries tomorrow)`, and the `sky: the sky job failed today (it retries tomorrow)` line is added as well. That case means today's run failed but logged nothing readable; dropping the marker line would hide a failure doctor knows about. Before this task the `elif` showed that line only when no sky error at all was in the window.
2. **D18 uses `tail -n 20`** (from `log.MAX_LINES`): the log is trimmed to its last 20 lines, so this prints the whole log, and `shlex.quote` keeps a HOME with a space or a quote safe to paste.
3. **D9 uses a zone 9 hours ahead of the machine's own zone** (computed from `self.NOW.astimezone().utcoffset()`), not a fixed `+09:00`: a fixed offset is a no-op on a machine in that zone. 21:00 local is then 06:00 the next day in the test's zone, so without the conversion the line reads "yesterday". RED evidence (Step 2) was produced by removing the conversion and running the test under `TZ=UTC`, `Europe/Madrid`, `Asia/Tokyo`, `Pacific/Kiritimati` (+14) and `Pacific/Pago_Pago` (−11): it failed in all five; with the conversion back it passes in all five.
4. **README exit-code sentence:** install prints the summary line, then the headline, the notes and the new-session note, so the summary is not the last line. Uninstall's last line on exit 2 is `Moonlit Candle partly uninstalled; still installed: <names>.`, so the sentence now names both.

- [ ] **Step 1: Write the failing tests**

`tests/test_components_fish.py`. Replace the import:

```python
from datetime import datetime
```

with:

```python
from datetime import datetime, timedelta, timezone
```

In `DoctorTest.test_long_messages_are_cut`, replace:

```python
        self.assertTrue(line.endswith("…"))
        self.assertLess(len(line), 170)
```

with:

```python
        message = line.split("today at 09:14: ", 1)[1]
        self.assertEqual(len(message), fish.MESSAGE_MAX)
        self.assertTrue(message.endswith("…"))
```

In `DoctorTest`, after `test_the_sky_fail_marker`, add:

```python
    def test_a_sky_fail_marker_from_yesterday_adds_nothing(self):
        runner.install(self.ctx())
        self.log("2026-10-02T08:00:00 sky: boom")
        (self.home / ".cache" / "witchy" / "sky-fail").write_text("2026-10-02\n", encoding="utf-8")
        output = self.doctor()[1]
        self.assertIn("⚠ fish              sky: last run failed yesterday: boom\n", output)
        self.assertNotIn("retries tomorrow", output)
        (self.home / ".cache" / "witchy" / "ritual.log").unlink()
        output = self.doctor()[1]
        self.assertNotIn("sky:", output)
        self.assertIn("✓ fish              no greeting or sky errors in the last 7 days", output)

    def test_only_a_sky_error_from_today_retries_tomorrow(self):
        runner.install(self.ctx())
        self.log("2026-10-01T08:00:00 sky: boom")
        (self.home / ".cache" / "witchy" / "sky-fail").write_text("2026-10-03\n", encoding="utf-8")
        output = self.doctor()[1]
        self.assertIn("⚠ fish              sky: last run failed 2 days ago: boom\n", output)
        self.assertIn("⚠ fish              sky: the sky job failed today (it retries tomorrow)\n", output)

    def test_the_fix_for_a_log_line_shows_the_log(self):
        self.home = self.root / "my home"
        self.home.mkdir()
        runner.install(self.ctx())
        self.log("2026-10-03T09:14:00 greeting: KeyError('name')")
        (self.home / ".cache" / "witchy" / "sky-fail").write_text("2026-10-03\n", encoding="utf-8")
        output = self.doctor()[1]
        fix = f"    fix: tail -n 20 '{self.home}/.cache/witchy/ritual.log'\n"
        self.assertEqual(output.count(fix), 2, output)  # the greeting line and the fail-marker line
```

In `DoctorTest.test_an_aware_now_compares_with_the_local_log`, replace:

```python
        ctx = self.ctx()
        ctx.now = lambda: self.NOW.astimezone()
```

with:

```python
        local = self.NOW.astimezone()  # 21:00 in this machine's zone, whatever it is
        ahead = local.astimezone(timezone(local.utcoffset() + timedelta(hours=9)))  # 06:00 the next day there
        ctx = self.ctx()
        ctx.now = lambda: ahead
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_components_fish.DoctorTest`
Expected (real output from the prototype, trimmed):
```
FAIL: test_only_a_sky_error_from_today_retries_tomorrow (…)
AssertionError: '⚠ fish              sky: last run failed 2 days ago: boom\n' not found in '✓ fish              20 files match\n…
FAIL: test_the_fix_for_a_log_line_shows_the_log (…)
AssertionError: 0 != 2 : ✓ fish              20 files match
Ran 13 tests in 0.718s
FAILED (failures=2)
```
D7 (`test_long_messages_are_cut`) and D8 (`test_a_sky_fail_marker_from_yesterday_adds_nothing`) pin the current behaviour and pass here: no RED. D9's new `test_an_aware_now_compares_with_the_local_log` passes too, because the code already converts. Its RED evidence: with `now = now.astimezone().replace(tzinfo=None)` in `log_checks` temporarily changed to `now = now.replace(tzinfo=None)`, it fails under every `TZ` tried:
```
$ TZ=UTC /usr/bin/python3 -m unittest tests.test_components_fish.DoctorTest.test_an_aware_now_compares_with_the_local_log
AssertionError: 'greeting: last run failed today at 09:14' not found in "✓ fish              20 files match\n✓ fish …
FAILED (failures=1)
(the same with TZ=Europe/Madrid, Asia/Tokyo, Pacific/Kiritimati and Pacific/Pago_Pago)
```
Put the line back before going on.

- [ ] **Step 3: Implement**

`witchy/components/fish.py`. Replace:

```python
import re
import shutil
```

with:

```python
import re
import shlex
import shutil
```

Replace the function `log_checks` with:

```python
def log_checks(ctx: Any) -> list[Check]:
    """Doctor lines for the greeting and the sky job: their newest error from the last week, and the fail marker."""
    path = ctx.cache_dir / log.NAME
    now = ctx.now()
    if now.tzinfo is not None:
        now = now.astimezone().replace(tzinfo=None)  # the log holds local wall-clock times
    errors = {kind: found for kind, found in _last_errors(path).items() if now - found[0] < RECENT}
    show_log = f"tail -n {log.MAX_LINES} {shlex.quote(str(path))}"  # the whole log
    checks = []
    if "greeting" in errors:
        stamp, message = errors["greeting"]
        checks.append(Check("warn", "fish", f"greeting: last run failed {_when(stamp, now)}: {_short(message)}",
                            show_log))
    try:
        failed_today = (ctx.cache_dir / sky.FAIL).read_text(encoding="utf-8").strip() == now.date().isoformat()
    except (OSError, ValueError):
        failed_today = False
    sky_today = "sky" in errors and errors["sky"][0].date() == now.date()
    if "sky" in errors:
        stamp, message = errors["sky"]
        retry = " (it retries tomorrow)" if failed_today and sky_today else ""
        checks.append(Check("warn", "fish", f"sky: last run failed {_when(stamp, now)}: {_short(message)}{retry}",
                            fix_command("windows-terminal")))
    if failed_today and not sky_today:
        # Today's failure logged nothing readable; an older sky error says nothing about it.
        checks.append(Check("warn", "fish", "sky: the sky job failed today (it retries tomorrow)", show_log))
    if not checks:
        checks.append(Check("ok", "fish", "no greeting or sky errors in the last 7 days"))
    return checks
```

`README.md`. Replace:

```
`2` done with warnings (a component was skipped or failed; the last line says which).
```

with:

```
`2` done with warnings (a component was skipped or failed: install names it in its summary line, `3/4 components installed · skipped: …`, and uninstall in its last line, `… still installed: …`).
```

Replace the row:

```
| `⚠ fish  sky: the sky job failed today (it retries tomorrow)` | the sky job failed today and logged nothing readable | see `~/.cache/witchy/ritual.log` |
```

with:

```
| `⚠ fish  sky: the sky job failed today (it retries tomorrow)` | the sky job failed today and logged no error from today | `tail -n 20 ~/.cache/witchy/ritual.log` |
```

In the row that starts ``| `⚠ fish  greeting: last run failed …` ``, replace:

```
| see `~/.cache/witchy/ritual.log`; `ritual` shows the greeting |
```

with:

```
| `tail -n 20 ~/.cache/witchy/ritual.log`; `ritual` shows the greeting |
```

`docs/superpowers/specs/2026-10-02-shell-ritual-design.md`, section 8. In the bullet that starts `- The newest \`greeting\` and \`sky\` errors are shown only`, replace:

```
A sky fail marker for today adds `(it retries tomorrow)`.
```

with:

```
A sky fail marker for today adds `(it retries tomorrow)` to a sky error from today; without a sky error from today it shows as `sky: the sky job failed today (it retries tomorrow)`. The fix for the greeting line and that marker line is `tail -n 20 <ritual.log>` (the path quoted for the shell).
```

- [ ] **Step 4: Run the whole suite on both interpreters**

Run (any manual witchy run uses a temporary HOME):
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
H=$(mktemp -d); HOME=$H XDG_CONFIG_HOME=$H/.config python3 -m witchy validate; rm -rf $H
```
Expected: `Ran 526 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/components/fish.py tests/test_components_fish.py README.md docs/superpowers/specs/2026-10-02-shell-ritual-design.md
git commit -m "fix: doctor retries the sky only after a failure today, and its log fix is a command" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Deterministic fish shell tests

**Items:** D19 sky-job negative tests no longer sleep 0.3 s and hope; D20 no hard-coded `/usr/bin/python3` or `PATH=/usr/bin:/bin` in the fish tests.

**Files:**
- Modify: `tests/test_fish_files.py` (`import re`, `TOOL_DIRS`, the `PATH` in `FishTestCase.setUp`, the whole `SkyJobStartTest` class)
- Modify: `tests/test_fish_integration.py` (`import sys`, `TOOL_DIRS`, `PATH`, `python=sys.executable`)
- Test: the same two files

**Interfaces:**
- Consumes: `build.fish_files`, `FishTestCase.fish(script, *args, interactive, env)`, `content/fish/conf.d/witchy.fish`
- Produces: test-only `SkyJobStartTest.sky_job_started(interactive=True, session=True) -> bool`; module constant `TOOL_DIRS` in both files

**Decisions:**
1. Detection is `fish_trace=1` in the environment (works on fish 3.7). fish prints each command to stderr before running it, synchronously, so the `... ritual' --sky` line is there the moment fish exits; no waiting. The helper also asserts the trace shows `source .../conf.d/witchy.fish`, so an empty or broken trace cannot pass as "did not start".
2. Every negative has a positive control using the same helper: stale stamp, no stamp and "failure yesterday" all assert `sky_job_started()` is true. The stale-stamp test also keeps the untraced run that checks the shell is quiet (stdout and stderr empty).
3. The remaining positive waits stay as `wait_for_python` (polls up to 5 s).
4. PATH is the stub folder, then the folder of `shutil.which("fish")`, then `/usr/bin:/bin` (de-duplicated). Python is `sys.executable`. The `/usr/bin/python3` strings that are only rendered into templates (never executed) in `RenderTest` are left alone.

- [ ] **Step 1: Write the tests**

In `tests/test_fish_files.py`: add `import re` before `import shutil`; after `FISH = shutil.which("fish")` add

```python
# Where the tests look for tools: fish's own folder and the system ones, not the user's whole PATH.
TOOL_DIRS = list(dict.fromkeys([str(Path(FISH).parent) if FISH else "/usr/bin", "/usr/bin", "/bin"]))
```

in `FishTestCase.setUp` replace `"PATH": f"{self.python.parent}:/usr/bin:/bin"}` with `"PATH": ":".join([str(self.python.parent), *TOOL_DIRS])}`. Replace the whole class `SkyJobStartTest` with:

```python
class SkyJobStartTest(FishTestCase):
    """Whether the job started is read from fish_trace, which prints every command before it runs. That is
    synchronous, so a job that was not started is a fact, not a timeout. The starting cases are the controls
    that prove the trace can see the job."""

    WT = {"WT_SESSION": "f00d"}

    def setUp(self):
        super().setUp()
        (self.witchy / "ritual-config.json").write_text("{}", encoding="utf-8")
        self.cache.mkdir(parents=True)
        self.bin = moon.phase_bin(datetime.now(timezone.utc))

    def start_shell(self, env=None, interactive=True, session=True):
        return self.fish("true", interactive=interactive, env={**(self.WT if session else {}), **(env or {})})

    def sky_job_started(self, interactive=True, session=True):
        """Starts a shell with tracing on and says whether it ran the --sky command. It also checks that the
        trace saw the file that decides, so that an empty trace cannot pass for "did not start"."""
        done = self.start_shell({"fish_trace": "1"}, interactive, session)
        lines = done.stderr.splitlines()
        self.assertTrue(any(re.search(r"source .*conf\.d/witchy\.fish$", line) for line in lines), done.stderr[-500:])
        return any(re.search(r"^-+> .*/ritual'? --sky$", line) for line in lines)

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
        (self.home / "python-args").unlink()
        self.assertTrue(self.sky_job_started())

    def test_starts_the_job_when_there_is_no_stamp_yet(self):
        self.assertTrue(self.sky_job_started())
        self.assertEqual(self.wait_for_python()[3], "--sky")

    def test_does_nothing_when_the_stamp_is_current(self):
        (self.cache / "sky-bin").write_text(f"{self.bin}\n", encoding="utf-8")
        self.assertFalse(self.sky_job_started())
        self.assertIsNone(self.python_args())

    def test_does_nothing_after_a_failure_today(self):
        (self.cache / "sky-fail").write_text(date.today().isoformat() + "\n", encoding="utf-8")
        self.assertFalse(self.sky_job_started())
        self.assertIsNone(self.python_args())

    def test_retries_the_day_after_a_failure(self):
        (self.cache / "sky-fail").write_text((date.today() - timedelta(days=1)).isoformat() + "\n", encoding="utf-8")
        self.assertTrue(self.sky_job_started())
        self.assertEqual(self.wait_for_python()[3], "--sky")

    def test_needs_an_interactive_windows_terminal_shell_and_the_config(self):
        self.assertFalse(self.sky_job_started(interactive=False))
        self.assertFalse(self.sky_job_started(session=False))
        (self.witchy / "ritual-config.json").unlink()
        self.assertFalse(self.sky_job_started())
        self.assertIsNone(self.python_args())
```

In `tests/test_fish_integration.py`: add `import sys` after `import subprocess`; after `FISH = shutil.which("fish")` add the same two lines (comment and `TOOL_DIRS`); replace `"PATH": "/usr/bin:/bin"}` with `"PATH": ":".join(TOOL_DIRS)}` and `python="/usr/bin/python3"` with `python=sys.executable`.

- [ ] **Step 2: Run them (no RED; test-only change)**

To prove the detection can fail, temporarily delete the two lines starting `test "$stamp" = ` and `test "$failed" = ` from `content/fish/conf.d/witchy.fish`, run, then `git checkout` the file:

Run: `/usr/bin/python3 -m unittest tests.test_fish_files.SkyJobStartTest`
Expected (real output):
```
FAIL: test_does_nothing_after_a_failure_today (tests.test_fish_files.SkyJobStartTest.test_does_nothing_after_a_failure_today)
AssertionError: True is not false
FAIL: test_does_nothing_when_the_stamp_is_current (tests.test_fish_files.SkyJobStartTest.test_does_nothing_when_the_stamp_is_current)
AssertionError: True is not false
FAILED (failures=2)
```

- [ ] **Step 3: Implement** nothing; test-only.

- [ ] **Step 4: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 526 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_fish_files.py tests/test_fish_integration.py
git commit -m "test: fish sky-job tests read fish_trace instead of sleeping; no hard-coded python or PATH"
```

---

### Task 9: Sky image cache: tolerate bad files, prune old keys

**Items:** B7 unreadable cache file crashes plan(); B8 cached file not checked for PNG shape; B9 orphan key directories pile up

**Files:**
- Modify: `witchy/sky_render.py` (`_whole_png`, `_read_png`, `_prune`, `_KEY`, new `cached`; imports `re`, `shutil`)
- Modify: `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (sky cache sentence, section 4.5)
- Test: `tests/test_sky_render.py`

**Interfaces:**
- Consumes: `jsonio.write_atomic_bytes(path, data)`, `sky_render.render`; `cached` keeps its signature
- Produces: `cached(root, colours, size=SIZE, write=True) -> list[bytes]` (unchanged); private `_whole_png(data)`, `_read_png(path) -> bytes | None`, `_prune(root, keep)`

**Decisions:**
1. A cached file counts only if it starts with the PNG signature and ends with the 12-byte IEND chunk (`IEND` + its CRC `AE426082`). That catches truncation, the realistic failure. No decode or CRC check.
2. Pruning runs only when at least one file was written in this call, so a dry run (`write=False`), a read-only cache and a full cache hit delete nothing. Only real directories (not symlinks) named `[0-9a-f]{16}` other than the current key are removed, with `ignore_errors=True`.

- [ ] **Step 1: Write the failing tests**

Add these methods to `CacheTest`, after `test_no_write_leaves_no_cache`:

```diff
diff --git a/tests/test_sky_render.py b/tests/test_sky_render.py
index b5f4b9e..ea39372 100644
--- a/tests/test_sky_render.py
+++ b/tests/test_sky_render.py
@@ -62,4 +62,50 @@ class CacheTest(unittest.TestCase):
             self.assertEqual(list(Path(tmp).iterdir()), [])
 
+    def test_an_unreadable_cache_file_is_a_miss(self):
+        with tempfile.TemporaryDirectory() as tmp:
+            first = sky_render.cached(Path(tmp), palette.SKY, SMALL)
+            real = Path.read_bytes
+
+            def read_bytes(path):
+                if path.name == "sky-3.png":
+                    raise PermissionError("denied")
+                return real(path)
+
+            with mock.patch.object(Path, "read_bytes", read_bytes):
+                second = sky_render.cached(Path(tmp), palette.SKY, SMALL)
+        self.assertEqual(first, second)
+
+    def test_a_cache_file_that_is_not_a_whole_png_is_rendered_again(self):
+        with tempfile.TemporaryDirectory() as tmp:
+            first = sky_render.cached(Path(tmp), palette.SKY, SMALL)
+            files = sorted(Path(tmp).glob("*/sky-*.png"))
+            files[0].write_bytes(b"not a png")
+            files[1].write_bytes(first[1][:-5])  # cut short, so no IEND
+            second = sky_render.cached(Path(tmp), palette.SKY, SMALL)
+            self.assertEqual(files[0].read_bytes(), first[0])
+        self.assertEqual(first, second)
+
+    def test_older_cache_directories_are_pruned_after_a_write(self):
+        with tempfile.TemporaryDirectory() as tmp:
+            root = Path(tmp)
+            (root / "0123456789abcdef").mkdir()
+            (root / "0123456789abcdef" / "sky-0.png").write_bytes(b"old")
+            (root / "notes").mkdir()
+            (root / "ABCDEF0123456789").mkdir()  # not a key: keys are lowercase hex
+            (root / "0123456789abcde0").write_text("a file, not a directory")
+            sky_render.cached(root, palette.SKY, SMALL)
+            names = sorted(path.name for path in root.iterdir())
+            self.assertEqual(len(names), 4)
+            self.assertNotIn("0123456789abcdef", names)
+            self.assertEqual(sum(1 for name in names if len(name) == 16 and (root / name / "sky-0.png").is_file()), 1)
+            for kept in ("notes", "ABCDEF0123456789", "0123456789abcde0"):
+                self.assertIn(kept, names)
+
+    def test_a_dry_run_prunes_nothing(self):
+        with tempfile.TemporaryDirectory() as tmp:
+            (Path(tmp) / "0123456789abcdef").mkdir()
+            sky_render.cached(Path(tmp), palette.SKY, SMALL, write=False)
+            self.assertTrue((Path(tmp) / "0123456789abcdef").is_dir())
+
 
 if __name__ == "__main__":
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_sky_render`
Expected (real output from the prototype):
```
ERROR: test_an_unreadable_cache_file_is_a_miss ... PermissionError: denied
FAIL: test_a_cache_file_that_is_not_a_whole_png_is_rendered_again ... AssertionError: b'not a png' != b'\x89PNG...'
FAIL: test_older_cache_directories_are_pruned_after_a_write ... AssertionError: '0123456789abcdef' unexpectedly found in ['0123456789abcde0', '0123456789abcdef', '9235919e16c21562', 'ABCDEF0123456789', 'notes']
Ran 11 tests ... FAILED (failures=2, errors=1)
(test_a_dry_run_prunes_nothing passes already: it pins existing behaviour.)
```

- [ ] **Step 3: Implement**

Add `import re` and `import shutil` to the imports, add the `_KEY` line after `SPARKLES`, and replace `cached` with the helpers and new function below. Spec: extend the cache sentence as shown.

```diff
diff --git a/docs/superpowers/specs/2026-10-02-shell-ritual-design.md b/docs/superpowers/specs/2026-10-02-shell-ritual-design.md
index 3d099c8..711d0f2 100644
--- a/docs/superpowers/specs/2026-10-02-shell-ritual-design.md
+++ b/docs/superpowers/specs/2026-10-02-shell-ritual-design.md
@@ -166,5 +166,5 @@ On this machine step 2 selects `{51855cb2-8cce-5362-8f54-464b92b32386}`, the pro
 - Shared starfield: a fixed seed places about 220 stars (single pixels and 2×2 dots in `#F3EAF7`, `#FFD477`, `#B99AFF`) and 6–8 four-point sparkles; identical in all 8 images.
 - The moon: radius 150 px, centred about 260 px from the right and bottom edges. The lit part is drawn for the bin's phase in `#FFD477`; the dark part is a faint `#1D1230` disc with a `#38234D` rim; a soft glow scales with illumination.
-- Output is deterministic. Renders are cached in `~/.cache/witchy/sky/<hash of renderer source + palette>/`, so only the first build pays (about 1 s per image).
+- Output is deterministic. Renders are cached in `~/.cache/witchy/sky/<hash of renderer source + palette>/`, so only the first build pays (about 1 s per image). A cached file that cannot be read or is not a whole PNG is rendered again, and after a write the directories of older keys (16 lowercase hex characters) are removed.
 - **Spike gate:** before building the sky job, a manual check confirms that Windows Terminal applies a changed `backgroundImage` path without a restart. If it does not, ship a single image for the install-day phase (`moonlit-candle-sky.png`) and no sky job; everything else in this spec is unchanged.
 - **Spike result (2026-10-03): passed.** An atomic replace of `settings.json` that only changed `backgroundImage` was applied to an open tab without a restart, so the eight images and the sky job stay in scope.
diff --git a/witchy/sky_render.py b/witchy/sky_render.py
index b2b2258..922e5ad 100644
--- a/witchy/sky_render.py
+++ b/witchy/sky_render.py
@@ -9,4 +9,6 @@ import json
 import math
 import random
+import re
+import shutil
 import struct
 import zlib
@@ -20,4 +22,5 @@ SEED = 1031  # fixed, so the starfield is identical in all eight images
 STARS = 220
 SPARKLES = 7
+_KEY = re.compile(r"[0-9a-f]{16}")  # the cache directory names
 
 
@@ -97,4 +100,27 @@ def render(bin_: int, colours: dict[str, str], size: tuple[int, int] = SIZE) ->
 
 
+def _whole_png(data: bytes) -> bool:
+    return data.startswith(b"\x89PNG\r\n\x1a\n") and data.endswith(b"IEND\xaeB`\x82")
+
+
+def _read_png(path: Path) -> bytes | None:
+    """The cached image, or None when it is missing, unreadable, or not a whole PNG."""
+    try:
+        data = path.read_bytes()
+    except OSError:
+        return None
+    return data if _whole_png(data) else None
+
+
+def _prune(root: Path, keep: str) -> None:
+    """Remove the cache directories of older renderers and palettes (their names are 16 hex characters)."""
+    try:
+        for entry in root.iterdir():
+            if entry.name != keep and _KEY.fullmatch(entry.name) and entry.is_dir() and not entry.is_symlink():
+                shutil.rmtree(entry, ignore_errors=True)
+    except OSError:
+        pass  # leftovers only cost disk space
+
+
 def cached(root: Path, colours: dict[str, str], size: tuple[int, int] = SIZE, write: bool = True) -> list[bytes]:
     """All eight images, read from ``root/<key>/`` when this renderer, palette and size made them before."""
@@ -102,7 +128,8 @@ def cached(root: Path, colours: dict[str, str], size: tuple[int, int] = SIZE, wr
                          + json.dumps([colours, list(size)], sort_keys=True).encode("utf-8")).hexdigest()[:16]
     images = []
+    wrote = False
     for bin_ in range(BINS):
         path = root / key / f"sky-{bin_}.png"
-        data = path.read_bytes() if path.is_file() else None
+        data = _read_png(path)
         if data is None:
             data = render(bin_, colours, size)
@@ -110,6 +137,9 @@ def cached(root: Path, colours: dict[str, str], size: tuple[int, int] = SIZE, wr
                 try:
                     jsonio.write_atomic_bytes(path, data)
+                    wrote = True
                 except OSError:
                     pass  # the cache only saves the next render
         images.append(data)
+    if wrote:
+        _prune(root, key)
     return images
```

- [ ] **Step 4: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 530 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_sky_render.py witchy/sky_render.py docs/superpowers/specs/2026-10-02-shell-ritual-design.md
git commit -m "fix: sky cache treats unreadable or truncated images as misses and prunes older key directories"
```

---

### Task 10: Validate sky colours, Tide colour keys by name, derive eza git colours

**Items:** B10 required sky keys; D10 Tide colour keys found by `"color" in key`; D11 undocumented contrast exemption of the separator colour; D12 eza git colours not tied to TIDE

**Files:**
- Modify: `witchy/sky_render.py` (`COLOURS`)
- Modify: `witchy/validate.py` (`is_tide_colour`, `validate_sky`, use in `validate_tide` and `validate_all`)
- Modify: `witchy/palette.py` (separator comment, EZA git roles derived from TIDE)
- Modify: `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (section 11 items 2 and 3)
- Test: `tests/test_validate.py`, `tests/test_prompt_palette.py`

**Interfaces:**
- Consumes: `palette.TIDE`, `palette.SKY`, `validate.Failure`, `validate.HEX`
- Produces: `sky_render.COLOURS: tuple[str, ...]`; `validate.is_tide_colour(key: str) -> bool`; `validate.validate_sky(sky: Mapping[str, Any]) -> list[Failure]`

**Decisions:**
1. Required sky keys come from `sky_render.COLOURS` (what `render` indexes), not from `palette.SKY`, so dropping a key from the palette is caught. A test renders with exactly those keys, so the tuple cannot drift from the renderer.
2. Tide colour keys: the name contains the word `color` between underscores (`"color" in key.split("_")`). Tide 6.1.1 names every colour that way (`_bg_color`, `color_branch`, `color_default`, `_separator_diff_color`), so a suffix rule would miss `tide_context_color_default`, while the old substring match would claim a name like `tide_colorful_icon`. Everything else (item lists, `tide_cmd_duration_threshold`) is checked as a string or tuple of strings.
3. D11: comment in `palette.py` plus a sentence in the spec; the format check already covers the key (now tested). The existing exemption test in `test_prompt_palette.py` keeps the exempt set at exactly this one key.
4. D12: derive in `palette.py` with `"#" + TIDE[...]`. The values are unchanged (`#FFD477`, `#FFB86B`, `#FF6B9F`); a test pins the rendered `EZA_COLORS` string byte for byte and the tie to TIDE.

- [ ] **Step 1: Write the failing tests**

Edit `tests/test_validate.py`: add `import dataclasses` after `import copy`, add `sky_render` to the `from witchy import ...` line, and add two methods to `SkyValidateTest`. Edit `tests/test_prompt_palette.py`: import `build`; update the exemption test, add `test_colour_keys_are_the_ones_with_a_colour_word` to `TideNamesTest`, two tests to `TideValidateTest`, and the new `EzaDerivedTest` class before `EzaValidateTest`.

```diff
diff --git a/tests/test_prompt_palette.py b/tests/test_prompt_palette.py
index 48818ce..9420e32 100644
--- a/tests/test_prompt_palette.py
+++ b/tests/test_prompt_palette.py
@@ -2,5 +2,5 @@ import unittest
 from unittest import mock
 
-from witchy import palette, validate
+from witchy import build, palette, validate
 
 # `fish -c 'set -U | string match -r "^tide_\S+"'` on Tide 6.1.1 (2026-10-03), the version the spec targets.
@@ -70,7 +70,18 @@ class TideNamesTest(unittest.TestCase):
     def test_every_tide_colour_is_validated_for_contrast_or_exempt(self):
         checked = {name for pair in validate.TIDE_TEXT_PAIRS + validate.TIDE_SECONDARY_PAIRS for name in pair if name}
-        colours = {key for key in palette.TIDE if "color" in key}
+        colours = {key for key in palette.TIDE if validate.is_tide_colour(key)}
+        # It sits between segments that share a background, so no single background exists to test it on.
         self.assertEqual(colours - checked, {"tide_prompt_color_separator_same_color"})
 
+    def test_colour_keys_are_the_ones_with_a_colour_word(self):
+        for key in ("tide_pwd_bg_color", "tide_git_color_branch", "tide_context_color_default",
+                    "tide_left_prompt_separator_diff_color"):
+            self.assertTrue(validate.is_tide_colour(key), key)
+        for key in ("tide_left_prompt_items", "tide_cmd_duration_threshold", "tide_colorful_icon", "tide_pwd_decolor"):
+            self.assertFalse(validate.is_tide_colour(key), key)
+        self.assertEqual({key for key in palette.TIDE if validate.is_tide_colour(key)},
+                         {key for key in palette.TIDE if key not in (
+                             "tide_left_prompt_items", "tide_right_prompt_items", "tide_cmd_duration_threshold")})
+
 
 class TideValidateTest(unittest.TestCase):
@@ -78,4 +89,12 @@ class TideValidateTest(unittest.TestCase):
         self.assertEqual(validate.validate_tide(palette.TIDE), [])
 
+    def test_a_name_that_only_contains_color_is_not_a_colour(self):
+        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_colorful_icon="x")))
+        self.assertEqual(found, set())
+
+    def test_the_exempt_separator_colour_is_still_format_checked(self):
+        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_prompt_color_separator_same_color="grey")))
+        self.assertIn(("format", "tide.tide_prompt_color_separator_same_color"), found)
+
     def test_colours_need_six_hex_digits_without_a_hash(self):
         for bad in ("#B99AFF", "b99aff", "B99AF"):
@@ -110,4 +129,19 @@ class TideValidateTest(unittest.TestCase):
 
 
+class EzaDerivedTest(unittest.TestCase):
+    def test_git_colours_are_tides_git_colours(self):
+        tide = palette.TIDE
+        self.assertEqual(palette.EZA["git_new"], "#" + tide["tide_git_bg_color"])
+        for role in ("git_modified", "git_renamed", "git_typechange"):
+            self.assertEqual(palette.EZA[role], "#" + tide["tide_git_bg_color_unstable"])
+        self.assertEqual(palette.EZA["git_deleted"], "#" + tide["tide_git_bg_color_urgent"])
+
+    def test_the_rendered_string_is_unchanged(self):
+        self.assertEqual(build.eza_colors(palette.EZA),
+                         "di=38;2;185;154;255:ex=38;2;116;232;184:ln=38;2;119;217;255:sn=38;2;169;154;185"
+                         ":sb=38;2;169;154;185:da=38;2;169;154;185:ga=38;2;255;212;119:gm=38;2;255;184;107"
+                         ":gv=38;2;255;184;107:gt=38;2;255;184;107:gd=38;2;255;107;159")
+
+
 class EzaValidateTest(unittest.TestCase):
     def test_real_colours_pass(self):
diff --git a/tests/test_validate.py b/tests/test_validate.py
index 609a82b..874e72c 100644
--- a/tests/test_validate.py
+++ b/tests/test_validate.py
@@ -1,3 +1,4 @@
 import copy
+import dataclasses
 import tempfile
 import unittest
@@ -5,5 +6,5 @@ from pathlib import Path
 from unittest import mock
 
-from witchy import content, palette, validate
+from witchy import content, palette, sky_render, validate
 
 
@@ -173,4 +174,19 @@ class SkyValidateTest(unittest.TestCase):
         self.assertIn(("format", "sky.moon"), {(f.rule, f.item) for f in failures})
 
+    def test_every_colour_the_renderer_reads_must_be_present(self):
+        colours = {key: "#FFFFFF" for key in sky_render.COLOURS}
+        sky_render.render(0, colours, (64, 36))  # these are exactly the keys the renderer indexes
+        self.assertEqual(validate.validate_sky(colours), [])
+        for key in sky_render.COLOURS:
+            failures = validate.validate_sky({k: v for k, v in colours.items() if k != key})
+            self.assertEqual([(f.rule, f.item) for f in failures], [("missing-token", f"sky.{key}")])
+
+    def test_validate_all_reports_a_missing_sky_colour(self):
+        sky = {key: value for key, value in palette.SKY.items() if key != "moon_rim"}
+        variant = dataclasses.replace(palette.VARIANTS["midnight"], sky=sky)
+        with mock.patch.dict(palette.VARIANTS, {"midnight": variant}):
+            failures = validate.validate_all()
+        self.assertIn(("missing-token", "sky.moon_rim"), {(f.rule, f.item) for f in failures})
+
 
 if __name__ == "__main__":
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_validate tests.test_prompt_palette`
Expected (real output from the prototype):
```
ERROR: test_every_colour_the_renderer_reads_must_be_present ... AttributeError: module 'witchy.sky_render' has no attribute 'COLOURS'
ERROR: test_colour_keys_are_the_ones_with_a_colour_word ... AttributeError: module 'witchy.validate' has no attribute 'is_tide_colour'
ERROR: test_every_tide_colour_is_validated_for_contrast_or_exempt ... AttributeError: ... 'is_tide_colour'
FAIL: test_validate_all_reports_a_missing_sky_colour ... AssertionError: ('missing-token', 'sky.moon_rim') not found in set()
FAIL: test_a_name_that_only_contains_color_is_not_a_colour ... AssertionError: Items in the first set but not the second:
Ran 50 tests ... FAILED (failures=2, errors=3)
(EzaDerivedTest and test_the_exempt_separator_colour_is_still_format_checked pass already: they pin existing behaviour so the refactor cannot change it.)
```

- [ ] **Step 3: Implement**

Apply the edits below.

```diff
diff --git a/docs/superpowers/specs/2026-10-02-shell-ritual-design.md b/docs/superpowers/specs/2026-10-02-shell-ritual-design.md
index 711d0f2..68e05f4 100644
--- a/docs/superpowers/specs/2026-10-02-shell-ritual-design.md
+++ b/docs/superpowers/specs/2026-10-02-shell-ritual-design.md
@@ -381,6 +381,6 @@ python3 -m witchy mood [VARIANT]
 
 1. `ritual.json`: exactly 22 tarot cards, `number` 0–21 each once, unique names, `upright` and `reversed` non-empty and at most 60 characters; `name` non-empty, at most 24 characters; the 8 sabbats present with a blessing; the 3 lunar lines present; blessings and lunar lines at most 48 characters.
-2. Ritual text colours and the 8 sabbat accents at least 4.5:1 on `#0D0916`; the earthshine `#38234D`, the sky images and the stars are exempt as decorative.
-3. Tide pairs at least 4.5:1: each segment's text colour on its background (moon, pwd anchors and dirs, git colours on all three git backgrounds, status, cmd_duration, time), and `character` colours on `#0D0916`. `tide_pwd_color_truncated_dirs` and the frame colour need 3:1.
+2. Ritual text colours and the 8 sabbat accents at least 4.5:1 on `#0D0916`; the earthshine `#38234D`, the sky images and the stars are exempt as decorative. Every sky colour the renderer reads must be present and `#RRGGBB`.
+3. Tide pairs at least 4.5:1: each segment's text colour on its background (moon, pwd anchors and dirs, git colours on all three git backgrounds, status, cmd_duration, time), and `character` colours on `#0D0916`. `tide_pwd_color_truncated_dirs` and the frame colour need 3:1. `tide_prompt_color_separator_same_color` has no contrast pair (it sits between segments that share a background); only its format is checked.
 4. eza colours at least 4.5:1 on `#0D0916`.
 5. Every variant passes every rule; colour format `^#?[0-9A-F]{6}$` (Tide values without `#`).
diff --git a/witchy/palette.py b/witchy/palette.py
index 7fe5b84..5dc332c 100644
--- a/witchy/palette.py
+++ b/witchy/palette.py
@@ -208,4 +208,6 @@ TIDE: dict[str, str | tuple[str, ...]] = {
     "tide_character_color_failure": "FF6B9F",
     "tide_prompt_color_frame_and_connection": "6E5A80",
+    # Drawn between segments that share a background, so no single background exists to test it on: it is
+    # in no contrast pair in validate.py, only format-checked.
     "tide_prompt_color_separator_same_color": "A99AB9",
     "tide_status_bg_color": "1D1230",
@@ -220,5 +222,6 @@ TIDE: dict[str, str | tuple[str, ...]] = {
 }
 
-# eza (spec 7): build.eza_colors turns these into EZA_COLORS. Git status uses Tide's three git colours.
+# eza (spec 7): build.eza_colors turns these into EZA_COLORS. Git status uses Tide's three git colours,
+# taken from TIDE (which has no "#").
 EZA: dict[str, str] = {
     "directory": "#B99AFF",
@@ -227,9 +230,9 @@ EZA: dict[str, str] = {
     "size": "#A99AB9",
     "date": "#A99AB9",
-    "git_new": "#FFD477",
-    "git_modified": "#FFB86B",
-    "git_renamed": "#FFB86B",
-    "git_typechange": "#FFB86B",
-    "git_deleted": "#FF6B9F",
+    "git_new": "#" + TIDE["tide_git_bg_color"],
+    "git_modified": "#" + TIDE["tide_git_bg_color_unstable"],
+    "git_renamed": "#" + TIDE["tide_git_bg_color_unstable"],
+    "git_typechange": "#" + TIDE["tide_git_bg_color_unstable"],
+    "git_deleted": "#" + TIDE["tide_git_bg_color_urgent"],
 }
 
diff --git a/witchy/sky_render.py b/witchy/sky_render.py
index 922e5ad..dd4beaf 100644
--- a/witchy/sky_render.py
+++ b/witchy/sky_render.py
@@ -22,4 +22,5 @@ SEED = 1031  # fixed, so the starfield is identical in all eight images
 STARS = 220
 SPARKLES = 7
+COLOURS = ("background", "moon", "moon_dark", "moon_rim", "star", "star_gold", "star_violet")  # what render reads
 _KEY = re.compile(r"[0-9a-f]{16}")  # the cache directory names
 
diff --git a/witchy/validate.py b/witchy/validate.py
index 4474c9f..506b9bd 100644
--- a/witchy/validate.py
+++ b/witchy/validate.py
@@ -7,5 +7,5 @@ from pathlib import Path
 from typing import Any, Mapping
 
-from . import content, palette, tokens
+from . import content, palette, sky_render, tokens
 from .contrast import contrast_ratio
 
@@ -285,4 +285,21 @@ def validate_ritual_palette(colours: Mapping[str, Any], background: str = palett
 
 
+def is_tide_colour(key: str) -> bool:
+    """Tide names a colour variable with the word ``color``: ``tide_pwd_bg_color``, ``tide_git_color_branch``."""
+    return "color" in key.split("_")
+
+
+def validate_sky(sky: Mapping[str, Any]) -> list[Failure]:
+    """Every colour the sky renderer reads is present and #RRGGBB. The sky is decorative: no contrast rule."""
+    failures: list[Failure] = []
+    for key in sky_render.COLOURS:
+        if key not in sky:
+            failures.append(Failure("missing-token", f"sky.{key}", "-", "is missing from the sky colours"))
+    for key, value in sky.items():
+        if not isinstance(value, str) or not HEX.match(value):
+            failures.append(Failure("format", f"sky.{key}", str(value), "is not #RRGGBB in uppercase"))
+    return failures
+
+
 def validate_tide(tide: Mapping[str, Any], background: str = palette.BACKGROUND) -> list[Failure]:
     """Every Tide variable is present; colours are RRGGBB without "#"; segment text reads on its background."""
@@ -293,8 +310,8 @@ def validate_tide(tide: Mapping[str, Any], background: str = palette.BACKGROUND)
     bad = set()
     for key, value in tide.items():
-        if "color" in key and not (isinstance(value, str) and TIDE_HEX.match(value)):
+        if is_tide_colour(key) and not (isinstance(value, str) and TIDE_HEX.match(value)):
             failures.append(Failure("format", f"tide.{key}", str(value), "is not RRGGBB in uppercase, without #"))
             bad.add(key)
-        elif "color" not in key and not (isinstance(value, str) or
+        elif not is_tide_colour(key) and not (isinstance(value, str) or
                                          (isinstance(value, tuple) and all(isinstance(v, str) for v in value))):
             failures.append(Failure("format", f"tide.{key}", str(value), "must be a string or a tuple of strings"))
@@ -337,6 +354,5 @@ def validate_all(content_dir: Path = content.CONTENT_DIR) -> list[Failure]:
         failures += validate_palette(variant.claude_overrides, variant.wt_scheme, variant.statusline,
                                      variant.background, variant.foreground)
-        failures += [Failure("format", f"sky.{key}", str(value), "is not #RRGGBB in uppercase")
-                     for key, value in variant.sky.items() if not isinstance(value, str) or not HEX.match(value)]
+        failures += validate_sky(variant.sky)
         failures += validate_ritual_palette(variant.ritual, variant.background)
         failures += validate_tide(variant.tide, variant.background)
```

- [ ] **Step 4: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 537 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_validate.py tests/test_prompt_palette.py witchy/sky_render.py witchy/validate.py witchy/palette.py docs/superpowers/specs/2026-10-02-shell-ritual-design.md
git commit -m "fix: validate the sky colours the renderer reads, find Tide colours by name, derive eza git colours from Tide"
```

---

### Task 11: Windows helpers: percent in paths, USERNAME never queried, doctor docs

**Items:** B5 `windows.echo` treats any `%` as unset; B3 renamed-account test does not prove USERNAME is never queried; B15 README row misses `failed:`

**Files:**
- Modify: `witchy/windows.py` (`echo`)
- Modify: `README.md` (troubleshooting row)
- Test: `tests/test_windows.py`, `tests/test_wt.py`

**Interfaces:**
- Consumes: `fake_windows(echo=..., calls=...)` from `tests/fakes.py` (unchanged)
- Produces: nothing new

**Decisions:**
1. cmd.exe prints the literal `%VAR%` back for an unset variable, so that exact string is the signal. `wt.py` line 20 is the only other caller (`USERNAME`), unaffected.
2. B3 is test only: the code already skips `USERNAME` when `USERPROFILE` resolves, so that test has no RED. B15 is docs only.

- [ ] **Step 1: Write the failing tests**

Add a method to `UserHomeTest` (before `test_missing_folder_or_variable_is_none`) and extend `LookupFixTest.test_profile_folder_wins_over_a_renamed_account`:

```diff
diff --git a/tests/test_windows.py b/tests/test_windows.py
index 9eb0b11..7498064 100644
--- a/tests/test_windows.py
+++ b/tests/test_windows.py
@@ -29,4 +29,12 @@ class UserHomeTest(unittest.TestCase):
                          windows.WindowsHome("C:\\Users\\manue", self.mnt / "c" / "Users" / "manue"))
 
+    def test_a_percent_sign_in_the_profile_path_is_a_value_not_an_unset_variable(self):
+        (self.mnt / "c" / "Users" / "100%").mkdir(parents=True)
+        run = fake_windows(echo={"USERPROFILE": "C:\\Users\\100%\r\n"})
+        self.assertEqual(windows.echo("USERPROFILE", run), "C:\\Users\\100%")
+        self.assertEqual(windows.user_home(run, self.mnt),
+                         windows.WindowsHome("C:\\Users\\100%", self.mnt / "c" / "Users" / "100%"))
+        self.assertIsNone(windows.echo("USERPROFILE", fake_windows()))  # cmd.exe prints %USERPROFILE% back
+
     def test_missing_folder_or_variable_is_none(self):
         self.assertIsNone(windows.user_home(fake_windows(echo={"USERPROFILE": "C:\\Users\\gone\r\n"}), self.mnt))
diff --git a/tests/test_wt.py b/tests/test_wt.py
index b8615f7..13079f3 100644
--- a/tests/test_wt.py
+++ b/tests/test_wt.py
@@ -210,7 +210,9 @@ class LookupFixTest(unittest.TestCase):
 
     def test_profile_folder_wins_over_a_renamed_account(self):
-        run = fake_windows(echo={"USERPROFILE": "C:\\Users\\manue\r\n", "USERNAME": "Manuel\r\n"})
+        calls = []
+        run = fake_windows(echo={"USERPROFILE": "C:\\Users\\manue\r\n", "USERNAME": "Manuel\r\n"}, calls=calls)
         found = wt.locate_settings(None, run=run, users_root=self.mnt / "c" / "Users", mount_root=self.mnt)
         self.assertEqual(found, self.settings)
+        self.assertNotIn(["cmd.exe", "/c", "echo %USERNAME%"], calls)
 
     def test_recorded_path_is_used_without_asking_windows(self):
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_windows tests.test_wt`
Expected (real output from the prototype):
```
FAIL: test_a_percent_sign_in_the_profile_path_is_a_value_not_an_unset_variable ... AssertionError: None != 'C:\\Users\\100%'
Ran 36 tests ... FAILED (failures=1)
(The B3 assertion passes already: no RED, by design. B15 is docs.)
```

- [ ] **Step 3: Implement**

Apply the edits below.

```diff
diff --git a/README.md b/README.md
index 85e5c05..7be6e02 100644
--- a/README.md
+++ b/README.md
@@ -69,5 +69,5 @@ Run `python3 -m witchy doctor`. Each `⚠` or `✗` line is followed by the comm
 | `⚠ fish  greeting: last run failed …` | the greeting hit an error in the last 7 days and printed nothing | see `~/.cache/witchy/ritual.log`; `ritual` shows the greeting |
 | `⚠ fish  sky: last run failed …` | the sky job could not move the moon (for example, you set your own `backgroundImage`); it retries once a day | `python3 -m witchy install --only windows-terminal` puts the moon sky back |
-| `⚠ …  last install (…): skipped: …` | a component was skipped or failed at the last install | read the reason, then install `--only` that component |
+| `⚠ …  last install (…): skipped: …` or `failed: …` | a component was skipped or failed at the last install | read the reason, then install `--only` that component |
 | `✗ state  … damaged` | `state.json` is not readable | fix or remove the file by hand |
 
diff --git a/witchy/windows.py b/witchy/windows.py
index 87d5b99..48aab8c 100644
--- a/witchy/windows.py
+++ b/witchy/windows.py
@@ -21,5 +21,5 @@ class WindowsHome:
 
 def echo(variable: str, run: Callable[..., Any] = subprocess.run) -> str | None:
-    """The value of a Windows environment variable, or None."""
+    """The value of a Windows environment variable, or None. cmd.exe prints ``%VAR%`` back when it is unset."""
     try:
         # cwd=/mnt/c keeps cmd.exe from warning about a UNC working directory. cmd.exe answers in the OEM code
@@ -30,5 +30,5 @@ def echo(variable: str, run: Callable[..., Any] = subprocess.run) -> str | None:
         return None
     value = (done.stdout or "").strip()
-    return value if done.returncode == 0 and value and "%" not in value else None
+    return value if done.returncode == 0 and value and value != f"%{variable}%" else None
```

- [ ] **Step 4: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 538 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_windows.py tests/test_wt.py witchy/windows.py README.md
git commit -m "fix: a percent sign in the Windows profile path is a value, not an unset variable"
```

---

### Task 12: `ritual` arguments: the sky flag, argument errors, `--date`

**Items:**
- C3: `--sky` had one test (the date flag); pin the rest: `sky.run(home, now)`, nothing printed, no `last-ritual` stamp, a job exception is logged and exits 0, `--sky` with `--full`/`--omen` is an argument error.
- C6: an argument error under `fish_greeting` (stderr to `/dev/null`) left no trace for doctor; log it when stderr is not a terminal.
- C7: `--date` used `date.fromisoformat`, which takes `20261031` and `2026-W44-6` on 3.11+ but not on 3.10; accept exactly `YYYY-MM-DD` on both.
- C8: `--date` kept today's UTC offset, so a preview across a DST change had the wrong offset; use the local offset of the previewed day.

**Files:**
- Modify: `witchy/ritual/cli.py` (`iso_day`, `_Parser`, `_arguments` takes the log path, the preview's offset)
- Modify: `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (6.1 `--date`, 6.7 bad arguments)
- Test: `tests/test_ritual_cli.py`

**Interfaces:**
- Consumes: `log.append(path, message, now)`, `log.NAME`
- Produces:
  - `cli.ISO_DAY` (compiled pattern), `cli.iso_day(text: str) -> date` (raises `argparse.ArgumentTypeError`)
  - `cli._Parser(log_path: Path, **kwargs)`, an `argparse.ArgumentParser` whose `error` also logs `greeting: bad arguments: <message>` when `sys.stderr` is not a TTY
  - `cli._arguments(argv, log_path: Path)` (was `_arguments(argv)`)

**Decisions:**
1. **The TTY check reads `sys.stderr` at error time.** argparse itself writes usage to `sys.stderr`, so patching `sys.stderr` in a test both captures the usage text and decides TTY or not (a `StringIO` subclass whose `isatty()` is True plays the terminal). No new parameter on `main`. `sys.stderr` may be `None` (stderr closed); that counts as "not a terminal".
2. **The log timestamp is `datetime.now()`,** like the existing exception path: the injected `now` is not resolved yet when parsing fails.
3. **`[0-9]`, not `\d`, in `ISO_DAY`.** `\d` matches other scripts' digits (`２０２６-10-31`), which `fromisoformat` rejects anyway; `[0-9]` gives the same clear message for them. A regex match that is not a real day (`2026-02-30`) gets the same message.
4. **The preview resolves through the system's local zone:** `datetime.combine(day, now.time()).astimezone()` (a naive datetime's `astimezone()` uses the C library's local time, so it follows `TZ` and DST). The injected `now` only supplies the wall time. The real `now` carries a fixed offset with no zone key, so this is the only stdlib way to get "the offset in force on that day" without a tz database. The test pins the zone with `TZ` + `time.tzset()` using the POSIX rule `CET-1CEST,M3.5.0,M10.5.0/3` (Europe/Madrid's rules), which needs no zoneinfo files. The existing `--date` tests stay deterministic: they only check the sabbat countdown (Samhain is a fixed date) and the absent stamp; checked under `TZ=UTC`, `Pacific/Kiritimati` and `America/Adak`.
5. **An error from `sky.run` is logged with the `greeting:` prefix,** because `cli.main` catches it, as today. `sky.run` logs its own failures as `sky:` and never raises in practice.

- [ ] **Step 1: Write the failing tests**

In `tests/test_ritual_cli.py` (edit 1 of 5), replace:

```python
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
```

with:

```python
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta, timezone
```

In `tests/test_ritual_cli.py` (edit 2 of 5), replace:

```python
PLAIN = {"NO_COLOR": "1", "FISH_VERSION": "3.7.0"}
```

with:

```python
PLAIN = {"NO_COLOR": "1", "FISH_VERSION": "3.7.0"}
LOG_LINE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d greeting: bad arguments: (.*)$")


class Terminal(io.StringIO):
    """A stderr that a person reads."""

    def isatty(self):
        return True
```

In `tests/test_ritual_cli.py` (edit 3 of 5), in `CliTestCase`, replace:

```python
        self.assertEqual(code, 0)
        return out.getvalue()
```

with:

```python
        self.assertEqual(code, 0)
        return out.getvalue()

    def bad_arguments(self, argv, tty=False):
        """Run with arguments argparse rejects; return what went to stderr."""
        err = Terminal() if tty else io.StringIO()
        with mock.patch("sys.stderr", err), self.assertRaises(SystemExit) as caught:
            cli.main(list(argv), env=PLAIN, out=io.StringIO(), now=SAMHAIN_NIGHT, home=self.home, root=self.root)
        self.assertEqual(caught.exception.code, 2)
        return err.getvalue()
```

In `tests/test_ritual_cli.py` (edit 4 of 5), in `SkyModeTest`, replace:

```python
            self.run_cli(["--sky", "--date", "2026-12-24"])
        run.assert_called_once_with(self.home, SAMHAIN_NIGHT)
```

with:

```python
            self.run_cli(["--sky", "--date", "2026-12-24"])
        run.assert_called_once_with(self.home, SAMHAIN_NIGHT)

    def test_runs_the_job_on_now_and_prints_nothing(self):
        with mock.patch.object(sky, "run", return_value=0) as run:
            self.assertEqual(self.run_cli(["--sky"]), "")
        run.assert_called_once_with(self.home, SAMHAIN_NIGHT)
        self.assertFalse(self.stamp.exists())

    def test_an_error_from_the_job_is_logged(self):
        with mock.patch.object(sky, "run", side_effect=OSError("disk full")):
            self.assertEqual(self.run_cli(["--sky"]), "")
        self.assertIn("greeting: OSError('disk full')", self.log.read_text(encoding="utf-8"))
        self.assertFalse(self.stamp.exists())

    def test_sky_and_another_mode_is_an_argument_error(self):
        for mode in ("--full", "--omen"):
            with self.subTest(mode), mock.patch.object(sky, "run") as run:
                self.assertIn(f"argument {mode}: not allowed with argument --sky", self.bad_arguments(["--sky", mode]))
                run.assert_not_called()


class ArgumentErrorTest(CliTestCase):
    def test_a_typed_ritual_shows_usage_and_logs_nothing(self):
        err = self.bad_arguments(["--full", "--omen"], tty=True)
        self.assertTrue(err.startswith("usage: ritual "), err)
        self.assertIn("ritual: error: argument --omen: not allowed with argument --full", err)
        self.assertFalse(self.log.exists())

    def test_the_greeting_logs_what_nobody_sees(self):
        # fish_greeting sends stderr to /dev/null: the error must reach doctor through the log
        err = self.bad_arguments(["--full", "--omen"])
        self.assertTrue(err.startswith("usage: ritual "), err)
        lines = self.log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(LOG_LINE.match(lines[0]).group(1), "argument --omen: not allowed with argument --full")

    def test_the_date_must_be_yyyy_mm_dd(self):
        for text in ("20261031", "2026-W44-6", "2026-1-5", "2026-02-30", "２０２６-10-31"):
            with self.subTest(text):
                self.assertIn(f"argument --date: {text!r} is not a date in the form YYYY-MM-DD",
                              self.bad_arguments(["--date", text], tty=True))
        self.assertEqual(cli.iso_day("2026-10-31"), date(2026, 10, 31))


class PreviewZoneTest(CliTestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(time.tzset)  # runs last, once TZ is back
        zone = mock.patch.dict(os.environ, {"TZ": "CET-1CEST,M3.5.0,M10.5.0/3"})  # Europe/Madrid's rules
        zone.start()
        self.addCleanup(zone.stop)
        time.tzset()

    def test_a_preview_takes_the_offset_of_its_own_day(self):
        today = datetime(2026, 10, 3, 21, 30, tzinfo=CEST)
        for day, hours in (("2026-12-01", 1), ("2026-10-10", 2)):
            with self.subTest(day), mock.patch.object(cli, "omen_line", wraps=cli.omen_line) as omen:
                self.run_cli(["--omen", "--date", day], now=today)
                shown = omen.call_args.args[0]
                self.assertEqual((shown.replace(tzinfo=None), shown.utcoffset()),
                                 (datetime.combine(date.fromisoformat(day), today.time()), timedelta(hours=hours)))
```

(Edit 5 of 5 is none: `EntryPointTest` and the rest stay as they are.)

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_ritual_cli` and `/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest tests.test_ritual_cli`
Expected (real output from the prototype, 3.12; the three `SkyModeTest` additions pin existing behaviour and pass):
```
ERROR: test_the_date_must_be_yyyy_mm_dd (tests.test_ritual_cli.ArgumentErrorTest.test_the_date_must_be_yyyy_mm_dd)
AttributeError: module 'witchy.ritual.cli' has no attribute 'iso_day'
ERROR: test_the_greeting_logs_what_nobody_sees (tests.test_ritual_cli.ArgumentErrorTest.test_the_greeting_logs_what_nobody_sees)
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/tmpzlyc6pqt/home/.cache/witchy/ritual.log'
FAIL: test_the_date_must_be_yyyy_mm_dd (...) [20261031]
AssertionError: SystemExit not raised
FAIL: test_the_date_must_be_yyyy_mm_dd (...) [2026-1-5]
AssertionError: "argument --date: '2026-1-5' is not a date in the form YYYY-MM-DD" not found in "usage: ritual [-h] [--full | --omen | --sky] [--debug] [--date DATE]\nritual: error: argument --date: invalid fromisoformat value: '2026-1-5'\n"
FAIL: test_a_preview_takes_the_offset_of_its_own_day (tests.test_ritual_cli.PreviewZoneTest...) [2026-12-01]
AssertionError: Tuples differ: (datetime.datetime(2026, 12, 1, 21, 30), datetime.timedelta(seconds=7200)) != (datetime.datetime(2026, 12, 1, 21, 30), datetime.timedelta(seconds=3600))
Ran 30 tests in 0.100s
FAILED (failures=6, errors=2)
```
On 3.10 the same counts; `20261031` and `2026-W44-6` fail with `invalid fromisoformat value` instead of `SystemExit not raised`.

- [ ] **Step 3: Implement**

In `witchy/ritual/cli.py` (edit 1 of 6), replace:

```python
import os
import shutil
```

with:

```python
import os
import re
import shutil
```

In `witchy/ritual/cli.py` (edit 2 of 6), replace:

```python
from typing import Mapping, TextIO
```

with:

```python
from typing import Mapping, NoReturn, TextIO
```

In `witchy/ritual/cli.py` (edit 3 of 6), replace:

```python
SEPARATOR = (" · ", "label", False)
```

with:

```python
SEPARATOR = (" · ", "label", False)
ISO_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
```

In `witchy/ritual/cli.py` (edit 4 of 6), replace the function `_arguments` with:

```python
def iso_day(text: str) -> date:
    """``--date``: YYYY-MM-DD only (from 3.11, date.fromisoformat also takes 20261031 and 2026-W44-6)."""
    if ISO_DAY.fullmatch(text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(f"{text!r} is not a date in the form YYYY-MM-DD")


class _Parser(argparse.ArgumentParser):
    """Exits 2 with usage as usual, and also logs the error when stderr is not a terminal.

    fish_greeting sends stderr to /dev/null, so without the log a broken call would be invisible to doctor.
    """

    def __init__(self, log_path: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self.log_path = log_path

    def error(self, message: str) -> NoReturn:
        if not (sys.stderr and sys.stderr.isatty()):
            log.append(self.log_path, f"greeting: bad arguments: {message}", datetime.now())
        super().error(message)


def _arguments(argv: list[str] | None, log_path: Path) -> argparse.Namespace:
    parser = _Parser(log_path, prog="ritual", description="The Moonlit Candle greeting")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--full", action="store_true", help="always show the full ritual")
    mode.add_argument("--omen", action="store_true", help="show the one-line omen")
    mode.add_argument("--sky", action="store_true", help="move the Windows Terminal sky to tonight's phase")
    parser.add_argument("--debug", action="store_true", help="print the time each stage took")
    parser.add_argument("--date", type=iso_day, help="preview another day (YYYY-MM-DD)")
    return parser.parse_args(argv)
```

In `witchy/ritual/cli.py` (edit 5 of 6), in `main`, replace:

```python
    args = _arguments(argv)
```

with:

```python
    args = _arguments(argv, cache / log.NAME)
```

In `witchy/ritual/cli.py` (edit 6 of 6), in `main`, replace:

```python
        if args.date and not args.sky:  # the sky job always works on the real now
            now = datetime.combine(args.date, now.timetz())
```

with:

```python
        if args.date and not args.sky:  # the sky job always works on the real now
            # the same wall time, with the local UTC offset of that day (it differs across a DST change)
            now = datetime.combine(args.date, now.time()).astimezone()
```

In `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (edit 1 of 2), section 6.1, replace:

```markdown
`--date YYYY-MM-DD` (preview another day) |
```

with:

```markdown
`--date YYYY-MM-DD` (preview another day: the same wall time, with that day's UTC offset; any other date form is an argument error) |
```

In `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (edit 2 of 2), section 6.7, replace:

```markdown
- Any exception: print nothing, exit 0, and append the error to `ritual.log`. Doctor shows the last logged error.
```

with:

```markdown
- Any exception: print nothing, exit 0, and append the error to `ritual.log`. Doctor shows the last logged error.
- Bad arguments: usage on stderr, exit 2. When stderr is not a terminal (`fish_greeting` sends it to `/dev/null`), the error is also logged as `greeting: bad arguments: …`.
```

The README's `ritual --date 2026-10-31   # preview another day` stays correct; no README change.

Never check the error path by hand with the real HOME: with stderr not a terminal it writes `~/.cache/witchy/ritual.log`. Use `HOME=$(mktemp -d)` for any manual run.

- [ ] **Step 4: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 545 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/ritual/cli.py tests/test_ritual_cli.py docs/superpowers/specs/2026-10-02-shell-ritual-design.md
git commit -m "fix: ritual takes only YYYY-MM-DD, previews with that day's UTC offset, and logs argument errors nobody sees

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: The ritual log and the entry point

**Items:**
- C9: `log.append` wrote the whole message; an exception repr can hold the whole greeting. Collapse whitespace and cut to 300 characters, the same cap as `__main__.py`'s fallback, with the numbers shared and checked.
- C13: the log write was read-modify-write with `write_text`; a sky job and a greeting at once could lose a line or leave half a file. Serialise writers with `ritual.log.lock` and replace the file atomically; still never raise.
- C14: `__main__.py` put `~/.claude/witchy` first on `sys.path`, so a stray `json.py` there would shadow the stdlib. Load the package without touching `sys.path`.

**Files:**
- Modify: `witchy/ritual/log.py` (`MAX_CHARS`, `LOCK_TIMEOUT`, `append` locked and atomic)
- Modify: `witchy/ritual/__main__.py` (`MAX_LINES`, `MAX_CHARS`; the installed copy loaded with `importlib`)
- Modify: `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (6.1, the `log.py` row)
- Test: `tests/test_ritual_log.py`, `tests/test_ritual_package.py`

**Interfaces:**
- Consumes: `build.ritual_package()` (tests)
- Produces:
  - `log.MAX_CHARS = 300`, `log.LOCK_TIMEOUT = 1.0`
  - `log.append(path, message, now)`: same signature; also creates `<path>.lock` (`~/.cache/witchy/ritual.log.lock`) beside the log
  - `__main__.MAX_LINES = 20`, `__main__.MAX_CHARS = 300` (module-level, checked against `log` by a test)

**Decisions:**
1. **The numbers are repeated in `__main__.py` and a test keeps them equal.** `__main__._log_failure` runs when an import failed, possibly `log` itself, so it must not import `log`. It had `[:300]` and `[-20:]  # 20 is log.MAX_LINES`; now both are named constants and `test_the_entry_point_cuts_at_the_same_length` reads them from the file. Both cap the message *after* the timestamp, prefix included (`__main__` now cuts `greeting: <repr>`, as `log.append` does).
2. **A separate lock file, `ritual.log.lock`,** because the log itself is replaced on every write (a lock on a replaced file serialises nothing). `sky._locked` is not reused: `sky` imports `log` (a cycle), it raises `SkyError` and waits 10 s. The log waits at most `LOCK_TIMEOUT = 1.0` s, then drops the line silently: a stopped writer must never hold up a shell. The lock is released when its file closes.
3. **No `fsync`.** The log is disposable (spec 3.3: `~/.cache/witchy/` can go at any time) and the greeting has a 200 ms budget. The temp file + `os.replace` already rules out a half-written file for readers and concurrent writers.
4. **The log file is now created with mode 0600** (from `mkstemp`), where `write_text` gave 0644. Only the user and doctor (same user) read it.
5. **The installed copy is loaded with `importlib.util.spec_from_file_location("ritual", …)` instead of `sys.path.append`.** Appending the parent would let any other top-level `ritual` on `sys.path` (system `dist-packages` stays on the path under `-I`) stand in for ours; loading by file location rules out both shadowings. Checked by hand as well: a `ritual` package on `PYTHONPATH` plus a stray `json.py` beside the package, and the greeting still printed. `-B` still holds (no `__pycache__`).
6. **`__main__._log_failure` stays unlocked.** It only runs when the package cannot be imported, and must use the stdlib alone.

- [ ] **Step 1: Write the failing tests**

In `tests/test_ritual_log.py` (edit 1 of 2), replace:

```python
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from witchy.ritual import log
```

with:

```python
import fcntl
import re
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from witchy.ritual import log

WRITTEN = re.compile(r"^2026-10-31T21:00:00 greeting: ([AB]) ([0-9]{3}) x{200}$")
```

In `tests/test_ritual_log.py` (edit 2 of 2), add these methods to `LogTest`, after `test_corrupt_utf8_in_log_is_ignored`:

```python
    def test_a_long_message_is_cut(self):
        log.append(self.path, "greeting: UnicodeEncodeError(\n  " + "x" * 1000, datetime(2026, 10, 31, 21, 0))
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        message = ("greeting: UnicodeEncodeError( " + "x" * 1000)[:log.MAX_CHARS]  # whitespace collapsed, then cut
        self.assertEqual(lines[0], "2026-10-31T21:00:00 " + message)

    def test_the_entry_point_cuts_at_the_same_length(self):
        # __main__.py cannot import log (it may be what failed), so it repeats the numbers
        text = (Path(log.__file__).parent / "__main__.py").read_text(encoding="utf-8")
        self.assertEqual(re.search(r"^MAX_LINES = ([0-9]+)", text, re.M).group(1), str(log.MAX_LINES))
        self.assertEqual(re.search(r"^MAX_CHARS = ([0-9]+)", text, re.M).group(1), str(log.MAX_CHARS))

    def append_at_once(self, count):
        """Two writers append ``count`` lines each at the same time, like a greeting and a sky job."""
        def write(name):
            for number in range(count):
                log.append(self.path, f"greeting: {name} {number:03d} " + "x" * 200, datetime(2026, 10, 31, 21, 0))

        writers = [threading.Thread(target=write, args=(name,)) for name in "AB"]
        for writer in writers:
            writer.start()
        for writer in writers:
            writer.join()
        return self.path.read_text(encoding="utf-8").splitlines()

    def test_two_writers_at_once_lose_no_line(self):
        started = time.monotonic()
        with mock.patch.object(log, "MAX_LINES", 1000):
            lines = self.append_at_once(100)
        self.assertLess(time.monotonic() - started, 1.0)
        matches = [WRITTEN.match(line) for line in lines]
        self.assertTrue(all(matches), lines)
        for name in "AB":
            self.assertEqual([int(m.group(2)) for m in matches if m.group(1) == name], list(range(100)))

    def test_two_writers_at_once_keep_the_last_twenty(self):
        lines = self.append_at_once(50)
        self.assertEqual(len(lines), log.MAX_LINES)
        self.assertTrue(all(WRITTEN.match(line) for line in lines), lines)
        self.assertEqual(WRITTEN.match(lines[-1]).group(2), "049")  # the last append of either writer

    def test_a_held_lock_gives_up_quietly(self):
        self.path.parent.mkdir(parents=True)
        with open(self.path.with_name(self.path.name + ".lock"), "a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            with mock.patch.object(log, "LOCK_TIMEOUT", 0.05):
                log.append(self.path, "greeting: boom", datetime(2026, 10, 31))  # must not raise
        self.assertFalse(self.path.exists())
        log.append(self.path, "greeting: boom", datetime(2026, 10, 31))
        self.assertEqual(log.last(self.path), "2026-10-31T00:00:00 greeting: boom")
```

(Threads are enough: `flock` locks belong to the open file description, and each `append` opens the lock file itself, so two threads conflict exactly as two processes do. 2 × 100 appends take about 0.1 s.)

In `tests/test_ritual_package.py`, add this method to `InstalledCopyTest`, after `test_a_missing_module_is_logged_not_shown`:

```python
    def test_a_stray_module_beside_the_package_does_not_shadow_the_standard_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / ".claude" / "witchy" / "ritual"
            target.mkdir(parents=True)
            for name, data in build.ritual_package().items():
                (target / name).write_bytes(data)
            (target.parent / "json.py").write_text('raise ImportError("the stray json.py was imported")\n',
                                                   encoding="utf-8")
            env = {"HOME": tmp, "NO_COLOR": "1", "PATH": os.environ.get("PATH", "")}
            done = subprocess.run([PYTHON, "-I", "-B", str(target), "--omen", "--date", "2026-10-31"],
                                  capture_output=True, text=True, env=env, cwd=tmp, timeout=10)
            self.assertEqual((done.returncode, done.stderr), (0, ""))
            self.assertIn("🕯️ Samhain", done.stdout)
            self.assertFalse((Path(tmp) / ".cache" / "witchy" / "ritual.log").exists())
```

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_ritual_log tests.test_ritual_package` (and the same with the 3.10 interpreter)
Expected (real output from the prototype, 3.12):
```
ERROR: test_a_held_lock_gives_up_quietly (tests.test_ritual_log.LogTest.test_a_held_lock_gives_up_quietly)
AttributeError: <module 'witchy.ritual.log' from '…/witchy/ritual/log.py'> does not have the attribute 'LOCK_TIMEOUT'
ERROR: test_a_long_message_is_cut (tests.test_ritual_log.LogTest.test_a_long_message_is_cut)
AttributeError: module 'witchy.ritual.log' has no attribute 'MAX_CHARS'
ERROR: test_the_entry_point_cuts_at_the_same_length (tests.test_ritual_log.LogTest.test_the_entry_point_cuts_at_the_same_length)
AttributeError: 'NoneType' object has no attribute 'group'
FAIL: test_two_writers_at_once_lose_no_line (tests.test_ritual_log.LogTest.test_two_writers_at_once_lose_no_line)
AssertionError: Lists differ: [58, 59, 60, 61, 65, 67, 68, 73, 75, 76, 7[57 chars], 99] != [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12,[343 chars], 99]
FAIL: test_a_stray_module_beside_the_package_does_not_shadow_the_standard_library (tests.test_ritual_package.InstalledCopyTest...)
AssertionError: '🕯️ Samhain' not found in ''
Ran 15 tests in 0.229s
FAILED (failures=2, errors=3)
```
On 3.10 `test_two_writers_at_once_keep_the_last_twenty` also failed (`AssertionError: 13 != 20`); on 3.12 it passed by chance in that run. The lost lines vary from run to run; `test_two_writers_at_once_lose_no_line` failed on every run.

- [ ] **Step 3: Implement**

In `witchy/ritual/log.py`, replace everything above `def last` with:

```python
"""~/.cache/witchy/ritual.log: the last 20 errors of the greeting and the sky job, for doctor."""
from __future__ import annotations

import fcntl
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

NAME = "ritual.log"
MAX_LINES = 20
MAX_CHARS = 300  # per message; an exception's repr can hold the whole greeting
LOCK_TIMEOUT = 1.0  # seconds; past it the line is dropped, so a stuck writer never holds up a shell


def append(path: Path, message: str, now: datetime) -> None:
    """Add one line; never raises, because the greeting must stay silent.

    The greeting and the sky job may log at once: writers take ``ritual.log.lock`` in turn (a lock on the log
    itself would not hold across the replace) and swap in a whole new file, so a reader never sees half of one.
    """
    try:
        line = f"{now:%Y-%m-%dT%H:%M:%S} " + " ".join(message.split())[:MAX_CHARS]
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path.with_name(path.name + ".lock"), "a") as lock:
            deadline = time.monotonic() + LOCK_TIMEOUT
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        return
                    time.sleep(0.01)
            old = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
            fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write("\n".join([*old, line][-MAX_LINES:]) + "\n")
                os.replace(tmp, path)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
    except (OSError, ValueError):
        pass
```

(`def last` stays as it is.)

In `witchy/ritual/__main__.py` (edit 1 of 3), replace:

```python
signal.signal(signal.SIGINT, signal.SIG_DFL)  # a Ctrl-C while a shell starts must end the greeting silently
```

with:

```python
signal.signal(signal.SIGINT, signal.SIG_DFL)  # a Ctrl-C while a shell starts must end the greeting silently
MAX_LINES = 20  # log.MAX_LINES and log.MAX_CHARS; a test keeps them equal
MAX_CHARS = 300
```

In `witchy/ritual/__main__.py` (edit 2 of 3), in `_log_failure`, replace:

```python
        message = " ".join(repr(exc).split())[:300]
        lines.append(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} greeting: {message}")
        path.write_text("\n".join(lines[-20:]) + "\n", encoding="utf-8")  # 20 is log.MAX_LINES
```

with:

```python
        message = " ".join(f"greeting: {exc!r}".split())[:MAX_CHARS]
        lines.append(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {message}")
        path.write_text("\n".join(lines[-MAX_LINES:]) + "\n", encoding="utf-8")
```

In `witchy/ritual/__main__.py` (edit 3 of 3), replace:

```python
    else:  # the installed copy, run as a directory
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from ritual.cli import main
```

with:

```python
    else:  # the installed copy, run as a directory
        # Load this folder as the package "ritual" without adding its parent to sys.path: a stray json.py
        # there would shadow the stdlib, and appending it instead would let another "ritual" stand in for this one.
        import importlib.util
        here = Path(__file__).resolve().parent
        spec = importlib.util.spec_from_file_location("ritual", here / "__init__.py",
                                                      submodule_search_locations=[str(here)])
        sys.modules["ritual"] = package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(package)
        from ritual.cli import main
```

In `docs/superpowers/specs/2026-10-02-shell-ritual-design.md`, section 6.1, replace:

```markdown
| `log.py` | `~/.cache/witchy/ritual.log`, trimmed to the last 20 lines |
```

with:

```markdown
| `log.py` | `~/.cache/witchy/ritual.log`, trimmed to the last 20 lines, each message cut to 300 characters; writers take `ritual.log.lock` in turn and replace the file atomically |
```

- [ ] **Step 4: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 551 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/ritual/log.py witchy/ritual/__main__.py tests/test_ritual_log.py tests/test_ritual_package.py docs/superpowers/specs/2026-10-02-shell-ritual-design.md
git commit -m "fix: the ritual log caps each message, serialises writers and replaces the file atomically; the installed copy keeps the stdlib first

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: The sky job: the stamp under the lock, a config that is not an object, CRLF and duplicates

**Items:**
- C4: no test for a `settings.json` with CRLF line endings; pin that the job keeps CRLF and changes only the image.
- C5: no test for a sky value that appears twice; pin that the file is untouched and the log says `appears 2 times`.
- C10: `sky-bin` was written after the lock was released, so a shell opening at a bin boundary could start one extra job; write it inside the locked section, for both the changed and the unchanged case.
- C11: a `ritual-config.json` that is not a JSON object logged `'list' object has no attribute 'get'`; raise `SkyError` with a clear message.

**Files:**
- Modify: `witchy/ritual/sky.py` (`update` takes the stamp path and writes it under the lock; checks the config type; `run` no longer writes the stamp)
- Modify: `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (4.5, when `sky-bin` is written)
- Test: `tests/test_sky_job.py`

**Interfaces:**
- Consumes: `sky._locked(path)` (patched in a test), `log.last`
- Produces: `sky.update(config: object, lock: Path, stamp: Path, target: int) -> bool` (was `update(config: dict, lock: Path, target: int)`; only `sky.run` calls it, no test calls it directly)

**Decisions:**
1. **`update` takes the stamp path** rather than the cache folder, so the lock and the stamp stay separate, explicit arguments as before. `run` passes `cache / STAMP`.
2. **The early `return False` became `if current != wanted:`,** so the one stamp write sits after both paths inside `with _locked(lock):`. A failure (including a failed stamp write) still raises and `run` logs it with the fail marker, as before.
3. **The fix narrows the window, it does not close it:** `conf.d/witchy.fish` reads `sky-bin` without the lock, so a shell that reads it while a job is still running starts a second job; that job then waits for the lock, finds tonight's image and only rewrites the stamp (spec 4.5's "the second sees the updated stamp").
4. **C4 and C5 pin existing behaviour (no RED, as expected):** `json.loads` treats `\r\n` as whitespace and the job replaces only the value's text; a duplicate already raised `appears 2 times`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_sky_job.py` (edit 1 of 5), replace:

```python
import unittest
from datetime import datetime, timedelta, timezone
```

with:

```python
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
```

In `tests/test_sky_job.py` (edit 2 of 5), add these methods to `SkyJobTest`, after `test_already_showing_tonight_writes_only_the_stamp` (before `assert_failed`):

```python
    def test_windows_line_endings_survive(self):
        crlf = WT_TEXT.replace("\n", "\r\n")
        self.settings.write_bytes(crlf.encode("utf-8"))
        self.run_job()
        self.assertEqual(self.settings.read_bytes(),
                         crlf.replace("moonlit-candle-sky-1.png", "moonlit-candle-sky-4.png").encode("utf-8"))

    def test_the_stamp_is_written_before_the_lock_is_released(self):
        # a shell opening right after the job must see the new stamp, or it starts the job again
        stamp, real, seen = self.cache / sky.STAMP, sky._locked, []

        @contextmanager
        def locked(path):
            with real(path):
                yield
                seen.append(stamp.read_text(encoding="utf-8") if stamp.exists() else None)

        for case, image in (("moved", "sky-1.png"), ("already showing tonight", "sky-4.png")):
            with self.subTest(case):
                stamp.unlink(missing_ok=True)
                self.settings.write_text(WT_TEXT.replace("sky-1.png", image), encoding="utf-8")
                with mock.patch.object(sky, "_locked", locked):
                    self.run_job()
                self.assertEqual(seen.pop(), "4\n")
```

In `tests/test_sky_job.py` (edit 3 of 5), add after `test_a_malformed_config_is_reported_as_such`:

```python
    def test_a_config_that_is_not_an_object_is_reported_as_such(self):
        (self.home / sky.CONFIG).write_text("[]", encoding="utf-8")
        self.run_job()
        self.assert_failed(f"{sky.CONFIG} is not usable: it must be a JSON object")
```

In `tests/test_sky_job.py` (edit 4 of 5), add after `test_a_missing_profile`:

```python
    def test_a_value_that_appears_twice_is_not_rewritten(self):
        text = WT_TEXT.replace('"hidden": true,', '"backgroundImage": "ms-appdata:///local/moonlit-candle-sky-1.png",\n'
                                                  '                "hidden": true,')
        self.settings.write_text(text, encoding="utf-8")
        self.run_job()
        self.assert_failed("appears 2 times", text)
```

(Edit 5 of 5 is none: the other tests stay as they are.)

- [ ] **Step 2: Run them and watch them fail**

Run: `/usr/bin/python3 -m unittest tests.test_sky_job` (and the same with the 3.10 interpreter)
Expected (real output from the prototype, 3.12; `test_windows_line_endings_survive` and `test_a_value_that_appears_twice_is_not_rewritten` pass, they pin existing behaviour):
```
FAIL: test_a_config_that_is_not_an_object_is_reported_as_such (tests.test_sky_job.SkyJobTest.test_a_config_that_is_not_an_object_is_reported_as_such)
AssertionError: '.claude/witchy/ritual-config.json is not usable: it must be a JSON object' not found in "2026-10-26T08:00:00 sky: 'list' object has no attribute 'get'"
FAIL: test_the_stamp_is_written_before_the_lock_is_released (tests.test_sky_job.SkyJobTest.test_the_stamp_is_written_before_the_lock_is_released) [moved]
AssertionError: None != '4\n'
FAIL: test_the_stamp_is_written_before_the_lock_is_released (tests.test_sky_job.SkyJobTest.test_the_stamp_is_written_before_the_lock_is_released) [already showing tonight]
AssertionError: None != '4\n'
Ran 17 tests in 0.270s
FAILED (failures=3)
```

- [ ] **Step 3: Implement**

In `witchy/ritual/sky.py` (edit 1 of 2), replace the function `update` with:

```python
def update(config: object, lock: Path, stamp: Path, target: int) -> bool:
    """Set the profile's backgroundImage to sky image ``target``; False when it already shows it.

    Either way ``stamp`` gets ``target`` before the lock is released, so the next shell sees the new bin.
    """
    if not isinstance(config, dict):
        raise SkyError(f"{CONFIG} is not usable: it must be a JSON object")
    settings, guid, sky = config.get("settings"), config.get("profile_guid"), config.get("sky")
    if not (isinstance(settings, str) and isinstance(guid, str) and isinstance(sky, list) and len(sky) == moon.BINS
            and all(isinstance(image, str) for image in sky)):
        raise SkyError(f"{CONFIG} is not usable: sky must list {moon.BINS} images")
    settings = Path(settings)
    with _locked(lock):
        raw = settings.read_bytes()
        try:
            text = raw.decode("utf-8")
            data = json.loads(text)
        except ValueError as exc:
            raise SkyError(f"{settings} is not plain JSON ({exc})") from exc
        profile = _profile(data, guid)
        if profile is None:
            raise SkyError(f"profile {guid} not found in {settings}")
        current = profile.get(KEY)
        if current not in sky:
            raise SkyError(f"{KEY} was changed by hand ({current!r}); leaving it")
        wanted = sky[target]
        if current != wanted:
            matches = list(re.finditer(rf'("{KEY}"\s*:\s*){re.escape(json.dumps(current))}', text))
            if len(matches) != 1:
                raise SkyError(f"{KEY} {current!r} appears {len(matches)} times in {settings}")
            match = matches[0]
            new_text = text[:match.start()] + match.group(1) + json.dumps(wanted) + text[match.end():]
            profile[KEY] = wanted
            if json.loads(new_text) != data:
                raise SkyError(f"rewriting {KEY} would change more than that value")
            if settings.read_bytes() != raw:
                raise SkyError(f"{settings} changed while the sky job ran")
            _write_atomic(settings, new_text.encode("utf-8"))
        stamp.write_text(f"{target}\n", encoding="utf-8")
    return current != wanted
```

In `witchy/ritual/sky.py` (edit 2 of 2), in `run`, replace:

```python
        target = moon.phase_bin(now)
        update(config, cache / LOCK, target)
        (cache / STAMP).write_text(f"{target}\n", encoding="utf-8")
```

with:

```python
        update(config, cache / LOCK, cache / STAMP, moon.phase_bin(now))
```

In `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (edit 1 of 2), section 4.5, replace:

```markdown
Otherwise it sets the new value, re-checks the file hash, writes atomically and updates `sky-bin`.
```

with:

```markdown
Otherwise it sets the new value, re-checks the file hash, writes atomically and updates `sky-bin` before it releases the lock.
```

In `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (edit 2 of 2), section 4.5, replace:

```markdown
When the profile already shows tonight's image it only writes `sky-bin`.
```

with:

```markdown
When the profile already shows tonight's image it only writes `sky-bin`, also under the lock.
```

- [ ] **Step 4: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 555 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add witchy/ritual/sky.py tests/test_sky_job.py docs/superpowers/specs/2026-10-02-shell-ritual-design.md
git commit -m "fix: the sky job writes sky-bin under the lock and names a config that is not a JSON object

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Astronomy and layout guards (tests only)

**Items:**
- C1: no test that a time zone moves a season date: the September equinox of 2026 (00:05 UTC on the 23rd) is Mabon on the 22nd at UTC−5.
- C2: the published-minute tests (120 s) cannot catch small coefficient typos; Meeus's worked examples should be checked to about 1 s. **Already covered at `0df90e9`; nothing added** (see Decisions).
- C12: `layout.side_by_side` misaligns if an art row is wider than `art.WIDTH`; guard the invariant for all 8 phases.

**Files:**
- Test: `tests/test_wheel.py`, `tests/test_art.py`

**Interfaces:**
- Consumes: `wheel.sabbat_dates(year, tz) -> dict[str, date]` (key `"Mabon"`), `art.picture(fraction, day)`, `art.WIDTH`, `layout.cell_width(text)`
- Produces: nothing new

**Decisions:**
1. **No RED: both new tests pin existing behaviour.** The art guard was checked to fail when a wide glyph is forced in (patching `art.STAR_GLYPHS` to `("🌕",)` gives `29 not less than or equal to 28`). The Mabon test would fail if `sabbat_dates` ignored its `tz`. The code computes the 2026 September equinox at 00:05:31 UTC, so 19:05 on the 22nd at UTC−5.
2. **C2 needs no change.** `tests/test_moon.py::LunationTest.test_meeus_example_49a` (new moon of 1977 Feb, k = −283, JDE 2443192.65118) and `tests/test_wheel.py::SeasonTest.test_meeus_example_27a` (June solstice 1962, JDE 2437837.39245) already exist with `delta=1` s. Both sides go through `julian_to_utc` with the same `DELTA_T`, so the comparison is in TD, exact to the JDE, and ΔT plays no part. The residuals are 0.23 s and 0.15 s; Meeus prints 5 decimals (0.86 s), so 1 s is the tightest honest tolerance. I know of no other worked example in ch. 27 or 49 for the cases the code computes (new moon, full moon, the four seasons) whose value I am sure of, so I added none. The published-minute tests stay at 120 s. Measured errors there: seasons 2024–2030 at most 56 s, moons at most 28 s; the moon test could go down to 60 s if wanted, but that is a separate decision, so I left it.

- [ ] **Step 1: Write the tests**

In `tests/test_wheel.py`, add to `SabbatTest`, after `test_the_day_and_the_countdown`:

```python
    def test_the_time_zone_can_move_a_season_to_the_day_before(self):
        # The September equinox of 2026 is 00:05 UTC on the 23rd: still the 22nd five hours west of Greenwich.
        self.assertEqual(wheel.sabbat_dates(2026, timezone.utc)["Mabon"], date(2026, 9, 23))
        self.assertEqual(wheel.sabbat_dates(2026, timezone(timedelta(hours=-5)))["Mabon"], date(2026, 9, 22))
```

In `tests/test_art.py` (edit 1 of 2), replace:

```python
from witchy.ritual import art
```

with:

```python
from witchy.ritual import art, layout
```

In `tests/test_art.py` (edit 2 of 2), add to `PictureTest`, after `test_the_disc_sits_between_the_margins`:

```python
    def test_no_row_is_wider_than_the_art_column(self):
        # layout.side_by_side pads each art row to art.WIDTH; a wider row would push the info column right
        for phase in range(8):
            for offset in range(31):  # the stars move daily
                day = date(2026, 10, 1) + timedelta(days=offset)
                for row in art.picture(phase / 8, day):
                    row = "".join(char for char, _ in row)
                    self.assertLessEqual(layout.cell_width(row), art.WIDTH, (phase, day, row))
```

- [ ] **Step 2: Run them (no RED: they pin existing behaviour)**

Run: `/usr/bin/python3 -m unittest tests.test_art tests.test_wheel tests.test_moon` (and the same with the 3.10 interpreter)
Expected (real output from the prototype):
```
Ran 20 tests in …s

OK
```

- [ ] **Step 3: Implement**

Nothing: no source change.

- [ ] **Step 4: Run the whole suite on both interpreters**

Run:
```bash
/usr/bin/python3 -m unittest discover -s tests -t .
/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .
python3 -m witchy validate
```
Expected: `Ran 557 tests … OK` on both, and `Moonlit Candle: all checks passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_art.py tests/test_wheel.py
git commit -m "test: a time zone moves a season date, and no moon art row is wider than its column

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 16: Read-only check against the real install

**Items:** Review Focus 5. The state the code on `main` wrote on the real machine must load and plan cleanly with this branch, and nothing may be written.

**Files:** none changed.

**Interfaces:**
- Consumes: the whole branch.
- Produces: nothing new.

This task runs witchy against the user's real HOME, which the Global Constraints allow only for `doctor` and `--dry-run`. Run exactly the commands below and nothing else. No `install`, `uninstall` or `mood` without `--dry-run`, and no `ritual`.

- [ ] **Step 1: Take a snapshot of every place witchy touches**

```bash
snap() { find ~/.cache/witchy ~/.claude/witchy ~/.claude/state* ~/.claude/settings.json ~/.config/fish /mnt/c/Users/manue/AppData/Local/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState -maxdepth 3 -printf '%p %T@ %s\n' 2>/dev/null | sort | sha256sum; }
before=$(snap)
```

- [ ] **Step 2: Run doctor and both dry runs from the repo root**

```bash
python3 -m witchy doctor; echo "exit=$?"
python3 -m witchy install --dry-run > /tmp/witchy-install-dry.txt 2>&1; echo "exit=$?"; tail -3 /tmp/witchy-install-dry.txt
python3 -m witchy uninstall --dry-run > /tmp/witchy-uninstall-dry.txt 2>&1; echo "exit=$?"; tail -4 /tmp/witchy-uninstall-dry.txt
```

Expected (seen on the merged prototype):
- `doctor`: ten `✓` lines (claude ×2, font, windows-terminal ×3, fish ×4, the last being `no greeting or sky errors in the last 7 days`), then `exit=0`.
- `install --dry-run`: `exit=0`, ending `Dry run: nothing was written.`. Each component's actions now follow its own diff (Task 1).
- `uninstall --dry-run`: `exit=0`, with `fish: restore 31 Tide variables`, `fish: refresh Tide's prompt items` and the new `fish: remove /home/eimi/.claude/witchy/ritual if empty` (Task 1). It ends `Dry run: nothing was written.`.

A `✗`, a traceback or a non-zero exit is a failure. Stop and report it verbatim.

- [ ] **Step 3: Prove nothing was written**

```bash
after=$(snap); [ "$before" = "$after" ] && echo "NOTHING CHANGED on disk" || echo "FILES CHANGED"
rm -f /tmp/witchy-install-dry.txt /tmp/witchy-uninstall-dry.txt
```

Expected: `NOTHING CHANGED on disk`.

- [ ] **Step 4: Tell the user, don't act**

The installed copy on the real machine still runs `main`'s code. The greeting package fixes (Tasks 12–14), the fish files and the new state handling only reach it through a real `install`. Report this to the user and ask whether to reinstall. Do not run it.

No commit: this task changes no files.
