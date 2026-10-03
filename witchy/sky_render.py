"""The Windows Terminal sky: one shared starfield and the moon for each of the eight phase bins.

Stdlib only: a pre-filled bytearray where only star and moon pixels are touched, written as a PNG.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import struct
import zlib
from pathlib import Path

from . import jsonio
from .ritual.moon import BINS

SIZE = (2560, 1440)
SEED = 1031  # fixed, so the starfield is identical in all eight images
STARS = 220
SPARKLES = 7


def _rgb(colour: str) -> tuple[int, int, int]:
    value = colour.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _mix(a: tuple[int, ...], b: tuple[int, ...], amount: float) -> tuple[int, ...]:
    return tuple(round(x + (y - x) * amount) for x, y in zip(a, b))


def _png(width: int, height: int, raw: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")


def render(bin_: int, colours: dict[str, str], size: tuple[int, int] = SIZE) -> bytes:
    """A PNG of the sky for phase bin ``bin_`` (0 new … 7 waning crescent), northern-hemisphere view."""
    width, height = size
    scale = width / SIZE[0]
    stride = 1 + 3 * width
    raw = bytearray((b"\x00" + bytes(_rgb(colours["background"])) * width) * height)

    def put(x: int, y: int, rgb: tuple[int, ...]) -> None:
        if 0 <= x < width and 0 <= y < height:
            offset = y * stride + 1 + 3 * x
            raw[offset:offset + 3] = bytes(rgb)

    rng = random.Random(SEED)
    star_colours = [_rgb(colours[key]) for key in ("star", "star_gold", "star_violet")]
    for _ in range(STARS):
        x, y = int(rng.random() * width), int(rng.random() * height)
        rgb = star_colours[int(rng.random() * len(star_colours))]
        dot = 2 if rng.random() < 0.25 else 1
        for dx in range(dot):
            for dy in range(dot):
                put(x + dx, y + dy, rgb)
    sparkle = _rgb(colours["star"])
    for _ in range(SPARKLES):
        x, y = int(rng.random() * width), int(rng.random() * height)
        arm = max(1, round((3 + rng.random() * 3) * scale))
        for d in range(-arm, arm + 1):
            put(x + d, y, sparkle)
            put(x, y + d, sparkle)

    radius = 150 * scale
    cx, cy = width - 260 * scale, height - 260 * scale
    lit, dark, rim = _rgb(colours["moon"]), _rgb(colours["moon_dark"]), _rgb(colours["moon_rim"])
    light = (1 - math.cos(2 * math.pi * bin_ / BINS)) / 2
    waxing = bin_ <= BINS // 2
    terminator_scale = math.cos(2 * math.pi * bin_ / BINS)
    reach = radius * 1.35
    rim_width = max(1.0, 2 * scale)
    for y in range(max(0, int(cy - reach)), min(height, int(cy + reach) + 1)):
        ny = (y + 0.5 - cy) / radius
        for x in range(max(0, int(cx - reach)), min(width, int(cx + reach) + 1)):
            nx = (x + 0.5 - cx) / radius
            distance = math.hypot(nx, ny)
            if distance > 1:
                fade = 1 - (distance - 1) / 0.35
                if fade > 0 and light > 0:  # a soft glow that grows with the lit fraction
                    offset = y * stride + 1 + 3 * x
                    put(x, y, _mix(tuple(raw[offset:offset + 3]), lit, 0.22 * light * fade * fade))
                continue
            terminator = terminator_scale * math.sqrt(max(0.0, 1 - ny * ny))
            if light > 0 and (nx if waxing else -nx) >= terminator:
                put(x, y, lit)
            elif (1 - distance) * radius <= rim_width:
                put(x, y, rim)
            else:
                put(x, y, dark)
    return _png(width, height, bytes(raw))


def cached(root: Path, colours: dict[str, str], size: tuple[int, int] = SIZE, write: bool = True) -> list[bytes]:
    """All eight images, read from ``root/<key>/`` when this renderer, palette and size made them before."""
    key = hashlib.sha256(Path(__file__).read_bytes()
                         + json.dumps([colours, list(size)], sort_keys=True).encode("utf-8")).hexdigest()[:16]
    images = []
    for bin_ in range(BINS):
        path = root / key / f"sky-{bin_}.png"
        data = path.read_bytes() if path.is_file() else None
        if data is None:
            data = render(bin_, colours, size)
            if write:
                try:
                    jsonio.write_atomic_bytes(path, data)
                except OSError:
                    pass  # the cache only saves the next render
        images.append(data)
    return images
