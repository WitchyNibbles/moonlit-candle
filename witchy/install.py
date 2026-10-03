"""install / uninstall: put every piece in place, remember what was there, give it back.

Every file change is planned first, so --dry-run can show it and a real run can
back each file up before touching it. state.json records what each setting held
before; uninstall gives exactly that back, and restores a settings file's
original bytes when nothing else has touched it since.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import build, claude_settings, content, jsonio, palette, validate, wt
from .components.base import (Abort, Change, JsonPlan, apply_changes as _apply, check_unchanged as _check_unchanged,
                              read as _read, restore_copy as _restore_copy, restore_json, sha as _sha,
                              show_changes as _show)
from .context import Context

_restore_json = restore_json

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
