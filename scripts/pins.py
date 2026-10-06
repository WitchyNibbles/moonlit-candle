"""Write content/pins.json from the real fisher 4.4.5 and Tide 6.1.1 releases (spec 5.1, D21).

Usage: python3 scripts/pins.py [<output file>]

It downloads fisher's bootstrap file and the release tarball of each plugin from the URLs fisher itself uses,
and records the SHA-256 of the bootstrap file and of every file fisher copies when it installs the plugin.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import tarfile
import urllib.request
from pathlib import Path
from typing import Callable

OUTPUT = Path(__file__).resolve().parent.parent / "content" / "pins.json"
BOOTSTRAP = "https://raw.githubusercontent.com/jorgebucaran/fisher/4.4.5/functions/fisher.fish"
PLUGINS = ("jorgebucaran/fisher@4.4.5", "ilancosman/tide@v6.1.1")
FOLDERS = ("functions", "themes", "conf.d", "completions")  # what fisher copies from a plugin
TIMEOUT = 120
LIMIT = 16 * 1024 * 1024


def tarball_url(plugin: str) -> str:
    """The URL fisher 4.4.5 downloads ``owner/repo@ref`` from."""
    repo, ref = plugin.split("@", 1)
    return f"https://api.github.com/repos/{repo}/tarball/{ref}"


def plugin_files(archive: bytes) -> dict[str, str]:
    """The SHA-256 of each file fisher installs from a release tarball, by path below fisher's folder.

    fisher copies the entries of functions/, themes/, conf.d/ and completions/ in the archive's top folder
    (not the ones whose name starts with a dot), with everything below a folder among them.
    """
    found = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        for member in tar.getmembers():
            parts = member.name.split("/")
            if len(parts) < 3 or parts[1] not in FOLDERS or parts[2].startswith("."):
                continue
            if member.issym() or member.islnk():
                raise ValueError(f"{member.name} is a link; fisher would copy its target")
            if member.isfile():
                found["/".join(parts[1:])] = hashlib.sha256(tar.extractfile(member).read()).hexdigest()
    if not found:
        raise ValueError("the archive holds no file fisher would install")
    return dict(sorted(found.items()))


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
