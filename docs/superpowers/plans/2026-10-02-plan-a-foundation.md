# Plan A: Foundation (components, state v2, doctor) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the `witchy` installer as an ordered list of components with a v2 state file, then add `doctor`, `mood`, `--only`, a lock and honest exit codes, without changing what gets installed today.

**Architecture:** Each installable piece becomes a component object with `plan / apply / restore / check`. `witchy/runner.py` validates, plans every selected component, then applies them one at a time and saves `state.json` (v2) after each. `install.py` shrinks to re-exports so existing tests and the CLI keep working. Palette data becomes variant-keyed (only `midnight` exists).

**Tech Stack:** Python 3.10+ standard library only (`fcntl`, `dataclasses`, `json`, `argparse`, `unittest`). GitHub Actions for CI.

**Spec:** `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (revision 2). This plan covers spec sections 3 (all), 8 (CLI) and 13 steps 1–3. Plans B (Windows) and C (shell) follow in later sessions.

## Global Constraints

- Python 3.10 or newer, standard library only; every test passes on `/usr/bin/python3` (3.12) and `/usr/bin/python3.10`.
- Test command: `/usr/bin/python3 -m unittest discover -s tests -t .` (run from the repo root).
- No test touches the real `~/.claude`, Windows Terminal, `cmd.exe` or the network: tests use a temporary `HOME`, a fake Windows Terminal `settings.json` passed through `wt_settings`, `run=refuse_cmd`, and `lock_path` inside the temp dir.
- Installer messages are English and neutral in tone. Docstrings and comments are English.
- Exit codes for `install`/`uninstall`: `0` all ok, `1` nothing changed (validation failure, lock busy, abort), `2` done with warnings (a component skipped or failed).
- Every file witchy rewrites is backed up first (`<file>.bak-witchy-YYYYmmdd-HHMMSS`) and written atomically (`jsonio.write_atomic_bytes`). A settings file that is not strict JSON is never rewritten.
- Component order: `claude`, then `windows-terminal` (Plans B and C insert `font` before `windows-terminal` and append `fish`). Uninstall runs in reverse order.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Spec refinements made while planning

These keep the spec's intent and fix details that would break existing guarantees. Task 9 records them in the spec.

1. **Lock location.** The spec says `~/.claude/witchy/.lock`. Uninstall must leave nothing behind in `~/.claude`, so the lock file lives at `$XDG_RUNTIME_DIR/witchy-<uid>.lock` (falling back to the system temp dir). `Context.lock_path` overrides it in tests.
2. **`last_install.at`** is the run's `ctx.stamp` (`YYYYmmdd-HHMMSS`), not an ISO timestamp, so two installs with the same stamp produce the same state.
3. **Variants change colours only.** Theme name, scheme name and installed paths stay `Moonlit Candle` / `moonlit-candle` for every variant, so `mood` never has to move files.
4. **Uninstall exit code.** A restore that cannot be written keeps that component's state entry and exits `2` (was `1`), matching "done with warnings".

## Review Focus

Inputs and failure modes the spec implies but no feature test would naturally hit. Each has a test in the task named.

1. **The real v1 `state.json` on this machine** must migrate without losing a single previous value → Task 3 (fixture from the real file) and Task 7 (v1 state still uninstalls byte-for-byte).
2. **A stale lock file left by a killed process** must not block the next run (flock is released by the OS; the file stays) → Task 7 `test_stale_lock_file_does_not_block`.
3. **`--only` must not disturb other components' state entries** → Task 7 `test_only_runs_named_components_and_keeps_other_entries`.
4. **A damaged `state.json`** must make `doctor` print a `✗` line and exit 1, never a traceback → Task 8 `test_damaged_state_is_a_failure_line`.
5. **A machine without Windows Terminal** (CI, another distro) must install the Claude side, exit `2`, and say what was skipped → Task 7 `test_no_windows_terminal_is_skipped_with_exit_2`.

---

## File structure

| File | Status | Responsibility |
| :- | :- | :- |
| `content/output-style.md` | modify | the user's edited voice, reworded neutrally |
| `.github/workflows/tests.yml` | create | CI on 3.10 and 3.12 |
| `witchy/palette.py` | modify | add `Variant`, `VARIANTS`, `DEFAULT_VARIANT` |
| `witchy/build.py` | modify | `render_outputs(content_dir, variant)` |
| `witchy/validate.py` | modify | validate every variant |
| `witchy/errors.py` | create | `Abort`, `ComponentFailed` |
| `witchy/state.py` | create | load / migrate / save `state.json` v2 |
| `witchy/context.py` | create | `Context` (moved from `install.py`, new fields) |
| `witchy/components/__init__.py` | create | `all_components()`, `NAMES` |
| `witchy/components/base.py` | create | `Change`, `JsonPlan`, `Plan`, `Check`, shared file helpers |
| `witchy/components/claude.py` | create | Claude files and settings keys |
| `witchy/components/windows_terminal.py` | create | Windows Terminal scheme |
| `witchy/runner.py` | create | lock, install, uninstall, doctor, mood |
| `witchy/install.py` | rewrite | thin re-exports for tests and old imports |
| `witchy/wt.py` | modify | public `profile()` helper |
| `witchy/__main__.py` | modify | `--only`, `doctor`, `mood` |
| `README.md` | rewrite | English, new commands, troubleshooting |
| `tests/fixtures/state-v1.json` | create | anonymised real v1 state |
| `tests/test_content.py`, `tests/test_state.py`, `tests/test_components_claude.py`, `tests/test_components_wt.py`, `tests/test_runner.py` | create | new tests |
| `tests/test_install.py`, `tests/test_cli.py`, `tests/test_build.py`, `tests/test_validate.py`, `tests/test_palette.py` | modify | v2 state paths, exit codes, variants |

---

### Task 1: Adopt the edited output style and add CI

**Files:**
- Modify: `content/output-style.md`
- Create: `tests/test_content.py`
- Create: `.github/workflows/tests.yml`

**Interfaces:**
- Consumes: `witchy.content.read_output_style()`, `witchy.validate.validate_all()`
- Produces: nothing used by later tasks.

- [ ] **Step 1: Write the failing test**

Create `tests/test_content.py`:

```python
import unittest

from witchy import content, validate


class OutputStyleTest(unittest.TestCase):
    def test_output_style_names_no_diagnosis(self):
        # The repo is public; the voice rules are what matter, not personal health details.
        self.assertNotIn("ADHD", content.read_output_style())

    def test_output_style_keeps_the_reply_shape_rules(self):
        text = content.read_output_style()
        self.assertIn("## Shape every reply", text)
        self.assertIn("Write for a reader who skims", text)

    def test_content_still_validates(self):
        self.assertEqual([f for f in validate.validate_all() if f.rule == "content"], [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/usr/bin/python3 -m unittest tests.test_content -v`
Expected: FAIL in `test_output_style_keeps_the_reply_shape_rules` (the repo still has the older style without that section).

- [ ] **Step 3: Copy the user's edited style and reword it**

```bash
cp ~/.claude/output-styles/witchynibbles.md content/output-style.md
/usr/bin/python3 - <<'EOF'
from pathlib import Path
path = Path("content/output-style.md")
text = path.read_text(encoding="utf-8")
replacements = {
    "## Shape every reply (ADHD-friendly, low token)": "## Shape every reply (skimmable, low token)",
    "The user has ADHD; long walls of text are hard to read.":
        "Write for a reader who skims: short blocks, one idea per line. Long walls of text are hard to read.",
}
for old, new in replacements.items():
    assert text.count(old) == 1, f"expected exactly one {old!r}"
    text = text.replace(old, new)
assert "ADHD" not in text
path.write_text(text, encoding="utf-8")
EOF
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/usr/bin/python3 -m unittest tests.test_content -v`
Expected: 3 tests PASS.

- [ ] **Step 5: Add the CI workflow**

Create `.github/workflows/tests.yml`:

```yaml
name: tests

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python: ["3.10", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      - name: Install fish (used by the shell tests in Plan C)
        run: sudo apt-get update && sudo apt-get install -y fish
      - name: Run tests
        run: python -m unittest discover -s tests -t . -v
```

- [ ] **Step 6: Run the whole suite**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .`
Expected: OK (all existing tests plus the 3 new ones).

- [ ] **Step 7: Commit**

```bash
git add content/output-style.md tests/test_content.py .github/workflows/tests.yml
git commit -m "feat: adopt the edited output style with neutral wording; add CI

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Variant-ready palette, build and validate

**Files:**
- Modify: `witchy/palette.py` (append at the end)
- Modify: `witchy/build.py` (`render_outputs`)
- Modify: `witchy/validate.py` (`validate_all`)
- Modify: `tests/test_palette.py`, `tests/test_build.py`, `tests/test_validate.py` (append tests)

**Interfaces:**
- Consumes: existing `palette.CLAUDE_OVERRIDES`, `WT_SCHEME`, `STATUSLINE`, `BACKGROUND`, `FOREGROUND`.
- Produces:
  - `palette.Variant` (frozen dataclass: `name: str`, `claude_base: str`, `background: str`, `foreground: str`, `claude_overrides: dict[str, str]`, `wt_scheme: dict[str, str]`, `statusline: dict[str, str]`)
  - `palette.VARIANTS: dict[str, Variant]`, `palette.DEFAULT_VARIANT = "midnight"`
  - `build.render_outputs(content_dir: Path = content.CONTENT_DIR, variant: str = palette.DEFAULT_VARIANT) -> dict[str, str]`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_palette.py` (inside a new class; add `import dataclasses` at the top if missing):

```python
class VariantTest(unittest.TestCase):
    def test_midnight_is_the_default_and_holds_the_module_colours(self):
        midnight = palette.VARIANTS[palette.DEFAULT_VARIANT]
        self.assertEqual(palette.DEFAULT_VARIANT, "midnight")
        self.assertEqual(midnight.claude_base, "dark")
        # Same objects, so mock.patch.dict on the module constants also patches the variant.
        self.assertIs(midnight.claude_overrides, palette.CLAUDE_OVERRIDES)
        self.assertIs(midnight.wt_scheme, palette.WT_SCHEME)
        self.assertIs(midnight.statusline, palette.STATUSLINE)
        self.assertEqual((midnight.background, midnight.foreground), (palette.BACKGROUND, palette.FOREGROUND))
```

Append to `tests/test_build.py` (add `import json` and `from unittest import mock` and `from witchy import palette` if missing):

```python
class VariantBuildTest(unittest.TestCase):
    def test_default_variant_is_midnight(self):
        self.assertEqual(build.render_outputs(variant="midnight"), build.render_outputs())

    def test_render_uses_the_variant_colours(self):
        midnight = palette.VARIANTS["midnight"]
        dawn = palette.Variant("dawn", "light", midnight.background, midnight.foreground,
                               dict(midnight.claude_overrides, claude="#AA5500"), midnight.wt_scheme,
                               midnight.statusline)
        with mock.patch.dict(palette.VARIANTS, {"dawn": dawn}):
            theme = json.loads(build.render_outputs(variant="dawn")[build.THEME])
        self.assertEqual(theme["base"], "light")
        self.assertEqual(theme["overrides"]["claude"], "#AA5500")
        self.assertEqual(theme["name"], palette.THEME_NAME)
```

Append to `tests/test_validate.py` (add `from unittest import mock` and `from witchy import palette` if missing):

```python
class VariantValidateTest(unittest.TestCase):
    def test_every_variant_is_validated(self):
        midnight = palette.VARIANTS["midnight"]
        broken = palette.Variant("broken", "dark", midnight.background, midnight.foreground,
                                 dict(midnight.claude_overrides, claude="#111111"), midnight.wt_scheme,
                                 midnight.statusline)
        with mock.patch.dict(palette.VARIANTS, {"broken": broken}):
            failures = validate.validate_all()
        self.assertIn(("text-contrast", "claude.claude"), {(f.rule, f.item) for f in failures})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_palette tests.test_build tests.test_validate -v`
Expected: FAIL / ERROR with `AttributeError: module 'witchy.palette' has no attribute 'VARIANTS'`.

- [ ] **Step 3: Implement**

Append to `witchy/palette.py` (and add `from dataclasses import dataclass` to its imports):

```python
@dataclass(frozen=True)
class Variant:
    """One complete colour set. Variants change colours only: theme name, scheme name and
    installed paths stay the same, so switching never has to move files."""

    name: str
    claude_base: str
    background: str
    foreground: str
    claude_overrides: dict[str, str]
    wt_scheme: dict[str, str]
    statusline: dict[str, str]


DEFAULT_VARIANT = "midnight"
VARIANTS: dict[str, Variant] = {
    "midnight": Variant("midnight", "dark", BACKGROUND, FOREGROUND, CLAUDE_OVERRIDES, WT_SCHEME, STATUSLINE),
}
```

Replace `render_outputs` in `witchy/build.py`:

```python
def render_outputs(content_dir: Path = content.CONTENT_DIR,
                   variant: str = palette.DEFAULT_VARIANT) -> dict[str, str]:
    colours = palette.VARIANTS[variant]
    spinner = content.load_spinner(content_dir)
    return {
        THEME: _json({"name": palette.THEME_NAME, "base": colours.claude_base, "overrides": colours.claude_overrides}),
        OUTPUT_STYLE: content.read_output_style(content_dir),
        STATUSLINE: statusline_source(colours.statusline),
        TIPS: _json({"tips": spinner["tips"]}),
        WT_SCHEME: _json(colours.wt_scheme),
    }
```

Replace the first line of `validate_all` in `witchy/validate.py` (`failures = validate_palette()`) with:

```python
    failures: list[Failure] = []
    for variant in palette.VARIANTS.values():
        failures += validate_palette(variant.claude_overrides, variant.wt_scheme, variant.statusline,
                                     variant.background, variant.foreground)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add witchy/palette.py witchy/build.py witchy/validate.py tests/test_palette.py tests/test_build.py tests/test_validate.py
git commit -m "feat: make the palette variant-keyed with a single midnight variant

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: State file v2 with v1 migration

**Files:**
- Create: `witchy/errors.py`
- Create: `witchy/state.py`
- Create: `tests/fixtures/state-v1.json` (generated from the real file, anonymised)
- Create: `tests/test_state.py`

**Interfaces:**
- Consumes: `jsonio.read_json`, `jsonio.write_atomic_bytes`, `jsonio.StrictJsonError`, `palette.DEFAULT_VARIANT`.
- Produces:
  - `errors.Abort(Exception)`, `errors.ComponentFailed(Exception)`
  - `state.VERSION = 2`
  - `state.empty(variant: str) -> dict`
  - `state.migrate(v1: dict) -> dict`
  - `state.load(path: Path) -> dict | None` (raises `Abort`)
  - `state.save(path: Path, data: dict) -> None`
  - v2 shape: `{"version": 2, "variant": str, "last_install": {"at": str, "results": {name: str}} | None, "components": {name: entry}}`

- [ ] **Step 1: Generate the anonymised fixture**

```bash
mkdir -p tests/fixtures
/usr/bin/python3 - <<'EOF'
import json, re
from pathlib import Path
src = Path.home() / ".claude" / "witchy" / "state.json"
text = src.read_text(encoding="utf-8")
text = text.replace(str(Path.home()), "/home/user")
text = re.sub(r"/mnt/c/Users/[^/\"]+", "/mnt/c/Users/user", text)
data = json.loads(text)
assert data["version"] == 1, data["version"]
Path("tests/fixtures/state-v1.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
EOF
grep -ciE "eimi|manue" tests/fixtures/state-v1.json
```

Expected: the last command prints `0`. If it prints more, extend the replacements until it prints `0`.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_state.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from witchy import state
from witchy.errors import Abort

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "state-v1.json"


class MigrateTest(unittest.TestCase):
    def test_migrates_the_real_v1_state_keeping_every_record(self):
        v1 = json.loads(FIXTURE.read_text(encoding="utf-8"))
        v2 = state.migrate(v1)
        self.assertEqual(v2["version"], 2)
        self.assertEqual(v2["variant"], "midnight")
        self.assertIsNone(v2["last_install"])
        self.assertEqual(v2["components"]["claude"], {"files": v1["files"], "settings": v1["claude_settings"]})
        self.assertEqual(v2["components"]["windows-terminal"], v1["windows_terminal"])

    def test_v1_without_windows_terminal_has_no_entry(self):
        v1 = {"version": 1, "files": [], "claude_settings": {"keys": {}}, "windows_terminal": None}
        self.assertNotIn("windows-terminal", state.migrate(v1)["components"])


class LoadSaveTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "witchy" / "state.json"

    def test_missing_file_is_none(self):
        self.assertIsNone(state.load(self.path))

    def test_save_then_load_round_trips(self):
        data = dict(state.empty("midnight"), components={"claude": {"files": []}})
        state.save(self.path, data)
        self.assertEqual(state.load(self.path), data)

    def test_v1_file_loads_as_v2(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
        self.assertEqual(state.load(self.path)["version"], 2)

    def test_damaged_file_aborts(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{", encoding="utf-8")
        with self.assertRaises(Abort) as raised:
            state.load(self.path)
        self.assertIn("The state file is damaged", str(raised.exception))

    def test_unknown_version_aborts(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"version": 9}', encoding="utf-8")
        with self.assertRaises(Abort) as raised:
            state.load(self.path)
        self.assertIn("unknown format", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_state -v`
Expected: ERROR `ModuleNotFoundError: No module named 'witchy.errors'`.

- [ ] **Step 4: Implement**

Create `witchy/errors.py`:

```python
"""Exceptions shared by the runner and the components."""
from __future__ import annotations


class Abort(Exception):
    """Stop before anything is written; the message says why."""


class ComponentFailed(Exception):
    """A component could not finish; the message is the reason recorded in state."""
```

Create `witchy/state.py`:

```python
"""state.json: what witchy installed, and what every setting held before."""
from __future__ import annotations

import json
from pathlib import Path

from . import jsonio, palette
from .errors import Abort

VERSION = 2


def empty(variant: str) -> dict:
    return {"version": VERSION, "variant": variant, "last_install": None, "components": {}}


def migrate(v1: dict) -> dict:
    """Turn a version 1 state (written before components existed) into version 2, keeping every record."""
    components = {"claude": {"files": v1["files"], "settings": v1["claude_settings"]}}
    if v1.get("windows_terminal"):
        components["windows-terminal"] = v1["windows_terminal"]
    return {"version": VERSION, "variant": palette.DEFAULT_VARIANT, "last_install": None, "components": components}


def load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data, _ = jsonio.read_json(path)
    except jsonio.StrictJsonError as exc:
        raise Abort(f"{exc}\nThe state file is damaged; fix or remove {path} by hand.") from exc
    version = data.get("version") if isinstance(data, dict) else None
    if version == 1:
        return migrate(data)
    if version == VERSION:
        return data
    raise Abort(f"{path} has an unknown format; fix or remove it by hand.")


def save(path: Path, data: dict) -> None:
    jsonio.write_atomic_bytes(path, (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `/usr/bin/python3 -m unittest tests.test_state -v`
Expected: 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add witchy/errors.py witchy/state.py tests/fixtures/state-v1.json tests/test_state.py
git commit -m "feat: add state.json v2 with migration from v1

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Move shared pieces into `context.py` and `components/base.py` (no behaviour change)

**Files:**
- Create: `witchy/context.py`
- Create: `witchy/components/__init__.py` (empty for now: a one-line docstring)
- Create: `witchy/components/base.py`
- Modify: `witchy/install.py` (import the moved pieces instead of defining them)

**Interfaces:**
- Consumes: `errors.Abort`, `errors.ComponentFailed`, `jsonio`.
- Produces:
  - `context.Context` dataclass with every existing field plus `only: tuple[str, ...] = ()`, `lock_path: Path | None = None`, `variant: str | None = None`, `outputs: dict[str, str] | None = None`; properties `claude_dir`, `state_path`, `lock_file`; method `say(message)`.
  - In `components/base.py`: `sha(data)`, `read(path)`, `Change`, `JsonPlan`, `Plan`, `Check`, `Component` (Protocol), `fix_command(name) -> str`, `backup_checks(name, backups) -> list[Check]`, `check_unchanged(changes)`, `show_changes(ctx, changes)`, `apply_changes(ctx, changes) -> dict[Path, Path]`, `restore_copy(entry) -> Change | None`, `restore_json(entry, restore, warnings) -> Change | None`. `Abort` and `ComponentFailed` are re-exported from `base`.

- [ ] **Step 1: Create `witchy/context.py`**

```python
"""Everything a command needs to know about where it runs."""
from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, TextIO

from . import build


@dataclass
class Context:
    home: Path
    env: Mapping[str, str]
    out: TextIO
    dry_run: bool = False
    wt_settings: Path | None = None
    python: str | None = None
    stamp: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d-%H%M%S"))
    run: Callable[..., Any] = subprocess.run
    dist: Path = field(default_factory=lambda: build.DIST)
    only: tuple[str, ...] = ()
    lock_path: Path | None = None
    variant: str | None = None
    outputs: dict[str, str] | None = None

    @property
    def claude_dir(self) -> Path:
        return self.home / ".claude"

    @property
    def state_path(self) -> Path:
        return self.claude_dir / "witchy" / "state.json"

    @property
    def lock_file(self) -> Path:
        # Outside HOME on purpose: uninstall must leave nothing behind in ~/.claude.
        if self.lock_path is not None:
            return self.lock_path
        base = self.env.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
        return Path(base) / f"witchy-{os.getuid()}.lock"

    def say(self, message: str) -> None:
        print(message, file=self.out)
```

- [ ] **Step 2: Create `witchy/components/__init__.py`**

```python
"""The pieces witchy installs, in the order they are installed."""
```

- [ ] **Step 3: Create `witchy/components/base.py`**

The bodies of `Change`, `JsonPlan`, `check_unchanged`, `show_changes`, `apply_changes`, `restore_copy` and `restore_json` are moved verbatim from `install.py` (`Change`, `JsonPlan`, `_check_unchanged`, `_show`, `_apply`, `_restore_copy`, `_restore_json`), with `_sha`/`_read` renamed to `sha`/`read`:

```python
"""What every component shares: planned file changes, plans, doctor checks, careful writes."""
from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from .. import jsonio
from ..errors import Abort, ComponentFailed

__all__ = ["Abort", "ComponentFailed", "Change", "JsonPlan", "Plan", "Check", "Component", "sha", "read",
           "fix_command", "backup_checks", "check_unchanged", "show_changes", "apply_changes",
           "restore_copy", "restore_json"]


def sha(data: bytes | None) -> str | None:
    return None if data is None else hashlib.sha256(data).hexdigest()


def read(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


@dataclass
class Change:
    """One file's planned content; ``None`` means absent (before) or deleted (after)."""

    path: Path
    before: bytes | None
    after: bytes | None
    backup: bool = True


@dataclass
class JsonPlan:
    """A planned settings-file rewrite plus what state.json must remember about it."""

    change: Change
    previous: dict | None
    extra: dict

    def entry(self, backup: Path | None) -> dict:
        after = sha(self.change.after)
        if self.previous:
            # The first backup stays the right restore target while each reinstall overwrites exactly what
            # witchy wrote last time; a file someone else edited in between is restored key by key instead.
            ok = self.previous["byte_restore_ok"] and sha(self.change.before) == self.previous["installed_sha256"]
            base = {**self.previous, "installed_sha256": after, "byte_restore_ok": ok}
        else:
            existed = self.change.before is not None
            base = {"path": str(self.change.path), "existed": existed,
                    "backup": str(backup) if backup else None, "installed_sha256": after,
                    "byte_restore_ok": not existed or backup is not None}
        return {**base, **self.extra}


@dataclass
class Plan:
    """What a component will do. ``skip`` set means it will do nothing, and says why."""

    changes: list[Change] = field(default_factory=list)
    skip: str | None = None
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def skipped(cls, reason: str) -> Plan:
        return cls(skip=reason)


@dataclass(frozen=True)
class Check:
    """One doctor line. ``level`` is "ok", "warn" or "fail"; ``fix`` is a command to run."""

    level: str
    component: str
    message: str
    fix: str = ""


class Component(Protocol):
    name: str

    def plan(self, ctx: Any, entry: dict | None) -> Plan: ...

    def apply(self, ctx: Any, plan: Plan) -> dict: ...

    def restore(self, ctx: Any, entry: dict) -> Plan: ...

    def check(self, ctx: Any, entry: dict) -> list[Check]: ...


def fix_command(name: str) -> str:
    return f"python3 -m witchy install --only {name}"


def backup_checks(name: str, backups: list[str | None]) -> list[Check]:
    return [Check("warn", name, f"backup {path} is missing; uninstall cannot give back the original bytes")
            for path in backups if path and not Path(path).exists()]


def check_unchanged(changes: list[Change]) -> None:
    """Planning and writing are apart in time (the cmd.exe lookup); never overwrite what another program wrote."""
    for change in changes:
        if read(change.path) != change.before:
            raise Abort(f"{change.path} changed while planning; nothing was written. Run the command again.")


def show_changes(ctx: Any, changes: list[Change]) -> None:
    for change in changes:
        if change.before == change.after:
            continue
        if change.before is None:
            ctx.say(f"create {change.path} ({len(change.after.splitlines())} lines)")
        elif change.after is None:
            ctx.say(f"remove {change.path}")
        else:
            before = change.before.decode("utf-8", "replace").splitlines(keepends=True)
            after = change.after.decode("utf-8", "replace").splitlines(keepends=True)
            ctx.out.writelines(difflib.unified_diff(before, after, f"{change.path} (now)", f"{change.path} (after)"))
            ctx.say("")


def apply_changes(ctx: Any, changes: list[Change]) -> dict[Path, Path]:
    backups: dict[Path, Path] = {}
    for change in changes:
        if change.before == change.after:
            continue
        if change.before is not None and change.backup:
            backups[change.path] = jsonio.backup(change.path, ctx.stamp)
        if change.after is None:
            change.path.unlink(missing_ok=True)
            verb = "removed"
        else:
            jsonio.write_atomic_bytes(change.path, change.after)
            verb = "created" if change.before is None else "updated"
        note = f" (backup: {backups[change.path]})" if change.path in backups else ""
        ctx.say(f"{verb} {change.path}{note}")
    return backups


def restore_copy(entry: dict) -> Change | None:
    path = Path(entry["path"])
    current = read(path)
    original = read(Path(entry["backup"])) if entry.get("backup") else None
    if current is None and original is None:
        return None
    # Keep a copy of anything the user edited (for example with /theme → Ctrl+E) before it goes.
    edited = current is not None and sha(current) != entry["installed_sha256"]
    return Change(path, current, original, backup=edited)


def restore_json(entry: dict, restore: Callable[[dict], tuple[dict, list[str]]], warnings: list[str]) -> Change | None:
    path = Path(entry["path"])
    current = read(path)
    if current is None:
        # A file witchy created and an earlier uninstall already removed is back to how it started.
        if entry["existed"]:
            warnings.append(f"{path} no longer exists; nothing to restore there.")
        return None
    if entry["byte_restore_ok"] and sha(current) == entry["installed_sha256"]:
        if not entry["existed"]:
            return Change(path, current, None, backup=False)
        original = read(Path(entry["backup"])) if entry.get("backup") else None
        if original is not None:
            return Change(path, current, original, backup=False)
    try:
        data, text = jsonio.read_json(path)
    except jsonio.StrictJsonError:
        warnings.append(f"{path} is no longer plain JSON; restore it by hand from {entry.get('backup')}.")
        return None
    if not isinstance(data, dict):
        warnings.append(f"{path} no longer holds a JSON object; restore it by hand from {entry.get('backup')}.")
        return None
    restored, notes = restore(data)
    warnings.extend(notes)
    if notes and entry.get("backup"):
        warnings.append(f"The file as it was before install is kept at {entry['backup']}.")
    if restored == data:
        return None
    return Change(path, current, jsonio.dumps_like(restored, text).encode("utf-8"))
```

- [ ] **Step 4: Make `install.py` use the moved pieces**

In `witchy/install.py`:
1. Delete the definitions of `_sha`, `_read`, `Abort`, `Change`, `JsonPlan`, `Context`, `_check_unchanged`, `_show`, `_apply`, `_restore_copy`. Keep `_restore_json` as a module-level name (a test patches it) by assigning it.
2. Add these imports and aliases below the existing `from . import ...` line:

```python
from .components.base import (Abort, Change, JsonPlan, apply_changes as _apply, check_unchanged as _check_unchanged,
                              read as _read, restore_copy as _restore_copy, restore_json, sha as _sha,
                              show_changes as _show)
from .context import Context

_restore_json = restore_json
```

3. In `uninstall`, the call `_restore_json(...)` stays as is (it now resolves to the alias, which `mock.patch("witchy.install._restore_json")` still replaces).
4. Remove imports that became unused (`difflib`, `hashlib`, `dataclass`, `field`, `datetime`), keeping `json`, `subprocess`, `sys`, `Path`, typing names still referenced.

- [ ] **Step 5: Run the whole suite**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .`
Expected: OK with the same test count as after Task 3. This task changes no behaviour.

- [ ] **Step 6: Commit**

```bash
git add witchy/context.py witchy/components/__init__.py witchy/components/base.py witchy/install.py
git commit -m "refactor: move Context and file helpers into context.py and components/base.py

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The `claude` component

**Files:**
- Create: `witchy/components/claude.py`
- Create: `tests/test_components_claude.py`

**Interfaces:**
- Consumes: `base.*` from Task 4, `context.Context`, `build.render_outputs`, `claude_settings.desired_keys/apply_keys/restore_keys`, `content.load_spinner`, `records.snapshot`.
- Produces:
  - `components.claude.ClaudeComponent` with `name = "claude"` and `plan / apply / restore / check`.
  - Entry shape: `{"files": [{"path", "backup", "installed_sha256"}], "settings": JsonPlan.entry(...)}` (the v1 `files` / `claude_settings` records, unchanged).
  - Module constants `COPIES` (dist path → path relative to HOME), `RESTART_NOTE`, `DEFAULT_PYTHON`; function `python_for(ctx) -> str`.
  - `plan` reads `ctx.outputs` (set by the runner) and raises `Abort` when `~/.claude/settings.json` is not a plain JSON object.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_components_claude.py`:

```python
import io
import json
import tempfile
import unittest
from pathlib import Path

from witchy import build
from witchy.components.base import Abort, apply_changes
from witchy.components.claude import RESTART_NOTE, ClaudeComponent
from witchy.context import Context


class ClaudeComponentTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.claude = self.home / ".claude"
        self.claude.mkdir(parents=True)
        self.settings = self.claude / "settings.json"
        self.settings.write_text(json.dumps({"theme": "dark", "model": "opus"}, indent=2) + "\n", encoding="utf-8")
        self.component = ClaudeComponent()

    def ctx(self, stamp="20261002-120000"):
        self.out = io.StringIO()
        ctx = Context(home=self.home, env={}, out=self.out, python="/usr/bin/python3", stamp=stamp,
                      dist=self.root / "dist", variant="midnight")
        ctx.outputs = build.render_outputs(variant="midnight")
        return ctx

    def install(self):
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        return ctx, plan, self.component.apply(ctx, plan)

    def data(self):
        return json.loads(self.settings.read_text(encoding="utf-8"))

    def test_apply_writes_files_and_returns_the_entry(self):
        _, plan, entry = self.install()
        self.assertEqual(self.component.name, "claude")
        self.assertEqual(len(entry["files"]), 4)
        for record in entry["files"]:
            self.assertTrue(Path(record["path"]).is_file(), record["path"])
            self.assertTrue(record["path"].startswith(str(self.claude)))
        self.assertEqual(entry["settings"]["keys"]["theme"]["previous"], {"value": "dark"})
        self.assertEqual(self.data()["theme"], "custom:moonlit-candle")
        self.assertEqual(self.data()["model"], "opus")
        self.assertIn(RESTART_NOTE, plan.notes)

    def test_restore_gives_back_settings_before_removing_copies(self):
        ctx, _, entry = self.install()
        plan = self.component.restore(self.ctx(stamp="20261002-130000"), entry)
        self.assertEqual(plan.changes[0].path, self.settings)
        apply_changes(ctx, plan.changes)
        self.assertEqual(self.data(), {"theme": "dark", "model": "opus"})
        self.assertFalse((self.claude / "themes" / "moonlit-candle.json").exists())

    def test_check_is_ok_after_install(self):
        ctx, _, entry = self.install()
        self.assertEqual({check.level for check in self.component.check(ctx, entry)}, {"ok"})

    def test_check_fails_when_a_key_drifts(self):
        ctx, _, entry = self.install()
        self.settings.write_text(json.dumps(dict(self.data(), theme="light"), indent=2) + "\n", encoding="utf-8")
        fails = [c for c in self.component.check(ctx, entry) if c.level == "fail"]
        self.assertEqual(len(fails), 1)
        self.assertIn("theme", fails[0].message)
        self.assertEqual(fails[0].fix, "python3 -m witchy install --only claude")

    def test_check_fails_when_an_installed_file_changes(self):
        ctx, _, entry = self.install()
        (self.claude / "witchy" / "statusline.py").write_text("# edited\n", encoding="utf-8")
        fails = [c for c in self.component.check(ctx, entry) if c.level == "fail"]
        self.assertTrue(any("statusline.py" in c.message for c in fails))

    def test_check_warns_when_the_settings_backup_is_gone(self):
        ctx, _, entry = self.install()
        Path(entry["settings"]["backup"]).unlink()
        warns = [c for c in self.component.check(ctx, entry) if c.level == "warn"]
        self.assertTrue(any("backup" in c.message for c in warns))

    def test_settings_with_comments_abort_the_plan(self):
        self.settings.write_text('{\n  // a comment\n  "theme": "dark"\n}\n', encoding="utf-8")
        with self.assertRaises(Abort):
            self.component.plan(self.ctx(), None)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_components_claude -v`
Expected: ERROR `ModuleNotFoundError: No module named 'witchy.components.claude'`.

- [ ] **Step 3: Implement `witchy/components/claude.py`**

```python
"""claude: the theme, output style, status line and tips files, and the five settings keys."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .. import build, claude_settings, content, jsonio
from ..records import snapshot
from .base import (Abort, Change, Check, JsonPlan, Plan, apply_changes, backup_checks, fix_command, read,
                   restore_copy, restore_json, sha)

DEFAULT_PYTHON = "/usr/bin/python3"
RESTART_NOTE = "Restart Claude Code once so it starts watching ~/.claude/themes/"

# dist/ file -> its home, relative to HOME
COPIES = {
    build.THEME: Path(".claude/themes/moonlit-candle.json"),
    build.OUTPUT_STYLE: Path(".claude/output-styles/witchynibbles.md"),
    build.STATUSLINE: Path(".claude/witchy/statusline.py"),
    build.TIPS: Path(".claude/witchy/tips.json"),
}


def python_for(ctx: Any) -> str:
    # Not the pyenv shim: its version follows each project's .python-version.
    if ctx.python:
        return ctx.python
    return DEFAULT_PYTHON if Path(DEFAULT_PYTHON).is_file() else sys.executable


class ClaudeComponent:
    name = "claude"

    def plan(self, ctx: Any, entry: dict | None) -> Plan:
        earlier = {Path(record["path"]): record for record in (entry or {}).get("files", [])}
        files, changes = [], []
        for rel, target in COPIES.items():
            path = ctx.home / target
            before = read(path)
            after = ctx.outputs[rel].encode("utf-8")
            previous = earlier.get(path)
            ours = previous is not None and sha(before) == previous["installed_sha256"]
            changes.append(Change(path, before, after, backup=not ours))
            files.append((path, previous, after))
        settings = self._plan_settings(ctx, (entry or {}).get("settings"))
        notes = [] if (ctx.claude_dir / "themes").is_dir() else [RESTART_NOTE]
        return Plan(changes=[*changes, settings.change], notes=notes, data={"files": files, "settings": settings})

    def _plan_settings(self, ctx: Any, previous: dict | None) -> JsonPlan:
        path = ctx.claude_dir / "settings.json"
        before = read(path)
        data, text = {}, None
        if before is not None:
            try:
                data, text = jsonio.read_json(path)
            except jsonio.StrictJsonError as exc:
                raise Abort(f"{exc}\n{path} is not plain JSON; nothing was changed.") from exc
            if not isinstance(data, dict):
                raise Abort(f"{path} does not hold a JSON object; nothing was changed.")
        desired = claude_settings.desired_keys(ctx.home, python_for(ctx), content.load_spinner()["verbs"])
        new_data, keys = claude_settings.apply_keys(data, desired, previous["keys"] if previous else None)
        after = jsonio.dumps_like(new_data, text).encode("utf-8")
        return JsonPlan(Change(path, before, after), previous, {"keys": keys})

    def apply(self, ctx: Any, plan: Plan) -> dict:
        backups = apply_changes(ctx, plan.changes)
        settings: JsonPlan = plan.data["settings"]
        return {
            "files": [
                {"path": str(path),
                 "backup": previous["backup"] if previous else (str(backups[path]) if path in backups else None),
                 "installed_sha256": sha(after)}
                for path, previous, after in plan.data["files"]
            ],
            "settings": settings.entry(backups.get(settings.change.path)),
        }

    def restore(self, ctx: Any, entry: dict) -> Plan:
        warnings: list[str] = []
        record = entry["settings"]
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
        record = entry["settings"]
        try:
            data, _ = jsonio.read_json(Path(record["path"]))
        except (OSError, jsonio.StrictJsonError) as exc:
            checks.append(Check("fail", self.name, f"cannot read {record['path']}: {exc}", fix))
        else:
            data = data if isinstance(data, dict) else {}
            drift = [key for key, key_record in record["keys"].items()
                     if snapshot(data, key) != {"value": key_record["installed"]}]
            if drift:
                checks.append(Check("fail", self.name, "settings changed: " + ", ".join(drift), fix))
            else:
                checks.append(Check("ok", self.name, f"theme {claude_settings.THEME} active, "
                                                     f"{len(record['keys'])} settings keys match"))
        checks.extend(backup_checks(self.name, [record.get("backup"), *(f.get("backup") for f in entry["files"])]))
        return checks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m unittest tests.test_components_claude -v`
Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add witchy/components/claude.py tests/test_components_claude.py
git commit -m "feat: add the claude component

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The `windows-terminal` component

**Files:**
- Modify: `witchy/wt.py` (add public `profile`)
- Create: `witchy/components/windows_terminal.py`
- Create: `tests/test_components_wt.py`

**Interfaces:**
- Consumes: `base.*`, `wt.locate_settings/find_profile/apply_scheme/restore_scheme/manual_snippet`, `palette.VARIANTS`.
- Produces:
  - `wt.profile(data, guid) -> dict | None`
  - `components.windows_terminal.WindowsTerminalComponent` with `name = "windows-terminal"`; constant `WT_SKIP`.
  - Entry shape: the v1 `windows_terminal` record (`path`, `existed`, `backup`, `installed_sha256`, `byte_restore_ok`, `profile_guid`, `previous_color_scheme`, `previous_scheme`, `schemes_key_absent`, `installed_color_scheme`).
  - `plan` returns `Plan.skipped(reason)` (after printing the existing message) when the settings file is missing, not plain JSON, has no matching profile, belongs to another profile's install, or `apply_scheme` raises `ValueError`.
  - `apply` raises `ComponentFailed` when the write fails (after printing the existing message).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_components_wt.py`:

```python
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy.components.base import ComponentFailed, apply_changes
from witchy.components.windows_terminal import WindowsTerminalComponent
from witchy.context import Context

UBUNTU = "{05f3f843-450a-55ad-a264-cacf368dafe5}"
WT = {"profiles": {"defaults": {}, "list": [
    {"guid": UBUNTU, "name": "Ubuntu", "source": "Microsoft.WSL", "colorScheme": "One Half Dark"}]}, "schemes": []}


def refuse_cmd(*args, **kwargs):
    raise AssertionError("cmd.exe must not run in tests")


class WindowsTerminalComponentTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.wt = self.root / "settings.json"
        self.wt.write_text(json.dumps(WT, indent=4) + "\n", encoding="utf-8")
        self.component = WindowsTerminalComponent()

    def ctx(self, wt_settings=None, stamp="20261002-120000"):
        self.out = io.StringIO()
        return Context(home=self.root / "home", env={"WT_PROFILE_ID": UBUNTU}, out=self.out,
                       wt_settings=wt_settings or self.wt, stamp=stamp, run=refuse_cmd, variant="midnight")

    def ubuntu(self):
        return json.loads(self.wt.read_text(encoding="utf-8"))["profiles"]["list"][0]

    def install(self):
        ctx = self.ctx()
        return ctx, self.component.apply(ctx, self.component.plan(ctx, None))

    def test_apply_sets_the_scheme_and_returns_the_record(self):
        _, entry = self.install()
        self.assertEqual(self.component.name, "windows-terminal")
        self.assertEqual(self.ubuntu()["colorScheme"], "Moonlit Candle")
        self.assertEqual(entry["profile_guid"], UBUNTU)
        self.assertEqual(entry["previous_color_scheme"], {"value": "One Half Dark"})

    def test_missing_settings_file_is_skipped(self):
        plan = self.component.plan(self.ctx(wt_settings=self.root / "nope.json"), None)
        self.assertEqual(plan.skip, "settings.json not found")

    def test_settings_with_comments_are_skipped_with_a_snippet(self):
        self.wt.write_text('{\n  // comment\n  "profiles": []\n}\n', encoding="utf-8")
        plan = self.component.plan(self.ctx(), None)
        self.assertEqual(plan.skip, "settings.json is not plain JSON")
        self.assertIn('"schemes"', self.out.getvalue())

    def test_failed_write_raises_component_failed(self):
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        with mock.patch("witchy.jsonio.write_atomic_bytes", side_effect=PermissionError(13, "denied")):
            with self.assertRaises(ComponentFailed):
                self.component.apply(ctx, plan)

    def test_restore_gives_back_the_previous_scheme(self):
        ctx, entry = self.install()
        apply_changes(ctx, self.component.restore(self.ctx(stamp="20261002-130000"), entry).changes)
        self.assertEqual(self.ubuntu()["colorScheme"], "One Half Dark")

    def test_check_is_ok_then_fails_when_the_scheme_changes(self):
        ctx, entry = self.install()
        self.assertEqual({c.level for c in self.component.check(ctx, entry)}, {"ok"})
        data = json.loads(self.wt.read_text(encoding="utf-8"))
        data["profiles"]["list"][0]["colorScheme"] = "Campbell"
        self.wt.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        fails = [c for c in self.component.check(ctx, entry) if c.level == "fail"]
        self.assertEqual(len(fails), 1)
        self.assertIn("Campbell", fails[0].message)
        self.assertEqual(fails[0].fix, "python3 -m witchy install --only windows-terminal")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_components_wt -v`
Expected: ERROR `ModuleNotFoundError: No module named 'witchy.components.windows_terminal'`.

- [ ] **Step 3: Add `wt.profile`**

In `witchy/wt.py`, directly after `_profile`:

```python
def profile(data: Any, guid: str) -> dict | None:
    """The profile with this GUID (case-insensitive), or None."""
    return _profile(data, guid)
```

- [ ] **Step 4: Implement `witchy/components/windows_terminal.py`**

```python
"""windows-terminal: the Moonlit Candle colour scheme on the WSL profile."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import jsonio, palette, wt
from .base import (Change, Check, ComponentFailed, JsonPlan, Plan, apply_changes, backup_checks, fix_command,
                   restore_json)

WT_SKIP = "skipping the terminal colour scheme"


class WindowsTerminalComponent:
    name = "windows-terminal"

    def plan(self, ctx: Any, entry: dict | None) -> Plan:
        scheme = palette.VARIANTS[ctx.variant or palette.DEFAULT_VARIANT].wt_scheme
        path = wt.locate_settings(ctx.wt_settings, run=ctx.run)
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
        try:
            new_data, record = wt.apply_scheme(data, scheme, guid, entry)
        except ValueError as exc:
            ctx.say(f"Windows Terminal: {exc}; {WT_SKIP}.")
            return Plan.skipped(str(exc))
        change = Change(path, path.read_bytes(), jsonio.dumps_like(new_data, text).encode("utf-8"))
        return Plan(changes=[change], data={"json": JsonPlan(change, entry, record)})

    def apply(self, ctx: Any, plan: Plan) -> dict:
        json_plan: JsonPlan = plan.data["json"]
        try:
            backups = apply_changes(ctx, plan.changes)
        except OSError as exc:
            ctx.say(f"Windows Terminal: could not write {json_plan.change.path} ({exc}); {WT_SKIP}.")
            raise ComponentFailed(f"could not write {json_plan.change.path}") from exc
        return json_plan.entry(backups.get(json_plan.change.path))

    def restore(self, ctx: Any, entry: dict) -> Plan:
        warnings: list[str] = []
        change = restore_json(entry, lambda data: wt.restore_scheme(data, entry), warnings)
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
        return checks + backup_checks(self.name, [entry.get("backup")])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `/usr/bin/python3 -m unittest tests.test_components_wt -v`
Expected: 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add witchy/wt.py witchy/components/windows_terminal.py tests/test_components_wt.py
git commit -m "feat: add the windows-terminal component

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The runner — install and uninstall through components

**Files:**
- Modify: `witchy/components/__init__.py`
- Create: `witchy/runner.py` (install, uninstall, lock; doctor and mood come in Task 8)
- Rewrite: `witchy/install.py`
- Create: `tests/test_runner.py`
- Modify: `tests/test_install.py`

**Interfaces:**
- Consumes: Tasks 2–6.
- Produces:
  - `components.all_components() -> list` (`[ClaudeComponent(), WindowsTerminalComponent()]`), `components.NAMES: tuple[str, ...]`
  - `runner.locked(ctx)` context manager (raises `Abort(LOCK_BUSY)`)
  - `runner.install(ctx, components=None) -> int`, `runner.uninstall(ctx, components=None) -> int`
  - Constants `runner.LOCK_BUSY`, `runner.INSTALLED`, `runner.NEW_SESSION_NOTE`
  - `install.py` re-exports: `Context`, `Abort`, `Change`, `install`, `uninstall`, `RESTART_NOTE`, `NEW_SESSION_NOTE`, `WT_SKIP`, `DEFAULT_PYTHON`, and the modules `build`, `claude_settings`, `content`, `jsonio`, `palette`, `validate`, `wt` (tests patch through `witchy.install.<module>`).

- [ ] **Step 1: Write the failing runner tests**

Create `tests/test_runner.py`:

```python
import fcntl
import io
import json
import tempfile
import unittest
from pathlib import Path

from witchy import runner, state
from witchy.components.base import Abort, Change, ComponentFailed, Plan
from witchy.context import Context


class Fake:
    """A component that records what the runner asks of it."""

    def __init__(self, name, log, skip=None, fail=False, abort=False, on_apply=None, restore_changes=None):
        self.name, self.log, self.skip, self.fail, self.abort = name, log, skip, fail, abort
        self.on_apply = on_apply
        self.restore_changes = restore_changes or []

    def plan(self, ctx, entry):
        self.log.append(("plan", self.name))
        if self.abort:
            raise Abort(f"{self.name} refuses")
        return Plan.skipped(self.skip) if self.skip else Plan(notes=[f"{self.name} note"])

    def apply(self, ctx, plan):
        self.log.append(("apply", self.name))
        if self.on_apply:
            self.on_apply(ctx)
        if self.fail:
            raise ComponentFailed("boom")
        return {"installed": self.name}

    def restore(self, ctx, entry):
        self.log.append(("restore", self.name))
        return Plan(changes=list(self.restore_changes))

    def check(self, ctx, entry):
        return []


class RunnerTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.log = []

    def ctx(self, **kwargs):
        self.out = io.StringIO()
        return Context(home=self.home, env={}, out=self.out, stamp="20261002-120000", dist=self.root / "dist",
                       lock_path=self.root / "witchy.lock", **kwargs)

    def state(self):
        return json.loads((self.home / ".claude" / "witchy" / "state.json").read_text(encoding="utf-8"))

    def write_state(self, components):
        state.save(self.home / ".claude" / "witchy" / "state.json", dict(state.empty("midnight"), components=components))


class InstallRunnerTest(RunnerTestCase):
    def test_installs_in_order_and_records_results(self):
        a, b = Fake("a", self.log), Fake("b", self.log)
        self.assertEqual(runner.install(self.ctx(), [a, b]), 0)
        self.assertEqual(self.log, [("plan", "a"), ("plan", "b"), ("apply", "a"), ("apply", "b")])
        data = self.state()
        self.assertEqual(data["version"], 2)
        self.assertEqual(data["variant"], "midnight")
        self.assertEqual(data["components"], {"a": {"installed": "a"}, "b": {"installed": "b"}})
        self.assertEqual(data["last_install"], {"at": "20261002-120000", "results": {"a": "ok", "b": "ok"}})
        self.assertIn("2/2 components installed", self.out.getvalue())
        self.assertIn("a note", self.out.getvalue())

    def test_state_is_saved_after_each_component(self):
        seen = []
        b = Fake("b", self.log, on_apply=lambda ctx: seen.append(json.loads(ctx.state_path.read_text())["components"]))
        runner.install(self.ctx(), [Fake("a", self.log), b])
        self.assertEqual(seen, [{"a": {"installed": "a"}}])

    def test_skipped_component_exits_2_and_keeps_its_old_entry(self):
        self.write_state({"b": {"old": True}})
        code = runner.install(self.ctx(), [Fake("a", self.log), Fake("b", self.log, skip="nope")])
        self.assertEqual(code, 2)
        self.assertEqual(self.state()["components"]["b"], {"old": True})
        self.assertEqual(self.state()["last_install"]["results"]["b"], "skipped: nope")
        self.assertIn("1/2 components installed · skipped: b (nope)", self.out.getvalue())

    def test_failed_component_exits_2(self):
        code = runner.install(self.ctx(), [Fake("a", self.log), Fake("b", self.log, fail=True)])
        self.assertEqual(code, 2)
        self.assertEqual(self.state()["last_install"]["results"]["b"], "failed: boom")
        self.assertNotIn("b", self.state()["components"])

    def test_abort_while_planning_exits_1_and_applies_nothing(self):
        code = runner.install(self.ctx(), [Fake("a", self.log), Fake("b", self.log, abort=True)])
        self.assertEqual(code, 1)
        self.assertNotIn(("apply", "a"), self.log)
        self.assertIn("b refuses", self.out.getvalue())

    def test_lock_busy_exits_1_and_writes_nothing(self):
        with open(self.root / "witchy.lock", "a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            code = runner.install(self.ctx(), [Fake("a", self.log)])
        self.assertEqual(code, 1)
        self.assertIn(runner.LOCK_BUSY, self.out.getvalue())
        self.assertEqual(self.log, [])
        self.assertFalse((self.home / ".claude").exists())

    def test_stale_lock_file_does_not_block(self):
        (self.root / "witchy.lock").write_text("", encoding="utf-8")
        self.assertEqual(runner.install(self.ctx(), [Fake("a", self.log)]), 0)

    def test_dry_run_takes_no_lock_and_writes_nothing(self):
        with open(self.root / "witchy.lock", "a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            code = runner.install(self.ctx(dry_run=True), [Fake("a", self.log)])
        self.assertEqual(code, 0)
        self.assertEqual(self.log, [("plan", "a")])
        self.assertFalse((self.home / ".claude").exists())

    def test_only_runs_named_components_and_keeps_other_entries(self):
        self.write_state({"b": {"old": True}})
        code = runner.install(self.ctx(only=("a",)), [Fake("a", self.log), Fake("b", self.log)])
        self.assertEqual(code, 0)
        self.assertEqual(self.log, [("plan", "a"), ("apply", "a")])
        self.assertEqual(self.state()["components"], {"a": {"installed": "a"}, "b": {"old": True}})


class UninstallRunnerTest(RunnerTestCase):
    def test_uninstall_runs_in_reverse_order_and_removes_state(self):
        a, b = Fake("a", self.log), Fake("b", self.log)
        runner.install(self.ctx(), [a, b])
        self.log.clear()
        self.assertEqual(runner.uninstall(self.ctx(), [a, b]), 0)
        self.assertEqual(self.log, [("restore", "b"), ("restore", "a")])
        self.assertFalse((self.home / ".claude" / "witchy").exists())

    def test_failed_restore_keeps_that_entry_and_exits_2(self):
        blocker = self.root / "blocker"
        blocker.write_text("a file, so nothing can be created inside it", encoding="utf-8")
        a = Fake("a", self.log)
        b = Fake("b", self.log, restore_changes=[Change(blocker / "x.json", None, b"{}")])
        runner.install(self.ctx(), [a, b])
        self.assertEqual(runner.uninstall(self.ctx(), [a, b]), 2)
        self.assertEqual(self.state()["components"], {"b": {"installed": "b"}})
        self.assertIn("run uninstall again", self.out.getvalue())

    def test_uninstall_only_keeps_the_other_entries(self):
        a, b = Fake("a", self.log), Fake("b", self.log)
        runner.install(self.ctx(), [a, b])
        self.assertEqual(runner.uninstall(self.ctx(only=("a",)), [a, b]), 0)
        self.assertEqual(self.state()["components"], {"b": {"installed": "b"}})

    def test_nothing_to_uninstall(self):
        self.assertEqual(runner.uninstall(self.ctx(), [Fake("a", self.log)]), 0)
        self.assertIn("Nothing to uninstall", self.out.getvalue())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_runner -v`
Expected: ERROR `ImportError: cannot import name 'runner' from 'witchy'`.

- [ ] **Step 3: Register the components**

Replace `witchy/components/__init__.py`:

```python
"""The pieces witchy installs, in the order they are installed."""
from __future__ import annotations

from .claude import ClaudeComponent
from .windows_terminal import WindowsTerminalComponent


def all_components() -> list:
    return [ClaudeComponent(), WindowsTerminalComponent()]


NAMES: tuple[str, ...] = tuple(component.name for component in all_components())
```

- [ ] **Step 4: Implement `witchy/runner.py`**

```python
"""Run the components: plan all of them, then apply one at a time and save state after each."""
from __future__ import annotations

import fcntl
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator, Sequence

from . import build, palette, state as statefile, validate
from .components import all_components
from .components.base import Component, apply_changes, check_unchanged, show_changes
from .errors import Abort, ComponentFailed

LOCK_BUSY = "another witchy command is running"
INSTALLED = "Moonlit Candle installed. Undo with: python3 -m witchy uninstall"
NEW_SESSION_NOTE = ("The output style applies from your next message; restart Claude Code if the theme "
                    "or status line do not update.")


@contextmanager
def locked(ctx: Any) -> Iterator[None]:
    """Hold an exclusive lock for the whole command; a second witchy command stops right away.

    The OS releases a flock when the process dies, so a lock file left behind never blocks.
    """
    path = ctx.lock_file
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Abort(LOCK_BUSY) from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _components(components: Sequence[Component] | None) -> list:
    return list(components) if components is not None else all_components()


def _selected(ctx: Any, components: list) -> list:
    return [component for component in components if not ctx.only or component.name in ctx.only]


def _summary(results: dict[str, str]) -> str:
    ok = sum(1 for result in results.values() if result == "ok")
    line = f"{ok}/{len(results)} components installed"
    for kind in ("skipped", "failed"):
        named = [f"{name} ({result.split(': ', 1)[1]})" for name, result in results.items()
                 if result.startswith(f"{kind}: ")]
        if named:
            line += f" · {kind}: " + ", ".join(named)
    return line


def install(ctx: Any, components: Sequence[Component] | None = None) -> int:
    failures = validate.validate_all()
    if failures:
        for failure in failures:
            ctx.say(str(failure))
        ctx.say("Validation failed; nothing was changed.")
        return 1
    try:
        with nullcontext() if ctx.dry_run else locked(ctx):
            return _install(ctx, _components(components))
    except Abort as exc:
        ctx.say(str(exc))
        return 1


def _install(ctx: Any, components: list) -> int:
    state = statefile.load(ctx.state_path)
    ctx.variant = ctx.variant or (state or {}).get("variant") or palette.DEFAULT_VARIANT
    ctx.outputs = build.render_outputs(variant=ctx.variant)
    entries = (state or {}).get("components", {})
    plans = [(component, component.plan(ctx, entries.get(component.name))) for component in _selected(ctx, components)]
    changes = [change for _, plan in plans if plan.skip is None for change in plan.changes]
    if ctx.dry_run:
        show_changes(ctx, changes)
        ctx.say("Dry run: nothing was written.")
        return 0
    check_unchanged(changes)
    build.write_dist(ctx.outputs, ctx.dist)
    new_state = state or statefile.empty(ctx.variant)
    new_state["variant"] = ctx.variant
    results: dict[str, str] = {}
    for component, plan in plans:
        if plan.skip is not None:
            results[component.name] = f"skipped: {plan.skip}"
        else:
            try:
                new_state["components"][component.name] = component.apply(ctx, plan)
                results[component.name] = "ok"
            except ComponentFailed as exc:
                results[component.name] = f"failed: {exc}"
        new_state["last_install"] = {"at": ctx.stamp, "results": dict(results)}
        # Saved after every component: a later one can fail on the Windows side, and the
        # record must already describe what is really installed.
        statefile.save(ctx.state_path, new_state)
    ctx.say(_summary(results))
    ctx.say(INSTALLED)
    for _, plan in plans:
        for note in plan.notes:
            ctx.say(note)
    ctx.say(NEW_SESSION_NOTE)
    return 0 if all(result == "ok" for result in results.values()) else 2


def uninstall(ctx: Any, components: Sequence[Component] | None = None) -> int:
    try:
        with nullcontext() if ctx.dry_run else locked(ctx):
            return _uninstall(ctx, _components(components))
    except Abort as exc:
        ctx.say(str(exc))
        return 1


def _save_or_remove(ctx: Any, state: dict) -> None:
    if state["components"]:
        statefile.save(ctx.state_path, state)
        return
    ctx.state_path.unlink(missing_ok=True)
    witchy_dir = ctx.state_path.parent
    if witchy_dir.is_dir() and not any(witchy_dir.iterdir()):
        witchy_dir.rmdir()


def _uninstall(ctx: Any, components: list) -> int:
    state = statefile.load(ctx.state_path)
    if state is None:
        ctx.say("Nothing to uninstall: ~/.claude/witchy/state.json not found.")
        return 0
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
    check_unchanged(changes)
    failed = []
    for component, plan in plans:
        try:
            apply_changes(ctx, plan.changes)
        except OSError as exc:
            ctx.say(f"{component.name}: could not write ({exc}); run uninstall again.")
            failed.append(component.name)
            continue
        del entries[component.name]
        _save_or_remove(ctx, state)
    _save_or_remove(ctx, state)
    for warning in warnings:
        ctx.say(warning)
    if failed:
        ctx.say("Moonlit Candle partly uninstalled; still installed: " + ", ".join(failed) + ".")
        return 2
    ctx.say("Moonlit Candle uninstalled.")
    return 0
```

- [ ] **Step 5: Run runner tests to verify they pass**

Run: `/usr/bin/python3 -m unittest tests.test_runner -v`
Expected: 13 tests PASS.

- [ ] **Step 6: Rewrite `witchy/install.py` as re-exports**

```python
"""install / uninstall: kept as the stable entry point; the work happens in runner.py and components/.

Every file change is planned first, so --dry-run can show it and a real run can back each file up
before touching it. state.json records what each setting held before; uninstall gives exactly that back.
"""
from __future__ import annotations

from . import build, claude_settings, content, jsonio, palette, validate, wt  # noqa: F401  (tests patch these)
from .components.base import Abort, Change  # noqa: F401
from .components.claude import DEFAULT_PYTHON, RESTART_NOTE  # noqa: F401
from .components.windows_terminal import WT_SKIP  # noqa: F401
from .context import Context  # noqa: F401
from .runner import NEW_SESSION_NOTE, install, uninstall  # noqa: F401
```

- [ ] **Step 7: Update `tests/test_install.py` for v2 state and exit codes**

1. In `InstallTestCase.ctx`, add `lock_path=self.root / "witchy.lock"` to the `install.Context(...)` call.
2. Add this helper to `InstallTestCase` and use it in `test_install_twice_is_idempotent` instead of `self.snapshot()` (state now records `last_install.at`, which legitimately changes between runs):

```python
    def snapshot_without_state(self):
        return {path: data for path, data in self.snapshot().items() if not path.endswith("state.json")}
```

3. Apply these mechanical replacements throughout the file:

| Old | New |
| :- | :- |
| `state["claude_settings"]` / `self.state()["claude_settings"]` | `state["components"]["claude"]["settings"]` / `self.state()["components"]["claude"]["settings"]` |
| `self.assertIsNone(state["windows_terminal"])` | `self.assertNotIn("windows-terminal", state["components"])` |
| `state["windows_terminal"][...]` | `state["components"]["windows-terminal"][...]` |
| `mock.patch("witchy.install._restore_json", side_effect=plan)` and `real = install._restore_json` | `mock.patch("witchy.components.claude.restore_json", side_effect=plan)` and `real = base.restore_json` (add `from witchy.components import base` to the imports) |

4. Exit codes that change by design (spec section 8; refinement 4):

| Test | Old expectation | New expectation |
| :- | :- | :- |
| `test_windows_terminal_with_comments_is_left_alone` | `install(...) == 0` | `== 2` |
| `test_no_windows_terminal_profile_skips_terminal` | `install(...) == 0` | `== 2` |
| `test_failed_windows_terminal_write_still_records_state` | first `install(...) == 0` | `== 2` |
| `test_refused_windows_terminal_restore_keeps_state_and_can_be_retried` | refused `uninstall(...) == 1` | `== 2` |
| `test_retry_after_a_refused_restore_is_silent_without_an_original_settings_file` | refused `uninstall(...) == 1` | `== 2` |

Uninstall now restores Windows Terminal first (reverse install order), so in `test_uninstall_removes_the_copies_only_after_the_settings_are_restored` replace the last two lines with:

```python
        # Windows Terminal is written first (reverse install order); Claude's settings.json is written back
        # while statusline.py still exists, so the settings never point at a deleted file.
        self.assertEqual(seen, [("settings.json", True), ("settings.json", True)])
        self.assertFalse((self.claude / "witchy" / "statusline.py").exists())
```

Any other failing assertion is a regression in the runner or components: fix the code, not the test.

5. Append the v1 round-trip and the no-Windows-Terminal tests to `InstallTest`:

```python
    def test_a_v1_state_from_before_the_refactor_still_uninstalls(self):
        before = self.snapshot()
        install.install(self.ctx())
        v2 = self.state()
        v1 = {"version": 1, "files": v2["components"]["claude"]["files"],
              "claude_settings": v2["components"]["claude"]["settings"],
              "windows_terminal": v2["components"].get("windows-terminal")}
        (self.claude / "witchy" / "state.json").write_text(json.dumps(v1, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 0)
        self.assertEqual(self.snapshot(), before)

    def test_no_windows_terminal_is_skipped_with_exit_2(self):
        ctx = self.ctx()
        ctx.wt_settings = self.root / "missing.json"
        self.assertEqual(install.install(ctx), 2)
        self.assertEqual(self.claude_settings()["theme"], "custom:moonlit-candle")
        self.assertIn("1/2 components installed · skipped: windows-terminal (settings.json not found)",
                      self.out.getvalue())
```

- [ ] **Step 8: Run the whole suite**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .`
Expected: OK. Also run `/usr/bin/python3.10 -m unittest discover -s tests -t .` → OK.

- [ ] **Step 9: Commit**

```bash
git add witchy/components/__init__.py witchy/runner.py witchy/install.py tests/test_runner.py tests/test_install.py
git commit -m "feat: install and uninstall through components with state v2, a lock and exit code 2

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: `doctor`, `mood` and `--only` on the command line

**Files:**
- Modify: `witchy/runner.py` (add `doctor`, `mood`)
- Modify: `witchy/__main__.py`
- Modify: `tests/test_runner.py` (append), `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: Task 7 runner, `base.Check`, `base.fix_command`, `palette.VARIANTS`, `components.NAMES`.
- Produces:
  - `runner.doctor(ctx, components=None) -> int` — prints one line per check as `"{symbol} {component:<17} {message}"` plus `"    fix: {fix}"` for non-ok checks with a fix; symbols `✓ ⚠ ✗`; exit 1 on any fail.
  - `runner.mood(ctx, variant: str | None, components=None) -> int`
  - CLI: `install/uninstall --only NAME` (repeatable, choices `components.NAMES`), `doctor`, `mood [VARIANT]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_runner.py` (add `from unittest import mock`, `from witchy import palette`, `from witchy.components.base import Check` to the imports):

```python
class CheckingFake(Fake):
    def __init__(self, name, log, checks=None, raises=None):
        super().__init__(name, log)
        self.checks, self.raises = checks or [], raises

    def check(self, ctx, entry):
        if self.raises:
            raise self.raises
        return self.checks


class DoctorTest(RunnerTestCase):
    def test_not_installed_is_a_warning(self):
        self.assertEqual(runner.doctor(self.ctx(), [Fake("a", self.log)]), 0)
        self.assertIn("⚠ a", self.out.getvalue())
        self.assertIn("fix: python3 -m witchy install --only a", self.out.getvalue())

    def test_failing_check_exits_1_and_shows_its_fix(self):
        self.write_state({"a": {}})
        failing = CheckingFake("a", self.log, checks=[Check("fail", "a", "theme drifted", "do the thing")])
        self.assertEqual(runner.doctor(self.ctx(), [failing]), 1)
        self.assertIn("✗ a", self.out.getvalue())
        self.assertIn("theme drifted", self.out.getvalue())
        self.assertIn("    fix: do the thing", self.out.getvalue())

    def test_ok_checks_exit_0(self):
        self.write_state({"a": {}})
        self.assertEqual(runner.doctor(self.ctx(), [CheckingFake("a", self.log, checks=[Check("ok", "a", "fine")])]), 0)
        self.assertIn("✓ a", self.out.getvalue())

    def test_raising_check_is_reported_not_crashed(self):
        self.write_state({"a": {}})
        self.assertEqual(runner.doctor(self.ctx(), [CheckingFake("a", self.log, raises=KeyError("path"))]), 1)
        self.assertIn("check crashed", self.out.getvalue())

    def test_damaged_state_is_a_failure_line(self):
        path = self.home / ".claude" / "witchy" / "state.json"
        path.parent.mkdir(parents=True)
        path.write_text("{", encoding="utf-8")
        self.assertEqual(runner.doctor(self.ctx(), [Fake("a", self.log)]), 1)
        self.assertIn("✗ state", self.out.getvalue())

    def test_last_install_skips_are_warned(self):
        state.save(self.home / ".claude" / "witchy" / "state.json",
                   dict(state.empty("midnight"), components={"a": {}},
                        last_install={"at": "20261002-120000", "results": {"a": "skipped: offline"}}))
        runner.doctor(self.ctx(), [CheckingFake("a", self.log, checks=[Check("ok", "a", "fine")])])
        self.assertIn("last install (20261002-120000): skipped: offline", self.out.getvalue())


class MoodTest(RunnerTestCase):
    def test_lists_active_and_available(self):
        self.assertEqual(runner.mood(self.ctx(), None, [Fake("a", self.log)]), 0)
        self.assertIn("active: midnight", self.out.getvalue())
        self.assertIn("available: midnight", self.out.getvalue())

    def test_unknown_variant_exits_1(self):
        self.assertEqual(runner.mood(self.ctx(), "dawn", [Fake("a", self.log)]), 1)
        self.assertIn("unknown variant 'dawn'; available: midnight", self.out.getvalue())

    def test_same_variant_is_a_no_op(self):
        self.write_state({"a": {"installed": "a"}})
        self.assertEqual(runner.mood(self.ctx(), "midnight", [Fake("a", self.log)]), 0)
        self.assertIn("already midnight", self.out.getvalue())
        self.assertEqual(self.log, [])

    def test_switching_reinstalls_with_the_new_variant(self):
        self.write_state({"a": {"installed": "a"}})
        with mock.patch.dict(palette.VARIANTS, {"dawn": palette.VARIANTS["midnight"]}):
            self.assertEqual(runner.mood(self.ctx(), "dawn", [Fake("a", self.log)]), 0)
        self.assertEqual(self.state()["variant"], "dawn")
        self.assertIn(("apply", "a"), self.log)
```

Append to `tests/test_cli.py` inside `CliTest`:

```python
    def test_help_lists_new_commands(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            main(["--help"])
        for command in ("doctor", "mood"):
            self.assertIn(command, out.getvalue())

    def test_only_rejects_unknown_components(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["install", "--only", "nope"])
        self.assertEqual(raised.exception.code, 2)

    def test_doctor_and_mood_run_on_an_empty_home(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp}), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["doctor"]), 0)
            self.assertEqual(main(["mood"]), 0)
        self.assertIn("not installed", out.getvalue())
        self.assertIn("active: midnight", out.getvalue())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_runner tests.test_cli -v`
Expected: ERROR `AttributeError: module 'witchy.runner' has no attribute 'doctor'` and CLI failures.

- [ ] **Step 3: Add `doctor` and `mood` to `witchy/runner.py`**

Add `Check` and `fix_command` to the `from .components.base import ...` line, then append:

```python
SYMBOLS = {"ok": "✓", "warn": "⚠", "fail": "✗"}


def _print_check(ctx: Any, check: Check) -> None:
    ctx.say(f"{SYMBOLS[check.level]} {check.component:<17} {check.message}")
    if check.fix and check.level != "ok":
        ctx.say(f"    fix: {check.fix}")


def doctor(ctx: Any, components: Sequence[Component] | None = None) -> int:
    try:
        state = statefile.load(ctx.state_path)
    except Abort as exc:
        _print_check(ctx, Check("fail", "state", " ".join(str(exc).split())))
        return 1
    entries = (state or {}).get("components", {})
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
    return 1 if any(check.level == "fail" for check in checks) else 0


def mood(ctx: Any, variant: str | None, components: Sequence[Component] | None = None) -> int:
    try:
        state = statefile.load(ctx.state_path)
    except Abort as exc:
        ctx.say(str(exc))
        return 1
    active = (state or {}).get("variant") or palette.DEFAULT_VARIANT
    available = ", ".join(palette.VARIANTS)
    if variant is None:
        ctx.say(f"active: {active}")
        ctx.say(f"available: {available}")
        return 0
    if variant not in palette.VARIANTS:
        ctx.say(f"unknown variant {variant!r}; available: {available}")
        return 1
    if state is not None and variant == active:
        ctx.say(f"already {variant}")
        return 0
    ctx.variant = variant
    return install(ctx, components)
```

- [ ] **Step 4: Update `witchy/__main__.py`**

Replace the whole file:

```python
"""python3 -m witchy validate | build | install | uninstall | doctor | mood"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import build, components, runner, validate
from .context import Context


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m witchy",
                                     description="Moonlit Candle theme for Claude Code and Windows Terminal")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="check palette contrast, tokens and content")
    commands.add_parser("build", help="validate, then write dist/")
    install_parser = commands.add_parser("install", help="build and put every piece in place")
    install_parser.add_argument("--dry-run", action="store_true", help="show the changes without writing anything")
    install_parser.add_argument("--wt-settings", type=Path, help="path to Windows Terminal settings.json")
    install_parser.add_argument("--only", action="append", choices=components.NAMES, metavar="NAME",
                                help=f"install only this component (repeatable): {', '.join(components.NAMES)}")
    uninstall_parser = commands.add_parser("uninstall", help="give back everything install changed")
    uninstall_parser.add_argument("--dry-run", action="store_true", help="show the changes without writing anything")
    uninstall_parser.add_argument("--only", action="append", choices=components.NAMES, metavar="NAME",
                                  help="uninstall only this component (repeatable)")
    commands.add_parser("doctor", help="check every installed piece and say how to fix it")
    mood_parser = commands.add_parser("mood", help="show or switch the colour variant")
    mood_parser.add_argument("variant", nargs="?", help="variant to switch to")
    args = parser.parse_args(argv)

    if args.command == "validate":
        failures = validate.validate_all()
        for failure in failures:
            print(failure)
        if not failures:
            print("Moonlit Candle: all checks passed")
        return 1 if failures else 0
    if args.command == "build":
        failures = build.build()
        for failure in failures:
            print(failure)
        if failures:
            print("Validation failed; dist/ was not written.")
            return 1
        print(f"Wrote {build.DIST}")
        return 0
    ctx = Context(home=Path.home(), env=os.environ, out=sys.stdout, dry_run=getattr(args, "dry_run", False),
                  wt_settings=getattr(args, "wt_settings", None), only=tuple(getattr(args, "only", None) or ()))
    if args.command == "install":
        return runner.install(ctx)
    if args.command == "uninstall":
        return runner.uninstall(ctx)
    if args.command == "doctor":
        return runner.doctor(ctx)
    return runner.mood(ctx, args.variant)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the whole suite**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .` and `/usr/bin/python3.10 -m unittest discover -s tests -t .`
Expected: OK on both.

- [ ] **Step 6: Commit**

```bash
git add witchy/runner.py witchy/__main__.py tests/test_runner.py tests/test_cli.py
git commit -m "feat: add doctor, mood and --only

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: English README, spec refinements, and a real-machine check

**Files:**
- Rewrite: `README.md`
- Modify: `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (sections 3.2, 3.3, 3.4, 8)

**Interfaces:**
- Consumes: the finished CLI.
- Produces: documentation only.

- [ ] **Step 1: Rewrite `README.md`**

````markdown
# Moonlit Candle

A witchy theme for Claude Code and Windows Terminal on WSL, inspired by [WitchyNibbles/Spellbound-Themes](https://github.com/WitchyNibbles/Spellbound-Themes): an aubergine night background, candle-gold accents, and pink for permissions.

It installs:

- The `moonlit-candle` Claude Code theme (`~/.claude/themes/`)
- The "Moonlit Candle" colour scheme on your WSL profile in Windows Terminal
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

Components, in install order: `claude`, `windows-terminal`.

`install` backs up every file it changes as `*.bak-witchy-<date>` and records the previous values in `~/.claude/witchy/state.json`; `uninstall` restores them. A `settings.json` that is not strict JSON (comments, trailing commas) is never rewritten: for Windows Terminal you get a snippet to paste by hand and the rest continues; for `~/.claude/settings.json` the install stops without changing anything.

Exit codes for `install` and `uninstall`: `0` everything done, `1` nothing changed, `2` done with warnings (a component was skipped or failed; the last line says which).

Restart Claude Code after installing.

## Troubleshooting

Run `python3 -m witchy doctor`. Each `⚠` or `✗` line is followed by the command that fixes it.

| Doctor says | Meaning | Fix |
| :- | :- | :- |
| `✗ claude  changed or missing: …` | an installed file was edited or deleted | `python3 -m witchy install --only claude` |
| `✗ claude  settings changed: theme, …` | a settings key no longer holds the witchy value | same as above, or keep your change |
| `✗ windows-terminal  profile colour scheme is …` | the profile uses another scheme | `python3 -m witchy install --only windows-terminal` |
| `⚠ windows-terminal  not installed` | Windows Terminal was not found or the profile did not match | set `WT_PROFILE_ID` or pass `--wt-settings PATH`, then install |
| `⚠ …  backup … is missing` | a backup was deleted | uninstall still works, key by key |
| `⚠ …  last install (…): skipped: …` | a component was skipped at the last install | read the reason, then install `--only` that component |
| `✗ state  … damaged` | `state.json` is not readable | fix or remove the file by hand |
| `another witchy command is running` | a second command is still holding the lock | wait for it to finish |

## Development

```sh
/usr/bin/python3 -m unittest discover -s tests -t . -v
/usr/bin/python3.10 -m unittest discover -s tests -t .
```

Colours live in `witchy/palette.py` (`VARIANTS`). Each installable piece is a component in `witchy/components/`. Designs: `docs/superpowers/specs/`. Architecture diagram: `docs/diagrams/witchy-components.html`.
````

- [ ] **Step 2: Record the spec refinements**

In `docs/superpowers/specs/2026-10-02-shell-ritual-design.md`:
1. Section 3.2, step 1: replace ``Take `~/.claude/witchy/.lock` `` with ``Take `$XDG_RUNTIME_DIR/witchy-<uid>.lock` (system temp dir as fallback; outside HOME so uninstall leaves nothing behind) ``.
2. Section 3.3: in the JSON example replace `"at": "2026-10-02T21:14:03"` with `"at": "20261002-211403"` and add the line `- `last_install.at` is the run stamp used for backups.`
3. Section 3.4: append `Variants change colours only; theme name, scheme name and installed paths stay the same.`
4. Section 8: after the exit-code bullet add `- An uninstall whose restore cannot be written keeps that component in state and exits 2; running uninstall again retries it.`

- [ ] **Step 3: Run the full suite on both Pythons**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .` and `/usr/bin/python3.10 -m unittest discover -s tests -t .`
Expected: OK on both.

- [ ] **Step 4: Real-machine dry run and doctor**

Run: `/usr/bin/python3 -m witchy install --dry-run; echo "exit=$?"`
Expected: the diff shows only the output-style file change (the neutral wording) and no other content changes; `exit=0`.

Run: `/usr/bin/python3 -m witchy doctor; echo "exit=$?"`
Expected: `✓ claude …` lines; the v1 state on this machine is migrated in memory; for `windows-terminal` either `✓` or a clear `✗/⚠` with a fix. Report the output verbatim in the task summary. Do **not** run a real `install` here: that is the user's call.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/superpowers/specs/2026-10-02-shell-ritual-design.md
git commit -m "docs: English README with doctor troubleshooting; record plan A spec refinements

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
