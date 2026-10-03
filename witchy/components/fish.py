"""fish: the greeting package, the fish functions and conf.d snippet, and the Tide prompt colours (spec 5, 6, 7)."""
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

FISH = "fish"
RITUAL_DIR = Path(".claude/witchy/ritual")
NEW_TAB_NOTE = "Open a new terminal tab to see the new prompt and greeting; open shells keep the old ones."
NO_EZA_NOTE = "eza is not installed, so ll and lt use ls; install it with: sudo apt install eza"
SENTINEL = "witchy-fish"  # whatever config.fish prints comes before it
EZA_FIX = "sudo apt install eza"
RECENT = timedelta(days=7)  # older greeting and sky errors are history, not a warning
MESSAGE_MAX = 100
LOG_LINE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d) (greeting|sky): (.*)$")

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
        unknown = False
        if updates:
            # After the files: the moon item must exist before Tide is told to show it (spec 5.3).
            try:
                result = run_command(ctx, set_command(updates, f"set {len(updates)} Tide variables"), check=False)
                done = set(_fields(result.stdout))
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
