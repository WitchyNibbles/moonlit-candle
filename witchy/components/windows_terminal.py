"""windows-terminal: the Moonlit Candle colour scheme and profile settings on the WSL profile."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import jsonio, palette, wt
from .base import (Change, Check, ComponentFailed, JsonPlan, Plan, apply_changes, backup_checks, fix_command,
                   restore_json)

WT_SKIP = "skipping the terminal colour scheme"
FONT_KEY = "font"
# Set only once the sky images are in place.
BACKGROUND_KEYS = ("backgroundImage", "backgroundImageOpacity", "backgroundImageAlignment",
                   "backgroundImageStretchMode")
NO_FONT_NOTE = "Windows Terminal: Maple Mono NF is not installed, so the profile font was left as it is."


def profile_keys(variant: palette.Variant, font: bool) -> dict[str, Any]:
    """The profile keys to set: the font only once Maple Mono NF is there."""
    return {key: value for key, value in variant.wt_profile.items()
            if key not in BACKGROUND_KEYS and (font or key != FONT_KEY)}


def _font_source(ctx: Any) -> str | None:
    """"planned" when this run's font component will install Maple Mono NF, "installed" when state records it."""
    planned = ctx.planned.get("font")
    if planned is not None and planned.skip is None:
        return "planned"
    return "installed" if "font" in ctx.entries else None


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

        def build(font: bool) -> tuple[bytes, dict]:
            new_data, record = wt.apply_scheme(data, scheme, guid, entry)
            recorded = (entry or {}).get("profile_keys")
            new_data, keys = wt.apply_profile_keys(new_data, guid, profile_keys(variant, font), recorded)
            record["profile_keys"] = {**(recorded or {}), **keys}
            return jsonio.dumps_like(new_data, text).encode("utf-8"), record

        font = _font_source(ctx)
        try:
            after, record = build(font is not None)
        except ValueError as exc:
            ctx.say(f"Windows Terminal: {exc}; {WT_SKIP}.")
            return Plan.skipped(str(exc))
        change = Change(path, path.read_bytes(), after)
        return Plan(changes=[change], notes=[] if font else [NO_FONT_NOTE],
                    data={"json": JsonPlan(change, entry, record), "build": build, "font": font})

    def apply(self, ctx: Any, plan: Plan) -> dict:
        json_plan: JsonPlan = plan.data["json"]
        if plan.data["font"] == "planned" and ctx.results.get("font") != "ok":
            ctx.say(NO_FONT_NOTE)
            json_plan.change.after, json_plan.extra = plan.data["build"](False)
        try:
            backups = apply_changes(ctx, [json_plan.change])
        except OSError as exc:
            ctx.say(f"Windows Terminal: could not write {json_plan.change.path} ({exc}); {WT_SKIP}.")
            raise ComponentFailed(f"could not write {json_plan.change.path}") from exc
        return json_plan.entry(backups.get(json_plan.change.path))

    def restore(self, ctx: Any, entry: dict) -> Plan:
        warnings: list[str] = []

        def give_back(data: dict) -> tuple[dict, list[str]]:
            restored, notes = wt.restore_scheme(data, entry)
            restored, more = wt.restore_profile_keys(restored, entry["profile_guid"], entry.get("profile_keys", {}))
            return restored, notes + more

        change = restore_json(entry, give_back, warnings)
        return Plan(changes=[change] if change is not None else [], warnings=warnings)

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
        return checks + backup_checks(self.name, [entry.get("backup")])
