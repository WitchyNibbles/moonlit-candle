"""The five ~/.claude/settings.json keys witchy owns, and how to hand them back."""
from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from .records import apply_keys, restore_keys  # noqa: F401  (part of this module's interface)

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


