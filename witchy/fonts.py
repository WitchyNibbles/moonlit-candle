"""Maple Mono NF: the pinned release, safe extraction, TrueType names and the per-user font registry."""
from __future__ import annotations

import io
import re
import struct
import subprocess
import urllib.request
import zipfile
from typing import Any, Callable

RELEASE = "v7.9"
URL = f"https://github.com/subframe7536/maple-font/releases/download/{RELEASE}/MapleMono-NF.zip"
SHA256 = "59098b87c895d871635d37680e88000ae2b2b25b55428195b228ec589e35fb89"
MEMBERS = ("MapleMono-NF-Regular.ttf", "MapleMono-NF-Italic.ttf", "MapleMono-NF-Bold.ttf",
           "MapleMono-NF-BoldItalic.ttf")
MEMBER_LIMIT = 20 * 1024 * 1024
DOWNLOAD_LIMIT = 64 * 1024 * 1024
FAMILY = "Maple Mono NF"
REGISTRY_KEY = r"HKCU\Software\Microsoft\Windows NT\CurrentVersion\Fonts"
_REG_VALUE = re.compile(r"^ {4}(.+?) {4}REG_[A-Z_]+ {4}(.*)$")


class FontArchiveError(ValueError):
    """The release archive or a font in it is not usable; nothing is installed."""


def fetch_url(url: str, timeout: float = 60) -> bytes:
    """Download over HTTPS; urllib checks the certificate against the system's trust store."""
    with urllib.request.urlopen(url, timeout=timeout) as response:
        data = response.read(DOWNLOAD_LIMIT + 1)
    if len(data) > DOWNLOAD_LIMIT:
        raise FontArchiveError(f"{url} is larger than {DOWNLOAD_LIMIT} bytes")
    return data


def extract(archive: bytes, names: tuple[str, ...] = MEMBERS, limit: int = MEMBER_LIMIT) -> dict[str, bytes]:
    """The named members only, looked up by exact name, each at most ``limit`` bytes."""
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            members = {}
            for name in names:
                info = bundle.getinfo(name)
                if info.file_size > limit:
                    raise FontArchiveError(f"{name} is larger than {limit} bytes")
                with bundle.open(info) as member:
                    data = member.read(limit + 1)
                if len(data) > limit:
                    raise FontArchiveError(f"{name} is larger than {limit} bytes")
                members[name] = data
            return members
    except (zipfile.BadZipFile, KeyError) as exc:
        raise FontArchiveError(f"the font archive is not usable ({exc})") from exc


def full_name(ttf: bytes) -> str:
    """The full font name (name ID 4), preferring the Windows English record, as the registry expects."""
    try:
        tables = struct.unpack_from(">H", ttf, 4)[0]
        for index in range(tables):
            tag, _, offset, _ = struct.unpack_from(">4sIII", ttf, 12 + 16 * index)
            if tag == b"name":
                break
        else:
            raise FontArchiveError("the font has no name table")
        _, count, strings = struct.unpack_from(">HHH", ttf, offset)
        fallback = None
        for index in range(count):
            platform, _, language, name_id, length, start = struct.unpack_from(">HHHHHH", ttf, offset + 6 + 12 * index)
            if name_id != 4:
                continue
            raw = ttf[offset + strings + start:offset + strings + start + length]
            if platform == 3 and language == 0x409:
                return raw.decode("utf-16-be")
            if platform == 1 and fallback is None:
                fallback = raw.decode("latin-1")
    except (struct.error, UnicodeDecodeError) as exc:
        raise FontArchiveError(f"the font's name table is not readable ({exc})") from exc
    if fallback:
        return fallback
    raise FontArchiveError("the font has no full name")


def parse_registry(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        match = _REG_VALUE.match(line.rstrip("\r"))
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values


def registered(run: Callable[..., Any] = subprocess.run) -> dict[str, str] | None:
    """The current user's font registry values, or None when reg.exe cannot be asked."""
    try:
        done = run(["reg.exe", "query", REGISTRY_KEY], capture_output=True, text=True, errors="replace", timeout=10)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return parse_registry(done.stdout or "") if done.returncode == 0 else None


def register_command(name: str, data: str) -> list[str]:
    return ["reg.exe", "add", REGISTRY_KEY, "/v", name, "/t", "REG_SZ", "/d", data, "/f"]
