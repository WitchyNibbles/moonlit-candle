"""The card of the day: the same card all day, from a hash of the local date."""
from __future__ import annotations

import hashlib
from datetime import date

NUMERALS = ("0", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV",
            "XVI", "XVII", "XVIII", "XIX", "XX", "XXI")
REVERSED_BELOW = 85  # digest[1] < 85: reversed about one day in three


def card_of(day: date, cards: list[dict]) -> tuple[dict, bool]:
    """The card for ``day`` and whether it is reversed."""
    digest = hashlib.sha256(day.isoformat().encode("ascii")).digest()
    ordered = sorted(cards, key=lambda card: card["number"])
    return ordered[digest[0] % len(ordered)], digest[1] < REVERSED_BELOW
