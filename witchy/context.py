"""Everything a command needs to know about where it runs."""
from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, TextIO

from . import build, fonts, windows


@dataclass
class Context:
    home: Path
    env: Mapping[str, str]
    out: TextIO
    dry_run: bool = False
    wt_settings: Path | None = None
    python: str | None = None
    stamp: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d-%H%M%S"))
    run: Callable[..., Any] = subprocess.run
    dist: Path = field(default_factory=lambda: build.DIST)
    only: tuple[str, ...] = ()
    lock_path: Path | None = None
    variant: str | None = None
    outputs: dict[str, str] | None = None
    mount_root: Path = field(default_factory=lambda: windows.MOUNT_ROOT)
    # Filled by the runner: what earlier components planned and how they ended, and what state records.
    planned: dict[str, Any] = field(default_factory=dict)
    entries: dict[str, dict] = field(default_factory=dict)
    results: dict[str, str] = field(default_factory=dict)
    fetch: Callable[[str], bytes] = fonts.fetch_url

    @property
    def claude_dir(self) -> Path:
        return self.home / ".claude"

    @property
    def cache_dir(self) -> Path:
        """Disposable: renders, downloads and locks that can be deleted at any time."""
        return self.home / ".cache" / "witchy"

    @property
    def state_path(self) -> Path:
        return self.claude_dir / "witchy" / "state.json"

    @property
    def lock_file(self) -> Path:
        # Outside HOME on purpose: uninstall must leave nothing behind in ~/.claude.
        if self.lock_path is not None:
            return self.lock_path
        runtime = self.env.get("XDG_RUNTIME_DIR")
        base = runtime if runtime and Path(runtime).is_dir() else tempfile.gettempdir()
        return Path(base) / f"witchy-{os.getuid()}.lock"

    def say(self, message: str) -> None:
        print(message, file=self.out)
