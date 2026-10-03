"""install / uninstall: kept as the stable entry point; the work happens in runner.py and components/.

Every file change is planned first, so --dry-run can show it and a real run can back each file up
before touching it. state.json records what each setting held before; uninstall gives exactly that back.
"""
from __future__ import annotations

from . import build, claude_settings, content, jsonio, palette, validate, wt  # noqa: F401  (tests patch these)
from .components.base import Abort, Change  # noqa: F401
from .components.claude import DEFAULT_PYTHON, RESTART_NOTE  # noqa: F401
from .components.windows_terminal import WT_SKIP  # noqa: F401
from .context import Context  # noqa: F401
from .runner import NEW_SESSION_NOTE, install, uninstall  # noqa: F401
