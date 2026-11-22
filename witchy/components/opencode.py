"""opencode: the theme file, and the one tui.json key that selects it."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from .. import build, jsonio
from ..records import apply_keys, restore_keys, snapshot
from .base import (Change, Check, ComponentFailed, JsonPlan, Plan, applied_records, apply_changes, backup_checks,
                   file_change, file_record, fix_command, read, restore_copy, restore_json, sha)

THEME = "moonlit-candle"
NO_OPENCODE_NOTE = "opencode was not found on PATH; the Moonlit Candle theme is ready for when it is installed."
JSONC_WARNING = ("opencode: {path} is not plain JSON (comments?) or not an object, so it was left untouched. "
                 f'Add "theme": "{THEME}" to it by hand.')
TUI_JSONC_WARNING = ("opencode: {path} sets \"theme\", and OpenCode reads it after tui.json, so it wins. "
                     "Remove that line to use Moonlit Candle.")

_COMMENT_OR_STRING = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.DOTALL)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")
_THEME_KEY = re.compile(r'"theme"\s*:')


def config_dir(ctx: Any) -> Path:
    """OpenCode's own rule: an absolute ``$XDG_CONFIG_HOME``, else ``~/.config``."""
    xdg = ctx.env.get("XDG_CONFIG_HOME") or ""
    base = Path(xdg) if xdg and Path(xdg).is_absolute() else ctx.home / ".config"
    return base / "opencode"


def _on_path(ctx: Any) -> bool:
    # Never None: that would search the real PATH instead of the context's.
    return shutil.which("opencode", path=ctx.env.get("PATH", "")) is not None


def _jsonc_theme(path: Path) -> Any:
    """The ``theme`` that a JSONC file sets, or None when it sets none."""
    text = read(path)
    if text is None:
        return None
    bare = _COMMENT_OR_STRING.sub(lambda m: m.group() if m.group().startswith('"') else " ",
                                  text.decode("utf-8", "replace"))
    try:
        data = json.loads(_TRAILING_COMMA.sub(r"\1", bare))
    except ValueError:
        return "?" if _THEME_KEY.search(bare) else None
    return data.get("theme") if isinstance(data, dict) else None


def _overrides(config: Path) -> Path | None:
    """``tui.jsonc`` when it picks a theme other than ours: OpenCode reads it after tui.json."""
    path = config / "tui.jsonc"
    theme = _jsonc_theme(path)
    return path if theme is not None and theme != THEME else None


class OpenCodeComponent:
    name = "opencode"

    def plan(self, ctx: Any, entry: dict | None) -> Plan:
        config = config_dir(ctx)
        earlier = {Path(record["path"]): record for record in (entry or {}).get("files", [])}
        theme = file_change(config / "themes" / f"{THEME}.json", ctx.outputs[build.OPENCODE_THEME].encode("utf-8"),
                            earlier)
        settings = self._plan_settings(ctx, config / "tui.json", (entry or {}).get("settings"))
        override = _overrides(config)
        if override is not None:
            ctx.say(TUI_JSONC_WARNING.format(path=override))
        notes = [] if _on_path(ctx) else [NO_OPENCODE_NOTE]
        changes = [theme, *([settings.change] if settings else [])]
        # "kept" is the record that stands when this run does not (fully) write tui.json: the one it gave back.
        return Plan(changes=changes, notes=notes, data={"earlier": earlier, "theme": theme, "settings": settings,
                                                        "kept": (entry or {}).get("settings")})

    def _plan_settings(self, ctx: Any, path: Path, previous: dict | None) -> JsonPlan | None:
        """The tui.json rewrite, or None (after a warning) when the file is not plain JSON."""
        before = read(path)
        data, text = {}, None
        if before is not None:
            try:
                data, text = jsonio.read_json(path)
            except jsonio.StrictJsonError:
                data = None
            if not isinstance(data, dict):
                ctx.say(JSONC_WARNING.format(path=path))
                return None
        new_data, keys = apply_keys(data, {"theme": THEME}, previous["keys"] if previous else None)
        after = jsonio.dumps_like(new_data, text).encode("utf-8")
        return JsonPlan(Change(path, before, after), previous, {"keys": keys})

    def apply(self, ctx: Any, plan: Plan) -> dict:
        theme: Change = plan.data["theme"]
        backups: dict[Path, Path] = {}
        try:
            apply_changes(ctx, plan.changes, backups)
        except OSError as exc:
            return self._partial(ctx, plan, backups, exc)
        entry: dict[str, Any] = {"files": [file_record(theme, plan.data["earlier"], backups)]}
        settings = self._settings_record(plan, backups, written=True)
        if settings:
            entry["settings"] = settings
        return entry

    def _partial(self, ctx: Any, plan: Plan, backups: dict[Path, Path], exc: OSError) -> dict:
        """Record what a write that failed part-way left in place, so uninstall gives back the right bytes."""
        settings: JsonPlan | None = plan.data["settings"]
        ctx.say(f"opencode: could not write ({exc}); run install again.")
        entry: dict[str, Any] = {"files": applied_records([plan.data["theme"]], plan.data["earlier"], backups)}
        written = settings is not None and read(settings.change.path) == settings.change.after
        record = self._settings_record(plan, backups, written=written)
        if record:
            entry["settings"] = record
        if not entry["files"] and "settings" not in entry:
            raise ComponentFailed(f"could not write ({exc})") from exc
        plan.outcome = f"failed: could not write ({exc})"
        return entry

    @staticmethod
    def _settings_record(plan: Plan, backups: dict[Path, Path], written: bool) -> dict | None:
        """The tui.json record to keep: the new one when the rewrite landed, else the one it gave back."""
        settings: JsonPlan | None = plan.data["settings"]
        if settings is not None and written:
            return settings.entry(backups.get(settings.change.path))
        return plan.data["kept"]

    def restore(self, ctx: Any, entry: dict) -> Plan:
        warnings: list[str] = []
        record = entry.get("settings")
        settings = None
        if record is not None:
            settings = restore_json(record, lambda data: restore_keys(data, record["keys"]), warnings)
        copies = [restore_copy(file_record) for file_record in entry["files"]]
        # tui.json first, so it never names a theme file that is already gone.
        return Plan(changes=[change for change in [settings, *copies] if change is not None], warnings=warnings)

    def check(self, ctx: Any, entry: dict) -> list[Check]:
        fix = fix_command(self.name)
        config = Path(entry["files"][0]["path"]).parent.parent if entry["files"] else config_dir(ctx)
        checks = []
        changed = [record["path"] for record in entry["files"]
                   if sha(read(Path(record["path"]))) != record["installed_sha256"]]
        if changed:
            checks.append(Check("fail", self.name, "changed or missing: " + ", ".join(changed), fix))
        else:
            checks.append(Check("ok", self.name, "theme file matches"))
        record = entry.get("settings")
        if record is None:
            checks.append(Check("fail", self.name, f'theme not selected in {config / "tui.json"}; '
                                                   f'add "theme": "{THEME}" to it by hand if it has comments', fix))
        else:
            checks.append(self._check_settings(record, fix))
        override = _overrides(config)
        if override is not None:
            checks.append(Check("warn", self.name, f'{override} sets "theme" and wins over tui.json',
                                f'remove "theme" from {override}'))
        if not _on_path(ctx):
            checks.append(Check("info", self.name, NO_OPENCODE_NOTE))
        backups = [(record or {}).get("backup"), *(f.get("backup") for f in entry["files"])]
        checks.extend(backup_checks(self.name, backups))
        return checks

    def _check_settings(self, record: dict, fix: str) -> Check:
        try:
            data, _ = jsonio.read_json(Path(record["path"]))
        except (OSError, jsonio.StrictJsonError) as exc:
            return Check("fail", self.name, f"cannot read {record['path']}: {exc}", fix)
        data = data if isinstance(data, dict) else {}
        drift = [key for key, key_record in record["keys"].items()
                 if snapshot(data, key) != {"value": key_record["installed"]}]
        if drift:
            return Check("fail", self.name, "settings changed: " + ", ".join(drift), fix)
        return Check("ok", self.name, f"theme {THEME} selected in {record['path']}")
