"""What every component shares: planned file changes, plans, doctor checks, careful writes."""
from __future__ import annotations

import difflib
import fcntl
import hashlib
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, Protocol

from .. import jsonio
from ..errors import Abort, ComponentFailed

__all__ = ["Abort", "ComponentFailed", "Change", "JsonPlan", "Plan", "Check", "Component", "sha", "read",
           "fix_command", "backup_checks", "check_unchanged", "show_changes", "apply_changes",
           "restore_copy", "restore_json", "file_lock"]


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
    """What a component will do. ``skip`` set means it will do nothing, and says why. ``actions`` describe work that is not a file change (a download, a reg.exe call) for dry runs. ``lock`` is held while the plan is applied."""

    changes: list[Change] = field(default_factory=list)
    skip: str | None = None
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    lock: Path | None = None
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def skipped(cls, reason: str) -> Plan:
        return cls(skip=reason)


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
