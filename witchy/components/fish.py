"""fish: the greeting package, the fish functions and conf.d snippet, and every Tide variable (spec 5, 6, 7)."""
from __future__ import annotations

import re
import shlex
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .. import build, fishprobe, palette
from ..ritual import caret, log, sky
from .base import (Check, Command, ComponentFailed, Plan, applied_records, apply_changes, backup_checks,
                   file_change, file_record, fix_command, read, restore_copy, run_command, sha)
from .claude import python_for

FISH = "fish"
RITUAL_DIR = Path(".claude/witchy/ritual")
NEW_TAB_NOTE = "Open a new terminal tab to see the new prompt and greeting; open shells keep the old ones."
GREETING_NOTE = "Open a new terminal tab to see the greeting."
NO_EZA_NOTE = "eza is not installed, so ll and lt use ls; install it with: sudo apt install eza"
EZA_FIX = "sudo apt install eza"
RECENT = timedelta(days=7)  # older greeting and sky errors are history, not a warning
MESSAGE_MAX = 100
SHOWN_MAX = 10  # drifted names listed by doctor
SHELL_TIMEOUT = 15  # seconds for doctor's new interactive shell, which runs the user's whole config (spec 9.1)
PROMPT_ITEMS = ("tide_left_prompt_items", "tide_right_prompt_items")
NOT_READY = "skipped: Tide not ready (run: python3 -m witchy install --only tide)"
LOG_LINE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d) (greeting|sky): (.*)$")
CARET = "tide_character_color"  # conf.d/witchy.fish sets it as a global on a sabbat and its eve (spec 15.3)

# Prints the sentinel, then the universal value of each name asked for and of every other universal tide_
# variable (Tide's private _tide_ ones are not listed): the name, "absent" or "exported"/"unexported", the
# element count and the elements. Every field ends in NUL, which no fish value can hold.
SNAPSHOT_SCRIPT = """\
printf '%s\\0' witchy-fish
set -l names $argv
for name in (set -U --names | string match 'tide_*')
    contains -- $name $argv; or set -a names $name
end
for name in $names
    set -e -g $name  # a global set by config.fish would hide the universal value here (doctor reports it)
    if set -q -U $name
        set -l flag unexported
        set -q -U -x $name; and set flag exported
        printf '%s\\0' $name $flag (count $$name) $$name
    else
        printf '%s\\0' $name absent
    end
end
"""

# Run by a new interactive shell, the way a new tab starts one: prints each name that has a global value (set
# by config.fish or conf.d, so it hides the universal one), its element count and its elements.
GLOBALS_SCRIPT = """\
printf '%s\\0' witchy-fish
for name in $argv
    if set -q -g $name
        printf '%s\\0' $name (count $$name) $$name
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


def tide_goes_first(ctx: Any) -> bool:
    """This run's tide plan changes which prompt fish runs and has not applied yet.

    fish then plans again once it has, and still asks fish itself whether Tide is ready, never how tide ended
    (spec D19). With ``--only fish`` there is no tide plan, so fish asks right away.
    """
    plan = ctx.planned.get("tide")
    return (plan is not None and plan.skip is None and bool(plan.data.get("reprobe"))
            and "tide" not in ctx.results)


def config_dir(ctx: Any) -> Path:
    """fish's own rule: $XDG_CONFIG_HOME/fish, else ~/.config/fish."""
    base = ctx.env.get("XDG_CONFIG_HOME")
    return Path(base) / "fish" if base else ctx.home / ".config" / "fish"


def snapshot(ctx: Any, names: list[str]) -> dict[str, dict]:
    """Each of ``names``, then every other universal ``tide_`` variable, as ``{"absent": True}`` or
    ``{"value": [...], "exported": bool}``."""
    done = run_command(ctx, Command((FISH, "-c", SNAPSHOT_SCRIPT, "--", *names), "read the Tide variables",
                                    exact=True))
    try:
        fields = fishprobe.fields(done.stdout)
        index, found = 0, {}
        while index < len(fields):
            name, flag = fields[index], fields[index + 1]
            if flag == "absent":
                found[name], index = {"absent": True}, index + 2
                continue
            count = int(fields[index + 2])
            found[name] = {"value": fields[index + 3:index + 3 + count], "exported": flag == "exported"}
            index += 3 + count
        return {**{name: found[name] for name in names}, **found}
    except (ValueError, IndexError, KeyError) as exc:
        raise ComponentFailed(f"could not read the Tide variables ({exc})") from exc


def shadows(ctx: Any, names: list[str]) -> dict[str, list[str]]:
    """The ``names`` a new interactive shell holds as globals, with their values.

    WITCHY_DOCTOR makes conf.d/witchy.fish skip the sky job and fish_greeting stay quiet; standard input is
    empty, so nothing waits for a key.
    """
    done = run_command(ctx, Command((FISH, "-i", "-c", GLOBALS_SCRIPT, "--", *names),
                                    "read the prompt variables a new shell sees", "", exact=True,
                                    timeout=SHELL_TIMEOUT, env={"WITCHY_DOCTOR": "1"}))
    try:
        fields = fishprobe.fields(done.stdout)
        found, index = {}, 0
        while index < len(fields):
            count = int(fields[index + 1])
            found[fields[index]] = fields[index + 2:index + 2 + count]
            index += 2 + count
        return found
    except (ValueError, IndexError) as exc:
        raise ComponentFailed(f"could not read the prompt variables a new shell sees ({exc})") from exc


def set_command(updates: list[tuple[str, str, list[str]]], label: str) -> Command:
    """One fish call that applies each (name, mode, values); mode is "set", "exported" or "erase"."""
    fields = [field for name, mode, values in updates for field in (name, mode, str(len(values)), *values)]
    return Command((FISH, "-c", SET_SCRIPT), label, "".join(f"{field}\0" for field in fields), exact=True)


def _values(value: str | tuple[str, ...]) -> list[str]:
    return [value] if isinstance(value, str) else list(value)


def desired(variant: str) -> dict[str, list[str]]:
    """Every variable witchy sets, as fish lists: all of Tide's, the moon item's and fish's own (spec 6.1)."""
    return {name: _values(value) for name, value in {**build.tide(variant), **palette.FISH}.items()}


def _action(name: str, mode: str, values: list[str], current: dict) -> str:
    now = _shown(current["value"]) if "value" in current else "unset"
    if mode == "erase":
        return f"fish: set -e -U {name} (now: {now})"
    return f"fish: set -U{'x' if mode == 'exported' else ''} {name} {' '.join(values)} (now: {now})"


def _shown(values: list[str]) -> str:
    """Values as printable text: a byte that is not UTF-8 shows as U+FFFD."""
    return " ".join(values).encode("utf-8", "surrogateescape").decode("utf-8", "replace")


def _changed_warning(name: str, current: dict) -> str:
    if name in PROMPT_ITEMS and "moon" in current.get("value", []):
        # The moon item's function goes with the files, and Tide would report it on every prompt.
        return (f"{name} was changed after install; leaving it as it is, but it still lists moon. "
                f"Remove it with: set -U {name} (string match -v moon ${name})")
    return f"{name} was changed after install; leaving it as it is."


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


def _today(ctx: Any) -> date:
    """The local day, as fish's `date +%F` and the sky job see it."""
    now = ctx.now()
    return (now.astimezone() if now.tzinfo is not None else now).date()


def _todays_caret(ctx: Any) -> str | None:
    """The colour today's line of the caret cache holds, or None (gold, or no usable cache)."""
    try:
        found = caret.read(ctx.cache_dir / caret.NAME).get(_today(ctx).isoformat())
    except OSError:
        return None
    return found[1] if found else None


def caret_check(ctx: Any) -> Check:
    """doctor's caret line (spec 15.3): today's colour from the cache, or gold, as a line to read; a warning when
    the cache holds no line for today, since then every new shell shows gold."""
    path = ctx.cache_dir / caret.NAME
    try:
        days = caret.read(path)
    except OSError:
        return Check("warn", "fish", "caret: gold (no caret cache yet; a new tab writes it)")
    today = _today(ctx).isoformat()
    if today not in days:
        written = next(iter(days), None)
        why = f"was written on {written}, not today" if written else "is damaged"
        return Check("warn", "fish", f"caret: gold (the caret cache {why})",
                     f"tail -n {log.MAX_LINES} {shlex.quote(str(ctx.cache_dir / log.NAME))}")
    found = days[today]
    return Check("info", "fish", f"caret: {found[0]} {found[1]} (today's cache)" if found else "caret: gold")


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
        notes = [] if shutil.which("eza", path=ctx.env.get("PATH")) else [NO_EZA_NOTE]
        # What earlier installs recorded stays recorded even when fish cannot be asked this time.
        recorded = (entry or {}).get("variables", {})
        plan = Plan(changes=changes, notes=notes, data={"earlier": earlier, "recorded": recorded, "records": {},
                                                        "updates": []})
        wanted = desired(variant)
        if tide_goes_first(ctx):
            plan.replan = True
            plan.actions = [f"fish: set {len(wanted)} prompt variables once tide has installed Tide "
                            "(fish is asked again then)"]
            return plan
        try:
            # Tide's readiness comes from fish itself, never from how the tide component ended (spec D19).
            reason = fishprobe.tide_ready(fishprobe.probe(ctx))
            current = None if reason else snapshot(ctx, list(wanted))
        except ComponentFailed as exc:
            missing = isinstance(exc.__cause__, FileNotFoundError)
            if not missing:  # fish is there but did not answer: its greeting still shows
                plan.notes.insert(0, GREETING_NOTE)
            plan.outcome = "skipped: fish not found" if missing else f"skipped: {exc}"
            ctx.say(f"fish: {'fish not found' if missing else exc}; prompt not recoloured.")
            return plan
        if current is None:
            plan.notes.insert(0, GREETING_NOTE)
            plan.outcome = NOT_READY
            ctx.say(f"fish: {reason}; prompt not recoloured. Run: {fix_command('tide')}")
            return plan
        records, updates = {}, []
        for name, values in wanted.items():
            # A reinstall keeps the value from before the first install, not witchy's own.
            previous = recorded[name]["previous"] if name in recorded else current[name]
            records[name] = {"previous": previous, "installed": values}
            if current[name].get("value") != values:
                updates.append((name, "exported" if previous.get("exported") else "set", values))
        for name in sorted(current.keys() - wanted.keys()):
            # A tide_ variable Tide 6.1.1 does not define is erased; uninstall gives it back (spec 6.1).
            previous = recorded[name]["previous"] if name in recorded else current[name]
            records[name] = {"previous": previous, "installed": None}
            if "value" in current[name]:
                updates.append((name, "erase", []))
        plan.data.update(records=records, updates=updates)
        plan.notes.insert(0, NEW_TAB_NOTE)
        plan.actions = [_action(name, mode, values, current[name]) for name, mode, values in updates]
        return plan

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
        updates = plan.data["updates"]
        done: set[str] = set()
        unknown = False
        if updates:
            # After the files: the moon item must exist before Tide is told to show it (spec 5.3).
            try:
                result = run_command(ctx, set_command(updates, f"set {len(updates)} Tide variables"), check=False)
                done = set(fishprobe.fields(result.stdout))
                ok = result.returncode == 0
                # Only the script's own exit 1 is a known stop; a signal or any other code may hide a set.
                unknown = result.returncode not in (0, 1)
            except (ComponentFailed, ValueError):
                ok = False
                unknown = True
            if unknown:
                # Fish may have set any of them; restore skips one that still holds its previous value.
                done = {name for name, _, _ in updates}
                plan.outcome = "failed: fish did not finish setting the Tide variables"
                ctx.say("fish: fish did not finish setting the Tide variables; run install again.")
            elif not ok:
                stopped = next((name for name, _, _ in updates if name not in done), updates[-1][0])
                plan.outcome = f"failed: could not set {stopped}"
                ctx.say(f"fish: could not set {stopped}; the Tide variables after it were not set.")
        pending = {name for name, _, _ in updates} - done
        variables.update({name: record for name, record in plan.data["records"].items() if name not in pending})
        return {"files": files, "variables": variables}

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

    def restore(self, ctx: Any, entry: dict) -> Plan:
        warnings: list[str] = []
        commands: list[Command] = []
        variables = entry.get("variables") or {}
        if variables:
            try:
                current = snapshot(ctx, list(variables))
            except ComponentFailed as exc:
                if not isinstance(exc.__cause__, FileNotFoundError):
                    raise  # fish is there but did not answer: keep the component and retry later
                warnings.append("fish: fish not found, so Tide keeps witchy's colours and the moon item; to reset "
                                "them, run tide configure in fish.")
                current = {}
            # The tide_ variables witchy set; fish's own (fish_emoji_width) and the erased ones do not go with Tide.
            ours = [name for name, record in variables.items()
                    if name.startswith("tide_") and record["installed"] is not None]
            if current and ours and all(current[name].get("absent") for name in ours):
                warnings.append("fish: the Tide variables witchy set are gone (was Tide removed?), so those are not "
                                "restored; fish_emoji_width and the tide_ variables witchy erased are given back.")
                current = {name: found for name, found in current.items() if name not in ours}
            undo = []
            for name, record in variables.items():
                if name not in current or current[name] == record["previous"]:
                    continue  # fish or Tide is gone, or this one was already given back by an earlier attempt
                if current[name].get("value") != record["installed"]:
                    warnings.append(_changed_warning(name, current[name]))
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

    def _prompt_checks(self, ctx: Any) -> list[Check]:
        """Every variable against the spec, not only the recorded ones (spec 9.1): drift, tide_ variables Tide
        does not define, and globals that hide a universal value in a new shell."""
        fix = fix_command(self.name)
        wanted = desired(ctx.variant or palette.DEFAULT_VARIANT)
        try:
            reason = fishprobe.tide_ready(fishprobe.probe(ctx))
            if reason:
                return [Check("warn", self.name, f"Tide variables not checked: {reason}", fix_command("tide"))]
            current = snapshot(ctx, list(wanted))
            hidden = shadows(ctx, list(wanted))
        except ComponentFailed as exc:
            return [Check("warn", self.name, f"cannot check the Tide variables: {exc}")]
        drift = sorted(name for name, values in wanted.items() if current[name].get("value") != values)
        more = f" (and {len(drift) - SHOWN_MAX} more)" if len(drift) > SHOWN_MAX else ""
        checks = [Check("fail", self.name, "prompt variables changed: " + ", ".join(drift[:SHOWN_MAX]) + more, fix)
                  if drift else Check("ok", self.name, f"{len(wanted)} prompt variables match")]
        strays = sorted(current.keys() - wanted.keys())
        if strays:
            checks.append(Check("fail", self.name, "not Tide 6.1.1 variables: " + ", ".join(strays), fix))
        # conf.d/witchy.fish's own caret global holds today's colour from the cache; any other global is not ours.
        caret_colour = _todays_caret(ctx)
        if caret_colour is not None and hidden.get(CARET) == [caret_colour]:
            del hidden[CARET]
        # The tide component disables `set -g tide_…` lines in config.fish and conf.d.
        checks += [Check("fail", self.name, f"{name} is overridden by a global in config.fish or conf.d",
                         fix_command("tide")) for name in sorted(hidden)]
        return checks

    def check(self, ctx: Any, entry: dict) -> list[Check]:
        fix = fix_command(self.name)
        changed = [record["path"] for record in entry["files"]
                   if sha(read(Path(record["path"]))) != record["installed_sha256"]]
        checks = [Check("fail", self.name, "changed or missing: " + ", ".join(changed), fix) if changed
                  else Check("ok", self.name, f"{len(entry['files'])} files match")]
        checks += self._prompt_checks(ctx)
        checks.append(caret_check(ctx))
        if shutil.which("eza", path=ctx.env.get("PATH")):
            checks.append(Check("ok", self.name, "eza found"))
        else:
            checks.append(Check("warn", self.name, f"eza missing — {EZA_FIX}", EZA_FIX))
        checks += log_checks(ctx)
        return checks + backup_checks(self.name, [record.get("backup") for record in entry["files"]])
