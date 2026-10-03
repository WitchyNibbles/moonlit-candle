# Plan B: Windows (lookup fix, font, profile keys, sky) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Ubuntu tab in Windows Terminal the full Moonlit Candle look (Maple Mono NF, box cursor, 🌙 tab, a starfield with the real moon phase) and make the installer find Windows Terminal on this machine, on top of the Plan A component architecture.

**Architecture:** A new `font` component (between `claude` and `windows-terminal`) downloads a pinned Maple Mono NF release and registers it per user. The `windows-terminal` component grows profile keys, eight pre-rendered sky PNGs and `~/.claude/witchy/ritual-config.json`, guarded by a shared `wt.lock`. A small pure `witchy/ritual/moon.py` and `witchy/sky_render.py` supply the phase bin and the images. `witchy/windows.py` finds the Windows profile folder from `%USERPROFILE%`.

**Tech Stack:** Python 3.10+ standard library only (`zlib`, `struct`, `zipfile`, `urllib.request`, `fcntl`, `unittest`). Windows tools called from WSL: `cmd.exe`, `reg.exe`.

**Spec:** `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (revision 2). This plan covers spec sections 4.1–4.4 and 13 steps 4–6. The sky job (4.5) is part of Plan C's greeting package. Plan A (`docs/superpowers/plans/2026-10-02-plan-a-foundation.md`) is done; this plan is written against the code at `3c83fd0`.

## Global Constraints

- Python 3.10 or newer, standard library only; every test passes on `/usr/bin/python3` (3.12) and on Python 3.10 (`/home/eimi/.pyenv/versions/3.10.0/bin/python3` on this machine; `/usr/bin/python3.10` does not exist here).
- Test command: `/usr/bin/python3 -m unittest discover -s tests -t .` (run from the repo root), and the same with the 3.10 interpreter.
- No test touches the real `~/.claude`, Windows Terminal, `cmd.exe`, `reg.exe`, the registry or the network: tests use a temporary `HOME`, `wt_settings` or a temporary `mount_root`, a fake `run` (`tests/fakes.py`), a fake `fetch`, and `lock_path` inside the temp dir.
- Every subprocess gets list arguments, never a shell string; values come from constants (spec 10.2).
- The font download is HTTPS with default certificate checks, pinned to release `v7.9` of `MapleMono-NF.zip` with SHA-256 `59098b87c895d871635d37680e88000ae2b2b25b55428195b228ec589e35fb89`; only the four named members are extracted, each capped at 20 MB (spec 10.1).
- Installer messages are English and neutral in tone. Docstrings and comments are English.
- Exit codes for `install`/`uninstall`: `0` all ok, `1` nothing changed, `2` done with warnings.
- Every file witchy rewrites is backed up first and written atomically (`jsonio.write_atomic_bytes`). A settings file that is not strict JSON is never rewritten.
- Component order: `claude`, `font`, `windows-terminal` (Plan C appends `fish`). Uninstall runs in reverse order and never removes the font.
- Writers of Windows Terminal's `settings.json` hold `~/.cache/witchy/wt.lock` and re-check the file's hash before replacing it (spec 4.2, 10.4).
- Commit messages end with the `Co-Authored-By:` trailer of the model that wrote the commit (Plan A ruling R6).

## Decisions made while planning

1. **Spike result (spec 4.4 gate): passed.** On 2026-10-03 an atomic replace of the real `settings.json` that only changed the Ubuntu profile's `backgroundImage` path was applied to an open tab without a restart. So this plan ships the eight phase images; Plan C ships the sky job.
2. **`settings.json` lookup order:** `--wt-settings`; the path recorded in state, if it still exists; `%USERPROFILE%` mapped to `/mnt/<drive>/…`; `C:\Users\%USERNAME%`. On this machine `%USERNAME%` is not the profile folder name, which made Plan A's real dry run skip Windows Terminal.
3. **When the `font` profile key is set:** the `font` component is recorded in state, or it is planned in this run and its apply returns `ok`. The `windows-terminal` component never queries the registry itself.
4. **Font failures** (download, checksum, copy, `reg.exe`) raise `ComponentFailed`, so the run records `failed: <reason>` for `font` (Plan A's runner semantics) and exits 2. Uninstall keeps the font (spec 2, Out).
5. **The installer holds `wt.lock` only while it writes Windows Terminal files**, through a new `Plan.lock`; the runner re-checks each plan's files under that lock and turns a mismatch into that component's failure instead of aborting the whole run.
6. **The sky images are written to Windows Terminal's `LocalState` folder** (the parent of `settings.json`), which `ms-appdata:///local/` names.
7. **From the Plan A final review, folded in here:** an unknown variant in state aborts with a fix; the lock falls back to the temp dir when `XDG_RUNTIME_DIR` is missing; `mood <variant>` reinstalls only installed components; dry runs summarise binary files; `apply_keys` leaves a key that already holds an equal value alone (no key-reorder rewrite). Deferred to Plan C: commands in `Plan` for uninstall (fish restore).

## Review Focus

1. **A renamed Windows account** (`%USERNAME%` ≠ profile folder) must still find `settings.json` → Task 2 `test_profile_folder_wins_over_a_renamed_account`.
2. **An offline or failed font install** must leave the profile's current `font` untouched → Task 5 `test_failed_font_install_leaves_the_font_alone`.
3. **A `backgroundImage` moved to another phase by the sky job** must still count as installed for doctor and uninstall → Task 6 `test_moved_sky_still_counts_as_installed`.
4. **A `settings.json` rewritten by another writer between planning and writing** must fail only that component and never be overwritten → Task 6 `test_a_file_changed_after_planning_fails_only_that_component`.
5. **A reinstall over a Plan A entry** (no `profile_keys`, no `files`) must add the new keys and keep the first recorded scheme → Task 5 `test_reinstall_over_a_plan_a_entry_adds_keys_and_keeps_the_first_scheme`.

---

## File structure

| File | Status | Responsibility |
| :- | :- | :- |
| `witchy/records.py` | modify | generic `apply_keys`, `restore_keys`, `is_installed` |
| `witchy/claude_settings.py` | modify | re-export the generic key helpers |
| `witchy/context.py` | modify | lock fallback; `mount_root`, `fetch`, `cache_dir`, `planned`, `entries`, `results`, `now`, `sky_size` |
| `witchy/runner.py` | modify | unknown variant, mood scope, dry-run actions, shared plan state, plan locks and re-check |
| `witchy/components/base.py` | modify | binary-aware `show_changes`; `Plan.actions`, `Plan.lock`; `file_lock` |
| `witchy/windows.py` | create | `echo`, `to_wsl`, `user_home` |
| `witchy/wt.py` | modify | lookup order, profile lookup (4.1), profile keys, sky names |
| `witchy/fonts.py` | create | pinned release, download, safe extraction, TTF full name, registry |
| `witchy/components/font.py` | create | the `font` component |
| `witchy/components/__init__.py` | modify | `claude`, `font`, `windows-terminal` |
| `witchy/ritual/__init__.py`, `witchy/ritual/moon.py` | create | phase age, bin, illumination (Plan C extends the package) |
| `witchy/sky_render.py` | create | deterministic PNG sky and its cache |
| `witchy/palette.py` | modify | `SKY`, `WT_PROFILE`; `Variant.sky`, `Variant.wt_profile` |
| `witchy/validate.py` | modify | sky colours must be `#RRGGBB` |
| `witchy/components/windows_terminal.py` | rewrite (Tasks 5, 6) | scheme, profile keys, sky images, ritual config |
| `README.md`, spec | modify | font, new doctor lines, recorded decisions |
| `tests/fakes.py` | create | fake Windows `run`, fake TTF and zip |
| `tests/test_base.py`, `tests/test_windows.py`, `tests/test_fonts.py`, `tests/test_components_font.py`, `tests/test_moon.py`, `tests/test_sky_render.py` | create | new tests |
| `tests/test_claude_settings.py`, `tests/test_runner.py`, `tests/test_wt.py`, `tests/test_components_wt.py`, `tests/test_install.py`, `tests/test_cli.py`, `tests/test_palette.py`, `tests/test_validate.py` | modify | new cases and updated helpers |

---

### Task 1: Hardening from the Plan A review

**Files:**
- Modify: `witchy/records.py`, `witchy/claude_settings.py`, `witchy/context.py`, `witchy/runner.py`, `witchy/components/base.py`
- Create: `tests/test_base.py`
- Modify: `tests/test_claude_settings.py`, `tests/test_runner.py` (append)

**Interfaces:**
- Consumes: Plan A's `records.snapshot/put_back`, `runner.install/_install/mood`, `Context.lock_file`, `base.show_changes`.
- Produces:
  - `records.is_installed(container: dict, key: str, record: dict, also: Iterable = ()) -> bool`
  - `records.apply_keys(data: dict, desired: Mapping, recorded: dict | None) -> tuple[dict, dict]` (moved from `claude_settings`, now leaves equal values in place)
  - `records.restore_keys(data: dict, records: dict, also_installed: Mapping[str, Iterable] | None = None) -> tuple[dict, list[str]]`
  - `claude_settings.apply_keys` / `claude_settings.restore_keys` stay importable (re-exports).
  - `show_changes` prints `create PATH (binary, N bytes)` and `update PATH (binary, A → B bytes)` for non-text files.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_claude_settings.py` (change the import line to `from witchy import claude_settings, records`):

```python
class EqualValueTest(unittest.TestCase):
    def setUp(self):
        self.desired = claude_settings.desired_keys(Path("/home/u"), "/usr/bin/python3", ["Brewing"])

    def test_an_equal_value_keeps_its_member_order(self):
        tips = self.desired["spinnerTipsOverride"]
        reordered = dict(reversed(list(tips.items())))
        result, recs = claude_settings.apply_keys({"spinnerTipsOverride": reordered}, self.desired, None)
        self.assertEqual(list(result["spinnerTipsOverride"]), list(reordered))
        self.assertEqual(recs["spinnerTipsOverride"]["previous"], {"value": reordered})

    def test_restore_accepts_other_values_that_count_as_installed(self):
        recs = {"backgroundImage": {"previous": {"absent": True}, "installed": "sky-1.png"}}
        restored, warnings = records.restore_keys({"backgroundImage": "sky-3.png"}, recs,
                                                  also_installed={"backgroundImage": ("sky-3.png",)})
        self.assertEqual((restored, warnings), ({}, []))

    def test_is_installed(self):
        record = {"previous": {"absent": True}, "installed": "a"}
        self.assertTrue(records.is_installed({"k": "a"}, "k", record))
        self.assertTrue(records.is_installed({"k": "b"}, "k", record, also=("b",)))
        self.assertFalse(records.is_installed({}, "k", record))
```

Append to `tests/test_runner.py`:

```python
class HardeningTest(RunnerTestCase):
    def save_state(self, variant, components):
        state.save(self.home / ".claude" / "witchy" / "state.json",
                   dict(state.empty(variant), components=components))

    def test_unknown_variant_in_state_aborts_install(self):
        self.save_state("dawn", {"a": {}})
        self.assertEqual(runner.install(self.ctx(), [Fake("a", self.log)]), 1)
        self.assertIn("unknown variant 'dawn'", self.out.getvalue())
        self.assertIn("python3 -m witchy mood midnight", self.out.getvalue())
        self.assertEqual(self.log, [])

    def test_mood_flags_an_unknown_active_variant(self):
        self.save_state("dawn", {})
        self.assertEqual(runner.mood(self.ctx(), None, [Fake("a", self.log)]), 0)
        self.assertIn("active: dawn (unknown; run: python3 -m witchy mood midnight)", self.out.getvalue())

    def test_mood_midnight_repairs_an_unknown_variant(self):
        self.save_state("dawn", {"a": {"installed": "a"}})
        self.assertEqual(runner.mood(self.ctx(), "midnight", [Fake("a", self.log)]), 0)
        self.assertEqual(self.state()["variant"], "midnight")

    def test_mood_repaints_only_installed_components(self):
        self.write_state({"a": {"installed": "a"}})
        with mock.patch.dict(palette.VARIANTS, {"dawn": palette.VARIANTS["midnight"]}):
            self.assertEqual(runner.mood(self.ctx(), "dawn", [Fake("a", self.log), Fake("b", self.log)]), 0)
        self.assertIn(("apply", "a"), self.log)
        self.assertNotIn(("plan", "b"), self.log)

    def test_missing_runtime_dir_falls_back_to_the_temp_dir(self):
        ctx = Context(home=self.home, env={"XDG_RUNTIME_DIR": str(self.root / "gone" / "run")}, out=io.StringIO())
        self.assertEqual(ctx.lock_file.parent, Path(tempfile.gettempdir()))

    def test_existing_runtime_dir_holds_the_lock(self):
        ctx = Context(home=self.home, env={"XDG_RUNTIME_DIR": str(self.root)}, out=io.StringIO())
        self.assertEqual(ctx.lock_file.parent, self.root)
```

Create `tests/test_base.py`:

```python
import io
import unittest
from pathlib import Path

from witchy.components.base import Change, show_changes

PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


class Ctx:
    def __init__(self):
        self.out = io.StringIO()

    def say(self, message):
        print(message, file=self.out)


class ShowChangesTest(unittest.TestCase):
    def test_binary_files_are_summarised(self):
        ctx = Ctx()
        show_changes(ctx, [Change(Path("/x/new.png"), None, PNG), Change(Path("/x/old.png"), PNG, PNG + b"\x00")])
        self.assertEqual(ctx.out.getvalue().splitlines(),
                         ["create /x/new.png (binary, 16 bytes)", "update /x/old.png (binary, 16 → 17 bytes)"])

    def test_text_files_still_show_a_diff(self):
        ctx = Ctx()
        show_changes(ctx, [Change(Path("/x/a.json"), b'{"a": 1}\n', b'{"a": 2}\n')])
        self.assertIn('+{"a": 2}', ctx.out.getvalue())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_claude_settings tests.test_runner tests.test_base -v`
Expected: FAIL/ERROR — `AttributeError: module 'witchy.records' has no attribute 'restore_keys'`, the variant and lock tests fail on today's behaviour, and the binary test prints `create /x/new.png (1 lines)`.

- [ ] **Step 3: Implement**

Replace `witchy/records.py`:

```python
"""What a key held before witchy set it, how to set it, and how to put it back."""
from __future__ import annotations

import copy
from typing import Any, Iterable, Mapping


def snapshot(container: dict, key: str) -> dict:
    return {"value": copy.deepcopy(container[key])} if key in container else {"absent": True}


def put_back(container: dict, key: str, previous: dict) -> None:
    if previous.get("absent"):
        container.pop(key, None)
    else:
        container[key] = copy.deepcopy(previous["value"])


def is_installed(container: dict, key: str, record: dict, also: Iterable[Any] = ()) -> bool:
    """Whether ``key`` still holds what witchy installed, or one of ``also`` (other values that count as witchy's)."""
    current = snapshot(container, key)
    return any(current == {"value": value} for value in (record["installed"], *also))


def apply_keys(data: dict, desired: Mapping[str, Any], recorded: dict | None) -> tuple[dict, dict]:
    """Set every desired key. On a reinstall the first-ever previous value is kept, not witchy's own.

    A key that already holds an equal value is left as it is, so a file is never rewritten just to
    reorder an object's members.
    """
    result = copy.deepcopy(data)
    records = {}
    for key, value in desired.items():
        earlier = (recorded or {}).get(key)
        previous = earlier["previous"] if earlier else snapshot(result, key)
        records[key] = {"previous": previous, "installed": copy.deepcopy(value)}
        if snapshot(result, key) != {"value": value}:
            result[key] = copy.deepcopy(value)
    return result, records


def restore_keys(data: dict, records: dict,
                 also_installed: Mapping[str, Iterable[Any]] | None = None) -> tuple[dict, list[str]]:
    """Give back each key's previous value, unless it no longer holds what witchy installed."""
    result = copy.deepcopy(data)
    warnings = []
    for key, record in records.items():
        if snapshot(result, key) == record["previous"]:
            continue  # already given back, for example by an uninstall that stopped part-way
        if not is_installed(result, key, record, (also_installed or {}).get(key, ())):
            warnings.append(f"{key} was changed after install; leaving it as it is.")
            continue
        put_back(result, key, record["previous"])
    return result, warnings
```

In `witchy/claude_settings.py`: delete the bodies of `apply_keys` and `restore_keys`, delete the now-unused imports (`copy`, and `put_back, snapshot` from `.records`), and add below the remaining imports:

```python
from .records import apply_keys, restore_keys  # noqa: F401  (part of this module's interface)
```

In `witchy/context.py`, replace the body of `lock_file` with:

```python
        # Outside HOME on purpose: uninstall must leave nothing behind in ~/.claude.
        if self.lock_path is not None:
            return self.lock_path
        runtime = self.env.get("XDG_RUNTIME_DIR")
        base = runtime if runtime and Path(runtime).is_dir() else tempfile.gettempdir()
        return Path(base) / f"witchy-{os.getuid()}.lock"
```

In `witchy/runner.py`, `_install`: directly after the line that sets `ctx.variant`, add:

```python
    if ctx.variant not in palette.VARIANTS:
        raise Abort(f"{ctx.state_path} names the unknown variant {ctx.variant!r}; "
                    f"run: python3 -m witchy mood {palette.DEFAULT_VARIANT}")
```

In `witchy/runner.py`, `mood`: replace the `if variant is None:` block and the two lines before `return install(ctx, components)` so the function reads:

```python
    active = (state or {}).get("variant") or palette.DEFAULT_VARIANT
    available = ", ".join(palette.VARIANTS)
    if variant is None:
        known = "" if active in palette.VARIANTS else f" (unknown; run: python3 -m witchy mood {palette.DEFAULT_VARIANT})"
        ctx.say(f"active: {active}{known}")
        ctx.say(f"available: {available}")
        return 0
    if variant not in palette.VARIANTS:
        ctx.say(f"unknown variant {variant!r}; available: {available}")
        return 1
    if state is not None and variant == active:
        ctx.say(f"already {variant}")
        return 0
    if state is not None and state["components"] and not ctx.only:
        # A variant switch repaints what is installed; it never brings back a component the user removed.
        ctx.only = tuple(state["components"])
    ctx.variant = variant
    return install(ctx, components)
```

In `witchy/components/base.py`, add above `show_changes` and replace `show_changes`:

```python
def _binary(data: bytes | None) -> bool:
    if data is None:
        return False
    if b"\0" in data:
        return True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def show_changes(ctx: Any, changes: list[Change]) -> None:
    for change in changes:
        if change.before == change.after:
            continue
        binary = _binary(change.before) or _binary(change.after)
        if change.before is None:
            detail = f"binary, {len(change.after)} bytes" if binary else f"{len(change.after.splitlines())} lines"
            ctx.say(f"create {change.path} ({detail})")
        elif change.after is None:
            ctx.say(f"remove {change.path}")
        elif binary:
            ctx.say(f"update {change.path} (binary, {len(change.before)} → {len(change.after)} bytes)")
        else:
            before = change.before.decode("utf-8", "replace").splitlines(keepends=True)
            after = change.after.decode("utf-8", "replace").splitlines(keepends=True)
            ctx.out.writelines(difflib.unified_diff(before, after, f"{change.path} (now)", f"{change.path} (after)"))
            ctx.say("")
```

- [ ] **Step 4: Run the whole suite on both Pythons**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .` and `/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .`
Expected: OK on both (200 Plan A tests + 11 new).

- [ ] **Step 5: Commit**

```bash
git add witchy/records.py witchy/claude_settings.py witchy/context.py witchy/runner.py witchy/components/base.py tests/test_base.py tests/test_claude_settings.py tests/test_runner.py
git commit -m "fix: harden variant, lock, mood, dry-run and key-rewrite edge cases

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 2: Find Windows Terminal on this machine (settings file and profile)

**Files:**
- Create: `witchy/windows.py`, `tests/fakes.py`, `tests/test_windows.py`
- Modify: `witchy/wt.py`, `witchy/context.py`, `witchy/components/windows_terminal.py`
- Modify: `tests/test_wt.py`, `tests/test_components_wt.py` (append)

**Interfaces:**
- Consumes: Plan A `wt.locate_settings/find_profile`, `WindowsTerminalComponent.plan`.
- Produces:
  - `windows.MOUNT_ROOT = Path("/mnt")`; `windows.WindowsHome(windows: str, wsl: Path)` (frozen dataclass)
  - `windows.echo(variable: str, run) -> str | None`, `windows.to_wsl(path: str, mount_root: Path = MOUNT_ROOT) -> Path | None`, `windows.user_home(run, mount_root: Path = MOUNT_ROOT) -> WindowsHome | None`
  - `wt.settings_path_in(user_home: Path) -> Path`; `wt.locate_settings(explicit, run=subprocess.run, users_root=USERS_ROOT, recorded: str | None = None, mount_root: Path = windows.MOUNT_ROOT) -> Path | None`
  - `wt.find_profile` step 2 matches visible profiles whose `source` is `Microsoft.WSL`, `Windows.Terminal.Wsl` or starts with `CanonicalGroupLimited.`.
  - `Context.mount_root: Path` (default `windows.MOUNT_ROOT`)
  - `tests/fakes.py`: `fake_windows(echo=None, reg_query="", reg_add_code=0, calls=None)`.

- [ ] **Step 1: Create the test fake**

Create `tests/fakes.py`:

```python
"""Stand-ins for the Windows side, so no test runs cmd.exe or reg.exe."""
import subprocess


def fake_windows(echo=None, reg_query="", reg_add_code=0, calls=None):
    """A ``run`` that answers like a Windows host.

    ``cmd.exe /c echo %VAR%`` prints ``echo[VAR]`` (cmd.exe prints ``%VAR%`` back when a variable is unset),
    ``reg.exe query`` prints ``reg_query`` and ``reg.exe add`` exits with ``reg_add_code``. Any other command
    fails the test. Every call is appended to ``calls`` when it is a list.
    """
    def run(args, **kwargs):
        args = list(args)
        if calls is not None:
            calls.append(args)
        if args[:2] == ["cmd.exe", "/c"] and args[2].startswith("echo %"):
            variable = args[2][len("echo %"):-1]
            stdout = (echo or {}).get(variable, f"%{variable}%\r\n")
            return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")
        if args[:2] == ["reg.exe", "query"]:
            return subprocess.CompletedProcess(args, 0, stdout=reg_query, stderr="")
        if args[:2] == ["reg.exe", "add"]:
            return subprocess.CompletedProcess(args, reg_add_code, stdout="", stderr="")
        raise AssertionError(f"unexpected command in a test: {args}")
    return run
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_windows.py`:

```python
import tempfile
import unittest
from pathlib import Path

from tests.fakes import fake_windows
from witchy import windows


class ToWslTest(unittest.TestCase):
    def test_drive_paths(self):
        self.assertEqual(windows.to_wsl("C:\\Users\\manue"), Path("/mnt/c/Users/manue"))
        self.assertEqual(windows.to_wsl("D:\\Data\\x\\", Path("/m")), Path("/m/d/Data/x"))

    def test_other_paths_are_not_mapped(self):
        self.assertIsNone(windows.to_wsl("arial.ttf"))
        self.assertIsNone(windows.to_wsl("\\\\server\\share\\x"))


class UserHomeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.mnt = Path(tmp.name) / "mnt"

    def test_profile_folder_from_userprofile(self):
        (self.mnt / "c" / "Users" / "manue").mkdir(parents=True)
        run = fake_windows(echo={"USERPROFILE": "C:\\Users\\manue\r\n"})
        self.assertEqual(windows.user_home(run, self.mnt),
                         windows.WindowsHome("C:\\Users\\manue", self.mnt / "c" / "Users" / "manue"))

    def test_missing_folder_or_variable_is_none(self):
        self.assertIsNone(windows.user_home(fake_windows(echo={"USERPROFILE": "C:\\Users\\gone\r\n"}), self.mnt))
        self.assertIsNone(windows.user_home(fake_windows(), self.mnt))

    def test_no_cmd_exe_is_none(self):
        def missing(args, **kwargs):
            raise FileNotFoundError("cmd.exe")
        self.assertIsNone(windows.user_home(missing, self.mnt))


if __name__ == "__main__":
    unittest.main()
```

Append to `tests/test_wt.py` (add `from tests.fakes import fake_windows` to the imports):

```python
CANONICAL = "{51855cb2-8cce-5362-8f54-464b92b32386}"
HIDDEN = "{2c4de342-38b7-51cf-b940-2309a097f518}"


def store_ubuntu():
    """The two Ubuntu profiles this machine has: a hidden duplicate and the Store distro's own."""
    data = settings()
    data["profiles"]["list"] = [
        {"guid": HIDDEN, "name": "Ubuntu", "source": "Windows.Terminal.Wsl", "hidden": True},
        {"guid": CANONICAL, "name": "Ubuntu", "source": "CanonicalGroupLimited.Ubuntu_79rhkp1fndgsc", "hidden": False},
    ]
    return data


class LookupFixTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.mnt = Path(tmp.name) / "mnt"
        self.settings = wt.settings_path_in(self.mnt / "c" / "Users" / "manue")
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text("{}")

    def test_profile_folder_wins_over_a_renamed_account(self):
        run = fake_windows(echo={"USERPROFILE": "C:\\Users\\manue\r\n", "USERNAME": "Manuel\r\n"})
        found = wt.locate_settings(None, run=run, users_root=self.mnt / "c" / "Users", mount_root=self.mnt)
        self.assertEqual(found, self.settings)

    def test_recorded_path_is_used_without_asking_windows(self):
        calls = []
        found = wt.locate_settings(None, run=fake_windows(calls=calls), recorded=str(self.settings),
                                   mount_root=self.mnt)
        self.assertEqual((found, calls), (self.settings, []))

    def test_stale_recorded_path_falls_back_to_the_profile_folder(self):
        run = fake_windows(echo={"USERPROFILE": "C:\\Users\\manue\r\n"})
        found = wt.locate_settings(None, run=run, recorded=str(self.mnt / "old.json"), mount_root=self.mnt)
        self.assertEqual(found, self.settings)


class StoreProfileTest(unittest.TestCase):
    def test_store_ubuntu_is_found_and_the_hidden_duplicate_ignored(self):
        self.assertEqual(wt.find_profile(store_ubuntu(), {"WSL_DISTRO_NAME": "Ubuntu"}), (CANONICAL, None))

    def test_two_visible_matches_are_ambiguous(self):
        data = store_ubuntu()
        data["profiles"]["list"][0]["hidden"] = False
        self.assertIsNone(wt.find_profile(data, {"WSL_DISTRO_NAME": "Ubuntu"})[0])
```

Append to `tests/test_components_wt.py` inside `WindowsTerminalComponentTest`:

```python
    def test_recorded_settings_path_is_reused_without_cmd_exe(self):
        _, entry = self.install()
        ctx = Context(home=self.root / "home", env={"WT_PROFILE_ID": UBUNTU}, out=io.StringIO(), run=refuse_cmd,
                      variant="midnight")
        plan = self.component.plan(ctx, entry)
        self.assertIsNone(plan.skip)
        self.assertEqual(plan.data["json"].change.path, self.wt)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_windows tests.test_wt tests.test_components_wt -v`
Expected: ERROR `ModuleNotFoundError: No module named 'witchy.windows'`, then failures for `settings_path_in`, the store profile and the recorded path.

- [ ] **Step 4: Implement**

Create `witchy/windows.py`:

```python
"""The Windows side of WSL: environment variables, the user's profile folder, path conversion."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

MOUNT_ROOT = Path("/mnt")
_DRIVE_PATH = re.compile(r"^([A-Za-z]):\\(.*)$")


@dataclass(frozen=True)
class WindowsHome:
    """The current Windows user's profile folder, as Windows and as WSL see it."""

    windows: str
    wsl: Path


def echo(variable: str, run: Callable[..., Any] = subprocess.run) -> str | None:
    """The value of a Windows environment variable, or None."""
    try:
        # cwd=/mnt/c keeps cmd.exe from warning about a UNC working directory. cmd.exe answers in the OEM code
        # page, so a name like "José" is not valid UTF-8: replace instead of raising.
        done = run(["cmd.exe", "/c", f"echo %{variable}%"], capture_output=True, text=True, errors="replace",
                   timeout=5, cwd="/mnt/c")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    value = (done.stdout or "").strip()
    return value if done.returncode == 0 and value and "%" not in value else None


def to_wsl(path: str, mount_root: Path = MOUNT_ROOT) -> Path | None:
    """``C:\\Users\\x`` as ``/mnt/c/Users/x``; None for anything that is not a drive path."""
    match = _DRIVE_PATH.match(path.strip())
    if not match:
        return None
    parts = [part for part in match.group(2).split("\\") if part]
    return mount_root.joinpath(match.group(1).lower(), *parts)


def user_home(run: Callable[..., Any] = subprocess.run, mount_root: Path = MOUNT_ROOT) -> WindowsHome | None:
    """``%USERPROFILE%``. It is the real folder name, which ``%USERNAME%`` is not after an account rename."""
    value = echo("USERPROFILE", run)
    path = to_wsl(value, mount_root) if value else None
    if path is None or not path.is_dir():
        return None
    return WindowsHome(value.rstrip("\\"), path)
```

In `witchy/wt.py`:

1. Add `from . import windows` below `from .records import put_back, snapshot`.
2. Replace `windows_username`, `settings_path_for` and `locate_settings` with:

```python
def windows_username(run: Callable[..., Any] = subprocess.run) -> str | None:
    """The Windows account name of this WSL session. Several users can have Windows Terminal installed."""
    return windows.echo("USERNAME", run)


def settings_path_in(user_home: Path) -> Path:
    return user_home / "AppData" / "Local" / "Packages" / PACKAGE / "LocalState" / "settings.json"


def settings_path_for(user: str, users_root: Path = USERS_ROOT) -> Path:
    return settings_path_in(users_root / user)


def locate_settings(explicit: Path | None, run: Callable[..., Any] = subprocess.run,
                    users_root: Path = USERS_ROOT, recorded: str | None = None,
                    mount_root: Path = windows.MOUNT_ROOT) -> Path | None:
    """--wt-settings, else the path recorded at the last install, else the %USERPROFILE% folder,
    else C:\\Users\\%USERNAME% (the account name and the folder name differ after a rename)."""
    if explicit is not None:
        return explicit if explicit.is_file() else None
    if recorded and Path(recorded).is_file():
        return Path(recorded)
    home = windows.user_home(run, mount_root)
    if home is not None and settings_path_in(home.wsl).is_file():
        return settings_path_in(home.wsl)
    user = windows_username(run)
    if not user:
        return None
    path = settings_path_for(user, users_root)
    return path if path.is_file() else None
```

3. Add below `_profile`:

```python
WSL_SOURCES = ("Microsoft.WSL", "Windows.Terminal.Wsl")


def _is_wsl(profile: dict) -> bool:
    source = str(profile.get("source", ""))
    return source in WSL_SOURCES or source.startswith("CanonicalGroupLimited.")
```

4. In `find_profile`, replace the `matches = ...` statement with:

```python
    matches = [p for p in profiles if isinstance(p, dict) and distro and p.get("hidden") is not True
               and _is_wsl(p) and p.get("name") == distro]
```

5. Update `find_profile`'s docstring to: `"""The profile to theme: WT_PROFILE_ID if it exists, else the one visible WSL profile named after the distro."""`

In `witchy/context.py`: add `from . import build, windows` (replacing `from . import build`) and the field `mount_root: Path = field(default_factory=lambda: windows.MOUNT_ROOT)` after `outputs`.

In `witchy/components/windows_terminal.py`, `plan`: replace the `path = wt.locate_settings(...)` line with:

```python
        path = wt.locate_settings(ctx.wt_settings, run=ctx.run, recorded=entry["path"] if entry else None,
                                  mount_root=ctx.mount_root)
```

- [ ] **Step 5: Run the whole suite on both Pythons**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .` and `/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .`
Expected: OK on both.

- [ ] **Step 6: Commit**

```bash
git add witchy/windows.py witchy/wt.py witchy/context.py witchy/components/windows_terminal.py tests/fakes.py tests/test_windows.py tests/test_wt.py tests/test_components_wt.py
git commit -m "fix: find Windows Terminal through %USERPROFILE% and the Store Ubuntu profile

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 3: The `font` component (Maple Mono NF)

**Files:**
- Create: `witchy/fonts.py`, `witchy/components/font.py`, `tests/test_fonts.py`, `tests/test_components_font.py`
- Modify: `witchy/components/__init__.py`, `witchy/components/base.py`, `witchy/runner.py`, `witchy/context.py`, `tests/fakes.py`, `tests/test_runner.py`, `tests/test_install.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `windows.user_home/to_wsl` (Task 2), `base.Change/Plan/ComponentFailed/apply_changes/read/sha/fix_command`, `jsonio.write_atomic_bytes`.
- Produces:
  - `fonts.RELEASE`, `fonts.URL`, `fonts.SHA256`, `fonts.MEMBERS`, `fonts.MEMBER_LIMIT`, `fonts.FAMILY`, `fonts.REGISTRY_KEY`, `fonts.FontArchiveError(ValueError)`
  - `fonts.fetch_url(url: str, timeout: float = 60) -> bytes`, `fonts.extract(archive: bytes, names=MEMBERS, limit=MEMBER_LIMIT) -> dict[str, bytes]`, `fonts.full_name(ttf: bytes) -> str`, `fonts.parse_registry(text: str) -> dict[str, str]`, `fonts.registered(run) -> dict[str, str] | None`, `fonts.register_command(name: str, data: str) -> list[str]`
  - `components.font.FontComponent` (`name = "font"`), constants `FONTS_SUBDIR`, `RESTART_WT_NOTE`, `KEPT_WARNING`
  - Entry shape: `{"preexisting": bool, "registered": {value name: windows path}, "files": [{"path", "installed_sha256"}], "release"?: str}`
  - `Plan.actions: list[str]` (printed by dry runs); `Context.fetch: Callable[[str], bytes]`, `Context.cache_dir -> Path` (`~/.cache/witchy`)
  - `components.all_components()` order: `claude`, `font`, `windows-terminal`.

- [ ] **Step 1: Add the font fakes**

Append to `tests/fakes.py` (add `import io`, `import struct` and `import zipfile` at the top):

```python
REG_KEY_LINE = "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts"


def reg_listing(values):
    """What ``reg.exe query <key>`` prints for these values."""
    lines = "".join(f"    {name}    REG_SZ    {data}\r\n" for name, data in values.items())
    return f"\r\n{REG_KEY_LINE}\r\n{lines}\r\n"


def make_ttf(full_name):
    """The smallest TrueType file whose name table holds ``full_name`` as name ID 4 (Windows, en-US)."""
    encoded = full_name.encode("utf-16-be")
    name_table = struct.pack(">HHH", 0, 1, 18) + struct.pack(">HHHHHH", 3, 1, 0x409, 4, len(encoded), 0) + encoded
    header = struct.pack(">IHHHH", 0x00010000, 1, 16, 0, 0)
    record = struct.pack(">4sIII", b"name", 0, 12 + 16, len(name_table))
    return header + record + name_table


def make_zip(members):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_fonts.py`:

```python
import unittest

from tests.fakes import make_ttf, make_zip, reg_listing
from witchy import fonts


class FullNameTest(unittest.TestCase):
    def test_reads_the_full_font_name(self):
        self.assertEqual(fonts.full_name(make_ttf("Maple Mono NF Bold Italic")), "Maple Mono NF Bold Italic")

    def test_not_a_font(self):
        with self.assertRaises(fonts.FontArchiveError):
            fonts.full_name(b"not a font")


class ExtractTest(unittest.TestCase):
    def members(self):
        return {name: make_ttf(name) for name in fonts.MEMBERS}

    def test_extracts_only_the_named_members(self):
        archive = make_zip({**self.members(), "MapleMono-NF-Thin.ttf": b"x", "../evil.ttf": b"x"})
        self.assertEqual(set(fonts.extract(archive)), set(fonts.MEMBERS))

    def test_missing_member(self):
        members = self.members()
        del members["MapleMono-NF-Bold.ttf"]
        with self.assertRaises(fonts.FontArchiveError):
            fonts.extract(make_zip(members))

    def test_oversized_member(self):
        with self.assertRaises(fonts.FontArchiveError):
            fonts.extract(make_zip(self.members()), limit=10)

    def test_not_a_zip(self):
        with self.assertRaises(fonts.FontArchiveError):
            fonts.extract(b"not a zip")


class RegistryTest(unittest.TestCase):
    def test_parse(self):
        text = reg_listing({"Fira Code Light (TrueType)": "C:\\Users\\u\\Fonts\\Fira.ttf", "Arial (TrueType)": "arial.ttf"})
        self.assertEqual(fonts.parse_registry(text), {"Fira Code Light (TrueType)": "C:\\Users\\u\\Fonts\\Fira.ttf",
                                                      "Arial (TrueType)": "arial.ttf"})

    def test_no_reg_exe_is_none(self):
        def missing(args, **kwargs):
            raise FileNotFoundError("reg.exe")
        self.assertIsNone(fonts.registered(missing))

    def test_register_command(self):
        self.assertEqual(fonts.register_command("Maple Mono NF Regular (TrueType)", "C:\\F\\a.ttf"),
                         ["reg.exe", "add", fonts.REGISTRY_KEY, "/v", "Maple Mono NF Regular (TrueType)",
                          "/t", "REG_SZ", "/d", "C:\\F\\a.ttf", "/f"])


if __name__ == "__main__":
    unittest.main()
```

Create `tests/test_components_font.py`:

```python
import hashlib
import io
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from tests.fakes import fake_windows, make_ttf, make_zip, reg_listing
from witchy import fonts
from witchy.components.base import ComponentFailed
from witchy.components.font import KEPT_WARNING, RESTART_WT_NOTE, FontComponent
from witchy.context import Context

STYLES = ("Regular", "Italic", "Bold", "Bold Italic")
FONTS_WIN = "C:\\Users\\user\\AppData\\Local\\Microsoft\\Windows\\Fonts"
OTHER_FONT = {"Fira Code Light (TrueType)": f"{FONTS_WIN}\\FiraCode.ttf"}


class FontComponentTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.mnt = self.root / "mnt"
        self.folder = self.mnt / "c" / "Users" / "user" / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"
        self.folder.mkdir(parents=True)
        self.archive = make_zip({name: make_ttf(f"Maple Mono NF {style}") for name, style in zip(fonts.MEMBERS, STYLES)})
        patcher = mock.patch.object(fonts, "SHA256", hashlib.sha256(self.archive).hexdigest())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.calls, self.fetched = [], []
        self.component = FontComponent()

    def fetch(self, url):
        self.fetched.append(url)
        return self.archive

    def ctx(self, reg=None, reg_add_code=0, fetch=None, echo=None):
        self.out = io.StringIO()
        run = fake_windows(echo={"USERPROFILE": "C:\\Users\\user\r\n"} if echo is None else echo,
                           reg_query=reg_listing(OTHER_FONT if reg is None else reg), reg_add_code=reg_add_code,
                           calls=self.calls)
        return Context(home=self.root / "home", env={}, out=self.out, run=run, mount_root=self.mnt,
                       fetch=fetch or self.fetch)

    def install(self, **kwargs):
        ctx = self.ctx(**kwargs)
        plan = self.component.plan(ctx, None)
        return ctx, plan, self.component.apply(ctx, plan)

    def test_planning_only_reads(self):
        # A dry run stops after planning: no download, no copy, no reg.exe add.
        self.component.plan(self.ctx(), None)
        self.assertEqual(self.fetched, [])
        self.assertEqual(list(self.folder.iterdir()), [])
        self.assertEqual([call[:2] for call in self.calls], [["cmd.exe", "/c"], ["reg.exe", "query"]])

    def test_installs_and_registers_four_fonts(self):
        _, plan, entry = self.install()
        self.assertEqual(self.component.name, "font")
        self.assertIn(RESTART_WT_NOTE, plan.notes)
        self.assertTrue(any(action.startswith("font: download") for action in plan.actions))
        for name in fonts.MEMBERS:
            self.assertTrue((self.folder / name).is_file(), name)
        adds = [call for call in self.calls if call[:2] == ["reg.exe", "add"]]
        self.assertEqual(len(adds), 4)
        self.assertEqual(adds[0], fonts.register_command("Maple Mono NF Regular (TrueType)",
                                                         f"{FONTS_WIN}\\MapleMono-NF-Regular.ttf"))
        self.assertEqual(set(entry["registered"]), {f"Maple Mono NF {style} (TrueType)" for style in STYLES})
        self.assertFalse(entry["preexisting"])
        self.assertEqual(self.fetched, [fonts.URL])

    def test_cached_archive_is_not_downloaded_again(self):
        self.install()
        self.install()
        self.assertEqual(self.fetched, [fonts.URL])

    def test_a_font_already_installed_by_hand_is_left_alone(self):
        (self.folder / "MapleMono-NF-Regular.ttf").write_bytes(b"font")
        present = {"Maple Mono NF Regular (TrueType)": f"{FONTS_WIN}\\MapleMono-NF-Regular.ttf"}
        _, plan, entry = self.install(reg={**OTHER_FONT, **present})
        self.assertEqual(plan.actions, [])
        self.assertEqual(entry, {"preexisting": True, "registered": present, "files": []})
        self.assertEqual(self.fetched, [])
        self.assertFalse(any(call[:2] == ["reg.exe", "add"] for call in self.calls))

    def test_offline_fails_and_copies_nothing(self):
        def offline(url):
            raise urllib.error.URLError("no network")
        with self.assertRaises(ComponentFailed):
            self.install(fetch=offline)
        self.assertIn("font: download failed", self.out.getvalue())
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_checksum_mismatch_fails_and_keeps_no_cache(self):
        with self.assertRaises(ComponentFailed):
            self.install(fetch=lambda url: b"not the release")
        self.assertIn("font: checksum mismatch, nothing installed", self.out.getvalue())
        self.assertFalse((self.root / "home" / ".cache" / "witchy" / f"MapleMono-NF-{fonts.RELEASE}.zip").exists())

    def test_registry_failure_fails(self):
        with self.assertRaises(ComponentFailed):
            self.install(reg_add_code=1)
        self.assertIn("could not register", self.out.getvalue())

    def test_no_windows_profile_is_skipped(self):
        plan = self.component.plan(self.ctx(echo={}), None)
        self.assertEqual(plan.skip, "Windows user folder not found")

    def test_restore_keeps_the_font(self):
        ctx, _, entry = self.install()
        plan = self.component.restore(ctx, entry)
        self.assertEqual((plan.changes, plan.warnings), ([], [KEPT_WARNING]))

    def test_check_is_ok_then_fails_when_unregistered(self):
        _, _, entry = self.install()
        self.assertEqual({c.level for c in self.component.check(self.ctx(reg=entry["registered"]), entry)}, {"ok"})
        fails = [c for c in self.component.check(self.ctx(), entry) if c.level == "fail"]
        self.assertEqual(len(fails), 1)
        self.assertIn("not registered", fails[0].message)
        self.assertEqual(fails[0].fix, "python3 -m witchy install --only font")


if __name__ == "__main__":
    unittest.main()
```

Append to `tests/test_runner.py` inside `InstallRunnerTest`:

```python
    def test_dry_run_lists_planned_actions(self):
        class Acting(Fake):
            def plan(self, ctx, entry):
                super().plan(ctx, entry)
                return Plan(actions=["font: download x"])

        self.assertEqual(runner.install(self.ctx(dry_run=True), [Acting("a", self.log)]), 0)
        self.assertIn("font: download x", self.out.getvalue())
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_fonts tests.test_components_font tests.test_runner -v`
Expected: ERROR `ModuleNotFoundError: No module named 'witchy.fonts'`, and `Plan.__init__() got an unexpected keyword argument 'actions'`.

- [ ] **Step 4: Implement `witchy/fonts.py`**

```python
"""Maple Mono NF: the pinned release, safe extraction, TrueType names and the per-user font registry."""
from __future__ import annotations

import io
import re
import struct
import subprocess
import urllib.request
import zipfile
from typing import Any, Callable

RELEASE = "v7.9"
URL = f"https://github.com/subframe7536/maple-font/releases/download/{RELEASE}/MapleMono-NF.zip"
SHA256 = "59098b87c895d871635d37680e88000ae2b2b25b55428195b228ec589e35fb89"
MEMBERS = ("MapleMono-NF-Regular.ttf", "MapleMono-NF-Italic.ttf", "MapleMono-NF-Bold.ttf",
           "MapleMono-NF-BoldItalic.ttf")
MEMBER_LIMIT = 20 * 1024 * 1024
DOWNLOAD_LIMIT = 64 * 1024 * 1024
FAMILY = "Maple Mono NF"
REGISTRY_KEY = r"HKCU\Software\Microsoft\Windows NT\CurrentVersion\Fonts"
_REG_VALUE = re.compile(r"^ {4}(.+?) {4}REG_[A-Z_]+ {4}(.*)$")


class FontArchiveError(ValueError):
    """The release archive or a font in it is not usable; nothing is installed."""


def fetch_url(url: str, timeout: float = 60) -> bytes:
    """Download over HTTPS; urllib checks the certificate against the system's trust store."""
    with urllib.request.urlopen(url, timeout=timeout) as response:
        data = response.read(DOWNLOAD_LIMIT + 1)
    if len(data) > DOWNLOAD_LIMIT:
        raise FontArchiveError(f"{url} is larger than {DOWNLOAD_LIMIT} bytes")
    return data


def extract(archive: bytes, names: tuple[str, ...] = MEMBERS, limit: int = MEMBER_LIMIT) -> dict[str, bytes]:
    """The named members only, looked up by exact name, each at most ``limit`` bytes."""
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            members = {}
            for name in names:
                info = bundle.getinfo(name)
                if info.file_size > limit:
                    raise FontArchiveError(f"{name} is larger than {limit} bytes")
                with bundle.open(info) as member:
                    data = member.read(limit + 1)
                if len(data) > limit:
                    raise FontArchiveError(f"{name} is larger than {limit} bytes")
                members[name] = data
            return members
    except (zipfile.BadZipFile, KeyError) as exc:
        raise FontArchiveError(f"the font archive is not usable ({exc})") from exc


def full_name(ttf: bytes) -> str:
    """The full font name (name ID 4), preferring the Windows English record, as the registry expects."""
    try:
        tables = struct.unpack_from(">H", ttf, 4)[0]
        for index in range(tables):
            tag, _, offset, _ = struct.unpack_from(">4sIII", ttf, 12 + 16 * index)
            if tag == b"name":
                break
        else:
            raise FontArchiveError("the font has no name table")
        _, count, strings = struct.unpack_from(">HHH", ttf, offset)
        fallback = None
        for index in range(count):
            platform, _, language, name_id, length, start = struct.unpack_from(">HHHHHH", ttf, offset + 6 + 12 * index)
            if name_id != 4:
                continue
            raw = ttf[offset + strings + start:offset + strings + start + length]
            if platform == 3 and language == 0x409:
                return raw.decode("utf-16-be")
            if platform == 1 and fallback is None:
                fallback = raw.decode("latin-1")
    except (struct.error, UnicodeDecodeError) as exc:
        raise FontArchiveError(f"the font's name table is not readable ({exc})") from exc
    if fallback:
        return fallback
    raise FontArchiveError("the font has no full name")


def parse_registry(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        match = _REG_VALUE.match(line.rstrip("\r"))
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values


def registered(run: Callable[..., Any] = subprocess.run) -> dict[str, str] | None:
    """The current user's font registry values, or None when reg.exe cannot be asked."""
    try:
        done = run(["reg.exe", "query", REGISTRY_KEY], capture_output=True, text=True, errors="replace", timeout=10)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return parse_registry(done.stdout or "") if done.returncode == 0 else None


def register_command(name: str, data: str) -> list[str]:
    return ["reg.exe", "add", REGISTRY_KEY, "/v", name, "/t", "REG_SZ", "/d", data, "/f"]
```

- [ ] **Step 5: Implement `witchy/components/font.py`**

```python
"""font: Maple Mono NF for the current Windows user (no admin rights needed). Uninstall keeps it."""
from __future__ import annotations

import hashlib
import http.client
import subprocess
from pathlib import Path
from typing import Any

from .. import fonts, jsonio, windows
from .base import Change, Check, ComponentFailed, Plan, apply_changes, fix_command, read, sha

FONTS_SUBDIR = ("AppData", "Local", "Microsoft", "Windows", "Fonts")
RESTART_WT_NOTE = "Restart Windows Terminal once so it sees Maple Mono NF."
KEPT_WARNING = "Maple Mono NF stays installed; remove it in Windows Settings > Fonts if you no longer want it."
KEEP = "keeping the current font"


class FontComponent:
    name = "font"

    def plan(self, ctx: Any, entry: dict | None) -> Plan:
        home = windows.user_home(ctx.run, ctx.mount_root)
        if home is None:
            ctx.say(f"font: Windows user folder not found; {KEEP}.")
            return Plan.skipped("Windows user folder not found")
        values = fonts.registered(ctx.run)
        if values is None:
            ctx.say(f"font: cannot read the font registry (reg.exe); {KEEP}.")
            return Plan.skipped("cannot read the font registry")
        present = self._present(ctx, values)
        if present:
            return Plan(data={"present": present})
        folder = home.wsl.joinpath(*FONTS_SUBDIR)
        archive = ctx.cache_dir / f"MapleMono-NF-{fonts.RELEASE}.zip"
        source = f"use {archive}" if archive.is_file() else f"download {fonts.URL}"
        actions = [f"font: {source} (sha256 {fonts.SHA256[:12]}…)",
                   *(f"font: copy {name} to {folder}" for name in fonts.MEMBERS),
                   f"font: register {len(fonts.MEMBERS)} fonts under {fonts.REGISTRY_KEY} with reg.exe"]
        return Plan(actions=actions, notes=[RESTART_WT_NOTE], data={"home": home, "folder": folder, "archive": archive})

    def _present(self, ctx: Any, values: dict[str, str]) -> dict[str, str]:
        """Registry values for Maple Mono NF whose file exists, whoever installed them."""
        present = {}
        for name, data in values.items():
            path = windows.to_wsl(data, ctx.mount_root)
            if name.startswith(fonts.FAMILY) and path is not None and path.is_file():
                present[name] = data
        return present

    def _archive(self, ctx: Any, path: Path) -> bytes:
        cached = read(path)
        if cached is not None and hashlib.sha256(cached).hexdigest() == fonts.SHA256:
            return cached
        try:
            data = ctx.fetch(fonts.URL)
        except (OSError, ValueError, http.client.HTTPException) as exc:
            ctx.say(f"font: download failed ({exc}); {KEEP}.")
            raise ComponentFailed(f"download failed ({exc})") from exc
        if hashlib.sha256(data).hexdigest() != fonts.SHA256:
            path.unlink(missing_ok=True)
            ctx.say("font: checksum mismatch, nothing installed.")
            raise ComponentFailed("checksum mismatch")
        try:
            jsonio.write_atomic_bytes(path, data)
        except OSError:
            pass  # the cache only saves the next download
        return data

    def apply(self, ctx: Any, plan: Plan) -> dict:
        if "present" in plan.data:
            return {"preexisting": True, "registered": plan.data["present"], "files": []}
        home, folder = plan.data["home"], plan.data["folder"]
        archive = self._archive(ctx, plan.data["archive"])
        try:
            members = fonts.extract(archive)
            names = {member: fonts.full_name(data) for member, data in members.items()}
        except fonts.FontArchiveError as exc:
            ctx.say(f"font: {exc}; {KEEP}.")
            raise ComponentFailed(str(exc)) from exc
        changes = [Change(folder / member, read(folder / member), data) for member, data in members.items()]
        try:
            apply_changes(ctx, changes)
        except OSError as exc:
            ctx.say(f"font: could not copy the font files ({exc}); {KEEP}.")
            raise ComponentFailed(f"could not copy the font files ({exc})") from exc
        registered = {}
        for change in changes:
            name = f"{names[change.path.name]} (TrueType)"
            data = "\\".join([home.windows, *FONTS_SUBDIR, change.path.name])
            try:
                done = ctx.run(fonts.register_command(name, data), capture_output=True, text=True,
                               errors="replace", timeout=10)
            except (OSError, ValueError, subprocess.SubprocessError):
                done = None
            if done is None or done.returncode != 0:
                ctx.say(f"font: could not register {name!r} under {fonts.REGISTRY_KEY}; {KEEP}.")
                raise ComponentFailed(f"could not register {name}")
            registered[name] = data
        return {"preexisting": False, "release": fonts.RELEASE, "registered": registered,
                "files": [{"path": str(change.path), "installed_sha256": sha(change.after)} for change in changes]}

    def restore(self, ctx: Any, entry: dict) -> Plan:
        return Plan(warnings=[KEPT_WARNING])

    def check(self, ctx: Any, entry: dict) -> list[Check]:
        fix = fix_command(self.name)
        checks = []
        changed = [record["path"] for record in entry["files"]
                   if sha(read(Path(record["path"]))) != record["installed_sha256"]]
        if changed:
            checks.append(Check("fail", self.name, "changed or missing: " + ", ".join(changed), fix))
        values = fonts.registered(ctx.run)
        if values is None:
            checks.append(Check("warn", self.name, "cannot read the font registry (reg.exe)"))
        else:
            lost = [name for name in entry["registered"] if name not in values]
            if lost:
                checks.append(Check("fail", self.name, "not registered: " + ", ".join(lost), fix))
        if not checks:
            checks.append(Check("ok", self.name, f"{fonts.FAMILY} registered ({len(entry['registered'])} fonts)"))
        return checks
```

- [ ] **Step 6: Wire it in**

`witchy/components/base.py`, class `Plan`: add after `warnings`:

```python
    actions: list[str] = field(default_factory=list)
```

and extend its docstring to: `"""What a component will do. ``skip`` set means it will do nothing, and says why. ``actions`` describe work that is not a file change (a download, a reg.exe call) for dry runs."""`

`witchy/runner.py`, `_install`, dry-run branch: replace it with:

```python
    if ctx.dry_run:
        show_changes(ctx, changes)
        for _, plan in plans:
            if plan.skip is None:
                for action in plan.actions:
                    ctx.say(action)
        ctx.say("Dry run: nothing was written.")
        return 0
```

`witchy/context.py`: change the import to `from . import build, fonts, windows`, and add the field and the property:

```python
    fetch: Callable[[str], bytes] = fonts.fetch_url
```

```python
    @property
    def cache_dir(self) -> Path:
        """Disposable: renders, downloads and locks that can be deleted at any time."""
        return self.home / ".cache" / "witchy"
```

`witchy/components/__init__.py`:

```python
"""The pieces witchy installs, in the order they are installed."""
from __future__ import annotations

from .claude import ClaudeComponent
from .font import FontComponent
from .windows_terminal import WindowsTerminalComponent


def all_components() -> list:
    return [ClaudeComponent(), FontComponent(), WindowsTerminalComponent()]


NAMES: tuple[str, ...] = tuple(component.name for component in all_components())
```

- [ ] **Step 7: Keep the end-to-end tests off the font**

The font component would run `cmd.exe` and download in the install tests; they cover `claude` and `windows-terminal`, so they select those two:

1. `tests/test_install.py`, `InstallTestCase.ctx`: add `only=("claude", "windows-terminal"),` to the `install.Context(...)` call.
2. `tests/test_cli.py`, `test_install_and_uninstall_commands`: change the install call to `main(["install", "--wt-settings", str(wt_file), "--only", "claude", "--only", "windows-terminal"])`.

- [ ] **Step 8: Run the whole suite on both Pythons**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .` and `/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .`
Expected: OK on both. Any other failing assertion is a regression: fix the code, not the test.

- [ ] **Step 9: Commit**

```bash
git add witchy/fonts.py witchy/components/font.py witchy/components/__init__.py witchy/components/base.py witchy/runner.py witchy/context.py tests/fakes.py tests/test_fonts.py tests/test_components_font.py tests/test_runner.py tests/test_install.py tests/test_cli.py
git commit -m "feat: add the font component for Maple Mono NF

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 4: Moon phase and the sky renderer

**Files:**
- Create: `witchy/ritual/__init__.py`, `witchy/ritual/moon.py`, `witchy/sky_render.py`, `tests/test_moon.py`, `tests/test_sky_render.py`
- Modify: `witchy/palette.py`, `witchy/validate.py`, `tests/test_palette.py`, `tests/test_validate.py`

**Interfaces:**
- Consumes: `palette.BACKGROUND`, `palette.FOREGROUND`, `validate.HEX`, `validate.Failure`, `jsonio.write_atomic_bytes`.
- Produces:
  - `ritual.moon`: `SYNODIC_DAYS`, `EPOCH`, `BINS = 8`, `NAMES`, `GLYPHS`, `age(when) -> float`, `phase_bin(when) -> int`, `illumination(when) -> int` (percent). Imports nothing from `witchy` (Plan C runs it from `~/.claude/witchy/ritual/`).
  - `sky_render.SIZE = (2560, 1440)`, `sky_render.render(bin_: int, colours: dict[str, str], size=SIZE) -> bytes` (PNG), `sky_render.cached(root: Path, colours, size=SIZE, write=True) -> list[bytes]` (eight images, bin 0 first)
  - `palette.SKY: dict[str, str]` with keys `background, moon, moon_dark, moon_rim, star, star_gold, star_violet`; `Variant.sky` (default empty dict; midnight holds `SKY`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_moon.py`:

```python
import unittest
from datetime import datetime, timedelta, timezone

from witchy.ritual import moon


class MoonTest(unittest.TestCase):
    def test_known_new_and_full_moons(self):
        new = datetime(2024, 4, 8, 12, tzinfo=timezone.utc)
        full = datetime(2024, 9, 18, 12, tzinfo=timezone.utc)
        self.assertEqual((moon.phase_bin(new), moon.illumination(new)), (0, 0))
        self.assertEqual((moon.phase_bin(full), moon.illumination(full)), (4, 100))

    def test_bin_edges(self):
        first = moon.EPOCH + timedelta(days=moon.SYNODIC_DAYS / 16)
        self.assertEqual(moon.phase_bin(first - timedelta(minutes=1)), 0)
        self.assertEqual(moon.phase_bin(first + timedelta(minutes=1)), 1)
        last = moon.EPOCH + timedelta(days=moon.SYNODIC_DAYS * 15 / 16)
        self.assertEqual(moon.phase_bin(last - timedelta(minutes=1)), 7)
        self.assertEqual(moon.phase_bin(last + timedelta(minutes=1)), 0)

    def test_names_and_glyphs(self):
        self.assertEqual((len(moon.NAMES), len(moon.GLYPHS)), (moon.BINS, moon.BINS))
        self.assertEqual((moon.NAMES[2], moon.GLYPHS[4]), ("First Quarter", "🌕"))


if __name__ == "__main__":
    unittest.main()
```

Create `tests/test_sky_render.py`:

```python
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from witchy import palette, sky_render

SMALL = (256, 144)


def decode(png):
    width, height = struct.unpack(">II", png[16:24])
    length = struct.unpack(">I", png[33:37])[0]
    return width, height, zlib.decompress(png[41:41 + length])


def pixel(width, raw, x, y):
    offset = y * (1 + 3 * width) + 1 + 3 * x
    return "#%02X%02X%02X" % tuple(raw[offset:offset + 3])


class RenderTest(unittest.TestCase):
    def test_small_renders_are_deterministic(self):
        self.assertEqual(sky_render.render(3, palette.SKY, SMALL), sky_render.render(3, palette.SKY, SMALL))

    def test_moon_sits_bottom_right_lit_on_the_right_when_waxing(self):
        width, height, raw = decode(sky_render.render(2, palette.SKY, SMALL))  # first quarter
        cx, cy = width - 26, height - 26  # 260 px from the edges at full size, scaled by 256/2560
        self.assertEqual(pixel(width, raw, cx + 7, cy), palette.SKY["moon"])
        self.assertEqual(pixel(width, raw, cx - 7, cy), palette.SKY["moon_dark"])

    def test_new_moon_is_dark(self):
        width, height, raw = decode(sky_render.render(0, palette.SKY, SMALL))
        self.assertEqual(pixel(width, raw, width - 26, height - 26), palette.SKY["moon_dark"])

    def test_the_starfield_is_shared_by_every_phase(self):
        _, height, one = decode(sky_render.render(1, palette.SKY, SMALL))
        _, _, five = decode(sky_render.render(5, palette.SKY, SMALL))
        half = (height // 2) * (1 + 3 * SMALL[0])  # the moon and its glow stay in the lower half
        self.assertEqual(one[:half], five[:half])

    def test_one_full_size_render(self):
        width, height, raw = decode(sky_render.render(4, palette.SKY))
        self.assertEqual((width, height), sky_render.SIZE)
        self.assertEqual(pixel(width, raw, width - 260, height - 260), palette.SKY["moon"])


class CacheTest(unittest.TestCase):
    def test_second_call_uses_the_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = sky_render.cached(Path(tmp), palette.SKY, SMALL)
            with mock.patch.object(sky_render, "render", side_effect=AssertionError("must not render")):
                second = sky_render.cached(Path(tmp), palette.SKY, SMALL)
        self.assertEqual(len(first), 8)
        self.assertEqual(first, second)

    def test_no_write_leaves_no_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            sky_render.cached(Path(tmp), palette.SKY, SMALL, write=False)
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
```

Append to `tests/test_validate.py`:

```python
class SkyValidateTest(unittest.TestCase):
    def test_sky_colours_must_be_hex(self):
        with mock.patch.dict(palette.SKY, {"moon": "gold"}):
            failures = validate.validate_all()
        self.assertIn(("format", "sky.moon"), {(f.rule, f.item) for f in failures})
```

In `tests/test_palette.py`, `VariantTest.test_midnight_is_the_default_and_holds_the_module_colours`, add:

```python
        self.assertIs(midnight.sky, palette.SKY)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_moon tests.test_sky_render tests.test_validate tests.test_palette -v`
Expected: ERROR `ModuleNotFoundError: No module named 'witchy.ritual'` and `No module named 'witchy.sky_render'`; `AttributeError: module 'witchy.palette' has no attribute 'SKY'`.

- [ ] **Step 3: Implement the moon**

Create `witchy/ritual/__init__.py`:

```python
"""The greeting package. It imports nothing from witchy, so it also runs from ~/.claude/witchy/ritual/."""
```

Create `witchy/ritual/moon.py`:

```python
"""The moon's display phase: mean synodic age, eight phase bins, illumination (spec 6.3)."""
from __future__ import annotations

import math
from datetime import datetime, timezone

SYNODIC_DAYS = 29.530588853
EPOCH = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)  # a new moon
BINS = 8
NAMES = ("New", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
         "Full", "Waning Gibbous", "Last Quarter", "Waning Crescent")
GLYPHS = ("🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘")


def age(when: datetime) -> float:
    """Days since the last new moon. A naive ``when`` is local time."""
    days = (when.astimezone(timezone.utc) - EPOCH).total_seconds() / 86400
    return days % SYNODIC_DAYS


def phase_bin(when: datetime) -> int:
    """0 (new) to 7 (waning crescent); each bin is 1/8 of the cycle centred on its phase."""
    return math.floor(age(when) / SYNODIC_DAYS * BINS + 0.5) % BINS


def illumination(when: datetime) -> int:
    """The lit fraction of the disc, as a whole percent."""
    return round((1 - math.cos(2 * math.pi * age(when) / SYNODIC_DAYS)) / 2 * 100)
```

- [ ] **Step 4: Implement the sky renderer**

Create `witchy/sky_render.py`:

```python
"""The Windows Terminal sky: one shared starfield and the moon for each of the eight phase bins.

Stdlib only: a pre-filled bytearray where only star and moon pixels are touched, written as a PNG.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import struct
import zlib
from pathlib import Path

from . import jsonio
from .ritual.moon import BINS

SIZE = (2560, 1440)
SEED = 1031  # fixed, so the starfield is identical in all eight images
STARS = 220
SPARKLES = 7


def _rgb(colour: str) -> tuple[int, int, int]:
    value = colour.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _mix(a: tuple[int, ...], b: tuple[int, ...], amount: float) -> tuple[int, ...]:
    return tuple(round(x + (y - x) * amount) for x, y in zip(a, b))


def _png(width: int, height: int, raw: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")


def render(bin_: int, colours: dict[str, str], size: tuple[int, int] = SIZE) -> bytes:
    """A PNG of the sky for phase bin ``bin_`` (0 new … 7 waning crescent), northern-hemisphere view."""
    width, height = size
    scale = width / SIZE[0]
    stride = 1 + 3 * width
    raw = bytearray((b"\x00" + bytes(_rgb(colours["background"])) * width) * height)

    def put(x: int, y: int, rgb: tuple[int, ...]) -> None:
        if 0 <= x < width and 0 <= y < height:
            offset = y * stride + 1 + 3 * x
            raw[offset:offset + 3] = bytes(rgb)

    rng = random.Random(SEED)
    star_colours = [_rgb(colours[key]) for key in ("star", "star_gold", "star_violet")]
    for _ in range(STARS):
        x, y = int(rng.random() * width), int(rng.random() * height)
        rgb = star_colours[int(rng.random() * len(star_colours))]
        dot = 2 if rng.random() < 0.25 else 1
        for dx in range(dot):
            for dy in range(dot):
                put(x + dx, y + dy, rgb)
    sparkle = _rgb(colours["star"])
    for _ in range(SPARKLES):
        x, y = int(rng.random() * width), int(rng.random() * height)
        arm = max(1, round((3 + rng.random() * 3) * scale))
        for d in range(-arm, arm + 1):
            put(x + d, y, sparkle)
            put(x, y + d, sparkle)

    radius = 150 * scale
    cx, cy = width - 260 * scale, height - 260 * scale
    lit, dark, rim = _rgb(colours["moon"]), _rgb(colours["moon_dark"]), _rgb(colours["moon_rim"])
    light = (1 - math.cos(2 * math.pi * bin_ / BINS)) / 2
    waxing = bin_ <= BINS // 2
    terminator_scale = math.cos(2 * math.pi * bin_ / BINS)
    reach = radius * 1.35
    rim_width = max(1.0, 2 * scale)
    for y in range(max(0, int(cy - reach)), min(height, int(cy + reach) + 1)):
        ny = (y + 0.5 - cy) / radius
        for x in range(max(0, int(cx - reach)), min(width, int(cx + reach) + 1)):
            nx = (x + 0.5 - cx) / radius
            distance = math.hypot(nx, ny)
            if distance > 1:
                fade = 1 - (distance - 1) / 0.35
                if fade > 0 and light > 0:  # a soft glow that grows with the lit fraction
                    offset = y * stride + 1 + 3 * x
                    put(x, y, _mix(tuple(raw[offset:offset + 3]), lit, 0.22 * light * fade * fade))
                continue
            terminator = terminator_scale * math.sqrt(max(0.0, 1 - ny * ny))
            if light > 0 and (nx if waxing else -nx) >= terminator:
                put(x, y, lit)
            elif (1 - distance) * radius <= rim_width:
                put(x, y, rim)
            else:
                put(x, y, dark)
    return _png(width, height, bytes(raw))


def cached(root: Path, colours: dict[str, str], size: tuple[int, int] = SIZE, write: bool = True) -> list[bytes]:
    """All eight images, read from ``root/<key>/`` when this renderer, palette and size made them before."""
    key = hashlib.sha256(Path(__file__).read_bytes()
                         + json.dumps([colours, list(size)], sort_keys=True).encode("utf-8")).hexdigest()[:16]
    images = []
    for bin_ in range(BINS):
        path = root / key / f"sky-{bin_}.png"
        data = path.read_bytes() if path.is_file() else None
        if data is None:
            data = render(bin_, colours, size)
            if write:
                try:
                    jsonio.write_atomic_bytes(path, data)
                except OSError:
                    pass  # the cache only saves the next render
        images.append(data)
    return images
```

- [ ] **Step 5: Add the sky colours to the palette and validation**

`witchy/palette.py`: change `from dataclasses import dataclass` to `from dataclasses import dataclass, field`. Add above `class Variant`:

```python
# The Windows Terminal sky (sky_render.py). Decorative, so exempt from the contrast rules (spec 11.2).
SKY: dict[str, str] = {
    "background": BACKGROUND,
    "moon": "#FFD477",
    "moon_dark": "#1D1230",
    "moon_rim": "#38234D",
    "star": FOREGROUND,
    "star_gold": "#FFD477",
    "star_violet": "#B99AFF",
}
```

Add a last field to `Variant`:

```python
    sky: dict[str, str] = field(default_factory=dict)
```

and change the midnight entry to:

```python
    "midnight": Variant("midnight", "dark", BACKGROUND, FOREGROUND, CLAUDE_OVERRIDES, WT_SCHEME, STATUSLINE,
                        sky=SKY),
```

`witchy/validate.py`, `validate_all`: inside the `for variant in palette.VARIANTS.values():` loop, after the `failures += validate_palette(...)` statement, add:

```python
        failures += [Failure("format", f"sky.{key}", str(value), "is not #RRGGBB in uppercase")
                     for key, value in variant.sky.items() if not isinstance(value, str) or not HEX.match(value)]
```

- [ ] **Step 6: Run the whole suite on both Pythons**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .` and `/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .`
Expected: OK on both. The full-size render test takes about 0.2 s.

- [ ] **Step 7: Commit**

```bash
git add witchy/ritual/__init__.py witchy/ritual/moon.py witchy/sky_render.py witchy/palette.py witchy/validate.py tests/test_moon.py tests/test_sky_render.py tests/test_palette.py tests/test_validate.py
git commit -m "feat: add the moon phase and a deterministic sky renderer

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 5: Windows Terminal profile keys and the font key

**Files:**
- Modify: `witchy/palette.py`, `witchy/wt.py`, `witchy/context.py`, `witchy/runner.py`
- Rewrite: `witchy/components/windows_terminal.py`
- Modify: `tests/test_palette.py`, `tests/test_wt.py`, `tests/test_components_wt.py`, `tests/test_runner.py`

**Interfaces:**
- Consumes: `records.apply_keys/restore_keys/is_installed` (Task 1), `wt.locate_settings` (Task 2), `ritual.moon.BINS` (Task 4).
- Produces:
  - `palette.WT_PROFILE: dict[str, Any]` (spec 4.2 without `backgroundImage`); `Variant.wt_profile` (default empty dict; midnight holds `WT_PROFILE`)
  - `wt.sky_file(bin_: int) -> str` (`moonlit-candle-sky-<bin>.png`), `wt.SKY_VALUES: tuple[str, ...]` (the eight `ms-appdata:///local/…` values), `wt.ALSO_INSTALLED`
  - `wt.apply_profile_keys(data, guid, desired, recorded) -> tuple[dict, dict]` (raises `ValueError` when the profile is missing), `wt.restore_profile_keys(data, guid, recorded) -> tuple[dict, list[str]]`, `wt.holds_installed(profile, key, record) -> bool`
  - `Context.planned: dict[str, Plan]`, `Context.entries: dict[str, dict]`, `Context.results: dict[str, str]` — set by the runner while it plans and applies.
  - `windows_terminal`: constants `FONT_KEY`, `BACKGROUND_KEYS`, `NO_FONT_NOTE`; function `profile_keys(variant, font: bool) -> dict`. Entry gains `"profile_keys": {key: {"previous", "installed"}}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_runner.py` inside `InstallRunnerTest`:

```python
    def test_later_components_see_earlier_plans_and_results(self):
        seen = {}

        class Watching(Fake):
            def plan(self, ctx, entry):
                seen["planned"] = list(ctx.planned)
                return super().plan(ctx, entry)

            def apply(self, ctx, plan):
                seen["results"] = dict(ctx.results)
                return super().apply(ctx, plan)

        runner.install(self.ctx(), [Fake("a", self.log), Watching("b", self.log)])
        self.assertEqual(seen, {"planned": ["a"], "results": {"a": "ok"}})
```

Append to `tests/test_wt.py`:

```python
class ProfileKeysTest(unittest.TestCase):
    def test_apply_and_restore_round_trip(self):
        data = settings()
        installed, recs = wt.apply_profile_keys(data, UBUNTU, {"cursorShape": "filledBox"}, None)
        self.assertEqual(wt.profile(installed, UBUNTU)["cursorShape"], "filledBox")
        restored, warnings = wt.restore_profile_keys(installed, UBUNTU, recs)
        self.assertEqual((restored, warnings), (data, []))

    def test_any_sky_value_counts_as_installed(self):
        installed, recs = wt.apply_profile_keys(settings(), UBUNTU, {"backgroundImage": wt.SKY_VALUES[1]}, None)
        wt.profile(installed, UBUNTU)["backgroundImage"] = wt.SKY_VALUES[6]
        self.assertTrue(wt.holds_installed(wt.profile(installed, UBUNTU), "backgroundImage", recs["backgroundImage"]))
        restored, warnings = wt.restore_profile_keys(installed, UBUNTU, recs)
        self.assertEqual((restored, warnings), (settings(), []))

    def test_missing_profile(self):
        with self.assertRaises(ValueError):
            wt.apply_profile_keys(settings(), "{00000000-0000-0000-0000-000000000000}", {"icon": "x"}, None)
```

In `tests/test_palette.py`, `VariantTest.test_midnight_is_the_default_and_holds_the_module_colours`, add:

```python
        self.assertIs(midnight.wt_profile, palette.WT_PROFILE)
```

In `tests/test_components_wt.py`, add `from witchy import palette`, `from witchy.components.base import Plan` and `from witchy.components.windows_terminal import NO_FONT_NOTE` to the imports, and append these methods inside `WindowsTerminalComponentTest` (methods, not a subclass, so the existing tests do not run twice):

```python
    def with_font(self, face):
        data = json.loads(self.wt.read_text(encoding="utf-8"))
        data["profiles"]["list"][0]["font"] = {"face": face}
        self.wt.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")

    def test_profile_keys_are_set_and_recorded(self):
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        entry = self.component.apply(ctx, plan)
        ubuntu = self.ubuntu()
        self.assertEqual((ubuntu["cursorShape"], ubuntu["tabTitle"], ubuntu["opacity"]), ("filledBox", "witchyterm", 93))
        self.assertNotIn("font", ubuntu)
        self.assertNotIn("backgroundImageOpacity", ubuntu)
        self.assertEqual(entry["profile_keys"]["cursorShape"], {"previous": {"absent": True}, "installed": "filledBox"})
        self.assertIn(NO_FONT_NOTE, plan.notes)

    def test_font_is_set_when_the_font_component_installs_it(self):
        ctx = self.ctx()
        ctx.planned["font"] = Plan()
        plan = self.component.plan(ctx, None)
        ctx.results["font"] = "ok"
        self.component.apply(ctx, plan)
        self.assertEqual(self.ubuntu()["font"], palette.WT_PROFILE["font"])

    def test_failed_font_install_leaves_the_font_alone(self):
        self.with_font("FiraCode Nerd Font")
        ctx = self.ctx()
        ctx.planned["font"] = Plan()
        plan = self.component.plan(ctx, None)
        ctx.results["font"] = "failed: download failed (offline)"
        entry = self.component.apply(ctx, plan)
        self.assertEqual(self.ubuntu()["font"], {"face": "FiraCode Nerd Font"})
        self.assertNotIn("font", entry["profile_keys"])
        self.assertIn(NO_FONT_NOTE, self.out.getvalue())

    def test_font_recorded_in_state_counts(self):
        ctx = self.ctx()
        ctx.entries = {"font": {"preexisting": True, "registered": {}, "files": []}}
        self.component.apply(ctx, self.component.plan(ctx, None))
        self.assertEqual(self.ubuntu()["font"], palette.WT_PROFILE["font"])

    def test_reinstall_over_a_plan_a_entry_adds_keys_and_keeps_the_first_scheme(self):
        original = self.ubuntu()
        with mock.patch.dict(palette.WT_PROFILE, {}, clear=True):
            _, entry = self.install()
        entry.pop("profile_keys")  # what a Plan A install recorded
        ctx = self.ctx(stamp="20261002-120500")
        entry = self.component.apply(ctx, self.component.plan(ctx, entry))
        self.assertEqual(entry["previous_color_scheme"], {"value": "One Half Dark"})
        self.assertEqual(entry["profile_keys"]["cursorShape"]["previous"], {"absent": True})
        apply_changes(ctx, self.component.restore(self.ctx(stamp="20261002-130000"), entry).changes)
        self.assertEqual(self.ubuntu(), original)

    def test_a_key_the_user_changed_is_kept_on_restore(self):
        ctx, entry = self.install()
        data = json.loads(self.wt.read_text(encoding="utf-8"))
        data["profiles"]["list"][0]["cursorShape"] = "bar"
        self.wt.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        plan = self.component.restore(self.ctx(stamp="20261002-130000"), entry)
        apply_changes(ctx, plan.changes)
        self.assertEqual(self.ubuntu()["cursorShape"], "bar")
        self.assertNotIn("tabTitle", self.ubuntu())
        self.assertIn("Windows Terminal: cursorShape was changed after install; leaving it as it is.", plan.warnings)

    def test_check_reports_a_drifted_profile_key(self):
        ctx, entry = self.install()
        data = json.loads(self.wt.read_text(encoding="utf-8"))
        data["profiles"]["list"][0]["tabTitle"] = "mine"
        self.wt.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        fails = [c for c in self.component.check(ctx, entry) if c.level == "fail"]
        self.assertEqual([c.message for c in fails], ["profile keys changed: tabTitle"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_runner tests.test_wt tests.test_palette tests.test_components_wt -v`
Expected: ERROR/FAIL — `Context` has no `planned`, `wt` has no `apply_profile_keys`, `palette` has no `WT_PROFILE`, and `NO_FONT_NOTE` cannot be imported.

- [ ] **Step 3: Palette, context and runner**

`witchy/palette.py`: add `from typing import Any` to the imports, and above `class Variant`:

```python
# Windows Terminal profile settings (spec 4.2). backgroundImage is chosen at install time from the moon phase.
WT_PROFILE: dict[str, Any] = {
    "font": {"face": "Maple Mono NF", "size": 12, "cellHeight": "1.1"},
    "cursorShape": "filledBox",
    "padding": "14",
    "opacity": 93,
    "useAcrylic": True,
    "backgroundImageOpacity": 0.12,
    "backgroundImageAlignment": "bottomRight",
    "backgroundImageStretchMode": "uniformToFill",
    "icon": "🌙",
    "tabTitle": "witchyterm",
    "suppressApplicationTitle": True,
}
```

Add a last field to `Variant`: `wt_profile: dict[str, Any] = field(default_factory=dict)`, and pass `wt_profile=WT_PROFILE` in the midnight entry (next to `sky=SKY`).

`witchy/context.py`: add after `mount_root`:

```python
    # Filled by the runner: what earlier components planned and how they ended, and what state records.
    planned: dict[str, Any] = field(default_factory=dict)
    entries: dict[str, dict] = field(default_factory=dict)
    results: dict[str, str] = field(default_factory=dict)
```

`witchy/runner.py`, `_install`: replace the `plans = [...]` statement with:

```python
    ctx.entries, ctx.planned = entries, {}
    plans = []
    for component in _selected(ctx, components):
        plan = component.plan(ctx, entries.get(component.name))
        ctx.planned[component.name] = plan
        plans.append((component, plan))
```

and replace `results: dict[str, str] = {}` with:

```python
    results: dict[str, str] = {}
    ctx.results = results
```

- [ ] **Step 4: Profile keys in `witchy/wt.py`**

Change the records import to `from .records import apply_keys, is_installed, put_back, restore_keys, snapshot`, add `from .ritual.moon import BINS`, and append:

```python
def sky_file(bin_: int) -> str:
    return f"moonlit-candle-sky-{bin_}.png"


SKY_VALUES = tuple(f"ms-appdata:///local/{sky_file(bin_)}" for bin_ in range(BINS))
# Values that still count as witchy's own: the sky job (Plan C) moves backgroundImage between the eight images.
ALSO_INSTALLED = {"backgroundImage": SKY_VALUES}


def holds_installed(profile: dict, key: str, record: dict) -> bool:
    return is_installed(profile, key, record, ALSO_INSTALLED.get(key, ()))


def apply_profile_keys(data: dict, guid: str, desired: dict, recorded: dict | None) -> tuple[dict, dict]:
    """Set ``desired`` on one profile, recording what each key held before (the first install's value wins)."""
    result = copy.deepcopy(data)
    profile = _profile(result, guid)
    if profile is None:
        raise ValueError(f"profile {guid} not found")
    updated, records = apply_keys(profile, desired, recorded)
    profile.clear()
    profile.update(updated)
    return result, records


def restore_profile_keys(data: dict, guid: str, recorded: dict) -> tuple[dict, list[str]]:
    """Undo apply_profile_keys, leaving alone whatever the user changed since."""
    result = copy.deepcopy(data)
    profile = _profile(result, guid)
    if profile is None or not recorded:
        return result, []  # restore_scheme already says when the profile is gone
    restored, warnings = restore_keys(profile, recorded, ALSO_INSTALLED)
    profile.clear()
    profile.update(restored)
    return result, [f"Windows Terminal: {warning}" for warning in warnings]
```

- [ ] **Step 5: Rewrite `witchy/components/windows_terminal.py`**

```python
"""windows-terminal: the Moonlit Candle colour scheme and profile settings on the WSL profile."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import jsonio, palette, wt
from .base import (Change, Check, ComponentFailed, JsonPlan, Plan, apply_changes, backup_checks, fix_command,
                   restore_json)

WT_SKIP = "skipping the terminal colour scheme"
FONT_KEY = "font"
# Set only once the sky images are in place.
BACKGROUND_KEYS = ("backgroundImage", "backgroundImageOpacity", "backgroundImageAlignment",
                   "backgroundImageStretchMode")
NO_FONT_NOTE = "Windows Terminal: Maple Mono NF is not installed, so the profile font was left as it is."


def profile_keys(variant: palette.Variant, font: bool) -> dict[str, Any]:
    """The profile keys to set: the font only once Maple Mono NF is there."""
    return {key: value for key, value in variant.wt_profile.items()
            if key not in BACKGROUND_KEYS and (font or key != FONT_KEY)}


def _font_source(ctx: Any) -> str | None:
    """"planned" when this run's font component will install Maple Mono NF, "installed" when state records it."""
    planned = ctx.planned.get("font")
    if planned is not None and planned.skip is None:
        return "planned"
    return "installed" if "font" in ctx.entries else None


class WindowsTerminalComponent:
    name = "windows-terminal"

    def plan(self, ctx: Any, entry: dict | None) -> Plan:
        variant = palette.VARIANTS[ctx.variant or palette.DEFAULT_VARIANT]
        scheme = variant.wt_scheme
        path = wt.locate_settings(ctx.wt_settings, run=ctx.run, recorded=entry["path"] if entry else None,
                                  mount_root=ctx.mount_root)
        if path is None:
            ctx.say(f"Windows Terminal settings.json not found; {WT_SKIP}.")
            return Plan.skipped("settings.json not found")
        try:
            data, text = jsonio.read_json(path)
        except jsonio.StrictJsonError:
            ctx.say(f"{path} is not plain JSON (comments?), so it was left untouched. Add this by hand:")
            ctx.say(wt.manual_snippet(scheme, ctx.env.get("WT_PROFILE_ID") or "<your WSL profile guid>"))
            return Plan.skipped("settings.json is not plain JSON")
        guid, reason = wt.find_profile(data, ctx.env)
        if guid is None:
            ctx.say(f"Windows Terminal: {reason}; {WT_SKIP}.")
            return Plan.skipped(reason)
        if entry and (entry["path"] != str(path) or entry["profile_guid"].lower() != guid.lower()):
            ctx.say(f"Windows Terminal: already installed for profile {entry['profile_guid']} in {entry['path']}; "
                    f"run uninstall first to move it; {WT_SKIP}.")
            return Plan.skipped("installed for another profile")

        def build(font: bool) -> tuple[bytes, dict]:
            new_data, record = wt.apply_scheme(data, scheme, guid, entry)
            recorded = (entry or {}).get("profile_keys")
            new_data, keys = wt.apply_profile_keys(new_data, guid, profile_keys(variant, font), recorded)
            record["profile_keys"] = {**(recorded or {}), **keys}
            return jsonio.dumps_like(new_data, text).encode("utf-8"), record

        font = _font_source(ctx)
        try:
            after, record = build(font is not None)
        except ValueError as exc:
            ctx.say(f"Windows Terminal: {exc}; {WT_SKIP}.")
            return Plan.skipped(str(exc))
        change = Change(path, path.read_bytes(), after)
        return Plan(changes=[change], notes=[] if font else [NO_FONT_NOTE],
                    data={"json": JsonPlan(change, entry, record), "build": build, "font": font})

    def apply(self, ctx: Any, plan: Plan) -> dict:
        json_plan: JsonPlan = plan.data["json"]
        if plan.data["font"] == "planned" and ctx.results.get("font") != "ok":
            ctx.say(NO_FONT_NOTE)
            json_plan.change.after, json_plan.extra = plan.data["build"](False)
        try:
            backups = apply_changes(ctx, [json_plan.change])
        except OSError as exc:
            ctx.say(f"Windows Terminal: could not write {json_plan.change.path} ({exc}); {WT_SKIP}.")
            raise ComponentFailed(f"could not write {json_plan.change.path}") from exc
        return json_plan.entry(backups.get(json_plan.change.path))

    def restore(self, ctx: Any, entry: dict) -> Plan:
        warnings: list[str] = []

        def give_back(data: dict) -> tuple[dict, list[str]]:
            restored, notes = wt.restore_scheme(data, entry)
            restored, more = wt.restore_profile_keys(restored, entry["profile_guid"], entry.get("profile_keys", {}))
            return restored, notes + more

        change = restore_json(entry, give_back, warnings)
        return Plan(changes=[change] if change is not None else [], warnings=warnings)

    def check(self, ctx: Any, entry: dict) -> list[Check]:
        fix = fix_command(self.name)
        path = Path(entry["path"])
        try:
            data, _ = jsonio.read_json(path)
        except (OSError, jsonio.StrictJsonError) as exc:
            return [Check("fail", self.name, f"cannot read {path}: {exc}", fix)]
        name = entry["installed_color_scheme"]
        found = wt.profile(data, entry["profile_guid"])
        schemes = data.get("schemes") if isinstance(data, dict) else None
        has_scheme = isinstance(schemes, list) and any(isinstance(s, dict) and s.get("name") == name for s in schemes)
        if found is None:
            checks = [Check("fail", self.name, f"profile {entry['profile_guid']} not found in {path}", fix)]
        elif found.get("colorScheme") != name:
            checks = [Check("fail", self.name, f"profile colour scheme is {found.get('colorScheme')!r}, not {name!r}",
                            fix)]
        elif not has_scheme:
            checks = [Check("fail", self.name, f"scheme {name!r} is missing from {path}", fix)]
        else:
            checks = [Check("ok", self.name, f"profile {entry['profile_guid']} uses {name}")]
        keys = entry.get("profile_keys") or {}
        if found is not None and keys:
            drift = [key for key, record in keys.items() if not wt.holds_installed(found, key, record)]
            checks.append(Check("fail", self.name, "profile keys changed: " + ", ".join(drift), fix) if drift
                          else Check("ok", self.name, f"{len(keys)} profile keys match"))
        return checks + backup_checks(self.name, [entry.get("backup")])
```

- [ ] **Step 6: Run the whole suite on both Pythons**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .` and `/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .`
Expected: OK on both. `tests/test_install.py` passes unchanged: uninstall restores the profile byte for byte.

- [ ] **Step 7: Commit**

```bash
git add witchy/palette.py witchy/wt.py witchy/context.py witchy/runner.py witchy/components/windows_terminal.py tests/test_palette.py tests/test_wt.py tests/test_components_wt.py tests/test_runner.py
git commit -m "feat: set the Windows Terminal profile keys, with the font only once it is installed

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 6: Sky images, ritual config and the shared Windows Terminal lock

**Files:**
- Modify: `witchy/components/base.py`, `witchy/runner.py`, `witchy/context.py`
- Rewrite: `witchy/components/windows_terminal.py`
- Modify: `tests/test_base.py`, `tests/test_runner.py`, `tests/test_components_wt.py`, `tests/test_install.py`

**Interfaces:**
- Consumes: Tasks 4 and 5 (`sky_render.cached`, `ritual.moon.phase_bin`, `wt.sky_file`, `wt.SKY_VALUES`, `profile_keys`, `_font_source`).
- Produces:
  - `Plan.lock: Path | None`; `base.file_lock(path: Path | None, timeout: float = 10.0)` context manager (raises `ComponentFailed` on timeout)
  - The runner holds each plan's lock while it re-checks that plan's files and applies it (install and uninstall); a mismatch fails that component only.
  - `Context.now: Callable[[], datetime]` (default `datetime.now`), `Context.sky_size: tuple[int, int]` (default `sky_render.SIZE`)
  - `windows_terminal`: `profile_keys(variant, font: bool, sky: str | None) -> dict`; `ritual_config(settings: Path, guid: str) -> bytes`; `RITUAL_CONFIG = Path(".claude/witchy/ritual-config.json")`; `WT_LOCK = "wt.lock"`
  - Entry gains `"files": [{"path", "backup", "installed_sha256"}]` (the eight PNGs in `LocalState`, then `ritual-config.json`).
  - `~/.claude/witchy/ritual-config.json`: `{"settings": "<settings.json path>", "profile_guid": "<guid>", "sky": [the eight SKY_VALUES]}` — read by Plan C's sky job.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_base.py` (add `import fcntl`, `import tempfile` and `from witchy.components.base import ComponentFailed, file_lock`):

```python
class FileLockTest(unittest.TestCase):
    def test_busy_lock_times_out_as_a_component_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wt.lock"
            with open(path, "a") as handle:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(ComponentFailed):
                    with file_lock(path, timeout=0.2):
                        pass

    def test_no_path_is_a_no_op(self):
        with file_lock(None):
            pass
```

Append to `tests/test_runner.py` inside `InstallRunnerTest`:

```python
    def test_a_file_changed_after_planning_fails_only_that_component(self):
        target = self.root / "settings.json"
        target.write_text("{}", encoding="utf-8")

        class Writing(Fake):
            def plan(self, ctx, entry):
                super().plan(ctx, entry)
                return Plan(changes=[Change(target, b"{}", b'{"x": 1}')])

        def sky_job(ctx):
            target.write_text('{"sky": 3}', encoding="utf-8")

        code = runner.install(self.ctx(), [Fake("a", self.log, on_apply=sky_job), Writing("b", self.log)])
        self.assertEqual(code, 2)
        self.assertTrue(self.state()["last_install"]["results"]["b"].startswith("failed: "))
        self.assertEqual(target.read_text(encoding="utf-8"), '{"sky": 3}')
        self.assertNotIn(("apply", "b"), self.log)

    def test_the_plan_lock_is_held_while_applying(self):
        lock = self.root / "wt.lock"
        seen = []

        class Locking(Fake):
            def plan(self, ctx, entry):
                super().plan(ctx, entry)
                return Plan(lock=lock)

            def apply(self, ctx, plan):
                with open(lock, "a") as handle:
                    try:
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        seen.append("free")
                    except BlockingIOError:
                        seen.append("held")
                return super().apply(ctx, plan)

        runner.install(self.ctx(), [Locking("a", self.log)])
        self.assertEqual(seen, ["held"])
```

In `tests/test_components_wt.py`:

1. Add the imports `from datetime import datetime, timezone`, `from witchy import jsonio, wt`, and change the windows_terminal import to `from witchy.components.windows_terminal import NO_FONT_NOTE, RITUAL_CONFIG, WindowsTerminalComponent`.
2. In `WindowsTerminalComponentTest.ctx`, add to the `Context(...)` call: `sky_size=(256, 144), now=lambda: datetime(2024, 9, 18, 12, tzinfo=timezone.utc)` (a full moon, bin 4).
3. In `test_recorded_settings_path_is_reused_without_cmd_exe` (Task 2), add the same two arguments to its `Context(...)` call.
4. In `test_profile_keys_are_set_and_recorded` (Task 5), the background keys are now installed: replace `self.assertNotIn("backgroundImageOpacity", ubuntu)` with `self.assertEqual(ubuntu["backgroundImageOpacity"], 0.12)`. This is the only Task 5 expectation that changes by design.
5. Append these methods inside `WindowsTerminalComponentTest`:

```python
    def config(self):
        return self.root / "home" / RITUAL_CONFIG

    def test_sky_images_background_and_ritual_config(self):
        _, entry = self.install()
        for bin_ in range(8):
            self.assertTrue((self.root / wt.sky_file(bin_)).is_file(), bin_)
        ubuntu = self.ubuntu()
        self.assertEqual(ubuntu["backgroundImage"], wt.SKY_VALUES[4])
        self.assertEqual(ubuntu["backgroundImageOpacity"], 0.12)
        self.assertEqual(json.loads(self.config().read_text(encoding="utf-8")),
                         {"settings": str(self.wt), "profile_guid": UBUNTU, "sky": list(wt.SKY_VALUES)})
        self.assertEqual(len(entry["files"]), 9)

    def test_failed_image_copy_sets_no_background(self):
        real = jsonio.write_atomic_bytes

        def write(path, data):
            if Path(path).suffix == ".png":
                raise PermissionError(13, "Permission denied", str(path))
            return real(path, data)

        with mock.patch("witchy.jsonio.write_atomic_bytes", side_effect=write):
            _, entry = self.install()
        self.assertNotIn("backgroundImage", self.ubuntu())
        self.assertEqual(self.ubuntu()["cursorShape"], "filledBox")
        self.assertIn("sky images not copied", self.out.getvalue())
        self.assertFalse(self.config().exists())
        self.assertEqual(entry["files"], [])

    def test_moved_sky_still_counts_as_installed(self):
        ctx, entry = self.install()
        data = json.loads(self.wt.read_text(encoding="utf-8"))
        data["profiles"]["list"][0]["backgroundImage"] = wt.SKY_VALUES[6]  # what the sky job does
        self.wt.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        self.assertEqual({c.level for c in self.component.check(ctx, entry)}, {"ok"})
        plan = self.component.restore(self.ctx(stamp="20261002-130000"), entry)
        apply_changes(ctx, plan.changes)
        self.assertNotIn("backgroundImage", self.ubuntu())
        self.assertFalse(any("changed after install" in warning for warning in plan.warnings))
        self.assertFalse((self.root / wt.sky_file(4)).exists())
        self.assertFalse(self.config().exists())

    def test_restore_writes_settings_first_under_the_lock(self):
        ctx, entry = self.install()
        plan = self.component.restore(ctx, entry)
        self.assertEqual(plan.changes[0].path, self.wt)
        self.assertEqual(plan.lock, ctx.cache_dir / "wt.lock")
```

In `tests/test_install.py`:

1. Add `from datetime import datetime, timezone` to the imports.
2. In `InstallTestCase.ctx`, add to the `install.Context(...)` call: `sky_size=(256, 144), now=lambda: datetime(2026, 9, 30, 12, tzinfo=timezone.utc),`.
3. In `InstallTestCase.snapshot`, skip the disposable cache (spec 3.3: `~/.cache/witchy/` is disposable):

```python
    def snapshot(self):
        files = {}
        cache = self.home / ".cache"
        for base in (self.home, self.wt.parent):
            for path in sorted(base.rglob("*")):
                if path.is_file() and ".bak-witchy-" not in path.name and cache not in path.parents:
                    files[str(path)] = path.read_bytes()
        return files
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_base tests.test_runner tests.test_components_wt tests.test_install -v`
Expected: ERROR — `cannot import name 'file_lock'`, `Plan` has no `lock`, `Context` has no `sky_size`, and `RITUAL_CONFIG` cannot be imported.

- [ ] **Step 3: Locks in `base.py` and the runner**

`witchy/components/base.py`: add `import fcntl`, `import time`, `from contextlib import contextmanager` and `Iterator` (to the `typing` import), add `"file_lock"` to `__all__`, add to `Plan` after `actions`:

```python
    lock: Path | None = None
```

and append to the docstring of `Plan`: ` ``lock`` is held while the plan is applied.`. Then add:

```python
@contextmanager
def file_lock(path: Path | None, timeout: float = 10.0) -> Iterator[None]:
    """Hold ``path`` exclusively, waiting up to ``timeout`` seconds (the sky job holds it only briefly)."""
    if path is None:
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as handle:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ComponentFailed(f"{path} is held by another process") from None
                time.sleep(0.1)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
```

`witchy/runner.py`: add `file_lock` to the `from .components.base import ...` line and add above `install`:

```python
def _recheck(changes: list) -> None:
    """Under the plan's lock: another writer (the sky job) may have rewritten a file since planning."""
    try:
        check_unchanged(changes)
    except Abort as exc:
        raise ComponentFailed(str(exc)) from exc
```

In `_install`'s apply loop, replace the `try:` block body so it reads:

```python
            try:
                with file_lock(plan.lock):
                    _recheck(plan.changes)
                    new_state["components"][component.name] = component.apply(ctx, plan)
                results[component.name] = "ok"
            except ComponentFailed as exc:
                results[component.name] = f"failed: {exc}"
```

In `_uninstall`'s loop, replace the `try:`/`except OSError` pair with:

```python
        try:
            with file_lock(plan.lock):
                _recheck(plan.changes)
                apply_changes(ctx, plan.changes)
        except (OSError, ComponentFailed) as exc:
```

(the body of the `except` block stays as it is).

`witchy/context.py`: change the import to `from . import build, fonts, sky_render, windows`, and add after `results`:

```python
    now: Callable[[], datetime] = datetime.now
    sky_size: tuple[int, int] = field(default_factory=lambda: sky_render.SIZE)
```

- [ ] **Step 4: Rewrite `witchy/components/windows_terminal.py`**

```python
"""windows-terminal: the Moonlit Candle scheme, profile settings and moon-phase sky on the WSL profile."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .. import jsonio, palette, sky_render, wt
from ..ritual import moon
from .base import (Change, Check, ComponentFailed, JsonPlan, Plan, apply_changes, backup_checks, fix_command, read,
                   restore_copy, restore_json, sha)

WT_SKIP = "skipping the terminal colour scheme"
WT_LOCK = "wt.lock"
FONT_KEY = "font"
# Set only once the sky images are in place.
BACKGROUND_KEYS = ("backgroundImage", "backgroundImageOpacity", "backgroundImageAlignment",
                   "backgroundImageStretchMode")
NO_FONT_NOTE = "Windows Terminal: Maple Mono NF is not installed, so the profile font was left as it is."
RITUAL_CONFIG = Path(".claude/witchy/ritual-config.json")


def profile_keys(variant: palette.Variant, font: bool, sky: str | None) -> dict[str, Any]:
    """The profile keys to set: the font only once Maple Mono NF is there, the background only with the sky."""
    keys = {key: value for key, value in variant.wt_profile.items()
            if (font or key != FONT_KEY) and (sky is not None or key not in BACKGROUND_KEYS)}
    if sky is not None:
        keys["backgroundImage"] = sky
    return keys


def ritual_config(settings: Path, guid: str) -> bytes:
    """What the sky job (Plan C) needs to move backgroundImage between the eight images."""
    data = {"settings": str(settings), "profile_guid": guid, "sky": list(wt.SKY_VALUES)}
    return (json.dumps(data, indent=2) + "\n").encode("utf-8")


def _font_source(ctx: Any) -> str | None:
    """"planned" when this run's font component will install Maple Mono NF, "installed" when state records it."""
    planned = ctx.planned.get("font")
    if planned is not None and planned.skip is None:
        return "planned"
    return "installed" if "font" in ctx.entries else None


def _file_change(path: Path, data: bytes, earlier: dict[Path, dict]) -> Change:
    before = read(path)
    previous = earlier.get(path)
    ours = previous is not None and sha(before) == previous["installed_sha256"]
    return Change(path, before, data, backup=not ours)


def _file_record(change: Change, earlier: dict[Path, dict], backups: dict[Path, Path]) -> dict:
    previous = earlier.get(change.path)
    backup = previous["backup"] if previous else (str(backups[change.path]) if change.path in backups else None)
    return {"path": str(change.path), "backup": backup, "installed_sha256": sha(change.after)}


class WindowsTerminalComponent:
    name = "windows-terminal"

    def plan(self, ctx: Any, entry: dict | None) -> Plan:
        variant = palette.VARIANTS[ctx.variant or palette.DEFAULT_VARIANT]
        scheme = variant.wt_scheme
        path = wt.locate_settings(ctx.wt_settings, run=ctx.run, recorded=entry["path"] if entry else None,
                                  mount_root=ctx.mount_root)
        if path is None:
            ctx.say(f"Windows Terminal settings.json not found; {WT_SKIP}.")
            return Plan.skipped("settings.json not found")
        try:
            data, text = jsonio.read_json(path)
        except jsonio.StrictJsonError:
            ctx.say(f"{path} is not plain JSON (comments?), so it was left untouched. Add this by hand:")
            ctx.say(wt.manual_snippet(scheme, ctx.env.get("WT_PROFILE_ID") or "<your WSL profile guid>"))
            return Plan.skipped("settings.json is not plain JSON")
        guid, reason = wt.find_profile(data, ctx.env)
        if guid is None:
            ctx.say(f"Windows Terminal: {reason}; {WT_SKIP}.")
            return Plan.skipped(reason)
        if entry and (entry["path"] != str(path) or entry["profile_guid"].lower() != guid.lower()):
            ctx.say(f"Windows Terminal: already installed for profile {entry['profile_guid']} in {entry['path']}; "
                    f"run uninstall first to move it; {WT_SKIP}.")
            return Plan.skipped("installed for another profile")
        sky = wt.SKY_VALUES[moon.phase_bin(ctx.now())]

        def build(font: bool, background: bool) -> tuple[bytes, dict]:
            new_data, record = wt.apply_scheme(data, scheme, guid, entry)
            recorded = (entry or {}).get("profile_keys")
            desired = profile_keys(variant, font, sky if background else None)
            new_data, keys = wt.apply_profile_keys(new_data, guid, desired, recorded)
            record["profile_keys"] = {**(recorded or {}), **keys}
            return jsonio.dumps_like(new_data, text).encode("utf-8"), record

        font = _font_source(ctx)
        try:
            after, record = build(font is not None, True)
        except ValueError as exc:
            ctx.say(f"Windows Terminal: {exc}; {WT_SKIP}.")
            return Plan.skipped(str(exc))
        earlier = {Path(item["path"]): item for item in (entry or {}).get("files", [])}
        renders = sky_render.cached(ctx.cache_dir / "sky", variant.sky, ctx.sky_size, write=not ctx.dry_run)
        # ms-appdata:///local/ is Windows Terminal's LocalState folder, the one that holds settings.json.
        images = [_file_change(path.parent / wt.sky_file(bin_), image, earlier) for bin_, image in enumerate(renders)]
        config = _file_change(ctx.home / RITUAL_CONFIG, ritual_config(path, guid), earlier)
        settings = Change(path, path.read_bytes(), after)
        return Plan(changes=[*images, settings, config], notes=[] if font else [NO_FONT_NOTE],
                    lock=ctx.cache_dir / WT_LOCK,
                    data={"json": JsonPlan(settings, entry, record), "build": build, "font": font,
                          "images": images, "config": config, "earlier": earlier})

    def apply(self, ctx: Any, plan: Plan) -> dict:
        json_plan: JsonPlan = plan.data["json"]
        settings, images, config, earlier = json_plan.change, plan.data["images"], plan.data["config"], plan.data["earlier"]
        backups: dict[Path, Path] = {}
        try:
            backups.update(apply_changes(ctx, images))
            background = True
        except OSError as exc:
            ctx.say(f"windows-terminal: sky images not copied ({exc})")
            background = False
        font = plan.data["font"] == "installed" or (plan.data["font"] == "planned" and ctx.results.get("font") == "ok")
        if plan.data["font"] == "planned" and not font:
            ctx.say(NO_FONT_NOTE)
        if (font, background) != (plan.data["font"] is not None, True):
            settings.after, json_plan.extra = plan.data["build"](font, background)
        try:
            backups.update(apply_changes(ctx, [settings]))
        except OSError as exc:
            for image in images:
                if image.before is None:
                    image.path.unlink(missing_ok=True)
            ctx.say(f"Windows Terminal: could not write {settings.path} ({exc}); {WT_SKIP}.")
            raise ComponentFailed(f"could not write {settings.path}") from exc
        entry = json_plan.entry(backups.get(settings.path))
        files = [_file_record(image, earlier, backups) for image in images if read(image.path) == image.after]
        if background:
            try:
                backups.update(apply_changes(ctx, [config]))
                files.append(_file_record(config, earlier, backups))
            except OSError as exc:
                ctx.say(f"windows-terminal: could not write {config.path} ({exc}); the sky keeps tonight's phase.")
        entry["files"] = files
        return entry

    def restore(self, ctx: Any, entry: dict) -> Plan:
        warnings: list[str] = []

        def give_back(data: dict) -> tuple[dict, list[str]]:
            restored, notes = wt.restore_scheme(data, entry)
            restored, more = wt.restore_profile_keys(restored, entry["profile_guid"], entry.get("profile_keys", {}))
            return restored, notes + more

        settings = restore_json(entry, give_back, warnings)
        files = [restore_copy(record) for record in entry.get("files", [])]
        # Settings first, so the profile never points at an image that is already gone.
        return Plan(changes=[change for change in [settings, *files] if change is not None], warnings=warnings,
                    lock=ctx.cache_dir / WT_LOCK)

    def check(self, ctx: Any, entry: dict) -> list[Check]:
        fix = fix_command(self.name)
        path = Path(entry["path"])
        try:
            data, _ = jsonio.read_json(path)
        except (OSError, jsonio.StrictJsonError) as exc:
            return [Check("fail", self.name, f"cannot read {path}: {exc}", fix)]
        name = entry["installed_color_scheme"]
        found = wt.profile(data, entry["profile_guid"])
        schemes = data.get("schemes") if isinstance(data, dict) else None
        has_scheme = isinstance(schemes, list) and any(isinstance(s, dict) and s.get("name") == name for s in schemes)
        if found is None:
            checks = [Check("fail", self.name, f"profile {entry['profile_guid']} not found in {path}", fix)]
        elif found.get("colorScheme") != name:
            checks = [Check("fail", self.name, f"profile colour scheme is {found.get('colorScheme')!r}, not {name!r}",
                            fix)]
        elif not has_scheme:
            checks = [Check("fail", self.name, f"scheme {name!r} is missing from {path}", fix)]
        else:
            checks = [Check("ok", self.name, f"profile {entry['profile_guid']} uses {name}")]
        keys = entry.get("profile_keys") or {}
        if found is not None and keys:
            drift = [key for key, record in keys.items() if not wt.holds_installed(found, key, record)]
            checks.append(Check("fail", self.name, "profile keys changed: " + ", ".join(drift), fix) if drift
                          else Check("ok", self.name, f"{len(keys)} profile keys match"))
        records = entry.get("files") or []
        if records:
            changed = [record["path"] for record in records
                       if sha(read(Path(record["path"]))) != record["installed_sha256"]]
            checks.append(Check("fail", self.name, "changed or missing: " + ", ".join(changed), fix) if changed
                          else Check("ok", self.name, f"{len(records)} sky files match"))
        return checks + backup_checks(self.name, [entry.get("backup")])
```

- [ ] **Step 5: Run the whole suite on both Pythons**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .` and `/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .`
Expected: OK on both. In `tests/test_install.py` the images appear in the fake Windows Terminal folder after install and are gone after uninstall, so every byte-for-byte round trip still holds. Any other failing assertion is a regression: fix the code, not the test.

- [ ] **Step 6: Commit**

```bash
git add witchy/components/base.py witchy/runner.py witchy/context.py witchy/components/windows_terminal.py tests/test_base.py tests/test_runner.py tests/test_components_wt.py tests/test_install.py
git commit -m "feat: install the moon-phase sky and ritual config under a shared Windows Terminal lock

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 7: README, spec record and a real-machine check

**Files:**
- Modify: `README.md`, `docs/superpowers/specs/2026-10-02-shell-ritual-design.md`

**Interfaces:**
- Consumes: the finished CLI.
- Produces: documentation only.

- [ ] **Step 1: Update `README.md`**

1. Replace the bullet `- The "Moonlit Candle" colour scheme on your WSL profile in Windows Terminal` with:

```markdown
- Maple Mono NF for your Windows user (no admin rights needed; it stays installed after uninstall)
- On your WSL profile in Windows Terminal: the "Moonlit Candle" colour scheme, Maple Mono NF, a box cursor, a 🌙 tab titled "witchyterm", and a starfield whose moon shows the current phase
```

2. Replace `Components, in install order: \`claude\`, \`windows-terminal\`.` with `Components, in install order: \`claude\`, \`font\`, \`windows-terminal\`.`
3. Replace `Restart Claude Code after installing.` with `Restart Claude Code and Windows Terminal after installing.`
4. In the troubleshooting table, delete the row `| \`another witchy command is running\` | … |` and insert these rows before the `✗ state` row:

```markdown
| `⚠ font  not installed` | Maple Mono NF was not downloaded or registered | `python3 -m witchy install --only font`, then restart Windows Terminal |
| `✗ font  not registered: …` | a font registry value is gone | same as above |
| `✗ windows-terminal  profile keys changed: …` | a profile setting no longer holds the witchy value | `python3 -m witchy install --only windows-terminal`, or keep your change |
| `✗ windows-terminal  changed or missing: …` | a sky image or `ritual-config.json` was edited or deleted | `python3 -m witchy install --only windows-terminal` |
```

5. Replace the row `| \`⚠ windows-terminal  not installed\` | Windows Terminal was not found or the profile did not match | … |` with:

```markdown
| `⚠ windows-terminal  not installed` | `settings.json` was not found (install prints "Windows Terminal settings.json not found") or the profile did not match | pass `--wt-settings PATH` or set `WT_PROFILE_ID`, then install |
```

6. Directly below the table, add: `` `install` and `uninstall` stop with `another witchy command is running` (exit 1) while a second witchy command holds the lock; wait for it to finish. ``

- [ ] **Step 2: Record the decisions in the spec**

In `docs/superpowers/specs/2026-10-02-shell-ritual-design.md`, check that each anchor appears exactly once, then:

1. Section 3.2: replace `records \`skipped: <reason>\` and the runner continues.` with `records \`skipped: <reason>\` (its plan skipped) or \`failed: <reason>\` (applying it failed) and the runner continues.`
2. Section 4.1: after the line beginning `On this machine step 2 selects`, add a paragraph: `` `settings.json` is found first, in this order: `--wt-settings`; the path recorded in state, if it still exists; `%USERPROFILE%` mapped to `/mnt/<drive>/…`; `C:\Users\%USERNAME%`. On this machine the account name and the profile folder differ. ``
3. Section 4.2: replace `It is set only if Maple Mono NF is registered; otherwise it is left untouched and the result is \`skipped\`.` with `It is set only if Maple Mono NF is registered: the \`font\` component is recorded in state, or it is planned in this run and installs successfully. Otherwise the key is left untouched and the summary says so.`
4. Section 4.2: at the end of the bullet beginning `- Install, uninstall and the sky job all take`, append ` The installer holds it only while it writes the Windows Terminal files.`
5. Section 4.3: after the bullet beginning `- Windows Terminal needs a restart`, add the bullet `- A failed download, checksum, copy or \`reg.exe\` call records \`failed: <reason>\` for \`font\`; font files already copied stay (uninstall never removes fonts).`
6. Section 4.4: after the bullet beginning `- **Spike gate:**`, add the bullet `- **Spike result (2026-10-03): passed.** An atomic replace of \`settings.json\` that only changed \`backgroundImage\` was applied to an open tab without a restart, so the eight images and the sky job stay in scope.`

- [ ] **Step 3: Run the full suite on both Pythons**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .` and `/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .`
Expected: OK on both.

- [ ] **Step 4: Real-machine dry run and doctor (controller only)**

The controller, not a subagent, runs these on the real machine. They only read (`cmd.exe` and `reg.exe query` included):

Run: `/usr/bin/python3 -m witchy install --dry-run; echo "exit=$?"`
Expected: `exit=0`; no "settings.json not found" line; the font actions (download, four copies, register); eight `create … moonlit-candle-sky-N.png (binary, …)` lines; a `settings.json` diff that adds the profile keys (including `font` and `backgroundImage`); `create ~/.claude/witchy/ritual-config.json`; the output-style diff from Plan A; no `spinnerTipsOverride` reorder.

Run: `/usr/bin/python3 -m witchy doctor; echo "exit=$?"`
Expected: `⚠ font  not installed` with its fix, `✓ windows-terminal` (the recorded entry has no profile keys yet), and the Plan A output-style `✗ claude` line. Report both outputs verbatim. Do **not** run a real `install`: that is the user's call.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/superpowers/specs/2026-10-02-shell-ritual-design.md
git commit -m "docs: document the font and sky; record plan B decisions in the spec

Co-Authored-By: <the trailer for the model writing this commit>"
```
