"""The Wheel of the Year: eight sabbats, the solstices and equinoxes from Meeus ch. 27 (northern hemisphere)."""
from __future__ import annotations

import math
from datetime import date, datetime, tzinfo

from .moon import julian_to_utc

SABBATS = ("Imbolc", "Ostara", "Beltane", "Litha", "Lughnasadh", "Mabon", "Samhain", "Yule")
FIXED = {"Imbolc": (2, 1), "Beltane": (5, 1), "Lughnasadh": (8, 1), "Samhain": (10, 31)}
SEASONS = {"Ostara": 0, "Litha": 1, "Mabon": 2, "Yule": 3}  # March equinox, June solstice, September, December
COUNTDOWN_DAYS = 7
# Meeus table 27.B (years 2000-3000): mean instants as polynomials in millennia from 2000
_MEAN = (
    (2451623.80984, 365242.37404, 0.05169, -0.00411, -0.00057),
    (2451716.56767, 365241.62603, 0.00325, 0.00888, -0.00030),
    (2451810.21715, 365242.01767, -0.11575, 0.00337, 0.00078),
    (2451900.05952, 365242.74049, -0.06223, -0.00823, 0.00032),
)
# Meeus table 27.C: periodic terms (A, B, C)
_PERIODIC = (
    (485, 324.96, 1934.136), (203, 337.23, 32964.467), (199, 342.08, 20.186), (182, 27.85, 445267.112),
    (156, 73.14, 45036.886), (136, 171.52, 22518.443), (77, 222.54, 65928.934), (74, 296.72, 3034.906),
    (70, 243.58, 9037.513), (58, 119.81, 33718.147), (52, 297.17, 150.678), (50, 21.02, 2281.226),
    (45, 247.54, 29929.562), (44, 325.15, 31555.956), (29, 60.93, 4443.417), (18, 155.12, 67555.328),
    (17, 288.79, 4562.452), (16, 198.04, 62894.029), (14, 199.76, 31436.921), (12, 95.39, 14577.848),
    (12, 287.11, 31931.756), (12, 320.81, 34777.259), (9, 227.73, 1222.114), (8, 15.45, 16859.074),
)


def season_instant(year: int, index: int) -> datetime:
    """The March equinox (0), June solstice (1), September equinox (2) or December solstice (3), in UTC."""
    y = (year - 2000) / 1000
    jde0 = sum(coefficient * y ** power for power, coefficient in enumerate(_MEAN[index]))
    t = (jde0 - 2451545.0) / 36525
    w = math.radians(35999.373 * t - 2.47)
    spread = 1 + 0.0334 * math.cos(w) + 0.0007 * math.cos(2 * w)
    s = sum(a * math.cos(math.radians(b + c * t)) for a, b, c in _PERIODIC)
    return julian_to_utc(jde0 + 0.00001 * s / spread)


def sabbat_dates(year: int, tz: tzinfo) -> dict[str, date]:
    """Each sabbat's local date in ``year``, in calendar order."""
    dates = {}
    for name in SABBATS:
        if name in FIXED:
            dates[name] = date(year, *FIXED[name])
        else:
            dates[name] = season_instant(year, SEASONS[name]).astimezone(tz).date()
    return dates


def upcoming(day: date, tz: tzinfo) -> tuple[str, int] | None:
    """The sabbat on ``day`` (0 days) or within the next seven days, with the days left; else None."""
    for year in (day.year, day.year + 1):
        for name, when in sabbat_dates(year, tz).items():
            if 0 <= (when - day).days <= COUNTDOWN_DAYS:
                return name, (when - day).days
    return None
