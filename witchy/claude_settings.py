"""The five ~/.claude/settings.json keys witchy owns, and how to hand them back."""
from __future__ import annotations

import copy
import shlex
from pathlib import Path
from typing import Any

from .records import put_back, snapshot

THEME = "custom:moonlit-candle"
OUTPUT_STYLE = "WitchyNibbles"
TIPS_LABEL = "Grimoire"
TIPS_FILE = "~/.claude/witchy/tips.json"
KEYS = ("theme", "statusLine", "spinnerVerbs", "spinnerTipsOverride", "outputStyle")


def desired_keys(home: Path, python: str, verbs: list[str]) -> dict[str, Any]:
    script = home / ".claude" / "witchy" / "statusline.py"
    return {
        "theme": THEME,
        "statusLine": {"type": "command", "command": f"{shlex.quote(python)} -I {shlex.quote(str(script))}", "padding": 0},
        "spinnerVerbs": {"mode": "replace", "verbs": list(verbs)},
        "spinnerTipsOverride": {"label": TIPS_LABEL, "tipsFile": TIPS_FILE, "excludeDefault": False},
        "outputStyle": OUTPUT_STYLE,
    }


def apply_keys(data: dict, desired: dict[str, Any], recorded: dict | None) -> tuple[dict, dict]:
    """Set every desired key. On a reinstall the first-ever previous value is kept, not witchy's own."""
    result = copy.deepcopy(data)
    records = {}
    for key, value in desired.items():
        earlier = (recorded or {}).get(key)
        previous = earlier["previous"] if earlier else snapshot(result, key)
        records[key] = {"previous": previous, "installed": copy.deepcopy(value)}
        result[key] = copy.deepcopy(value)
    return result, records


def restore_keys(data: dict, records: dict) -> tuple[dict, list[str]]:
    """Give back each key's previous value, unless it no longer holds what witchy installed."""
    result = copy.deepcopy(data)
    warnings = []
    for key, record in records.items():
        current = snapshot(result, key)
        if current == record["previous"]:
            continue  # already given back, for example by an uninstall that stopped part-way
        if current != {"value": record["installed"]}:
            warnings.append(f"{key} was changed after install; leaving it as it is.")
            continue
        put_back(result, key, record["previous"])
    return result, warnings
