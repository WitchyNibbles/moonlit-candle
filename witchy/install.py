"""install / uninstall: put every piece in place, remember what was there, give it back.

Every file change is planned first, so --dry-run can show it and a real run can
back each file up before touching it. state.json records what each setting held
before; uninstall gives exactly that back, and restores a settings file's
original bytes when nothing else has touched it since.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, TextIO

from . import build, claude_settings, content, jsonio, palette, validate, wt

STATE_VERSION = 1
DEFAULT_PYTHON = "/usr/bin/python3"
RESTART_NOTE = "Restart Claude Code once so it starts watching ~/.claude/themes/"
NEW_SESSION_NOTE = ("The output style applies from your next message; restart Claude Code if the theme "
                    "or status line do not update.")
WT_SKIP = "skipping the terminal colour scheme"

# dist/ file -> its home under ~/.claude
COPIES = {
    build.THEME: Path("themes/moonlit-candle.json"),
    build.OUTPUT_STYLE: Path("output-styles/witchynibbles.md"),
    build.STATUSLINE: Path("witchy/statusline.py"),
    build.TIPS: Path("witchy/tips.json"),
}


def _sha(data: bytes | None) -> str | None:
    return None if data is None else hashlib.sha256(data).hexdigest()


def _read(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


class Abort(Exception):
    """Stop before anything is written; the message says why."""


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
        after = _sha(self.change.after)
        if self.previous:
            # The first backup stays the right restore target while each reinstall overwrites exactly what
            # witchy wrote last time; a file someone else edited in between is restored key by key instead.
            ok = self.previous["byte_restore_ok"] and _sha(self.change.before) == self.previous["installed_sha256"]
            base = {**self.previous, "installed_sha256": after, "byte_restore_ok": ok}
        else:
            existed = self.change.before is not None
            base = {"path": str(self.change.path), "existed": existed,
                    "backup": str(backup) if backup else None, "installed_sha256": after,
                    "byte_restore_ok": not existed or backup is not None}
        return {**base, **self.extra}


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

    @property
    def claude_dir(self) -> Path:
        return self.home / ".claude"

    @property
    def state_path(self) -> Path:
        return self.claude_dir / "witchy" / "state.json"

    def say(self, message: str) -> None:
        print(message, file=self.out)


def _python(ctx: Context) -> str:
    # Not the pyenv shim: its version follows each project's .python-version.
    if ctx.python:
        return ctx.python
    return DEFAULT_PYTHON if Path(DEFAULT_PYTHON).is_file() else sys.executable


def _load_state(ctx: Context) -> dict | None:
    if not ctx.state_path.is_file():
        return None
    try:
        state, _ = jsonio.read_json(ctx.state_path)
    except jsonio.StrictJsonError as exc:
        raise Abort(f"{exc}\nThe state file is damaged; fix or remove {ctx.state_path} by hand.") from exc
    if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
        raise Abort(f"{ctx.state_path} has an unknown format; fix or remove it by hand.")
    return state


def _plan_copies(ctx: Context, outputs: dict[str, str], state: dict | None) -> tuple[list, list[Change]]:
    earlier = {Path(entry["path"]): entry for entry in (state or {}).get("files", [])}
    files, changes = [], []
    for rel, target in COPIES.items():
        path = ctx.claude_dir / target
        before = _read(path)
        after = outputs[rel].encode("utf-8")
        previous = earlier.get(path)
        ours = previous is not None and _sha(before) == previous["installed_sha256"]
        changes.append(Change(path, before, after, backup=not ours))
        files.append((path, previous, after))
    return files, changes


def _plan_claude_settings(ctx: Context, state: dict | None) -> JsonPlan:
    path = ctx.claude_dir / "settings.json"
    before = _read(path)
    data, text = {}, None
    if before is not None:
        try:
            data, text = jsonio.read_json(path)
        except jsonio.StrictJsonError as exc:
            raise Abort(f"{exc}\n{path} is not plain JSON; nothing was changed.") from exc
        if not isinstance(data, dict):
            raise Abort(f"{path} does not hold a JSON object; nothing was changed.")
    previous = state["claude_settings"] if state else None
    desired = claude_settings.desired_keys(ctx.home, _python(ctx), content.load_spinner()["verbs"])
    new_data, keys = claude_settings.apply_keys(data, desired, previous["keys"] if previous else None)
    after = jsonio.dumps_like(new_data, text).encode("utf-8")
    return JsonPlan(Change(path, before, after), previous, {"keys": keys})


def _plan_windows_terminal(ctx: Context, state: dict | None) -> JsonPlan | None:
    previous = (state or {}).get("windows_terminal")
    path = wt.locate_settings(ctx.wt_settings, run=ctx.run)
    if path is None:
        ctx.say(f"Windows Terminal settings.json not found; {WT_SKIP}.")
        return None
    try:
        data, text = jsonio.read_json(path)
    except jsonio.StrictJsonError:
        ctx.say(f"{path} is not plain JSON (comments?), so it was left untouched. Add this by hand:")
        ctx.say(wt.manual_snippet(palette.WT_SCHEME, ctx.env.get("WT_PROFILE_ID") or "<your WSL profile guid>"))
        return None
    guid, reason = wt.find_profile(data, ctx.env)
    if guid is None:
        ctx.say(f"Windows Terminal: {reason}; {WT_SKIP}.")
        return None
    if previous and (previous["path"] != str(path) or previous["profile_guid"].lower() != guid.lower()):
        ctx.say(f"Windows Terminal: already installed for profile {previous['profile_guid']} in {previous['path']}; "
                f"run uninstall first to move it; {WT_SKIP}.")
        return None
    try:
        new_data, record = wt.apply_scheme(data, palette.WT_SCHEME, guid, previous)
    except ValueError as exc:
        ctx.say(f"Windows Terminal: {exc}; {WT_SKIP}.")
        return None
    after = jsonio.dumps_like(new_data, text).encode("utf-8")
    return JsonPlan(Change(path, path.read_bytes(), after), previous, record)


def _check_unchanged(changes: list[Change]) -> None:
    """Planning and writing are apart in time (the cmd.exe lookup); never overwrite what another program wrote."""
    for change in changes:
        if _read(change.path) != change.before:
            raise Abort(f"{change.path} changed while planning; nothing was written. Run the command again.")


def _show(ctx: Context, changes: list[Change]) -> None:
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


def _apply(ctx: Context, changes: list[Change]) -> dict[Path, Path]:
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


def _save_state(ctx: Context, files: list, backups: dict[Path, Path], claude: JsonPlan, terminal: dict | None) -> None:
    new_state = {
        "version": STATE_VERSION,
        "files": [
            {"path": str(path),
             "backup": previous["backup"] if previous else (str(backups[path]) if path in backups else None),
             "installed_sha256": _sha(after)}
            for path, previous, after in files
        ],
        "claude_settings": claude.entry(backups.get(claude.change.path)),
        "windows_terminal": terminal,
    }
    jsonio.write_atomic_bytes(ctx.state_path, (json.dumps(new_state, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def install(ctx: Context) -> int:
    failures = validate.validate_all()
    if failures:
        for failure in failures:
            ctx.say(str(failure))
        ctx.say("Validation failed; nothing was changed.")
        return 1
    try:
        state = _load_state(ctx)
        outputs = build.render_outputs()
        files, changes = _plan_copies(ctx, outputs, state)
        claude = _plan_claude_settings(ctx, state)
    except Abort as exc:
        ctx.say(str(exc))
        return 1
    terminal = _plan_windows_terminal(ctx, state)
    changes.append(claude.change)
    themes_existed = (ctx.claude_dir / "themes").is_dir()
    if ctx.dry_run:
        _show(ctx, changes + ([terminal.change] if terminal else []))
        ctx.say("Dry run: nothing was written.")
        return 0

    try:
        _check_unchanged(changes + ([terminal.change] if terminal else []))
    except Abort as exc:
        ctx.say(str(exc))
        return 1
    build.write_dist(outputs, ctx.dist)
    backups = _apply(ctx, changes)
    # The originals are recorded before Windows Terminal is touched: its file lives on the Windows side and
    # can refuse the write, and a retry must not mistake the values already installed for the user's own.
    _save_state(ctx, files, backups, claude, (state or {}).get("windows_terminal"))
    if terminal:
        try:
            backups.update(_apply(ctx, [terminal.change]))
        except OSError as exc:
            ctx.say(f"Windows Terminal: could not write {terminal.change.path} ({exc}); {WT_SKIP}.")
        else:
            _save_state(ctx, files, backups, claude, terminal.entry(backups.get(terminal.change.path)))
    ctx.say("Moonlit Candle installed. Undo with: python3 -m witchy uninstall")
    if not themes_existed:
        ctx.say(RESTART_NOTE)
    ctx.say(NEW_SESSION_NOTE)
    return 0


def _restore_copy(entry: dict) -> Change | None:
    path = Path(entry["path"])
    current = _read(path)
    original = _read(Path(entry["backup"])) if entry.get("backup") else None
    if current is None and original is None:
        return None
    # Keep a copy of anything the user edited (for example with /theme → Ctrl+E) before it goes.
    edited = current is not None and _sha(current) != entry["installed_sha256"]
    return Change(path, current, original, backup=edited)


def _restore_json(entry: dict, restore: Callable[[dict], tuple[dict, list[str]]], warnings: list[str]) -> Change | None:
    path = Path(entry["path"])
    current = _read(path)
    if current is None:
        # A file witchy created and an earlier uninstall already removed is back to how it started.
        if entry["existed"]:
            warnings.append(f"{path} no longer exists; nothing to restore there.")
        return None
    if entry["byte_restore_ok"] and _sha(current) == entry["installed_sha256"]:
        if not entry["existed"]:
            return Change(path, current, None, backup=False)
        original = _read(Path(entry["backup"])) if entry.get("backup") else None
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


def uninstall(ctx: Context) -> int:
    try:
        state = _load_state(ctx)
    except Abort as exc:
        ctx.say(str(exc))
        return 1
    if state is None:
        ctx.say("Nothing to uninstall: ~/.claude/witchy/state.json not found.")
        return 0
    warnings: list[str] = []
    claude = state["claude_settings"]
    terminal = state.get("windows_terminal")
    copies = [_restore_copy(entry) for entry in state["files"]]
    settings = _restore_json(claude, lambda data: claude_settings.restore_keys(data, claude["keys"]), warnings)
    remote = _restore_json(terminal, lambda data: wt.restore_scheme(data, terminal), warnings) if terminal else None
    # Claude settings first, so they never point at deleted files; Windows Terminal last, it can refuse the write.
    local = [change for change in [settings, *copies] if change is not None]
    planned = local + ([remote] if remote else [])
    if ctx.dry_run:
        _show(ctx, planned)
        for warning in warnings:
            ctx.say(warning)
        ctx.say("Dry run: nothing was written.")
        return 0
    try:
        _check_unchanged(planned)
    except Abort as exc:
        ctx.say(str(exc))
        return 1
    _apply(ctx, local)
    if remote:
        try:
            _apply(ctx, [remote])
        except OSError as exc:
            for warning in warnings:
                ctx.say(warning)
            ctx.say(f"Windows Terminal: could not write {remote.path} ({exc}); run uninstall again.")
            return 1
    ctx.state_path.unlink(missing_ok=True)
    witchy_dir = ctx.state_path.parent
    if witchy_dir.is_dir() and not any(witchy_dir.iterdir()):
        witchy_dir.rmdir()
    for warning in warnings:
        ctx.say(warning)
    ctx.say("Moonlit Candle uninstalled.")
    return 0
