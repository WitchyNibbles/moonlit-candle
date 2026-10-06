"""Write content/pins.json from the real fisher 4.4.5 and Tide 6.1.1 releases (spec 5.1, D21).

Usage: python3 scripts/pins.py [<output file>]

It downloads fisher's bootstrap file and the release tarball of each plugin from the URLs fisher itself uses,
and records the SHA-256 of the bootstrap file and of every file fisher copies when it installs the plugin.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tarfile
import urllib.request
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from witchy.pinning import plugin_files, tarball_url  # noqa: E402  (shared with the tide component)

OUTPUT = Path(__file__).resolve().parent.parent / "content" / "pins.json"
BOOTSTRAP = "https://raw.githubusercontent.com/jorgebucaran/fisher/4.4.5/functions/fisher.fish"
PLUGINS = ("jorgebucaran/fisher@4.4.5", "ilancosman/tide@v6.1.1")
TIMEOUT = 120
LIMIT = 16 * 1024 * 1024


def pins(fetch: Callable[[str], bytes]) -> dict:
    return {"bootstrap": {"url": BOOTSTRAP, "sha256": hashlib.sha256(fetch(BOOTSTRAP)).hexdigest()},
            "plugins": {plugin: plugin_files(fetch(tarball_url(plugin))) for plugin in PLUGINS}}


def download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
        data = response.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError(f"{url} is larger than {LIMIT} bytes")
    return data


def main(argv: list[str], fetch: Callable[[str], bytes] = download) -> int:
    if len(argv) > 1:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    output = Path(argv[0]) if argv else OUTPUT
    try:
        found = pins(fetch)
        output.write_text(json.dumps(found, indent=2) + "\n", encoding="ascii")
    except (OSError, ValueError, tarfile.TarError) as exc:
        print(f"pins: {exc}", file=sys.stderr)
        return 1
    count = sum(len(files) for files in found["plugins"].values())
    print(f"wrote the pins of {count} files to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
