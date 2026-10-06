"""windows-terminal: the Moonlit Candle scheme, profile settings and moon-phase sky on the WSL profile."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .. import jsonio, palette, sky_render, wt
from ..ritual import moon
from .base import (Change, Check, ComponentFailed, JsonPlan, Plan, applied_records, apply_changes, backup_checks,
                   file_change, fix_command, read, restore_copy, restore_json, sha)

WT_SKIP = "skipping the terminal colour scheme"
WT_LOCK = "wt.lock"
FONT_KEY = "font"
# Set only once the sky images are in place.
BACKGROUND_KEYS = ("backgroundImage", "backgroundImageOpacity", "backgroundImageAlignment",
                   "backgroundImageStretchMode")
NO_FONT_NOTE = "Windows Terminal: Maple Mono NF is not installed, so the profile font was left as it is."
RITUAL_CONFIG = Path(".claude/witchy/ritual-config.json")


def profile_keys(variant: palette.Variant, font: bool, sky: str | None) -> dict[str, Any]:
    """The profile keys to set: the font only once Maple Mono NF is there, the background only with the sky."""
    keys = {key: value for key, value in variant.wt_profile.items()
            if (font or key != FONT_KEY) and (sky is not None or key not in BACKGROUND_KEYS)}
    if sky is not None:
        keys["backgroundImage"] = sky
    return keys


def ritual_config(settings: Path, guid: str) -> bytes:
    """What the sky job (Plan C) needs to move backgroundImage between the eight images."""
    data = {"settings": str(settings), "profile_guid": guid, "sky": list(wt.SKY_VALUES)}
    return (json.dumps(data, indent=2) + "\n").encode("utf-8")


def _font_source(ctx: Any) -> str | None:
    """"planned" when this run's font component will install Maple Mono NF, "installed" when state records it."""
    planned = ctx.planned.get("font")
    if planned is not None and planned.skip is None:
        return "planned"
    return "installed" if "font" in ctx.entries else None


def _put_back(images: list[Change]) -> None:
    """Undo this run's image writes once settings.json refused the write: no entry will describe them.

    Only a file that still holds this run's bytes is touched, and each one is best effort.
    """
    for image in images:
        if image.before == image.after:
            continue
        try:
            if read(image.path) != image.after:
                continue
            if image.before is None:
                image.path.unlink()
            else:
                jsonio.write_atomic_bytes(image.path, image.before)
        except OSError:
            pass  # best effort: the settings write is the failure that gets reported


class WindowsTerminalComponent:
    name = "windows-terminal"

    def plan(self, ctx: Any, entry: dict | None) -> Plan:
        variant = palette.VARIANTS[ctx.variant or palette.DEFAULT_VARIANT]
        scheme = variant.wt_scheme
        path = wt.locate_settings(ctx.wt_settings, run=ctx.run, recorded=entry["path"] if entry else None,
                                  mount_root=ctx.mount_root)
        if path is None:
            ctx.say(f"Windows Terminal settings.json not found; {WT_SKIP}.")
            return Plan.skipped("settings.json not found")
        try:
            data, text = jsonio.read_json(path)
        except jsonio.StrictJsonError:
            ctx.say(f"{path} is not plain JSON (comments?), so it was left untouched. Add this by hand:")
            ctx.say(wt.manual_snippet(scheme, ctx.env.get("WT_PROFILE_ID") or "<your WSL profile guid>"))
            return Plan.skipped("settings.json is not plain JSON")
        guid, reason = wt.find_profile(data, ctx.env)
        if guid is None:
            ctx.say(f"Windows Terminal: {reason}; {WT_SKIP}.")
            return Plan.skipped(reason)
        if entry and (entry["path"] != str(path) or entry["profile_guid"].lower() != guid.lower()):
            ctx.say(f"Windows Terminal: already installed for profile {entry['profile_guid']} in {entry['path']}; "
                    f"run uninstall first to move it; {WT_SKIP}.")
            return Plan.skipped("installed for another profile")
        sky = wt.SKY_VALUES[moon.phase_bin(ctx.now())]

        def build(font: bool, background: bool) -> tuple[bytes, dict]:
            new_data, record = wt.apply_scheme(data, scheme, guid, entry)
            new_data, record["purged"] = wt.purge_schemes(new_data, palette.PURGED_SCHEMES, scheme["name"],
                                                          (entry or {}).get("purged"))
            recorded = (entry or {}).get("profile_keys")
            desired = profile_keys(variant, font, sky if background else None)
            new_data, keys = wt.apply_profile_keys(new_data, guid, desired, recorded)
            record["profile_keys"] = {**(recorded or {}), **keys}
            return jsonio.dumps_like(new_data, text).encode("utf-8"), record

        font = _font_source(ctx)
        try:
            after, record = build(font is not None, True)
        except ValueError as exc:
            ctx.say(f"Windows Terminal: {exc}; {WT_SKIP}.")
            return Plan.skipped(str(exc))
        earlier = {Path(item["path"]): item for item in (entry or {}).get("files", [])}
        renders = sky_render.cached(ctx.cache_dir / "sky", variant.sky, ctx.sky_size, write=not ctx.dry_run)
        # ms-appdata:///local/ is Windows Terminal's LocalState folder, the one that holds settings.json.
        images = [file_change(path.parent / wt.sky_file(bin_), image, earlier) for bin_, image in enumerate(renders)]
        config = file_change(ctx.home / RITUAL_CONFIG, ritual_config(path, guid), earlier)
        # The bytes planning read: a save made during the render must fail the re-check, not be overwritten.
        settings = Change(path, text.encode("utf-8"), after)
        return Plan(changes=[*images, settings, config], notes=[] if font else [NO_FONT_NOTE],
                    lock=ctx.cache_dir / WT_LOCK,
                    data={"json": JsonPlan(settings, entry, record), "build": build, "font": font,
                          "images": images, "config": config, "earlier": earlier})

    def apply(self, ctx: Any, plan: Plan) -> dict:
        json_plan: JsonPlan = plan.data["json"]
        settings, images, config, earlier = json_plan.change, plan.data["images"], plan.data["config"], plan.data["earlier"]
        backups: dict[Path, Path] = {}
        try:
            apply_changes(ctx, images, backups)
            background = True
        except OSError as exc:
            ctx.say(f"windows-terminal: sky images not copied ({exc})")
            background = False
        font = plan.data["font"] == "installed" or (plan.data["font"] == "planned" and ctx.results.get("font") == "ok")
        if plan.data["font"] == "planned" and not font and NO_FONT_NOTE not in plan.notes:
            plan.notes.append(NO_FONT_NOTE)
        if (font, background) != (plan.data["font"] is not None, True):
            settings.after, json_plan.extra = plan.data["build"](font, background)
        try:
            apply_changes(ctx, [settings], backups)
        except OSError as exc:
            _put_back(images)
            ctx.say(f"Windows Terminal: could not write {settings.path} ({exc}); {WT_SKIP}.")
            raise ComponentFailed(f"could not write {settings.path}") from exc
        entry = json_plan.entry(backups.get(settings.path))
        if background:
            try:
                apply_changes(ctx, [config], backups)
            except OSError as exc:
                ctx.say(f"windows-terminal: could not write {config.path} ({exc}); the sky keeps tonight's phase.")
        entry["files"] = applied_records([*images, config], earlier, backups)
        return entry

    def restore(self, ctx: Any, entry: dict) -> Plan:
        warnings: list[str] = []

        def give_back(data: dict) -> tuple[dict, list[str]]:
            # The purge first: restore_scheme keeps the witchy scheme while profiles.defaults still names it.
            restored, purged = wt.restore_purged(data, entry.get("purged"))
            restored, notes = wt.restore_scheme(restored, entry)
            restored, more = wt.restore_profile_keys(restored, entry["profile_guid"], entry.get("profile_keys", {}))
            return restored, purged + notes + more

        settings = restore_json(entry, give_back, warnings)
        files = [restore_copy(record) for record in entry.get("files", [])]
        # Settings first, so the profile never points at an image that is already gone.
        return Plan(changes=[change for change in [settings, *files] if change is not None], warnings=warnings,
                    lock=ctx.cache_dir / WT_LOCK)

    def check(self, ctx: Any, entry: dict) -> list[Check]:
        fix = fix_command(self.name)
        path = Path(entry["path"])
        try:
            data, _ = jsonio.read_json(path)
        except (OSError, jsonio.StrictJsonError) as exc:
            return [Check("fail", self.name, f"cannot read {path}: {exc}", fix)]
        name = entry["installed_color_scheme"]
        found = wt.profile(data, entry["profile_guid"])
        schemes = data.get("schemes") if isinstance(data, dict) else None
        has_scheme = isinstance(schemes, list) and any(isinstance(s, dict) and s.get("name") == name for s in schemes)
        if found is None:
            checks = [Check("fail", self.name, f"profile {entry['profile_guid']} not found in {path}", fix)]
        elif found.get("colorScheme") != name:
            checks = [Check("fail", self.name, f"profile colour scheme is {found.get('colorScheme')!r}, not {name!r}",
                            fix)]
        elif not has_scheme:
            checks = [Check("fail", self.name, f"scheme {name!r} is missing from {path}", fix)]
        else:
            checks = [Check("ok", self.name, f"profile {entry['profile_guid']} uses {name}")]
        keys = entry.get("profile_keys") or {}
        if found is not None and keys:
            drift = [key for key, record in keys.items() if not wt.holds_installed(found, key, record)]
            checks.append(Check("fail", self.name, "profile keys changed: " + ", ".join(drift), fix) if drift
                          else Check("ok", self.name, f"{len(keys)} profile keys match"))
        for purged in palette.PURGED_SCHEMES:
            places = wt.purged_uses(data, purged)
            if places:
                checks.append(Check("fail", self.name, f"{purged} is still in {path.name}: " + ", ".join(places),
                                    fix))
        records = entry.get("files") or []
        if records:
            changed = [record["path"] for record in records
                       if sha(read(Path(record["path"]))) != record["installed_sha256"]]
            checks.append(Check("fail", self.name, "changed or missing: " + ", ".join(changed), fix) if changed
                          else Check("ok", self.name, f"{len(records)} sky files match"))
        return checks + backup_checks(self.name, [entry.get("backup"), *(record.get("backup") for record in records)])
