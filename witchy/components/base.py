"""What every component shares: planned file changes, plans, doctor checks, careful writes."""
from __future__ import annotations

import difflib
import fcntl
import hashlib
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, Protocol

from .. import jsonio
from ..errors import Abort, ComponentFailed

__all__ = ["Abort", "ComponentFailed", "Change", "Command", "JsonPlan", "Plan", "Check", "Component", "sha", "read",
           "fix_command", "backup_checks", "check_unchanged", "show_changes", "apply_changes", "run_command",
           "file_change", "file_record", "restore_copy", "restore_json", "file_lock"]

COMMAND_TIMEOUT = 5  # seconds for every fish call (spec 5.3)


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
    directory that is left empty. A skipped restore plan means the restore is blocked: nothing of the component
    is touched and it stays installed. ``outcome`` replaces "ok" in the install results when a plan applied only
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

    @classmethod
    def skipped(cls, reason: str) -> Plan:
        return cls(skip=reason)


@contextmanager
def file_lock(path: Path | None, timeout: float = 10.0) -> Iterator[None]:
    """Hold ``path`` exclusively, waiting up to ``timeout`` seconds (the sky job holds it only briefly)."""
    if path is None:
        yield
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(path, "a")
    except OSError as exc:
        raise ComponentFailed(f"cannot open {path} ({exc})") from exc
    with handle:
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


def run_command(ctx: Any, command: Command, check: bool = True) -> subprocess.CompletedProcess:
    """Run ``command`` through ``ctx.run`` with ``ctx.env`` and a timeout.

    A command that cannot start or times out raises ComponentFailed (the cause is kept, so a caller can tell a
    missing program from a slow one); a non-zero exit raises it too unless ``check`` is false.
    """
    try:
        done = ctx.run(list(command.args), input=command.input, capture_output=True, text=True, errors="replace",
                       timeout=COMMAND_TIMEOUT, env=dict(ctx.env))
    except subprocess.TimeoutExpired as exc:  # its text would hold the whole argument list
        raise ComponentFailed(f"could not {command.label} (timed out after {COMMAND_TIMEOUT} s)") from exc
    except OSError as exc:
        raise ComponentFailed(f"could not {command.label} ({exc.strerror or type(exc).__name__})") from exc
    except (ValueError, subprocess.SubprocessError) as exc:
        raise ComponentFailed(f"could not {command.label} ({str(exc)[:100]})") from exc
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
    """What state.json remembers about a copied file.

    A backup made in this run holds what someone else wrote after witchy, so uninstall must give that back;
    with none, the first backup ever made stays the restore target.
    """
    previous = earlier.get(change.path)
    if change.path in backups:
        backup = str(backups[change.path])
    else:
        backup = previous["backup"] if previous else None
    return {"path": str(change.path), "backup": backup, "installed_sha256": sha(read(change.path))}


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
    # A settings file that cannot be given back keeps the whole component installed: its other files
    # (the status line, the sky images) must stay while the settings still point at them.
    try:
        data, text = jsonio.read_json(path)
    except jsonio.StrictJsonError as exc:
        raise ComponentFailed(f"{path} is no longer plain JSON; make it plain JSON again") from exc
    if not isinstance(data, dict):
        raise ComponentFailed(f"{path} no longer holds a JSON object; fix it by hand")
    restored, notes = restore(data)
    warnings.extend(notes)
    if notes and entry.get("backup"):
        warnings.append(f"The file as it was before install is kept at {entry['backup']}.")
    if restored == data:
        return None
    return Change(path, current, jsonio.dumps_like(restored, text).encode("utf-8"))
