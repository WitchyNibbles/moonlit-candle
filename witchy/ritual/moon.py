"""The moon's display phase: mean synodic age, eight phase bins, illumination (spec 6.3)."""
from __future__ import annotations

import math
from datetime import datetime, timezone

SYNODIC_DAYS = 29.530588853
EPOCH = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)  # a new moon
BINS = 8
NAMES = ("New", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
         "Full", "Waning Gibbous", "Last Quarter", "Waning Crescent")
GLYPHS = ("🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘")


def age(when: datetime) -> float:
    """Days since the last new moon. A naive ``when`` is local time."""
    days = (when.astimezone(timezone.utc) - EPOCH).total_seconds() / 86400
    return days % SYNODIC_DAYS


def phase_bin(when: datetime) -> int:
    """0 (new) to 7 (waning crescent); each bin is 1/8 of the cycle centred on its phase."""
    return math.floor(age(when) / SYNODIC_DAYS * BINS + 0.5) % BINS


def illumination(when: datetime) -> int:
    """The lit fraction of the disc, as a whole percent."""
    return round((1 - math.cos(2 * math.pi * age(when) / SYNODIC_DAYS)) / 2 * 100)
