"""Run the components: plan all of them, then apply one at a time and save state after each."""
from __future__ import annotations

import fcntl
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator, Sequence

from . import build, palette, state as statefile, validate
from .components import all_components
from .components.base import Check, Component, apply_changes, check_unchanged, fix_command, show_changes
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
    if ctx.variant not in palette.VARIANTS:
        raise Abort(f"{ctx.state_path} names the unknown variant {ctx.variant!r}; "
                    f"run: python3 -m witchy mood {palette.DEFAULT_VARIANT}")
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
