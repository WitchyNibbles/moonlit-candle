"""font: Maple Mono NF for the current Windows user (no admin rights needed). Uninstall keeps it."""
from __future__ import annotations

import hashlib
import http.client
import subprocess
from pathlib import Path
from typing import Any

from .. import fonts, jsonio, windows
from .base import Change, Check, ComponentFailed, Plan, apply_changes, fix_command, read, sha

FONTS_SUBDIR = ("AppData", "Local", "Microsoft", "Windows", "Fonts")
RESTART_WT_NOTE = "Restart Windows Terminal once so it sees Maple Mono NF."
KEPT_WARNING = "Maple Mono NF stays installed; remove it in Windows Settings > Fonts if you no longer want it."
KEEP = "keeping the current font"


class FontComponent:
    name = "font"

    def plan(self, ctx: Any, entry: dict | None) -> Plan:
        home = windows.user_home(ctx.run, ctx.mount_root)
        if home is None:
            ctx.say(f"font: Windows user folder not found; {KEEP}.")
            return Plan.skipped("Windows user folder not found")
        values = fonts.registered(ctx.run)
        if values is None:
            ctx.say(f"font: cannot read the font registry (reg.exe); {KEEP}.")
            return Plan.skipped("cannot read the font registry")
        present = self._present(ctx, values)
        if present:
            return Plan(data={"present": present})
        folder = home.wsl.joinpath(*FONTS_SUBDIR)
        archive = ctx.cache_dir / f"MapleMono-NF-{fonts.RELEASE}.zip"
        source = f"use {archive}" if archive.is_file() else f"download {fonts.URL}"
        actions = [f"font: {source} (sha256 {fonts.SHA256[:12]}…)",
                   *(f"font: copy {name} to {folder}" for name in fonts.MEMBERS),
                   f"font: register {len(fonts.MEMBERS)} fonts under {fonts.REGISTRY_KEY} with reg.exe"]
        return Plan(actions=actions, notes=[RESTART_WT_NOTE], data={"home": home, "folder": folder, "archive": archive})

    def _present(self, ctx: Any, values: dict[str, str]) -> dict[str, str]:
        """Registry values for Maple Mono NF whose file exists, whoever installed them."""
        present = {}
        for name, data in values.items():
            path = windows.to_wsl(data, ctx.mount_root)
            if name.startswith(fonts.FAMILY) and path is not None and path.is_file():
                present[name] = data
        return present

    def _archive(self, ctx: Any, path: Path) -> bytes:
        cached = read(path)
        if cached is not None and hashlib.sha256(cached).hexdigest() == fonts.SHA256:
            return cached
        try:
            data = ctx.fetch(fonts.URL)
        except (OSError, ValueError, http.client.HTTPException) as exc:
            ctx.say(f"font: download failed ({exc}); {KEEP}.")
            raise ComponentFailed(f"download failed ({exc})") from exc
        if hashlib.sha256(data).hexdigest() != fonts.SHA256:
            path.unlink(missing_ok=True)
            ctx.say("font: checksum mismatch, nothing installed.")
            raise ComponentFailed("checksum mismatch")
        try:
            jsonio.write_atomic_bytes(path, data)
        except OSError:
            pass  # the cache only saves the next download
        return data

    def apply(self, ctx: Any, plan: Plan) -> dict:
        if "present" in plan.data:
            return {"preexisting": True, "registered": plan.data["present"], "files": []}
        home, folder = plan.data["home"], plan.data["folder"]
        archive = self._archive(ctx, plan.data["archive"])
        try:
            members = fonts.extract(archive)
            names = {member: fonts.full_name(data) for member, data in members.items()}
        except fonts.FontArchiveError as exc:
            ctx.say(f"font: {exc}; {KEEP}.")
            raise ComponentFailed(str(exc)) from exc
        changes = [Change(folder / member, read(folder / member), data) for member, data in members.items()]
        try:
            apply_changes(ctx, changes)
        except OSError as exc:
            ctx.say(f"font: could not copy the font files ({exc}); {KEEP}.")
            raise ComponentFailed(f"could not copy the font files ({exc})") from exc
        registered = {}
        for change in changes:
            name = f"{names[change.path.name]} (TrueType)"
            data = "\\".join([home.windows, *FONTS_SUBDIR, change.path.name])
            try:
                done = ctx.run(fonts.register_command(name, data), capture_output=True, text=True,
                               errors="replace", timeout=10)
            except (OSError, ValueError, subprocess.SubprocessError):
                done = None
            if done is None or done.returncode != 0:
                ctx.say(f"font: could not register {name!r} under {fonts.REGISTRY_KEY}; {KEEP}.")
                raise ComponentFailed(f"could not register {name}")
            registered[name] = data
        return {"preexisting": False, "release": fonts.RELEASE, "registered": registered,
                "files": [{"path": str(change.path), "installed_sha256": sha(change.after)} for change in changes]}

    def restore(self, ctx: Any, entry: dict) -> Plan:
        return Plan(warnings=[KEPT_WARNING])

    def check(self, ctx: Any, entry: dict) -> list[Check]:
        fix = fix_command(self.name)
        checks = []
        changed = [record["path"] for record in entry["files"]
                   if sha(read(Path(record["path"]))) != record["installed_sha256"]]
        if changed:
            checks.append(Check("fail", self.name, "changed or missing: " + ", ".join(changed), fix))
        values = fonts.registered(ctx.run)
        if values is None:
            checks.append(Check("warn", self.name, "cannot read the font registry (reg.exe)"))
        else:
            lost = [name for name in entry["registered"] if name not in values]
            if lost:
                checks.append(Check("fail", self.name, "not registered: " + ", ".join(lost), fix))
        if not checks:
            checks.append(Check("ok", self.name, f"{fonts.FAMILY} registered ({len(entry['registered'])} fonts)"))
        return checks
