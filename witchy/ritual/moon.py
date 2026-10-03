"""The moon: display phase (mean synodic age, eight bins, illumination; spec 6.3) and Meeus ch. 49 events."""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone, tzinfo

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


# Meeus, Astronomical Algorithms (2nd ed.), ch. 49: the instants of new and full moons.
DELTA_T = 69.0  # seconds of Terrestrial Time ahead of UTC; good to a few seconds through the 2020s
_UNIX_EPOCH_JD = 2440587.5
_LUNATION_ZERO = date(2000, 1, 6)  # lunation k = 0 is the new moon of 2000-01-06
# (coefficient for new moon, for full moon, E power, multipliers of M, M', F, Omega)
_PHASE_TERMS = (
    (-0.40720, -0.40614, 0, 0, 1, 0, 0),
    (0.17241, 0.17302, 1, 1, 0, 0, 0),
    (0.01608, 0.01614, 0, 0, 2, 0, 0),
    (0.01039, 0.01043, 0, 0, 0, 2, 0),
    (0.00739, 0.00734, 1, -1, 1, 0, 0),
    (-0.00514, -0.00515, 1, 1, 1, 0, 0),
    (0.00208, 0.00209, 2, 2, 0, 0, 0),
    (-0.00111, -0.00111, 0, 0, 1, -2, 0),
    (-0.00057, -0.00057, 0, 0, 1, 2, 0),
    (0.00056, 0.00056, 1, 1, 2, 0, 0),
    (-0.00042, -0.00042, 0, 0, 3, 0, 0),
    (0.00042, 0.00042, 1, 1, 0, 2, 0),
    (0.00038, 0.00038, 1, 1, 0, -2, 0),
    (-0.00024, -0.00024, 1, -1, 2, 0, 0),
    (-0.00017, -0.00017, 0, 0, 0, 0, 1),
    (-0.00007, -0.00007, 0, 2, 1, 0, 0),
    (0.00004, 0.00004, 0, 0, 2, -2, 0),
    (0.00004, 0.00004, 0, 3, 0, 0, 0),
    (0.00003, 0.00003, 0, 1, 1, -2, 0),
    (0.00003, 0.00003, 0, 0, 2, 2, 0),
    (-0.00003, -0.00003, 0, 1, 1, 2, 0),
    (0.00003, 0.00003, 0, -1, 1, 2, 0),
    (-0.00002, -0.00002, 0, -1, 1, -2, 0),
    (-0.00002, -0.00002, 0, 1, 3, 0, 0),
    (0.00002, 0.00002, 0, 0, 4, 0, 0),
)
# Planetary arguments: (coefficient × 1e-6, constant, rate per lunation)
_PLANETARY_TERMS = (
    (325, 299.77, 0.107408), (165, 251.88, 0.016321), (164, 251.83, 26.651886), (126, 349.42, 36.412478),
    (110, 84.66, 18.206239), (62, 141.74, 53.303771), (60, 207.14, 2.453732), (56, 154.84, 7.306860),
    (47, 34.52, 27.261239), (42, 207.19, 0.121824), (40, 291.34, 1.844379), (37, 161.72, 24.198154),
    (35, 239.56, 25.513099), (23, 331.55, 3.592518),
)


def julian_to_utc(jde: float) -> datetime:
    """A Julian Ephemeris Day as a UTC datetime."""
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(days=jde - _UNIX_EPOCH_JD, seconds=-DELTA_T)


def lunation_instant(k: float) -> datetime:
    """The new moon of lunation ``k`` (an integer) or its full moon (``k + 0.5``), in UTC; accurate to about a minute."""
    full = k % 1 != 0
    t = k / 1236.85
    jde = 2451550.09766 + 29.530588861 * k + 0.00015437 * t ** 2 - 0.000000150 * t ** 3 + 0.00000000073 * t ** 4
    e = 1 - 0.002516 * t - 0.0000074 * t ** 2
    m = 2.5534 + 29.10535670 * k - 0.0000014 * t ** 2 - 0.00000011 * t ** 3
    mp = 201.5643 + 385.81693528 * k + 0.0107582 * t ** 2 + 0.00001238 * t ** 3 - 0.000000058 * t ** 4
    f = 160.7108 + 390.67050284 * k - 0.0016118 * t ** 2 - 0.00000227 * t ** 3 + 0.000000011 * t ** 4
    omega = 124.7746 - 1.56375588 * k + 0.0020672 * t ** 2 + 0.00000215 * t ** 3
    for new_c, full_c, e_power, c_m, c_mp, c_f, c_omega in _PHASE_TERMS:
        angle = math.radians(c_m * m + c_mp * mp + c_f * f + c_omega * omega)
        jde += (full_c if full else new_c) * e ** e_power * math.sin(angle)
    a1 = 299.77 + 0.107408 * k - 0.009173 * t ** 2
    for index, (coefficient, constant, rate) in enumerate(_PLANETARY_TERMS):
        angle = a1 if index == 0 else constant + rate * k
        jde += coefficient * 1e-6 * math.sin(math.radians(angle))
    return julian_to_utc(jde)


def lunar_events(day: date, tz: tzinfo) -> list[str]:
    """"new", "full" or "blue" (a calendar month's second full moon) for each that falls on ``day`` in ``tz``."""
    base = math.floor((day - _LUNATION_ZERO).days / SYNODIC_DAYS)
    events = []
    for k in range(base - 1, base + 2):
        if lunation_instant(k).astimezone(tz).date() == day:
            events.append("new")
        if lunation_instant(k + 0.5).astimezone(tz).date() == day:
            before = lunation_instant(k - 0.5).astimezone(tz).date()
            events.append("blue" if (before.year, before.month) == (day.year, day.month) else "full")
    return events
