"""tide: fisher and Tide 6.1.1, pinned file by file, with Tide as the only prompt (spec 5)."""
from __future__ import annotations

import http.client
import shutil
from pathlib import Path
from typing import Any

from .. import content, fishprobe, installlog, jsonio
from .base import Command, ComponentFailed, Plan, read, sha

FISH = "fish"
FISHER_VERSION = "4.4.5"
# What fisher installs, as content/pins.json names it. Spelled out: fishprobe may still be loading when this is.
FISHER_SOURCE = "jorgebucaran/fisher@4.4.5"
TIDE_SOURCE = "ilancosman/tide@v6.1.1"
FISHER_TIMEOUT = 120  # seconds for each fisher call, which downloads (spec D20)
FISH_MISSING = "fish not found (sudo apt install fish)"
CURL_MISSING = "curl not found (sudo apt install curl)"
NOT_PINNED = "its files do not match the pinned release"

# Sources the pinned fisher.fish, then lets it install itself as a plugin.
BOOTSTRAP_SCRIPT = "source $argv[1]; and fisher install $argv[2]"
FISHER_SCRIPT = "fisher $argv"
# Replaces one Tide with another and keeps every universal tide_ variable: Tide's uninstall erases them and its
# install sets its own defaults. argv: the plugin to remove ("" for none), then the one to install. The values
# are put back even when the install fails, so a later run still has them.
SWAP_SCRIPT = """\
set -l names (set -U --names | string match 'tide_*')
for name in $names
    set -g __witchy_saved_$name $$name
    set -q -U -x $name; and set -g __witchy_exported_$name
end
test -n "$argv[1]"; and fisher remove $argv[1]
fisher install $argv[2]
set -l code $status
for name in $names
    set -l saved __witchy_saved_$name
    if set -q __witchy_exported_$name
        set -U -x $name $$saved
    else
        set -U $name $$saved
    end
end
exit $code
"""


def fisher_command(label: str, *args: str) -> Command:
    """``fisher <args>``: 120 s, and empty standard input (fisher reads plugin names from a pipe)."""
    return Command((FISH, "-c", FISHER_SCRIPT, "--", *args), label, "", timeout=FISHER_TIMEOUT)


def swap_command(label: str, remove: str, install: str) -> Command:
    return Command((FISH, "-c", SWAP_SCRIPT, "--", remove, install), label, "", timeout=FISHER_TIMEOUT)


def installed_name(found: fishprobe.Probe, plugin: str) -> str | None:
    """The name fisher lists ``plugin`` under (``owner/repo``, maybe with ``@ref``), or None."""
    return next((name for name in found.plugins if name.lower().split("@", 1)[0] == plugin), None)


def file_hashes(paths: list[str]) -> dict[str, str]:
    """The SHA-256 of each file fisher lists, by path below fisher's folder (``functions/tide.fish``); a listed
    folder (``functions/tide``) counts with every file below it."""
    hashes = {}
    for listed in paths:
        path = Path(listed)
        key = "/".join(path.parts[-2:])
        if path.is_dir():
            for inner in sorted(path.rglob("*")):
                if inner.is_file():
                    hashes[f"{key}/{inner.relative_to(path).as_posix()}"] = sha(inner.read_bytes())
        elif path.is_file():
            hashes[key] = sha(path.read_bytes())
    return hashes


def mismatches(found: fishprobe.Probe, plugin: str, pinned: dict[str, str]) -> list[str]:
    """The files of ``plugin`` that differ from ``pinned``, are missing, or are not pinned at all."""
    hashes = file_hashes(fishprobe.plugin_files(found, plugin) or [])
    return sorted(name for name in pinned.keys() | hashes.keys() if pinned.get(name) != hashes.get(name))


class TideComponent:
    name = "tide"

    def __init__(self, pins: dict | None = None):
        self.pins = pins

    def _pins(self) -> dict:
        if self.pins is None:
            self.pins = content.load_pins()
        return self.pins

    def _pinned(self, source: str) -> dict[str, str]:
        return self._pins()["plugins"][source]

    def _bootstrap_file(self, ctx: Any) -> Path:
        return ctx.cache_dir / f"fisher-{FISHER_VERSION}.fish"

    def plan(self, ctx: Any, entry: dict | None) -> Plan:
        try:
            found = fishprobe.probe(ctx)
        except ComponentFailed as exc:
            if isinstance(exc.__cause__, FileNotFoundError):
                ctx.say(f"tide: {FISH_MISSING}")
                return Plan.skipped(FISH_MISSING)
            return Plan.skipped(str(exc))
        data: dict[str, Any] = {"entry": entry or {}, "error": None, "fisher": None, "tide": None, "replace": None}
        actions = []
        fisher_name = installed_name(found, fishprobe.FISHER_PLUGIN)
        if found.fisher is None:
            data["fisher"] = "install"
            cached = self._bootstrap_file(ctx)
            bootstrap = self._pins()["bootstrap"]
            source = (f"use {cached}" if sha(read(cached)) == bootstrap["sha256"]
                      else f"download {bootstrap['url']} (sha256 {bootstrap['sha256'][:12]}…)")
            actions += [f"tide: {source}", f"tide: fisher install {FISHER_SOURCE}"]
        elif fisher_name == FISHER_SOURCE and mismatches(found, fishprobe.FISHER_PLUGIN, self._pinned(FISHER_SOURCE)):
            # witchy's own fisher; a fisher the user installed is theirs and is left as it is.
            data["fisher"] = "update"
            actions.append(f"tide: fisher install {FISHER_SOURCE} ({NOT_PINNED})")
        tide_name = installed_name(found, fishprobe.TIDE_PLUGIN)
        if found.tide is not None and tide_name is None:
            data["error"] = "Tide is installed without fisher, so witchy can neither check nor replace it; remove it"
        elif tide_name is None:
            data["tide"] = "install"
            actions.append(f"tide: fisher install {TIDE_SOURCE}")
        else:
            reason = (f"Tide is {found.tide or 'of an unknown version'}" if found.tide != fishprobe.TIDE_VERSION
                      else NOT_PINNED if mismatches(found, fishprobe.TIDE_PLUGIN, self._pinned(TIDE_SOURCE))
                      else None)
            if reason and tide_name == TIDE_SOURCE:
                data["tide"] = "update"
                actions.append(f"tide: fisher install {TIDE_SOURCE} ({reason})")
            elif reason:
                data["tide"], data["replace"] = "replace", tide_name
                actions.append(f"tide: fisher remove {tide_name}, then fisher install {TIDE_SOURCE} ({reason}); "
                               "the Tide variables keep their values")
        installs = data["fisher"] is not None or data["tide"] is not None
        if data["error"] is None and installs and not shutil.which("curl", path=ctx.env.get("PATH")):
            data["error"] = CURL_MISSING  # fisher downloads with curl; nothing is downloaded without it
        if data["error"] is not None:
            actions = [f"tide: cannot go ahead: {data['error']}"]
        # fish plans again after this plan ran when it installs anything (spec D19: fish asks fish itself).
        data["installs"] = installs and data["error"] is None
        return Plan(actions=actions, data=data)

    def apply(self, ctx: Any, plan: Plan) -> dict:
        data = plan.data
        if data["error"] is not None:
            ctx.say(f"tide: {data['error']}; nothing was changed.")
            raise ComponentFailed(data["error"])
        earlier = data["entry"]
        entry = {"installed_fisher": earlier.get("installed_fisher", False),
                 "installed_tide": earlier.get("installed_tide", False),
                 "previous_tide_plugin": earlier.get("previous_tide_plugin"),
                 "removed_plugins": list(earlier.get("removed_plugins", [])),
                 "disabled_files": list(earlier.get("disabled_files", [])),
                 "moved_prompt": earlier.get("moved_prompt")}
        start = dict(entry)
        try:
            if data["fisher"] == "install":
                self._install_fisher(ctx)
            elif data["fisher"] == "update":
                self._run(ctx, fisher_command("update fisher", "install", FISHER_SOURCE))
            if data["fisher"] is not None:
                self._verify(ctx, fishprobe.FISHER_PLUGIN, FISHER_SOURCE, "fisher")
                entry["installed_fisher"] = entry["installed_fisher"] or data["fisher"] == "install"
            if data["tide"] == "replace":
                # Recorded first: from here on the user's Tide may be gone, and uninstall must bring it back.
                entry["previous_tide_plugin"] = entry["previous_tide_plugin"] or data["replace"]
                self._run(ctx, swap_command("install Tide", data["replace"], TIDE_SOURCE))
            elif data["tide"] is not None:
                self._run(ctx, fisher_command("install Tide", "install", TIDE_SOURCE))
            if data["tide"] is not None:
                found = self._verify(ctx, fishprobe.TIDE_PLUGIN, TIDE_SOURCE, "Tide")
                entry["installed_tide"] = entry["installed_tide"] or data["tide"] == "install"
                reason = fishprobe.tide_ready(found)
                if reason:
                    raise ComponentFailed(f"Tide is installed but not ready: {reason}")
        except ComponentFailed as exc:
            ctx.say(f"tide: {exc}")
            if entry == start and not earlier:
                raise
            plan.outcome = f"failed: {exc}"  # what was installed so far stays recorded (ritual 3.3)
        return entry

    def _run(self, ctx: Any, command: Command) -> None:
        done = installlog.run(ctx, command)
        if done.returncode != 0:
            raise ComponentFailed(installlog.failure(ctx, command.label, done))

    def _install_fisher(self, ctx: Any) -> None:
        bootstrap = self._pins()["bootstrap"]
        cached = self._bootstrap_file(ctx)
        data = read(cached)
        if sha(data) != bootstrap["sha256"]:
            try:
                data = ctx.fetch(bootstrap["url"])
            except (OSError, ValueError, http.client.HTTPException) as exc:
                installlog.append(ctx, f"--- download {bootstrap['url']}: {exc}")
                raise ComponentFailed(f"could not download fisher ({exc})") from exc
            installlog.append(ctx, f"--- download {bootstrap['url']}: {len(data)} bytes, "
                                   f"sha256 {sha(data)}")
            if sha(data) != bootstrap["sha256"]:
                raise ComponentFailed("the downloaded fisher.fish does not match the pinned release")
            try:
                jsonio.write_atomic_bytes(cached, data)
            except OSError as exc:
                raise ComponentFailed(f"could not keep fisher.fish in {cached.parent} ({exc})") from exc
        self._run(ctx, Command((FISH, "-c", BOOTSTRAP_SCRIPT, "--", str(cached), FISHER_SOURCE), "install fisher",
                               "", timeout=FISHER_TIMEOUT))

    def _verify(self, ctx: Any, plugin: str, source: str, what: str) -> fishprobe.Probe:
        """After a fisher install: the plugin is there, at the pinned version, file by file (spec D21)."""
        found = fishprobe.probe(ctx)
        version = found.fisher if plugin == fishprobe.FISHER_PLUGIN else found.tide
        wanted = FISHER_VERSION if plugin == fishprobe.FISHER_PLUGIN else fishprobe.TIDE_VERSION
        name = installed_name(found, plugin)
        if name is None or version is None:
            raise ComponentFailed(f"{what} is still not installed (details: {installlog.shown(ctx)})")
        if version != wanted or mismatches(found, plugin, self._pinned(source)):
            self._run(ctx, fisher_command(f"remove {name}", "remove", name))
            raise ComponentFailed(f"{plugin} files do not match the pinned release")
        return found
