"""What fisher 4.4.5 downloads for ``owner/repo@ref`` and which of its files it installs (spec 5.1, D21).

Shared by scripts/pins.py, which records the hashes, and the tide component, which checks a release against
them before fisher installs it.
"""
from __future__ import annotations

import hashlib
import io
import tarfile

FOLDERS = ("functions", "themes", "conf.d", "completions")  # what fisher copies from a plugin


def tarball_url(plugin: str) -> str:
    """The URL fisher 4.4.5 downloads ``owner/repo@ref`` from."""
    repo, ref = plugin.split("@", 1)
    return f"https://api.github.com/repos/{repo}/tarball/{ref}"


def plugin_files(archive: bytes) -> dict[str, str]:
    """The SHA-256 of each file fisher installs from a release tarball, by path below fisher's folder.

    fisher copies the entries of functions/, themes/, conf.d/ and completions/ in the archive's top folder
    (not the ones whose name starts with a dot), with everything below a folder among them.
    Raises ValueError (or tarfile.TarError) for an archive that is not usable.
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
