"""claude: the theme, output style, status line and tips files, and the five settings keys."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .. import build, claude_settings, content, jsonio
from ..records import snapshot
from .base import (Abort, Change, Check, JsonPlan, Plan, apply_changes, backup_checks, fix_command, read,
                   restore_copy, restore_json, sha)

DEFAULT_PYTHON = "/usr/bin/python3"
RESTART_NOTE = "Restart Claude Code once so it starts watching ~/.claude/themes/"

# dist/ file -> its home, relative to HOME
COPIES = {
    build.THEME: Path(".claude/themes/moonlit-candle.json"),
    build.OUTPUT_STYLE: Path(".claude/output-styles/witchynibbles.md"),
    build.STATUSLINE: Path(".claude/witchy/statusline.py"),
    build.TIPS: Path(".claude/witchy/tips.json"),
}


def python_for(ctx: Any) -> str:
    # Not the pyenv shim: its version follows each project's .python-version.
    if ctx.python:
        return ctx.python
    return DEFAULT_PYTHON if Path(DEFAULT_PYTHON).is_file() else sys.executable


class ClaudeComponent:
    name = "claude"

    def plan(self, ctx: Any, entry: dict | None) -> Plan:
        earlier = {Path(record["path"]): record for record in (entry or {}).get("files", [])}
        files, changes = [], []
        for rel, target in COPIES.items():
            path = ctx.home / target
            before = read(path)
            after = ctx.outputs[rel].encode("utf-8")
            previous = earlier.get(path)
            ours = previous is not None and sha(before) == previous["installed_sha256"]
            changes.append(Change(path, before, after, backup=not ours))
            files.append((path, previous, after))
        settings = self._plan_settings(ctx, (entry or {}).get("settings"))
        notes = [] if (ctx.claude_dir / "themes").is_dir() else [RESTART_NOTE]
        return Plan(changes=[*changes, settings.change], notes=notes, data={"files": files, "settings": settings})

    def _plan_settings(self, ctx: Any, previous: dict | None) -> JsonPlan:
        path = ctx.claude_dir / "settings.json"
        before = read(path)
        data, text = {}, None
        if before is not None:
            try:
                data, text = jsonio.read_json(path)
            except jsonio.StrictJsonError as exc:
                raise Abort(f"{exc}\n{path} is not plain JSON; nothing was changed.") from exc
            if not isinstance(data, dict):
                raise Abort(f"{path} does not hold a JSON object; nothing was changed.")
        desired = claude_settings.desired_keys(ctx.home, python_for(ctx), content.load_spinner()["verbs"])
        new_data, keys = claude_settings.apply_keys(data, desired, previous["keys"] if previous else None)
        after = jsonio.dumps_like(new_data, text).encode("utf-8")
        return JsonPlan(Change(path, before, after), previous, {"keys": keys})

    def apply(self, ctx: Any, plan: Plan) -> dict:
        backups = apply_changes(ctx, plan.changes)
        settings: JsonPlan = plan.data["settings"]
        return {
            "files": [
                {"path": str(path),
                 "backup": previous["backup"] if previous else (str(backups[path]) if path in backups else None),
                 "installed_sha256": sha(after)}
                for path, previous, after in plan.data["files"]
            ],
            "settings": settings.entry(backups.get(settings.change.path)),
        }

    def restore(self, ctx: Any, entry: dict) -> Plan:
        warnings: list[str] = []
        record = entry["settings"]
        settings = restore_json(record, lambda data: claude_settings.restore_keys(data, record["keys"]), warnings)
        copies = [restore_copy(file_record) for file_record in entry["files"]]
        # Settings first, so they never point at files that are already gone.
        return Plan(changes=[change for change in [settings, *copies] if change is not None], warnings=warnings)

    def check(self, ctx: Any, entry: dict) -> list[Check]:
        fix = fix_command(self.name)
        checks = []
        changed = [record["path"] for record in entry["files"]
                   if sha(read(Path(record["path"]))) != record["installed_sha256"]]
        if changed:
            checks.append(Check("fail", self.name, "changed or missing: " + ", ".join(changed), fix))
        else:
            checks.append(Check("ok", self.name, f"{len(entry['files'])} files match"))
        record = entry["settings"]
        try:
            data, _ = jsonio.read_json(Path(record["path"]))
        except (OSError, jsonio.StrictJsonError) as exc:
            checks.append(Check("fail", self.name, f"cannot read {record['path']}: {exc}", fix))
        else:
            data = data if isinstance(data, dict) else {}
            drift = [key for key, key_record in record["keys"].items()
                     if snapshot(data, key) != {"value": key_record["installed"]}]
            if drift:
                checks.append(Check("fail", self.name, "settings changed: " + ", ".join(drift), fix))
            else:
                checks.append(Check("ok", self.name, f"theme {claude_settings.THEME} active, "
                                                     f"{len(record['keys'])} settings keys match"))
        checks.extend(backup_checks(self.name, [record.get("backup"), *(f.get("backup") for f in entry["files"])]))
        return checks
