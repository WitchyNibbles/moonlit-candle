"""tide: fisher and Tide 6.1.1, pinned file by file, with Tide as the only prompt (spec 5)."""
from __future__ import annotations

import copy
import http.client
import shutil
import tarfile
from pathlib import Path
from typing import Any

from .. import build, content, fishprobe, installlog, jsonio, pinning, takeover
from .base import Change, Command, ComponentFailed, Plan, read, sha, tilde
from .fish import config_dir

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
# install sets its own defaults. argv: the plugin to remove ("" for none), then the one to install ("" for none).
# The values are put back even when the install fails, so a later run still has them.
SWAP_SCRIPT = """\
set -l names (set -U --names | string match 'tide_*')
for name in $names
    set -e -g $name  # a global of the same name (from config.fish) would shadow the universal one
    set -g __witchy_saved_$name $$name
    set -q -U -x $name; and set -g __witchy_exported_$name
end
set -l code 0
if test -n "$argv[1]"
    fisher remove $argv[1]
    set code $status
end
if test -n "$argv[2]"
    fisher install $argv[2]
    set code $status
end
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
    """Remove ``remove`` and install ``install`` (either may be ``""``) with every tide_ variable kept."""
    return Command((FISH, "-c", SWAP_SCRIPT, "--", remove, install), label, "", timeout=FISHER_TIMEOUT)


def installed_name(found: fishprobe.Probe, plugin: str) -> str | None:
    """The name fisher lists ``plugin`` under (``owner/repo``, maybe with ``@ref``), or None."""
    return next((name for name in found.plugins if name.lower().split("@", 1)[0] == plugin), None)


def file_hashes(paths: list[str]) -> dict[str, str]:
    """The SHA-256 of each file fisher lists, by path below fisher's folder (``functions/tide.fish``); a listed
    folder (``functions/tide``) counts with every file below it. Raises ComponentFailed for an unreadable file."""
    hashes = {}
    try:
        for listed in paths:
            path = Path(listed)
            key = "/".join(path.parts[-2:])
            if path.is_dir():
                for inner in sorted(path.rglob("*")):
                    if inner.is_file():
                        hashes[f"{key}/{inner.relative_to(path).as_posix()}"] = sha(inner.read_bytes())
            elif path.is_file():
                hashes[key] = sha(path.read_bytes())
    except OSError as exc:
        raise ComponentFailed(f"could not read the files of a plugin ({exc})") from exc
    return hashes


def mismatches(found: fishprobe.Probe, plugin: str, pinned: dict[str, str]) -> list[str]:
    """The files of ``plugin`` that differ from ``pinned``, are missing, or are not pinned at all."""
    hashes = file_hashes(fishprobe.plugin_files(found, plugin) or [])
    return sorted(name for name in pinned.keys() | hashes.keys() if pinned.get(name) != hashes.get(name))


def aside(path: Path, stamp: str) -> Path:
    """A free ``<name>.bak-witchy-<stamp>`` beside ``path``."""
    target = path.with_name(f"{path.name}.bak-witchy-{stamp}")
    counter = 1
    while target.exists() or target.is_symlink():
        target = path.with_name(f"{path.name}.bak-witchy-{stamp}-{counter}")
        counter += 1
    return target


def located(path: Path) -> Path:
    """``path`` with its folder resolved: fisher may list a symlinked config folder by its target, while a
    symlinked file keeps its own name."""
    return path.parent.resolve() / path.name


def owners(ctx: Any, found: fishprobe.Probe) -> tuple[Path | None, list[str], takeover.Scan]:
    """Every other prompt owner (spec 5.2): a fish_prompt.fish no plugin installed, the other fisher plugins that
    ship one, and the lines of config.fish and conf.d that start one or set a global tide_ variable."""
    folder = config_dir(ctx)
    prompt = folder / "functions" / "fish_prompt.fish"
    where = located(prompt)
    listed = {Path(path) for files in found.plugins.values() for path in files}
    ours = {folder / name for name in build.fish_files("", Path())}  # witchy's own fish files
    hand_written = (prompt if (prompt.is_file() or prompt.is_symlink())
                    and where not in {located(path) for path in listed} else None)
    plugins = [name for name, files in found.plugins.items()
               if name.lower().split("@", 1)[0] != fishprobe.TIDE_PLUGIN
               and where in {located(Path(path)) for path in files}]
    return hand_written, plugins, takeover.scan(folder, listed | ours)


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
        prompt, plugins, scan = owners(ctx, found)
        data: dict[str, Any] = {"entry": entry or {}, "error": None, "fisher": None, "tide": None, "replace": None,
                                "prompt": prompt, "plugins": plugins, "lines": scan.lines}
        actions = []
        if prompt is not None:
            actions.append(f"tide: move {prompt} to {aside(prompt, ctx.stamp).name} (a fish_prompt that is not Tide's)")
        actions += [f"tide: fisher remove {name} (it ships its own fish_prompt)" for name in plugins]
        try:
            fisher_name = installed_name(found, fishprobe.FISHER_PLUGIN)
            if found.fisher is None:
                data["fisher"] = "install"
                cached = self._bootstrap_file(ctx)
                bootstrap = self._pins()["bootstrap"]
                source = (f"use {cached}" if sha(read(cached)) == bootstrap["sha256"]
                          else f"download {bootstrap['url']} (sha256 {bootstrap['sha256'][:12]}…)")
                actions += [f"tide: {source}",
                            f"tide: download {pinning.tarball_url(FISHER_SOURCE)} and check its files against the pins",
                            f"tide: fisher install {FISHER_SOURCE}"]
            elif fisher_name == FISHER_SOURCE and mismatches(found, fishprobe.FISHER_PLUGIN,
                                                             self._pinned(FISHER_SOURCE)):
                # witchy's own fisher; a fisher the user installed is theirs and is left as it is.
                data["fisher"] = "update"
                actions += [f"tide: download {pinning.tarball_url(FISHER_SOURCE)} and check its files against the pins",
                            f"tide: fisher install {FISHER_SOURCE} ({NOT_PINNED})"]
            tide_name = installed_name(found, fishprobe.TIDE_PLUGIN)
            if found.tide is not None and tide_name is None:
                data["error"] = ("Tide is installed without fisher, so witchy can neither check nor replace it; "
                                 "remove it")
            elif tide_name is None:
                data["tide"] = "install"
                actions += [f"tide: download {pinning.tarball_url(TIDE_SOURCE)} and check its files against the pins",
                            f"tide: fisher install {TIDE_SOURCE}"]
            else:
                reason = (f"Tide is {found.tide or 'of an unknown version'}" if found.tide != fishprobe.TIDE_VERSION
                          else NOT_PINNED if mismatches(found, fishprobe.TIDE_PLUGIN, self._pinned(TIDE_SOURCE))
                          else None)
                if reason and tide_name == TIDE_SOURCE:
                    data["tide"] = "update"
                    actions += [f"tide: download {pinning.tarball_url(TIDE_SOURCE)} and check its files "
                                "against the pins", f"tide: fisher install {TIDE_SOURCE} ({reason})"]
                elif reason:
                    data["tide"], data["replace"] = "replace", tide_name
                    actions += [f"tide: download {pinning.tarball_url(TIDE_SOURCE)} and check its files "
                                "against the pins",
                                f"tide: fisher remove {tide_name}, then fisher install {TIDE_SOURCE} ({reason}); "
                                "the Tide variables keep their values"]
        except ComponentFailed as exc:
            data["error"] = str(exc)
        installs = data["fisher"] is not None or data["tide"] is not None
        if scan.blockers:
            data["error"] = "; ".join(scan.blockers)
        elif data["error"] is None and installs and not shutil.which("curl", path=ctx.env.get("PATH")):
            data["error"] = CURL_MISSING  # fisher downloads with curl; nothing is downloaded without it
        if data["error"] is not None:
            return Plan(actions=[f"tide: cannot go ahead: {data['error']}"], data=data)
        # fish plans again once this plan ran when it changes which prompt fish runs (spec D19: fish asks fish).
        data["reprobe"] = installs or prompt is not None or bool(plugins)
        return Plan(changes=scan.changes, actions=actions, data=data)

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
        start = copy.deepcopy(entry)
        try:
            self._apply(ctx, plan, entry)
        except ComponentFailed as exc:
            ctx.say(f"tide: {exc}")
            if entry == start and not earlier:
                raise
            plan.outcome = f"failed: {exc}"  # what was installed so far stays recorded (ritual 3.3)
        return entry

    def _apply(self, ctx: Any, plan: Plan, entry: dict) -> None:
        data, earlier = plan.data, plan.data["entry"]
        if data["fisher"] == "install":
            self._install_fisher(ctx)
        elif data["fisher"] == "update":
            self._check_release(ctx, FISHER_SOURCE)
            self._run(ctx, fisher_command("update fisher", "install", FISHER_SOURCE))
        if data["fisher"] is not None:
            self._verify(ctx, fishprobe.FISHER_PLUGIN, FISHER_SOURCE, "fisher")
            entry["installed_fisher"] = entry["installed_fisher"] or data["fisher"] == "install"
        if data["tide"] is not None:
            # Checked before the prompt and plugins go: a release that does not match leaves them in place.
            self._check_release(ctx, TIDE_SOURCE)
        # Before Tide goes in: fisher refuses to put a file where another one already is.
        if data["prompt"] is not None:
            moved = self._move_prompt(ctx, data["prompt"])
            entry["moved_prompt"] = entry["moved_prompt"] or moved
        for name in data["plugins"]:
            # Recorded first: fisher may delete the plugin's files and still fail, and uninstall must bring it back.
            if name not in entry["removed_plugins"]:
                entry["removed_plugins"].append(name)
            self._run(ctx, fisher_command(f"remove {name}", "remove", name))
            ctx.say(f"tide: removed the fisher plugin {name}, which shipped its own fish_prompt")
        if data["tide"] == "replace":
            # Recorded first: from here on the user's Tide may be gone, and uninstall must bring it back.
            entry["previous_tide_plugin"] = entry["previous_tide_plugin"] or data["replace"]
            self._run(ctx, swap_command("install Tide", data["replace"], TIDE_SOURCE))
        elif data["tide"] is not None:
            self._run(ctx, fisher_command("install Tide", "install", TIDE_SOURCE))
        if data["tide"] is not None:
            # Fresh: no Tide was there before witchy, so a mismatch removes it with its variables (D13).
            fresh = data["tide"] == "install" and not entry["previous_tide_plugin"]
            try:
                found = self._verify(ctx, fishprobe.TIDE_PLUGIN, TIDE_SOURCE, "Tide",
                                     data["replace"] if data["tide"] == "replace" else None, fresh)
            except ComponentFailed as exc:
                if getattr(exc, "restored", False):
                    entry["previous_tide_plugin"] = earlier.get("previous_tide_plugin")  # it is back in place
                elif data["tide"] == "update" and not entry["installed_tide"]:
                    # The user's Tide was (or may be) removed: uninstall puts it back.
                    entry["previous_tide_plugin"] = entry["previous_tide_plugin"] or TIDE_SOURCE
                raise
            entry["installed_tide"] = entry["installed_tide"] or data["tide"] == "install"
            reason = fishprobe.tide_ready(found)
            if reason:
                raise ComponentFailed(f"Tide is installed but not ready: {reason}")
        # Last: while Tide is not in place, the user's own prompt line keeps working.
        self._disable_lines(ctx, plan, entry)

    def _move_prompt(self, ctx: Any, prompt: Path) -> dict:
        target = aside(prompt, ctx.stamp)
        try:
            data = read(prompt)
            prompt.rename(target)
        except OSError as exc:
            raise ComponentFailed(f"could not move {tilde(ctx, prompt)} aside ({exc.strerror or exc})") from exc
        ctx.say(f"tide: moved {tilde(ctx, prompt)} aside, a fish_prompt that was not Tide's "
                f"(backup: {tilde(ctx, target)})")
        return {"path": str(prompt), "backup": str(target), "installed_sha256": sha(data)}

    def _disable_lines(self, ctx: Any, plan: Plan, entry: dict) -> None:
        """Comment out each line of another prompt owner; a file's first backup stays its record (spec 5.2).

        fisher ran for minutes since the plan, so each file is checked again first: an edit is never overwritten."""
        records = {record["path"]: record for record in entry["disabled_files"]}
        for change in plan.changes:
            try:
                if read(change.path) != change.before:
                    raise ComponentFailed(f"{tilde(ctx, change.path)} changed while Tide was installed; its lines "
                                          "were not disabled. Run the command again.")
                backup = jsonio.backup(change.path, ctx.stamp)
                jsonio.write_atomic_bytes(change.path, change.after)
            except OSError as exc:
                raise ComponentFailed(f"could not write {tilde(ctx, change.path)} ({exc.strerror or exc})") from exc
            for line in plan.data["lines"]:
                if line.path == change.path:
                    ctx.say(f"tide: disabled {line.what} in {tilde(ctx, line.path)} line {line.number} "
                            f"(backup: {tilde(ctx, backup)})")
            earlier = records.get(str(change.path))
            records[str(change.path)] = {"path": str(change.path),
                                         "backup": earlier["backup"] if earlier else str(backup),
                                         "installed_sha256": sha(change.after)}
            entry["disabled_files"] = list(records.values())  # each file as it is written

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
        self._check_release(ctx, FISHER_SOURCE)
        self._run(ctx, Command((FISH, "-c", BOOTSTRAP_SCRIPT, "--", str(cached), FISHER_SOURCE), "install fisher",
                               "", timeout=FISHER_TIMEOUT))

    def _check_release(self, ctx: Any, source: str) -> None:
        """Before fisher installs ``source``: download the tarball it will fetch and hash every file it would copy.
        Nothing of an unverified release is run (fisher sources a plugin's conf.d as soon as it installs it)."""
        plugin, url = source.split("@", 1)[0], pinning.tarball_url(source)
        try:
            archive = ctx.fetch(url)
        except (OSError, ValueError, http.client.HTTPException) as exc:
            installlog.append(ctx, f"--- download {url}: {exc}")
            raise ComponentFailed(f"could not download {plugin} to check it ({exc})") from exc
        try:
            files = pinning.plugin_files(archive)
        except (ValueError, OSError, EOFError, tarfile.TarError) as exc:
            installlog.append(ctx, f"--- download {url}: {len(archive)} bytes, not usable ({exc})")
            files = None
        else:
            installlog.append(ctx, f"--- download {url}: {len(archive)} bytes, {len(files)} files, "
                                   f"sha256 {sha(archive)}")
        if files != self._pinned(source):
            raise ComponentFailed(f"{plugin} release does not match the pinned files")

    def _verify(self, ctx: Any, plugin: str, source: str, what: str, restore: str | None = None,
                fresh: bool = False) -> fishprobe.Probe:
        """After a fisher install: the plugin is there, at the pinned version, file by file (spec D21).

        A mismatch takes the plugin out again: fisher and a ``fresh`` Tide with a plain ``fisher remove`` (a fresh
        Tide's uninstall takes its own variables with it, D13); any other Tide through the swap, which keeps the Tide
        variables and puts back ``restore``, the Tide it replaced."""
        found = fishprobe.probe(ctx)
        version = found.fisher if plugin == fishprobe.FISHER_PLUGIN else found.tide
        wanted = FISHER_VERSION if plugin == fishprobe.FISHER_PLUGIN else fishprobe.TIDE_VERSION
        name = installed_name(found, plugin)
        if name is None or version is None:
            raise ComponentFailed(f"{what} is still not installed (details: {installlog.shown(ctx)})")
        if version != wanted or mismatches(found, plugin, self._pinned(source)):
            if plugin == fishprobe.FISHER_PLUGIN or fresh:
                self._run(ctx, fisher_command(f"remove {name}", "remove", name))
            else:
                self._run(ctx, swap_command(f"remove {name}" + (f" and install {restore} again" if restore else ""),
                                            name, restore or ""))
            error = ComponentFailed(f"{plugin} files do not match the pinned release")
            error.restored = restore is not None
            raise error
        return found

    def restore(self, ctx: Any, entry: dict) -> Plan:
        """Uninstall (spec 10): Tide goes or the earlier Tide comes back, then the removed prompt plugins, then
        fisher if witchy installed it; after those commands, the disabled lines and a moved fish_prompt come back."""
        warnings: list[str] = []
        commands: list[Command] = []
        changes = self._enable_lines(ctx, entry, warnings)
        found = None
        if entry["installed_fisher"] or entry["installed_tide"] or entry["previous_tide_plugin"] or \
                entry["removed_plugins"]:
            try:
                found = fishprobe.probe(ctx)
            except ComponentFailed as exc:
                if not isinstance(exc.__cause__, FileNotFoundError):
                    raise  # fish is there but did not answer: keep the component and retry later
                warnings.append("tide: fish not found, so fisher, Tide and the prompt plugins stay as they are.")
        removes_tide = False
        if found is not None:
            tide_name = installed_name(found, fishprobe.TIDE_PLUGIN)
            previous = entry["previous_tide_plugin"]
            if previous and (tide_name or "").lower() != previous.lower():
                commands.append(swap_command(f"put back {previous} in place of Tide {fishprobe.TIDE_VERSION}",
                                             tide_name or "", previous))
            elif not previous and entry["installed_tide"] and tide_name:
                # A plain remove: no Tide was there before, so Tide's uninstall takes its variables with it (D13).
                commands.append(fisher_command(f"remove Tide ({tide_name})", "remove", tide_name))
                removes_tide = True
            for plugin in entry["removed_plugins"]:
                if installed_name(found, plugin.lower().split("@", 1)[0]) is None:
                    commands.append(fisher_command(f"put back {plugin}", "install", plugin))
            fisher_name = installed_name(found, fishprobe.FISHER_PLUGIN)
            if entry["installed_fisher"] and fisher_name:
                commands.append(fisher_command(f"remove fisher ({fisher_name})", "remove", fisher_name))
        changes += self._prompt_back(ctx, entry.get("moved_prompt"), found, removes_tide, warnings)
        return Plan(changes=changes, commands=commands, warnings=warnings)

    def _enable_lines(self, ctx: Any, entry: dict, warnings: list[str]) -> list[Change]:
        """Each disabled line back as it was; the user's other edits to the file stay."""
        changes = []
        for record in entry["disabled_files"]:
            path = Path(record["path"])
            if path.is_symlink():
                warnings.append(f"tide: {tilde(ctx, path)} is a symlink now and is not edited; remove "
                                f"'{takeover.PREFIX.decode()}' from its lines yourself.")
                continue
            current = read(path)
            after = None if current is None else takeover.enable(current)
            if after != current:
                changes.append(Change(path, current, after, backup=sha(current) != record["installed_sha256"]))
        return changes

    def _prompt_back(self, ctx: Any, moved: dict | None, found: fishprobe.Probe | None, removes_tide: bool,
                     warnings: list[str]) -> list[Change]:
        """The fish_prompt.fish witchy moved aside, back in its place once Tide's is gone."""
        if not moved:
            return []
        path, backup = Path(moved["path"]), Path(moved["backup"])
        data, current = read(backup), read(path)
        tides = found is not None and str(path) in (fishprobe.plugin_files(found, fishprobe.TIDE_PLUGIN) or [])
        if data is None:
            warnings.append(f"tide: {tilde(ctx, backup)} is gone, so your fish_prompt cannot come back.")
            return []
        if current is not None and not (tides and removes_tide):
            warnings.append(f"tide: {tilde(ctx, path)} is not witchy's to replace; your fish_prompt stays at "
                            f"{tilde(ctx, backup)}.")
            return []
        # Runs after the commands: by then Tide's file is gone.
        return [Change(path, current, data, backup=False), Change(backup, data, None, backup=False)]
