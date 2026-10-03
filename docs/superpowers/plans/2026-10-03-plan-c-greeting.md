# Plan C: The Greeting Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the standalone greeting package `witchy/ritual/` (the ritual, the one-line omen and the Windows Terminal sky job), its texts in `content/ritual.json`, their validation, and the build step that turns them into the files Plan D installs.

**Architecture:** `witchy/ritual/` is a directory package that imports nothing from `witchy`: pure modules for the moon (Meeus ch. 49), the Wheel of the Year (Meeus ch. 27), the ASCII art, tarot, the system fetch, layout and the log, plus `sky.py` (the sky job) and `cli.py` (the greeting itself). `__main__.py` only finds `cli.main`, so the same code runs from the repository (`python3 -m witchy.ritual`) and as an installed copy (`python3 -I -B ~/.claude/witchy/ritual`). On the `witchy` side, `palette.RITUAL` holds the colours, `validate` checks the texts and colours, and `build.ritual_package()` returns the package as installed.

**Tech Stack:** Python 3.10+ standard library only (`math`, `datetime`, `hashlib`, `random`, `json`, `fcntl`, `unicodedata`, `textwrap`, `argparse`, `unittest`).

**Spec:** `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` (revision 2). This plan covers sections 6.1 and 6.3–6.7, the job half of 4.5, 11.1–11.2, and the `ritual` and `sky` rows of section 12. Plan D covers 5, 6.2 (the fish conditions), 7, the fish half of 4.5, 11.3–11.4, the Plan A carry-overs, acceptance (14) and the PR. Plans A and B are done; this plan is written against the code at `f36cf13`.

## Global Constraints

- Python 3.10 or newer, standard library only; every test passes on `/usr/bin/python3` (3.12) and on Python 3.10 (`/home/eimi/.pyenv/versions/3.10.0/bin/python3` on this machine).
- Test command: `/usr/bin/python3 -m unittest discover -s tests -t .` (run from the repo root), and the same with the 3.10 interpreter.
- `witchy/ritual/` imports nothing from `witchy`; inside the package, imports are relative (`from . import moon`). The installed copy runs as `python3 -I -B <dir>/ritual` (spec 6.1, 10.5).
- No test touches the real `~/.claude`, `~/.cache`, `~/.config/fish`, Windows Terminal, the network or today's date: tests pass `home`, `env`, `root`, `columns` and `now` explicitly.
- The greeting never breaks a shell: any exception prints nothing, exits 0 and appends one line to `~/.cache/witchy/ritual.log`, trimmed to the last 20 lines (spec 6.7).
- Colours (spec 6.4–6.6): salutation `#FFD477` bold; labels `#A99AB9`; values `#F3EAF7`; moon line `#B99AFF`; tarot name `#FF67B7`; reversed marker and meaning `#CFC3DB`; lit `#FFD477` fading to `#FFE3A3`; earthshine `#38234D`; stars `#B99AFF` and `#F3EAF7`; sabbat accents Imbolc `#F3EAF7`, Ostara `#74E8B8`, Beltane `#FF67B7`, Litha `#FFD477`, Lughnasadh `#FFB86B`, Mabon `#FFB86B`, Samhain `#FFB86B`, Yule `#E6DCEE`.
- Text limits (spec 11.1): `name` 1–24 characters; sabbat blessings and lunar lines 1–48; tarot `upright` and `reversed` 1–60; exactly 22 cards numbered 0–21 once each, unique names.
- The sky job edits `settings.json` only under `~/.cache/witchy/wt.lock`, never rewrites a file that is not strict JSON, re-checks the bytes before replacing, and replaces atomically (spec 4.2, 10.4).
- Messages, docstrings and comments are English and neutral in tone.
- Commit messages end with the `Co-Authored-By:` trailer of the model that wrote the commit.

## Decisions made while planning

1. **Prototype first.** Every module and test in this plan was run in a scratch copy of the repository on 3.12 and 3.10 before the plan was written (360 tests, `validate` clean). Meeus examples 49.a and 27.a match to the second; the 2024–2030 equinoxes and solstices land within 0.93 min of the published instants, and the new and full moons checked within 0.5 min.
2. **`cli.py` holds the greeting; `__main__.py` only finds it.** Spec 6.1 lists `__main__.py` as the argument parser; putting the logic in `cli.py` lets tests import it. `__main__.py` imports `.cli` when run as `python3 -m witchy.ritual`, and adds the parent folder to `sys.path` and imports `ritual.cli` when the installed directory is run.
3. **`data.json` lookup:** the package's own `data.json` (the installed copy), else `content/ritual.json` two folders up (the repository), so `python3 -m witchy.ritual --date …` previews work from a checkout.
4. **ΔT is a constant 69 s** (TT − UTC), good to a few seconds through the 2020s; event dates only care about minutes.
5. **The sky job edits the one value in the text** (a regex on `"backgroundImage": "<old value>"`, which must match exactly once), then re-parses the result and requires it to equal the original data with only that value changed. It never re-serialises, so Windows Terminal's layout survives. When the profile already shows tonight's image it only writes `sky-bin`; this also covers the first shell after an install.
6. **Shared names are duplicated, with a parity test:** `sky.LOCK` = `windows_terminal.WT_LOCK`, `sky.CONFIG` = `windows_terminal.RITUAL_CONFIG` (the package cannot import `witchy`).
7. **Stars and tarot are seeded from the local date** (`date.toordinal()` and `sha256("YYYY-MM-DD")`), so they change daily and stay put within a day.
8. **The fish version comes from the `FISH_VERSION` environment variable;** Plan D's fish functions pass it (`env FISH_VERSION=$FISH_VERSION …`), because fish does not export it.
9. **The omen** is `<phase glyph> <phase> <illumination>% · ✦ <card>[ (reversed)][ · 🕯️ <sabbat> | · ⋆ <sabbat> in N days]`, cut to the terminal width.
10. **Info lines wider than the column are wrapped (the tarot meaning) or cut with `…` (everything else),** so no line is ever wider than the terminal.
11. **`build.with_palette(source, colours)`** generalises the status line's PALETTE-block rewrite; `statusline_source` keeps its signature and calls it.

## Review Focus

1. **A lunar event near midnight UTC** must show on the user's local date, not the UTC date → Task 1 `test_events_use_the_local_date`.
2. **A missing or broken `data.json`, or unreadable `/proc`,** must leave the shell silent (exit 0, no output, one log line), or show `--` for the missing fetch value → Task 4 `test_missing_values_show_a_dash`, Task 7 `test_any_error_prints_nothing_and_is_logged` and `test_bad_data_prints_nothing`.
3. **Windows Terminal's own `settings.json` layout and every other profile** must survive the sky job byte for byte, except the one value → Task 6 `test_moves_the_sky_and_keeps_the_file_layout`.
4. **A `backgroundImage` the user chose themselves** must never be overwritten, and must not be retried on every new shell → Task 6 `test_a_value_the_user_chose_is_left_alone` and `test_the_fail_marker_stops_retries_until_tomorrow`.
5. **Narrow terminals and wide glyphs (emoji are two cells)** must never produce a line wider than the terminal, at any layout → Task 7 `test_no_line_is_wider_than_the_terminal`.

---

## File structure

| File | Status | Responsibility |
| :- | :- | :- |
| `witchy/ritual/moon.py` | modify | add Meeus ch. 49 instants and `lunar_events` |
| `witchy/ritual/wheel.py` | create | the 8 sabbats; Meeus ch. 27 solstices and equinoxes |
| `witchy/ritual/palette.py` | create | the greeting's colours (PALETTE block rewritten by build) |
| `witchy/ritual/art.py` | create | the 11 × 22 ASCII disc and the daily stars |
| `witchy/ritual/tarot.py` | create | card of the day |
| `witchy/ritual/fetch.py` | create | system lines; `clean` strips control characters |
| `witchy/ritual/layout.py` | create | cell widths, `fit`, side-by-side layout, colour rendering |
| `witchy/ritual/log.py` | create | `ritual.log`, last 20 lines |
| `witchy/ritual/sky.py` | create | the sky job |
| `witchy/ritual/cli.py` | create | full ritual, omen, auto mode, `--debug`, `--date`, error handling |
| `witchy/ritual/__main__.py` | create | finds `cli.main` in the repository or the installed copy |
| `content/ritual.json` | create | name, sabbat blessings, lunar lines, 22 tarot cards |
| `witchy/content.py` | modify | `RITUAL`, `load_ritual` |
| `witchy/palette.py` | modify | `RITUAL`, `RITUAL_DECORATIVE`, `Variant.ritual` |
| `witchy/validate.py` | modify | `validate_ritual`, `validate_ritual_palette`; both run in `validate_all` |
| `witchy/build.py` | modify | `with_palette`, `RITUAL_SOURCE`, `ritual_package` |
| `docs/superpowers/specs/2026-10-02-shell-ritual-design.md` | modify | record this plan's decisions |
| `tests/test_moon.py` | rewrite | existing tests plus Meeus and events |
| `tests/test_wheel.py`, `tests/test_ritual_content.py`, `tests/test_art.py`, `tests/golden/moon-{0..7}.txt`, `tests/test_tarot.py`, `tests/test_fetch.py`, `tests/test_layout.py`, `tests/test_ritual_log.py`, `tests/test_sky_job.py`, `tests/test_ritual_cli.py`, `tests/test_ritual_package.py` | create | new tests |

---

### Task 1: Lunar events (Meeus ch. 49)

**Files:**
- Modify: `witchy/ritual/moon.py`
- Rewrite: `tests/test_moon.py` (the three existing tests stay as they are)

**Interfaces:**
- Consumes: Plan B's `moon.SYNODIC_DAYS`, `EPOCH`, `BINS`, `NAMES`, `GLYPHS`, `age`, `phase_bin`, `illumination` (unchanged).
- Produces:
  - `moon.DELTA_T: float` (69.0 seconds)
  - `moon.julian_to_utc(jde: float) -> datetime` (aware, UTC)
  - `moon.lunation_instant(k: float) -> datetime` — the new moon of lunation `k` (an integer; `k = 0` is 2000-01-06) or its full moon (`k + 0.5`), in UTC
  - `moon.lunar_events(day: date, tz: tzinfo) -> list[str]` — any of `"new"`, `"full"`, `"blue"` whose instant falls on `day` in `tz`

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_moon.py` with:

```python
import unittest
from datetime import date, datetime, timedelta, timezone

from witchy.ritual import moon


class MoonTest(unittest.TestCase):
    def test_known_new_and_full_moons(self):
        new = datetime(2024, 4, 8, 12, tzinfo=timezone.utc)
        full = datetime(2024, 9, 18, 12, tzinfo=timezone.utc)
        self.assertEqual((moon.phase_bin(new), moon.illumination(new)), (0, 0))
        self.assertEqual((moon.phase_bin(full), moon.illumination(full)), (4, 100))

    def test_bin_edges(self):
        first = moon.EPOCH + timedelta(days=moon.SYNODIC_DAYS / 16)
        self.assertEqual(moon.phase_bin(first - timedelta(minutes=1)), 0)
        self.assertEqual(moon.phase_bin(first + timedelta(minutes=1)), 1)
        last = moon.EPOCH + timedelta(days=moon.SYNODIC_DAYS * 15 / 16)
        self.assertEqual(moon.phase_bin(last - timedelta(minutes=1)), 7)
        self.assertEqual(moon.phase_bin(last + timedelta(minutes=1)), 0)

    def test_names_and_glyphs(self):
        self.assertEqual((len(moon.NAMES), len(moon.GLYPHS)), (moon.BINS, moon.BINS))
        self.assertEqual((moon.NAMES[2], moon.GLYPHS[4]), ("First Quarter", "🌕"))


def utc(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


class LunationTest(unittest.TestCase):
    # Published instants (UTC, to the minute) of new and full moons.
    PUBLISHED = {
        0: ("2024-04-08 18:21", False),
        1: ("2024-09-18 02:34", True),
        2: ("2023-08-01 18:32", True),
        3: ("2023-08-31 01:36", True),
        4: ("2026-05-01 17:23", True),
        5: ("2026-05-31 08:45", True),
        6: ("2026-10-26 04:12", True),
    }

    def nearest(self, when, full):
        """The lunation instant closest to ``when``."""
        k = round((when - moon.lunation_instant(0)).days / moon.SYNODIC_DAYS - (0.5 if full else 0))
        return moon.lunation_instant(k + (0.5 if full else 0))

    def test_meeus_example_49a(self):
        # Meeus example 49.a: the new moon of February 1977 is JDE 2443192.65118 (TD).
        self.assertAlmostEqual(moon.julian_to_utc(2443192.65118).timestamp(),
                               moon.lunation_instant(-283).timestamp(), delta=1)

    def test_published_instants_within_two_minutes(self):
        for text, full in self.PUBLISHED.values():
            with self.subTest(text):
                self.assertLess(abs((self.nearest(utc(text), full) - utc(text)).total_seconds()), 120)


class LunarEventsTest(unittest.TestCase):
    def test_new_full_and_blue(self):
        cases = {"2024-04-08": ["new"], "2024-09-18": ["full"], "2023-08-01": ["full"], "2023-08-31": ["blue"],
                 "2026-05-01": ["full"], "2026-05-31": ["blue"], "2026-10-03": []}
        for day, expected in cases.items():
            with self.subTest(day):
                self.assertEqual(moon.lunar_events(date.fromisoformat(day), timezone.utc), expected)

    def test_events_use_the_local_date(self):
        # The full moon of 2024-09-18 02:34 UTC is still the 17th five hours west of Greenwich.
        west = timezone(timedelta(hours=-5))
        self.assertEqual(moon.lunar_events(date(2024, 9, 17), west), ["full"])
        self.assertEqual(moon.lunar_events(date(2024, 9, 18), west), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_moon -v`
Expected: the three existing tests pass; the four new ones fail with `AttributeError: module 'witchy.ritual.moon' has no attribute 'julian_to_utc'` (or `'lunation_instant'` / `'lunar_events'`).

- [ ] **Step 3: Implement**

Replace `witchy/ritual/moon.py` with:

```python
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
```

- [ ] **Step 4: Run the whole suite on both Pythons**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .` and `/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .`
Expected: OK on both (285 + 4 = 289 tests).

- [ ] **Step 5: Commit**

```bash
git add witchy/ritual/moon.py tests/test_moon.py
git commit -m "feat: add Meeus new and full moon instants and lunar events

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 2: The Wheel of the Year (Meeus ch. 27)

**Files:**
- Create: `witchy/ritual/wheel.py`, `tests/test_wheel.py`

**Interfaces:**
- Consumes: `moon.julian_to_utc` (Task 1).
- Produces:
  - `wheel.SABBATS: tuple[str, ...]` (calendar order, Imbolc first), `wheel.FIXED`, `wheel.SEASONS`, `wheel.COUNTDOWN_DAYS = 7`
  - `wheel.season_instant(year: int, index: int) -> datetime` (0 March equinox, 1 June solstice, 2 September equinox, 3 December solstice; UTC)
  - `wheel.sabbat_dates(year: int, tz: tzinfo) -> dict[str, date]`
  - `wheel.upcoming(day: date, tz: tzinfo) -> tuple[str, int] | None` — the sabbat on `day` (0) or within the next 7 days, with the days left

- [ ] **Step 1: Write the failing tests**

Create `tests/test_wheel.py`:

```python
import unittest
from datetime import date, datetime, timedelta, timezone

from witchy.ritual import wheel

# Published equinoxes and solstices, UTC to the minute: March, June, September, December.
PUBLISHED = {
    2024: ("03-20 03:06", "06-20 20:51", "09-22 12:44", "12-21 09:20"),
    2025: ("03-20 09:01", "06-21 02:42", "09-22 18:19", "12-21 15:03"),
    2026: ("03-20 14:46", "06-21 08:24", "09-23 00:05", "12-21 20:50"),
    2027: ("03-20 20:25", "06-21 14:11", "09-23 06:02", "12-22 02:42"),
    2028: ("03-20 02:17", "06-20 20:02", "09-22 11:45", "12-21 08:20"),
    2029: ("03-20 08:02", "06-21 01:48", "09-22 17:38", "12-21 14:14"),
    2030: ("03-20 13:52", "06-21 07:31", "09-22 23:27", "12-21 20:09"),
}
CET = timezone(timedelta(hours=1))


class SeasonTest(unittest.TestCase):
    def test_meeus_example_27a(self):
        # Meeus example 27.a: the June solstice of 1962 is JDE 2437837.39245 (TD).
        from witchy.ritual.moon import julian_to_utc
        self.assertAlmostEqual(wheel.season_instant(1962, 1).timestamp(),
                               julian_to_utc(2437837.39245).timestamp(), delta=1)

    def test_published_2024_to_2030_within_two_minutes(self):
        for year, instants in PUBLISHED.items():
            for index, text in enumerate(instants):
                expected = datetime.strptime(f"{year}-{text}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                with self.subTest(year=year, index=index):
                    self.assertLess(abs((wheel.season_instant(year, index) - expected).total_seconds()), 120)


class SabbatTest(unittest.TestCase):
    def test_dates_in_calendar_order(self):
        dates = wheel.sabbat_dates(2026, CET)
        self.assertEqual(list(dates), list(wheel.SABBATS))
        self.assertEqual((dates["Imbolc"], dates["Ostara"], dates["Samhain"], dates["Yule"]),
                         (date(2026, 2, 1), date(2026, 3, 20), date(2026, 10, 31), date(2026, 12, 21)))

    def test_the_day_and_the_countdown(self):
        cases = {"2026-10-31": ("Samhain", 0), "2026-10-26": ("Samhain", 5), "2026-10-30": ("Samhain", 1),
                 "2026-10-23": None, "2026-12-14": ("Yule", 7), "2027-01-25": ("Imbolc", 7)}
        for day, expected in cases.items():
            with self.subTest(day):
                self.assertEqual(wheel.upcoming(date.fromisoformat(day), CET), expected)

    def test_december_looks_ahead_to_next_year(self):
        self.assertEqual(wheel.upcoming(date(2026, 12, 31), CET), None)
        self.assertEqual(wheel.upcoming(date(2027, 1, 30), CET), ("Imbolc", 2))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_wheel -v`
Expected: ERROR `ImportError: cannot import name 'wheel' from 'witchy.ritual'`.

- [ ] **Step 3: Implement**

Create `witchy/ritual/wheel.py`:

```python
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
```

- [ ] **Step 4: Run the whole suite on both Pythons**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .` and `/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .`
Expected: OK on both (294 tests).

- [ ] **Step 5: Commit**

```bash
git add witchy/ritual/wheel.py tests/test_wheel.py
git commit -m "feat: add the Wheel of the Year with Meeus solstices and equinoxes

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 3: The greeting's texts, colours and validation

**Files:**
- Create: `content/ritual.json`, `witchy/ritual/palette.py`, `tests/test_ritual_content.py`
- Modify: `witchy/content.py`, `witchy/palette.py`, `witchy/validate.py`, `witchy/build.py`

**Interfaces:**
- Consumes: `build.palette_block`, `build.PALETTE_BLOCK`, `validate.Failure`, `validate._contrast`, `validate.HEX`, `validate.TEXT_MIN`.
- Produces:
  - `content.RITUAL = "ritual.json"`, `content.load_ritual(content_dir: Path = CONTENT_DIR) -> dict`
  - `palette.RITUAL: dict[str, str]` (20 keys, in the order below), `palette.RITUAL_DECORATIVE: tuple[str, ...]`, `Variant.ritual` (last field, default empty dict; midnight holds `RITUAL`)
  - `validate.SABBATS`, `validate.LUNAR_LINES`, `validate.validate_ritual(data) -> list[Failure]`, `validate.validate_ritual_palette(colours, background=palette.BACKGROUND) -> list[Failure]`; `validate_all` runs both
  - `build.RITUAL_SOURCE: Path` (`witchy/ritual`), `build.with_palette(source: Path, colours: dict[str, str]) -> str`
  - `witchy/ritual/palette.py`: `PALETTE` (the same 20 keys and values)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ritual_content.py`:

```python
import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from witchy import build, content, palette, validate

RITUAL_PALETTE_SOURCE = Path(build.RITUAL_SOURCE) / "palette.py"


def items(failures):
    return {failure.item for failure in failures}


class RitualTextTest(unittest.TestCase):
    def setUp(self):
        self.data = content.load_ritual()

    def check(self, change):
        data = copy.deepcopy(self.data)
        change(data)
        return items(validate.validate_ritual(data))

    def test_real_content_passes(self):
        self.assertEqual(validate.validate_ritual(self.data), [])

    def test_name(self):
        self.assertIn("ritual.name", self.check(lambda d: d.update(name="")))
        self.assertIn("ritual.name", self.check(lambda d: d.update(name="x" * 25)))

    def test_sabbats_and_lunar_lines(self):
        self.assertIn("ritual.sabbats.Yule", self.check(lambda d: d["sabbats"].pop("Yule")))
        self.assertIn("ritual.sabbats.Samhain", self.check(lambda d: d["sabbats"].update(Samhain="x" * 49)))
        self.assertIn("ritual.lunar.blue", self.check(lambda d: d["lunar"].pop("blue")))

    def test_tarot(self):
        self.assertIn("ritual.tarot", self.check(lambda d: d["tarot"].pop()))
        self.assertIn("ritual.tarot", self.check(lambda d: d["tarot"][1].update(number=0)))
        self.assertIn("ritual.tarot", self.check(lambda d: d["tarot"][1].update(name="The Fool")))
        self.assertIn("ritual.tarot.17.reversed", self.check(lambda d: d["tarot"][17].update(reversed="x" * 61)))
        self.assertIn("ritual.tarot.0.upright", self.check(lambda d: d["tarot"][0].update(upright="")))


class RitualPaletteTest(unittest.TestCase):
    def test_midnight_holds_the_module_colours(self):
        self.assertIs(palette.VARIANTS["midnight"].ritual, palette.RITUAL)

    def test_the_package_block_matches_the_palette(self):
        self.assertIn(build.palette_block(palette.RITUAL), RITUAL_PALETTE_SOURCE.read_text(encoding="utf-8"))

    def test_real_palette_passes(self):
        self.assertEqual(validate.validate_ritual_palette(palette.RITUAL), [])

    def test_text_and_accents_need_contrast_but_the_art_does_not(self):
        dark = dict(palette.RITUAL, label="#38234D", samhain="#503762", earthshine="#1D1230")
        self.assertEqual(items(validate.validate_ritual_palette(dark)), {"ritual.label", "ritual.samhain"})

    def test_format_and_missing_keys(self):
        broken = dict(palette.RITUAL, moon="violet")
        del broken["yule"]
        self.assertEqual(items(validate.validate_ritual_palette(broken)), {"ritual.moon", "ritual.yule"})


class ValidateAllTest(unittest.TestCase):
    def test_a_broken_ritual_file_fails_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(content.CONTENT_DIR, tmp, dirs_exist_ok=True)
            (Path(tmp) / content.RITUAL).write_text('{"name": ""}', encoding="utf-8")
            self.assertIn("ritual.name", items(validate.validate_all(Path(tmp))))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_ritual_content -v`
Expected: ERROR — `AttributeError: module 'witchy.build' has no attribute 'RITUAL_SOURCE'` at import.

- [ ] **Step 3: Add the texts**

Create `content/ritual.json`:

```json
{
  "name": "eimi",
  "sabbats": {
    "Imbolc": "the first light returns; kindle a flame",
    "Ostara": "day and night in balance; plant a seed",
    "Beltane": "fire and blossom; let joy run wild",
    "Litha": "the longest day; stand in your power",
    "Lughnasadh": "the first harvest; give thanks for bread",
    "Mabon": "the second harvest; share what you reaped",
    "Samhain": "the veil is thin tonight",
    "Yule": "the sun is reborn; light a candle"
  },
  "lunar": {
    "new": "set your intentions",
    "full": "charge your crystals",
    "blue": "a rare moon; make a bold wish"
  },
  "tarot": [
    {"number": 0, "name": "The Fool", "upright": "new beginnings, a leap of faith", "reversed": "recklessness; look before you leap"},
    {"number": 1, "name": "The Magician", "upright": "skill and will; you have the tools", "reversed": "scattered focus, tricks and half-truths"},
    {"number": 2, "name": "The High Priestess", "upright": "intuition; listen to the quiet voice", "reversed": "secrets kept, the inner voice ignored"},
    {"number": 3, "name": "The Empress", "upright": "abundance; tend what you are growing", "reversed": "a creative block; care for yourself first"},
    {"number": 4, "name": "The Emperor", "upright": "structure and steady authority", "reversed": "rigid control; loosen your grip"},
    {"number": 5, "name": "The Hierophant", "upright": "tradition and shared wisdom", "reversed": "question the rules you inherited"},
    {"number": 6, "name": "The Lovers", "upright": "a true choice; align heart and values", "reversed": "imbalance; a choice put off too long"},
    {"number": 7, "name": "The Chariot", "upright": "willpower; steer straight ahead", "reversed": "pulled in two directions at once"},
    {"number": 8, "name": "Strength", "upright": "quiet courage and patience", "reversed": "self-doubt; be gentle with yourself"},
    {"number": 9, "name": "The Hermit", "upright": "solitude and inner guidance", "reversed": "isolation; time to come back out"},
    {"number": 10, "name": "Wheel of Fortune", "upright": "the wheel turns; ride the change", "reversed": "a bad spin; it will turn again"},
    {"number": 11, "name": "Justice", "upright": "fairness, truth, cause and effect", "reversed": "an imbalance that needs owning"},
    {"number": 12, "name": "The Hanged Man", "upright": "pause and see it from another side", "reversed": "stalling; stop waiting to be saved"},
    {"number": 13, "name": "Death", "upright": "an ending that clears the way", "reversed": "clinging to what is already over"},
    {"number": 14, "name": "Temperance", "upright": "balance, patience, the middle way", "reversed": "excess; find your measure again"},
    {"number": 15, "name": "The Devil", "upright": "a binding habit; name the chain", "reversed": "breaking free, one link at a time"},
    {"number": 16, "name": "The Tower", "upright": "sudden upheaval; the truth breaks through", "reversed": "a collapse delayed, not avoided"},
    {"number": 17, "name": "The Star", "upright": "hope and renewal after the storm", "reversed": "despair, lost faith; rest and wait"},
    {"number": 18, "name": "The Moon", "upright": "illusion and dreams; trust your gut", "reversed": "the fog lifts; fears fade"},
    {"number": 19, "name": "The Sun", "upright": "joy, warmth, a clear success", "reversed": "a cloudy day; joy delayed, not denied"},
    {"number": 20, "name": "Judgement", "upright": "a calling; rise and answer it", "reversed": "self-doubt drowns out the call"},
    {"number": 21, "name": "The World", "upright": "completion; a cycle closes well", "reversed": "loose ends before the finish"}
  ]
}
```

In `witchy/content.py`: change the module docstring to `"""Hand-written content: spinner verbs and tips, the output style, and the greeting's texts."""`, add `RITUAL = "ritual.json"` below `OUTPUT_STYLE = "output-style.md"`, and add above `read_output_style`:

```python
def load_ritual(content_dir: Path = CONTENT_DIR) -> dict[str, Any]:
    data = json.loads((content_dir / RITUAL).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{RITUAL} must hold a JSON object")
    return data
```

- [ ] **Step 4: Add the colours**

In `witchy/palette.py`, add directly above the comment line `# Windows Terminal profile settings (spec 4.2).`:

```python
# The greeting (witchy/ritual/palette.py, spec 6.4-6.6). Text and the sabbat accents must read at 4.5:1;
# the moon art (lit, lit_mid, lit_soft, earthshine) and the stars are decorative (spec 11.2).
# Order matters: build.py writes this dict into the ritual's PALETTE block verbatim.
RITUAL: dict[str, str] = {
    "salutation": "#FFD477",
    "label": "#A99AB9",
    "value": FOREGROUND,
    "moon": "#B99AFF",
    "tarot": "#FF67B7",
    "muted": "#CFC3DB",
    "lit": "#FFD477",
    "lit_mid": "#FFDB8D",
    "lit_soft": "#FFE3A3",
    "earthshine": "#38234D",
    "star": FOREGROUND,
    "star_violet": "#B99AFF",
    "imbolc": "#F3EAF7",
    "ostara": "#74E8B8",
    "beltane": "#FF67B7",
    "litha": "#FFD477",
    "lughnasadh": "#FFB86B",
    "mabon": "#FFB86B",
    "samhain": "#FFB86B",
    "yule": "#E6DCEE",
}
RITUAL_DECORATIVE = ("lit", "lit_mid", "lit_soft", "earthshine", "star", "star_violet")

```

Add a last field to `Variant`: `ritual: dict[str, str] = field(default_factory=dict)`, and pass `ritual=RITUAL` in the midnight entry (after `wt_profile=WT_PROFILE`).

Create `witchy/ritual/palette.py`:

```python
"""The greeting's colours. build.py rewrites the PALETTE block from the active variant."""
from __future__ import annotations

# BEGIN PALETTE
PALETTE = {
    "salutation": "#FFD477",
    "label": "#A99AB9",
    "value": "#F3EAF7",
    "moon": "#B99AFF",
    "tarot": "#FF67B7",
    "muted": "#CFC3DB",
    "lit": "#FFD477",
    "lit_mid": "#FFDB8D",
    "lit_soft": "#FFE3A3",
    "earthshine": "#38234D",
    "star": "#F3EAF7",
    "star_violet": "#B99AFF",
    "imbolc": "#F3EAF7",
    "ostara": "#74E8B8",
    "beltane": "#FF67B7",
    "litha": "#FFD477",
    "lughnasadh": "#FFB86B",
    "mabon": "#FFB86B",
    "samhain": "#FFB86B",
    "yule": "#E6DCEE",
}
# END PALETTE
```

- [ ] **Step 5: Validate them**

In `witchy/validate.py`, add below `TIP_ID_MAX = 64`:

```python
# The greeting's texts (spec 11.1)
SABBATS = ("Imbolc", "Ostara", "Beltane", "Litha", "Lughnasadh", "Mabon", "Samhain", "Yule")
LUNAR_LINES = ("new", "full", "blue")
TAROT_CARDS = 22
NAME_MAX = 24
LINE_MAX = 48
MEANING_MAX = 60
```

Add directly above `def validate_content(`:

```python
def _short_text(failures: list[Failure], item: str, value: Any, limit: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\n" in value:
        failures.append(Failure("content", item, str(value)[:40], f"must be one line of 1-{limit} characters"))


def validate_ritual(data: Mapping[str, Any]) -> list[Failure]:
    """content/ritual.json: the salutation name, 8 sabbat blessings, 3 lunar lines and 22 tarot cards."""
    failures: list[Failure] = []
    _short_text(failures, "ritual.name", data.get("name"), NAME_MAX)
    sabbats = data.get("sabbats") if isinstance(data.get("sabbats"), dict) else {}
    for name in SABBATS:
        _short_text(failures, f"ritual.sabbats.{name}", sabbats.get(name), LINE_MAX)
    lunar = data.get("lunar") if isinstance(data.get("lunar"), dict) else {}
    for name in LUNAR_LINES:
        _short_text(failures, f"ritual.lunar.{name}", lunar.get(name), LINE_MAX)
    cards = data.get("tarot")
    if not isinstance(cards, list) or not all(isinstance(card, dict) for card in cards):
        return failures + [Failure("content", "ritual.tarot", "-", "must be a list of objects")]
    if len(cards) != TAROT_CARDS:
        failures.append(Failure("content", "ritual.tarot", str(len(cards)), f"must hold exactly {TAROT_CARDS} cards"))
    numbers = [card.get("number") for card in cards]
    if sorted(n for n in numbers if isinstance(n, int)) != list(range(TAROT_CARDS)):
        failures.append(Failure("content", "ritual.tarot", str(numbers)[:40], "numbers must be 0-21, each once"))
    names = [card.get("name") for card in cards]
    if len(set(map(str, names))) != len(names):
        failures.append(Failure("content", "ritual.tarot", "-", "card names must be unique"))
    for card in cards:
        item = f"ritual.tarot.{card.get('number')}"
        _short_text(failures, f"{item}.name", card.get("name"), MEANING_MAX)
        for side in ("upright", "reversed"):
            _short_text(failures, f"{item}.{side}", card.get(side), MEANING_MAX)
    return failures


def validate_ritual_palette(colours: Mapping[str, Any], background: str = palette.BACKGROUND) -> list[Failure]:
    """Every greeting colour is #RRGGBB; text and the sabbat accents reach 4.5:1 (spec 11.2)."""
    failures: list[Failure] = []
    for key in palette.RITUAL:
        if key not in colours:
            failures.append(Failure("missing-token", f"ritual.{key}", "-", "is missing from the ritual palette"))
    for key, value in colours.items():
        if not isinstance(value, str) or not HEX.match(value):
            failures.append(Failure("format", f"ritual.{key}", str(value), "is not #RRGGBB in uppercase"))
        elif key not in palette.RITUAL_DECORATIVE:
            _contrast(failures, "text-contrast", f"ritual.{key}", value, background, TEXT_MIN, value)
    return failures
```

In `validate_all`, inside the `for variant in palette.VARIANTS.values():` loop, after the sky-format statement, add:

```python
        if variant.ritual:
            failures += validate_ritual_palette(variant.ritual, variant.background)
```

and replace the `try:` … `return failures + validate_content(spinner, style)` tail with:

```python
    try:
        spinner = content.load_spinner(content_dir)
        style = content.read_output_style(content_dir)
        ritual = content.load_ritual(content_dir)
    except (OSError, ValueError) as exc:
        return failures + [Failure("content", str(content_dir), "-", f"cannot be read: {exc}")]
    return failures + validate_content(spinner, style) + validate_ritual(ritual)
```

- [ ] **Step 6: Generalise the palette rewrite**

In `witchy/build.py`, add `RITUAL_SOURCE = Path(__file__).resolve().parent / "ritual"` below `STATUSLINE_SOURCE = …`, and replace `statusline_source` with:

```python
def statusline_source(colours: dict[str, str] = palette.STATUSLINE, source: Path = STATUSLINE_SOURCE) -> str:
    """The status line script with its PALETTE block rewritten from ``colours``."""
    return with_palette(source, colours)


def with_palette(source: Path, colours: dict[str, str]) -> str:
    """``source`` with its one ``# BEGIN PALETTE`` block rewritten from ``colours``."""
    text = source.read_text(encoding="utf-8")
    rewritten, count = PALETTE_BLOCK.subn(lambda m: m.group(1) + palette_block(colours) + m.group(3), text)
    if count != 1:
        raise ValueError(f"{source} must contain exactly one PALETTE block, found {count}")
    return rewritten
```

- [ ] **Step 7: Run the whole suite on both Pythons, and validate**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .`, `/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .` and `/usr/bin/python3 -m witchy validate`
Expected: OK on both (304 tests); `Moonlit Candle: all checks passed`.

- [ ] **Step 8: Commit**

```bash
git add content/ritual.json witchy/ritual/palette.py witchy/content.py witchy/palette.py witchy/validate.py witchy/build.py tests/test_ritual_content.py
git commit -m "feat: add the greeting's texts and colours with their validation

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 4: The moon art, the card of the day and the system fetch

**Files:**
- Create: `witchy/ritual/art.py`, `witchy/ritual/tarot.py`, `witchy/ritual/fetch.py`
- Create: `tests/test_art.py`, `tests/golden/moon-0.txt` … `tests/golden/moon-7.txt`, `tests/test_tarot.py`, `tests/test_fetch.py`

**Interfaces:**
- Consumes: `content/ritual.json` (Task 3) in `tests/test_tarot.py`.
- Produces:
  - `art.ROWS = 11`, `art.COLS = 22`, `art.MARGIN = 3`, `art.WIDTH = 28`, `art.STAR_GLYPHS`, `art.STAR_COLOURS`; `art.disc(fraction: float) -> list[list[tuple[str, str | None]]]`; `art.picture(fraction: float, day: date) -> list[list[tuple[str, str | None]]]` (cells are `(character, palette key or None)`)
  - `tarot.NUMERALS`, `tarot.REVERSED_BELOW = 85`, `tarot.card_of(day: date, cards: list[dict]) -> tuple[dict, bool]`
  - `fetch.DASH = "--"`, `fetch.LABEL_WIDTH = 8`, `fetch.clean(text: str) -> str`, `fetch.lines(env, root: Path = Path("/"), release=<os.uname().release>) -> list[tuple[str, str]]` (labels `os`, `kernel`, `uptime`, `memory`, `shell`)

- [ ] **Step 1: Write the failing tests and the golden files**

Create `tests/test_art.py`:

```python
import unittest
from datetime import date, timedelta
from pathlib import Path

from witchy.ritual import art

GOLDEN = Path(__file__).resolve().parent / "golden"


def text(rows):
    return ["|" + "".join(char for char, _ in row) + "|" for row in rows]


class DiscTest(unittest.TestCase):
    def test_the_eight_phases_match_their_golden_files(self):
        for phase in range(8):
            with self.subTest(phase=phase):
                expected = (GOLDEN / f"moon-{phase}.txt").read_text(encoding="utf-8").splitlines()
                self.assertEqual(text(art.disc(phase / 8)), expected)

    def test_size_and_colours(self):
        rows = art.disc(0.3)
        self.assertEqual((len(rows), {len(row) for row in rows}), (art.ROWS, {art.COLS}))
        keys = {key for row in rows for _, key in row}
        self.assertEqual(keys, {None, "lit", "lit_mid", "lit_soft", "earthshine"})

    def test_waxing_is_lit_on_the_right(self):
        middle = art.disc(0.25)[art.ROWS // 2]
        self.assertEqual((middle[1][1], middle[-2][1]), ("earthshine", "lit_soft"))
        middle = art.disc(0.75)[art.ROWS // 2]
        self.assertEqual((middle[1][1], middle[-2][1]), ("lit_soft", "earthshine"))


class PictureTest(unittest.TestCase):
    def stars(self, day):
        return [(r, c, cell) for r, row in enumerate(art.picture(0.5, day)) for c, cell in enumerate(row)
                if cell[1] in art.STAR_COLOURS]

    def test_six_to_ten_stars_outside_the_disc(self):
        for offset in range(30):
            day = date(2026, 1, 1) + timedelta(days=offset)
            stars = self.stars(day)
            with self.subTest(day=day):
                self.assertTrue(6 <= len(stars) <= 10)
                self.assertTrue(all(cell[0] in art.STAR_GLYPHS for _, _, cell in stars))

    def test_stars_stay_put_within_a_day_and_move_the_next(self):
        self.assertEqual(self.stars(date(2026, 10, 31)), self.stars(date(2026, 10, 31)))
        self.assertNotEqual(self.stars(date(2026, 10, 31)), self.stars(date(2026, 11, 1)))

    def test_the_disc_sits_between_the_margins(self):
        rows = art.picture(0.5, date(2026, 10, 31))
        self.assertEqual({len(row) for row in rows}, {art.WIDTH})
        self.assertEqual(text([row[art.MARGIN:art.MARGIN + art.COLS] for row in rows]), text(art.disc(0.5)))


if __name__ == "__main__":
    unittest.main()
```

Create the eight golden files. Each line is one row of the disc between `|` marks (the spaces inside are part of the file). `tests/golden/moon-0.txt`:

```text
|      ░░░░░░░░░░      |
|   ░░░░░░░░░░░░░░░░   |
|  ░░░░░░░░░░░░░░░░░░  |
| ░░░░░░░░░░░░░░░░░░░░ |
|░░░░░░░░░░░░░░░░░░░░░░|
|░░░░░░░░░░░░░░░░░░░░░░|
|░░░░░░░░░░░░░░░░░░░░░░|
| ░░░░░░░░░░░░░░░░░░░░ |
|  ░░░░░░░░░░░░░░░░░░  |
|   ░░░░░░░░░░░░░░░░   |
|      ░░░░░░░░░░      |
```

`tests/golden/moon-1.txt`:

```text
|      ░░░░░░░░▒▒      |
|   ░░░░░░░░░░░░░▒▒▒   |
|  ░░░░░░░░░░░░░░░░▒▒  |
| ░░░░░░░░░░░░░░░░░▓▒▒ |
|░░░░░░░░░░░░░░░░░░░▓▒▒|
|░░░░░░░░░░░░░░░░░░░▓▒▒|
|░░░░░░░░░░░░░░░░░░░▓▒▒|
| ░░░░░░░░░░░░░░░░░▓▒▒ |
|  ░░░░░░░░░░░░░░░░▒▒  |
|   ░░░░░░░░░░░░░▒▒▒   |
|      ░░░░░░░░▒▒      |
```

`tests/golden/moon-2.txt`:

```text
|      ░░░░░▒▒▒▒▒      |
|   ░░░░░░░░▓▓▓▓▒▒▒▒   |
|  ░░░░░░░░░█▓▓▓▓▓▒▒▒  |
| ░░░░░░░░░░█████▓▓▓▒▒ |
|░░░░░░░░░░░██████▓▓▓▒▒|
|░░░░░░░░░░░██████▓▓▓▒▒|
|░░░░░░░░░░░██████▓▓▓▒▒|
| ░░░░░░░░░░█████▓▓▓▒▒ |
|  ░░░░░░░░░█▓▓▓▓▓▒▒▒  |
|   ░░░░░░░░▓▓▓▓▒▒▒▒   |
|      ░░░░░▒▒▒▒▒      |
```

`tests/golden/moon-3.txt`:

```text
|      ░░▒▒▒▒▒▒▒▒      |
|   ░░░▒▓▓▓▓▓▓▓▓▒▒▒▒   |
|  ░░▒▓▓▓▓▓██▓▓▓▓▓▒▒▒  |
| ░░░▓▓██████████▓▓▓▒▒ |
|░░░▓▓████████████▓▓▓▒▒|
|░░░▓▓████████████▓▓▓▒▒|
|░░░▓▓████████████▓▓▓▒▒|
| ░░░▓▓██████████▓▓▓▒▒ |
|  ░░▒▓▓▓▓▓██▓▓▓▓▓▒▒▒  |
|   ░░░▒▓▓▓▓▓▓▓▓▒▒▒▒   |
|      ░░▒▒▒▒▒▒▒▒      |
```

`tests/golden/moon-4.txt`:

```text
|      ▒▒▒▒▒▒▒▒▒▒      |
|   ▒▒▒▒▓▓▓▓▓▓▓▓▒▒▒▒   |
|  ▒▒▒▓▓▓▓▓██▓▓▓▓▓▒▒▒  |
| ▒▒▓▓▓██████████▓▓▓▒▒ |
|▒▒▓▓▓████████████▓▓▓▒▒|
|▒▒▓▓▓████████████▓▓▓▒▒|
|▒▒▓▓▓████████████▓▓▓▒▒|
| ▒▒▓▓▓██████████▓▓▓▒▒ |
|  ▒▒▒▓▓▓▓▓██▓▓▓▓▓▒▒▒  |
|   ▒▒▒▒▓▓▓▓▓▓▓▓▒▒▒▒   |
|      ▒▒▒▒▒▒▒▒▒▒      |
```

`tests/golden/moon-5.txt`:

```text
|      ▒▒▒▒▒▒▒▒░░      |
|   ▒▒▒▒▓▓▓▓▓▓▓▓▒░░░   |
|  ▒▒▒▓▓▓▓▓██▓▓▓▓▓▒░░  |
| ▒▒▓▓▓██████████▓▓░░░ |
|▒▒▓▓▓████████████▓▓░░░|
|▒▒▓▓▓████████████▓▓░░░|
|▒▒▓▓▓████████████▓▓░░░|
| ▒▒▓▓▓██████████▓▓░░░ |
|  ▒▒▒▓▓▓▓▓██▓▓▓▓▓▒░░  |
|   ▒▒▒▒▓▓▓▓▓▓▓▓▒░░░   |
|      ▒▒▒▒▒▒▒▒░░      |
```

`tests/golden/moon-6.txt`:

```text
|      ▒▒▒▒▒░░░░░      |
|   ▒▒▒▒▓▓▓▓░░░░░░░░   |
|  ▒▒▒▓▓▓▓▓█░░░░░░░░░  |
| ▒▒▓▓▓█████░░░░░░░░░░ |
|▒▒▓▓▓██████░░░░░░░░░░░|
|▒▒▓▓▓██████░░░░░░░░░░░|
|▒▒▓▓▓██████░░░░░░░░░░░|
| ▒▒▓▓▓█████░░░░░░░░░░ |
|  ▒▒▒▓▓▓▓▓█░░░░░░░░░  |
|   ▒▒▒▒▓▓▓▓░░░░░░░░   |
|      ▒▒▒▒▒░░░░░      |
```

`tests/golden/moon-7.txt`:

```text
|      ▒▒░░░░░░░░      |
|   ▒▒▒░░░░░░░░░░░░░   |
|  ▒▒░░░░░░░░░░░░░░░░  |
| ▒▒▓░░░░░░░░░░░░░░░░░ |
|▒▒▓░░░░░░░░░░░░░░░░░░░|
|▒▒▓░░░░░░░░░░░░░░░░░░░|
|▒▒▓░░░░░░░░░░░░░░░░░░░|
| ▒▒▓░░░░░░░░░░░░░░░░░ |
|  ▒▒░░░░░░░░░░░░░░░░  |
|   ▒▒▒░░░░░░░░░░░░░   |
|      ▒▒░░░░░░░░      |
```

Create `tests/test_tarot.py`:

```python
import json
import unittest
from datetime import date, timedelta
from pathlib import Path

from witchy.ritual import tarot

CARDS = json.loads((Path(__file__).resolve().parent.parent / "content" / "ritual.json").read_text("utf-8"))["tarot"]


class TarotTest(unittest.TestCase):
    def test_known_days(self):
        cases = {"2026-10-31": ("The Star", False), "2026-10-26": ("The Devil", True),
                 "2026-05-31": ("The Moon", False)}
        for day, expected in cases.items():
            card, reversed_ = tarot.card_of(date.fromisoformat(day), CARDS)
            self.assertEqual((card["name"], reversed_), expected)

    def test_the_order_of_the_list_does_not_matter(self):
        day = date(2026, 10, 31)
        self.assertEqual(tarot.card_of(day, CARDS), tarot.card_of(day, list(reversed(CARDS))))

    def test_reversed_about_one_day_in_three(self):
        days = [date(2026, 1, 1) + timedelta(days=offset) for offset in range(365)]
        share = sum(tarot.card_of(day, CARDS)[1] for day in days) / len(days)
        self.assertTrue(0.25 < share < 0.42, share)

    def test_numerals(self):
        self.assertEqual((len(tarot.NUMERALS), tarot.NUMERALS[17]), (22, "XVII"))


if __name__ == "__main__":
    unittest.main()
```

Create `tests/test_fetch.py`:

```python
import tempfile
import unittest
from pathlib import Path

from witchy.ritual import fetch


class FetchTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "etc").mkdir()
        (self.root / "proc").mkdir()

    def write(self, rel, text):
        (self.root / rel).write_text(text, encoding="utf-8")

    def lines(self, env=None, release="6.6.87.2-microsoft-standard-WSL2"):
        return dict(fetch.lines({"FISH_VERSION": "3.7.0"} if env is None else env, self.root, lambda: release))

    def test_every_value(self):
        self.write("etc/os-release", 'NAME="Ubuntu"\nPRETTY_NAME="Ubuntu 24.04.4 LTS"\n')
        self.write("proc/uptime", "11532.40 40000.00\n")
        self.write("proc/meminfo", "MemTotal:       16357904 kB\nMemFree: 1 kB\nMemAvailable:   12058624 kB\n")
        self.assertEqual(self.lines(), {"os": "Ubuntu 24.04.4 LTS", "kernel": "6.6.87.2-microsoft-standard-WSL2",
                                        "uptime": "3h 12m", "memory": "4.1 / 15.6 GiB", "shell": "fish 3.7.0"})

    def test_missing_values_show_a_dash(self):
        self.assertEqual(self.lines(env={}), {"os": "--", "kernel": "6.6.87.2-microsoft-standard-WSL2",
                                              "uptime": "--", "memory": "--", "shell": "--"})

    def test_uptime_formats(self):
        for seconds, expected in (("59.0", "0m"), ("754.2", "12m"), ("11532.4", "3h 12m"), ("273600.0", "3d 4h")):
            self.write("proc/uptime", f"{seconds} 1.0\n")
            self.assertEqual(self.lines()["uptime"], expected)

    def test_control_characters_are_stripped(self):
        self.write("etc/os-release", 'PRETTY_NAME="Ubuntu\x1b[31m 24.04\x07"\n')
        self.assertEqual(self.lines(release="6.6\x1b]0;x\x07")["os"], "Ubuntu[31m 24.04")
        self.assertEqual(self.lines(release="6.6\x1b]0;x\x07")["kernel"], "6.6]0;x")
        self.assertEqual(fetch.clean("  a\tb\n "), "ab")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_art tests.test_tarot tests.test_fetch -v`
Expected: ERROR `ImportError: cannot import name 'art'` (and `'tarot'`, `'fetch'`) `from 'witchy.ritual'`.

- [ ] **Step 3: Implement**

Create `witchy/ritual/art.py`:

```python
"""The ASCII moon: an 11 × 22 disc lit for the moon's age, and a few stars that move once a day."""
from __future__ import annotations

import math
import random
from datetime import date

ROWS, COLS = 11, 22  # two columns per row: terminal cells are about twice as tall as they are wide
MARGIN = 3
WIDTH = COLS + 2 * MARGIN
STAR_GLYPHS = ("✦", "⋆", "·", "˚")
STAR_COLOURS = ("star", "star_violet")
STAR_CLEARANCE = 1.25  # stars keep this far from the disc centre, in disc radii
# A cell: its character and the palette key it is drawn in (None for blank).
Cell = tuple  # (str, str | None)


def disc(fraction: float) -> list[list[Cell]]:
    """The moon ``fraction`` of the way through its cycle (0 new, 0.5 full); waxing light on the right."""
    phase = 2 * math.pi * fraction
    lit = (1 - math.cos(phase)) / 2 > 0.005
    waxing = fraction % 1 <= 0.5
    rows = []
    for r in range(ROWS):
        y = (r + 0.5 - ROWS / 2) / (ROWS / 2)
        row = []
        for c in range(COLS):
            x = (c + 0.5 - COLS / 2) / (COLS / 2)
            distance = math.hypot(x, y)
            if distance > 1:
                row.append((" ", None))
            elif lit and (x if waxing else -x) >= math.cos(phase) * math.sqrt(max(0.0, 1 - y * y)):
                row.append(("█", "lit") if distance < 0.55 else ("▓", "lit_mid") if distance < 0.8
                           else ("▒", "lit_soft"))
            else:
                row.append(("░", "earthshine"))
        rows.append(row)
    return rows


def picture(fraction: float, day: date) -> list[list[Cell]]:
    """The disc with a margin on each side and 6–10 stars placed from ``day``: they move daily, not hourly."""
    rows = [[(" ", None)] * MARGIN + row + [(" ", None)] * MARGIN for row in disc(fraction)]
    rng = random.Random(day.toordinal())
    wanted = rng.randint(6, 10)
    placed = 0
    for _ in range(200):
        if placed == wanted:
            break
        r, c = rng.randrange(ROWS), rng.randrange(WIDTH)
        x = (c - MARGIN + 0.5 - COLS / 2) / (COLS / 2)
        y = (r + 0.5 - ROWS / 2) / (ROWS / 2)
        neighbours = [rows[rr][cc][1] for rr in range(max(0, r - 1), min(ROWS, r + 2))
                      for cc in range(max(0, c - 1), min(WIDTH, c + 2))]
        if math.hypot(x, y) < STAR_CLEARANCE or any(key in STAR_COLOURS for key in neighbours):
            continue
        rows[r][c] = (rng.choice(STAR_GLYPHS), rng.choice(STAR_COLOURS))
        placed += 1
    return rows
```

Create `witchy/ritual/tarot.py`:

```python
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
```

Create `witchy/ritual/fetch.py`:

```python
"""A short system fetch from /etc and /proc; anything missing shows as --."""
from __future__ import annotations

import os
import unicodedata
from pathlib import Path
from typing import Callable, Mapping

DASH = "--"
LABEL_WIDTH = 8


def clean(text: str) -> str:
    """``text`` without control characters, so nothing it holds can move the cursor or change colours."""
    return "".join(ch for ch in text if not unicodedata.category(ch).startswith("C")).strip()


def _os_name(root: Path) -> str:
    for line in (root / "etc" / "os-release").read_text(encoding="utf-8", errors="replace").splitlines():
        key, _, value = line.partition("=")
        if key == "PRETTY_NAME":
            return value.strip().strip('"')
    raise ValueError("no PRETTY_NAME")


def _uptime(root: Path) -> str:
    minutes = int(float((root / "proc" / "uptime").read_text(encoding="ascii").split()[0]) // 60)
    days, rest = divmod(minutes, 24 * 60)
    hours, minutes = divmod(rest, 60)
    if days:
        return f"{days}d {hours}h"
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def _memory(root: Path) -> str:
    fields = {}
    for line in (root / "proc" / "meminfo").read_text(encoding="ascii").splitlines():
        key, _, value = line.partition(":")
        fields[key] = int(value.split()[0])  # kB
    total, available = fields["MemTotal"], fields["MemAvailable"]
    return f"{(total - available) / 2 ** 20:.1f} / {total / 2 ** 20:.1f} GiB"


def _shell(env: Mapping[str, str]) -> str:
    return f"fish {env['FISH_VERSION']}"


def lines(env: Mapping[str, str], root: Path = Path("/"),
          release: Callable[[], str] = lambda: os.uname().release) -> list[tuple[str, str]]:
    """(label, value) pairs; a value that cannot be read is --."""
    readers = (("os", lambda: _os_name(root)), ("kernel", release), ("uptime", lambda: _uptime(root)),
               ("memory", lambda: _memory(root)), ("shell", lambda: _shell(env)))
    result = []
    for label, reader in readers:
        try:
            value = clean(reader()) or DASH
        except (OSError, ValueError, KeyError, IndexError):
            value = DASH
        result.append((label, value))
    return result
```

- [ ] **Step 4: Run the whole suite on both Pythons**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .` and `/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .`
Expected: OK on both (318 tests). If a golden comparison fails, print the disc (`python3 -c "from witchy.ritual import art; [print('|' + ''.join(c for c, _ in r) + '|') for r in art.disc(2/8)]"`) and compare it with the file character by character; the code is the reference only after you have checked that the file was copied exactly.

- [ ] **Step 5: Commit**

```bash
git add witchy/ritual/art.py witchy/ritual/tarot.py witchy/ritual/fetch.py tests/test_art.py tests/golden tests/test_tarot.py tests/test_fetch.py
git commit -m "feat: add the moon art, the card of the day and the system fetch

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 5: Layout and the log

**Files:**
- Create: `witchy/ritual/layout.py`, `witchy/ritual/log.py`, `tests/test_layout.py`, `tests/test_ritual_log.py`

**Interfaces:**
- Produces:
  - `layout.WIDE`, `layout.GAP = 3`, `layout.ELLIPSIS`; a segment is `(text, palette key or None, bold)` and a line is a list of segments
  - `layout.cell_width(text: str) -> int`, `layout.line_width(line) -> int`, `layout.fit(line, width: int) -> line`, `layout.side_by_side(art: list[line], info: list[line], art_width: int) -> list[line]`, `layout.render(line, palette: dict[str, str] | None) -> str`
  - `log.NAME = "ritual.log"`, `log.MAX_LINES = 20`, `log.append(path: Path, message: str, now: datetime) -> None` (never raises), `log.last(path: Path) -> str | None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_layout.py`:

```python
import unittest

from witchy.ritual import layout

PALETTE = {"gold": "#FFD477", "muted": "#A99AB9"}


class WidthTest(unittest.TestCase):
    def test_cell_widths(self):
        cases = {"abc": 3, "🌕": 2, "🕯️ Samhain": 10, "✦ ⋆ · ˚": 7, "░▒▓█": 4, "": 0}
        for text, width in cases.items():
            with self.subTest(text):
                self.assertEqual(layout.cell_width(text), width)

    def test_fit_cuts_with_an_ellipsis(self):
        line = [("🌕 Full", "gold", False), (" · ✦ The Star", "muted", False)]
        self.assertIs(layout.fit(line, 40), line)
        cut = layout.fit(line, 10)
        self.assertEqual(cut, [("🌕 Full", "gold", False), (" ·…", "muted", False)])
        self.assertLessEqual(layout.line_width(cut), 10)

    def test_fit_never_splits_a_wide_glyph(self):
        cut = layout.fit([("ab🌕cd", None, False)], 4)
        self.assertEqual(layout.line_width(cut), 3)
        self.assertEqual(cut[0][0], "ab…")


class SideBySideTest(unittest.TestCase):
    def test_short_info_is_centred_beside_the_art(self):
        art = [[("art", None, False)]] * 5
        info = [[("one", "gold", False)], [("two", "gold", False)]]
        rows = layout.side_by_side(art, info, 6)
        plain = [layout.render(row, None) for row in rows]
        self.assertEqual(plain, ["art", "art      one", "art      two", "art", "art"])

    def test_tall_info_centres_the_art(self):
        rows = layout.side_by_side([[("A", None, False)]], [[("x", None, False)]] * 3, 2)
        self.assertEqual([layout.render(row, None) for row in rows], ["     x", "A    x", "     x"])


class RenderTest(unittest.TestCase):
    def test_colour_and_bold(self):
        text = layout.render([("Hi", "gold", True), (" there", "muted", False), ("  ", None, False)], PALETTE)
        self.assertEqual(text, "\x1b[1;38;2;255;212;119mHi\x1b[0m\x1b[38;2;169;154;185m there\x1b[0m")

    def test_no_colour(self):
        self.assertEqual(layout.render([("Hi", "gold", True), ("!", "muted", False)], None), "Hi!")


if __name__ == "__main__":
    unittest.main()
```

Create `tests/test_ritual_log.py`:

```python
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from witchy.ritual import log


class LogTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "cache" / log.NAME

    def test_appends_one_line_per_error_and_keeps_the_last_twenty(self):
        for minute in range(25):
            log.append(self.path, f"greeting: boom {minute}\nsecond line", datetime(2026, 10, 31, 21, minute))
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), log.MAX_LINES)
        self.assertEqual(lines[-1], "2026-10-31T21:24:00 greeting: boom 24 second line")
        self.assertEqual(log.last(self.path), lines[-1])

    def test_no_log(self):
        self.assertIsNone(log.last(self.path))

    def test_an_unwritable_log_is_ignored(self):
        self.path.parent.parent.mkdir(parents=True, exist_ok=True)
        self.path.parent.write_text("a file, not a folder", encoding="utf-8")
        log.append(self.path, "boom", datetime(2026, 10, 31))  # must not raise


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_layout tests.test_ritual_log -v`
Expected: ERROR `ImportError: cannot import name 'layout'` (and `'log'`) `from 'witchy.ritual'`.

- [ ] **Step 3: Implement**

Create `witchy/ritual/layout.py`:

```python
"""Lines of coloured segments, their width in terminal cells, and the three layouts."""
from __future__ import annotations

import unicodedata

# Emoji we print, drawn two cells wide. 🕯 is narrow in Unicode but terminals draw it wide with its VS16.
WIDE = frozenset("🌑🌒🌓🌔🌕🌖🌗🌘🕯")
ZERO_WIDTH = frozenset("️‍")
GAP = 3
ELLIPSIS = "…"
# A segment: (text, palette key or None, bold). A line: a list of segments.
Segment = tuple
Line = list


def cell_width(text: str) -> int:
    width = 0
    for ch in text:
        if ch in ZERO_WIDTH or unicodedata.combining(ch):
            continue
        width += 2 if ch in WIDE or unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def line_width(line: Line) -> int:
    return sum(cell_width(text) for text, _, _ in line)


def fit(line: Line, width: int) -> Line:
    """``line`` cut to ``width`` cells, ending in an ellipsis when it was too long."""
    if line_width(line) <= width:
        return line
    result, used = [], 0
    for text, key, bold in line:
        kept = ""
        for ch in text:
            size = cell_width(ch)
            if used + size > width - 1:
                result.append((kept + ELLIPSIS, key, bold))
                return result
            kept += ch
            used += size
        result.append((kept, key, bold))
    return result


def side_by_side(art: list[Line], info: list[Line], art_width: int) -> list[Line]:
    """Art on the left, ``GAP`` spaces, info on the right; the shorter block is centred vertically."""
    height = max(len(art), len(info))
    art_top, info_top = (height - len(art)) // 2, (height - len(info)) // 2
    rows = []
    for index in range(height):
        left = art[index - art_top] if 0 <= index - art_top < len(art) else []
        right = info[index - info_top] if 0 <= index - info_top < len(info) else []
        if right:
            left = left + [(" " * (art_width - line_width(left) + GAP), None, False)]
        rows.append(left + right)
    return rows


def render(line: Line, palette: dict[str, str] | None) -> str:
    """The line as text: 24-bit colour escapes, or plain text when ``palette`` is None (NO_COLOR)."""
    parts = []
    for text, key, bold in line:
        if palette is None or key is None:
            parts.append(text)
            continue
        colour = palette[key]
        red, green, blue = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
        parts.append(f"\x1b[{'1;' if bold else ''}38;2;{red};{green};{blue}m{text}\x1b[0m")
    return "".join(parts).rstrip(" ")
```

Create `witchy/ritual/log.py`:

```python
"""~/.cache/witchy/ritual.log: the last 20 errors of the greeting and the sky job, for doctor."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

NAME = "ritual.log"
MAX_LINES = 20


def append(path: Path, message: str, now: datetime) -> None:
    """Add one line; never raises, because the greeting must stay silent."""
    try:
        old = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        line = f"{now:%Y-%m-%dT%H:%M:%S} " + " ".join(message.split())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join([*old, line][-MAX_LINES:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def last(path: Path) -> str | None:
    """The newest line, or None when there is no log."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    return lines[-1] if lines else None
```

- [ ] **Step 4: Run the whole suite on both Pythons**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .` and `/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .`
Expected: OK on both (328 tests).

- [ ] **Step 5: Commit**

```bash
git add witchy/ritual/layout.py witchy/ritual/log.py tests/test_layout.py tests/test_ritual_log.py
git commit -m "feat: add the greeting's layout and error log

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 6: The sky job

**Files:**
- Create: `witchy/ritual/sky.py`, `tests/test_sky_job.py`

**Interfaces:**
- Consumes: `moon.phase_bin` (Plan B), `log.append`, `log.last`, `log.NAME` (Task 5); in tests, `windows_terminal.ritual_config`, `WT_LOCK`, `RITUAL_CONFIG` and `wt.SKY_VALUES` (Plan B).
- Produces:
  - `sky.CONFIG = Path(".claude/witchy/ritual-config.json")`, `sky.CACHE = Path(".cache/witchy")`, `sky.LOCK = "wt.lock"`, `sky.STAMP = "sky-bin"`, `sky.FAIL = "sky-fail"`, `sky.LOCK_TIMEOUT = 10.0`, `sky.KEY = "backgroundImage"`
  - `sky.SkyError(Exception)`, `sky.update(config: dict, lock: Path, target: int) -> bool` (False when the profile already shows image `target`)
  - `sky.run(home: Path, now: datetime) -> int` — always 0; writes `~/.cache/witchy/sky-bin` (`"<bin>\n"`) on success, and on any failure `~/.cache/witchy/sky-fail` (`"YYYY-MM-DD\n"`, today) plus one `ritual.log` line starting `sky: `; does nothing when `sky-fail` already holds today's date

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sky_job.py`:

```python
import fcntl
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from witchy import wt
from witchy.components import windows_terminal
from witchy.ritual import log, moon, sky

GUID = "{51855cb2-8cce-5362-8f54-464b92b32386}"
FULL_MOON = datetime(2026, 10, 26, 8, 0, tzinfo=timezone(timedelta(hours=1)))  # phase bin 4
# Windows Terminal's own layout: containers on their own line, ASCII escapes, no final newline.
WT_TEXT = """{
    "profiles": 
    {
        "list": 
        [
            {
                "guid": "{2c4de342-38b7-51cf-b940-2309a097f518}",
                "hidden": true,
                "name": "Ubuntu"
            },
            {
                "backgroundImage": "ms-appdata:///local/moonlit-candle-sky-1.png",
                "guid": "%s",
                "icon": "\\ud83c\\udf19",
                "name": "Ubuntu"
            }
        ]
    }
}""" % GUID


class SkyJobTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        self.settings = Path(tmp.name) / "LocalState" / "settings.json"
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(WT_TEXT, encoding="utf-8")
        config = self.home / sky.CONFIG
        config.parent.mkdir(parents=True)
        config.write_bytes(windows_terminal.ritual_config(self.settings, GUID))
        self.cache = self.home / sky.CACHE

    def run_job(self, now=FULL_MOON):
        self.assertEqual(sky.run(self.home, now), 0)

    def background(self):
        data = json.loads(self.settings.read_text(encoding="utf-8"))
        return data["profiles"]["list"][1]["backgroundImage"]

    def test_moves_the_sky_and_keeps_the_file_layout(self):
        self.run_job()
        self.assertEqual(self.background(), wt.SKY_VALUES[4])
        self.assertEqual(self.settings.read_text(encoding="utf-8"),
                         WT_TEXT.replace("moonlit-candle-sky-1.png", "moonlit-candle-sky-4.png"))
        self.assertEqual((self.cache / sky.STAMP).read_text(encoding="utf-8"), "4\n")
        self.assertFalse((self.cache / sky.FAIL).exists())

    def test_already_showing_tonight_writes_only_the_stamp(self):
        text = WT_TEXT.replace("sky-1.png", "sky-4.png")
        self.settings.write_text(text, encoding="utf-8")
        before = self.settings.stat().st_mtime_ns
        self.run_job()
        self.assertEqual((self.settings.read_text(encoding="utf-8"), self.settings.stat().st_mtime_ns), (text, before))
        self.assertEqual((self.cache / sky.STAMP).read_text(encoding="utf-8"), "4\n")

    def assert_failed(self, reason, text=WT_TEXT):
        self.assertEqual(self.settings.read_text(encoding="utf-8"), text)
        self.assertEqual((self.cache / sky.FAIL).read_text(encoding="utf-8"), "2026-10-26\n")
        self.assertIn(reason, log.last(self.cache / log.NAME))
        self.assertFalse((self.cache / sky.STAMP).exists())

    def test_a_value_the_user_chose_is_left_alone(self):
        text = WT_TEXT.replace("ms-appdata:///local/moonlit-candle-sky-1.png", "C:\\\\pics\\\\cat.png")
        self.settings.write_text(text, encoding="utf-8")
        self.run_job()
        self.assert_failed("was changed by hand", text)

    def test_comments_are_never_rewritten(self):
        text = "// my settings\n" + WT_TEXT
        self.settings.write_text(text, encoding="utf-8")
        self.run_job()
        self.assert_failed("is not plain JSON", text)

    def test_a_missing_profile(self):
        text = WT_TEXT.replace(GUID, "{00000000-0000-0000-0000-000000000000}")
        self.settings.write_text(text, encoding="utf-8")
        self.run_job()
        self.assert_failed("not found", text)

    def test_a_file_changed_during_the_job_is_not_overwritten(self):
        real, reads = Path.read_bytes, []

        def read_bytes(path):
            data = real(path)
            if path == self.settings and not reads:
                reads.append(path)
                path.write_text(WT_TEXT + " ", encoding="utf-8")  # another writer, right after our read
            return data

        with mock.patch.object(Path, "read_bytes", read_bytes):
            self.run_job()
        self.assert_failed("changed while the sky job ran", WT_TEXT + " ")

    def test_a_held_lock_fails_for_today(self):
        lock = self.cache / sky.LOCK
        lock.parent.mkdir(parents=True)
        with open(lock, "a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with mock.patch.object(sky, "LOCK_TIMEOUT", 0.2):
                self.run_job()
        self.assert_failed("held by another process")

    def test_the_fail_marker_stops_retries_until_tomorrow(self):
        self.cache.mkdir(parents=True)
        (self.cache / sky.FAIL).write_text("2026-10-26\n", encoding="utf-8")
        self.run_job()
        self.assertEqual(self.background(), wt.SKY_VALUES[1])
        self.run_job(FULL_MOON + timedelta(days=1))
        self.assertEqual(self.background(), wt.SKY_VALUES[moon.phase_bin(FULL_MOON + timedelta(days=1))])

    def test_no_config_fails_quietly(self):
        (self.home / sky.CONFIG).unlink()
        self.run_job()
        self.assertTrue((self.cache / sky.FAIL).is_file())

    def test_shares_names_with_the_installer(self):
        self.assertEqual(sky.LOCK, windows_terminal.WT_LOCK)
        self.assertEqual(sky.CONFIG, windows_terminal.RITUAL_CONFIG)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_sky_job -v`
Expected: ERROR `ImportError: cannot import name 'sky' from 'witchy.ritual'`.

- [ ] **Step 3: Implement**

Create `witchy/ritual/sky.py`:

```python
"""The sky job: point the Windows Terminal profile's backgroundImage at tonight's phase image (spec 4.5).

It edits the one value in place, so Windows Terminal's own formatting survives, and it shares
~/.cache/witchy/wt.lock with the installer.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from . import log, moon

CONFIG = Path(".claude/witchy/ritual-config.json")
CACHE = Path(".cache/witchy")
LOCK = "wt.lock"  # the same file as windows_terminal.WT_LOCK in the installer
STAMP = "sky-bin"
FAIL = "sky-fail"

LOCK_TIMEOUT = 10.0
KEY = "backgroundImage"


class SkyError(Exception):
    """The job left settings.json alone; the message says why."""


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    """Hold ``path`` like the installer's file_lock does, waiting up to LOCK_TIMEOUT seconds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as handle:
        deadline = time.monotonic() + LOCK_TIMEOUT
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SkyError(f"{path} is held by another process") from None
                time.sleep(0.1)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _write_atomic(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _profile(data: object, guid: str) -> dict | None:
    profiles = data.get("profiles") if isinstance(data, dict) else None
    listed = profiles.get("list") if isinstance(profiles, dict) else profiles
    for profile in listed if isinstance(listed, list) else []:
        if isinstance(profile, dict) and str(profile.get("guid", "")).lower() == guid.lower():
            return profile
    return None


def update(config: dict, lock: Path, target: int) -> bool:
    """Set the profile's backgroundImage to sky image ``target``; False when it already shows it."""
    settings, guid, sky = Path(config["settings"]), config["profile_guid"], config["sky"]
    with _locked(lock):
        raw = settings.read_bytes()
        try:
            text = raw.decode("utf-8")
            data = json.loads(text)
        except ValueError as exc:
            raise SkyError(f"{settings} is not plain JSON ({exc})") from exc
        profile = _profile(data, guid)
        if profile is None:
            raise SkyError(f"profile {guid} not found in {settings}")
        current = profile.get(KEY)
        if current not in sky:
            raise SkyError(f"{KEY} was changed by hand ({current!r}); leaving it")
        wanted = sky[target]
        if current == wanted:
            return False
        matches = list(re.finditer(rf'("{KEY}"\s*:\s*){re.escape(json.dumps(current))}', text))
        if len(matches) != 1:
            raise SkyError(f"{KEY} {current!r} appears {len(matches)} times in {settings}")
        match = matches[0]
        new_text = text[:match.start()] + match.group(1) + json.dumps(wanted) + text[match.end():]
        profile[KEY] = wanted
        if json.loads(new_text) != data:
            raise SkyError(f"rewriting {KEY} would change more than that value")
        if settings.read_bytes() != raw:
            raise SkyError(f"{settings} changed while the sky job ran")
        _write_atomic(settings, new_text.encode("utf-8"))
        return True


def run(home: Path, now: datetime) -> int:
    """Move the sky to ``now``'s phase. Failures are logged and retried at most once a day; always exits 0."""
    cache = home / CACHE
    today = now.date().isoformat()
    fail = cache / FAIL
    try:
        if fail.read_text(encoding="utf-8").strip() == today:
            return 0
    except OSError:
        pass
    try:
        config = json.loads((home / CONFIG).read_text(encoding="utf-8"))
        target = moon.phase_bin(now)
        update(config, cache / LOCK, target)
        (cache / STAMP).write_text(f"{target}\n", encoding="utf-8")
    except Exception as exc:  # the job runs in the background: it must never surface a traceback
        try:
            cache.mkdir(parents=True, exist_ok=True)
            fail.write_text(today + "\n", encoding="utf-8")
        except OSError:
            pass
        log.append(cache / log.NAME, f"sky: {exc}", now)
    return 0
```

- [ ] **Step 4: Run the whole suite on both Pythons**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .` and `/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .`
Expected: OK on both (338 tests). `tests.test_sky_job` takes well under a second; if it takes about 10 s, `LOCK_TIMEOUT` is being read at definition time instead of call time (it must be read inside `_locked`, so the test's patch applies).

- [ ] **Step 5: Commit**

```bash
git add witchy/ritual/sky.py tests/test_sky_job.py
git commit -m "feat: add the sky job that moves the Windows Terminal moon to tonight's phase

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 7: The greeting (`cli.py`, `__main__.py`)

**Files:**
- Create: `witchy/ritual/cli.py`, `witchy/ritual/__main__.py`, `tests/test_ritual_cli.py`

**Interfaces:**
- Consumes: every module from Tasks 1–6; `content/ritual.json` (Task 3).
- Produces:
  - `cli.DATA_FILES: tuple[Path, Path]`, `cli.CACHE`, `cli.STAMP = "last-ritual"`, `cli.FULL_EVERY = 600`, `cli.MIN_FULL_COLUMNS = 60`, `cli.SIDE_BY_SIDE = 80`, `cli.STACKED = 40`
  - `cli.load_data() -> dict`, `cli.salutation(hour: int) -> str`, `cli.info_lines(...)`, `cli.omen_line(...)`, `cli.art_lines(...)`, `cli.full_ritual(...)`
  - `cli.main(argv=None, *, env=None, out=None, now=None, home=None, root=Path("/"), columns=None) -> int` — always 0; flags `--full | --omen | --sky`, `--debug`, `--date YYYY-MM-DD`
  - `python3 -m witchy.ritual …` (repository) and `python3 -I -B <dir>/ritual …` (installed copy) both run `cli.main`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ritual_cli.py`:

```python
import io
import json
import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from witchy.ritual import cli, layout

CET = timezone(timedelta(hours=1))
CEST = timezone(timedelta(hours=2))
SAMHAIN_NIGHT = datetime(2026, 10, 31, 21, 30, tzinfo=CET)
ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
PLAIN = {"NO_COLOR": "1", "FISH_VERSION": "3.7.0"}


class CliTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        self.root = Path(tmp.name) / "root"
        (self.root / "etc").mkdir(parents=True)
        (self.root / "etc" / "os-release").write_text('PRETTY_NAME="Ubuntu 24.04.4 LTS"\n', encoding="utf-8")

    def run_cli(self, argv=(), env=None, now=SAMHAIN_NIGHT, columns=100):
        out = io.StringIO()
        code = cli.main(list(argv), env=PLAIN if env is None else env, out=out, now=now, home=self.home,
                        root=self.root, columns=columns)
        self.assertEqual(code, 0)
        return out.getvalue()

    @property
    def stamp(self):
        return self.home / ".cache" / "witchy" / cli.STAMP

    @property
    def log(self):
        return self.home / ".cache" / "witchy" / "ritual.log"


class FullRitualTest(CliTestCase):
    def test_side_by_side_at_100_columns(self):
        lines = self.run_cli(["--full"]).splitlines()
        self.assertEqual(lines[-1], "")  # one blank line after the greeting
        info = [line[31:] for line in lines if len(line) > 31]
        self.assertIn("Good evening, eimi", info)
        self.assertIn("🕯️ Samhain — the veil is thin tonight", info)
        self.assertIn("✦ XVII · The Star", info)
        self.assertIn("  hope and renewal after the storm", info)
        self.assertIn("os      Ubuntu 24.04.4 LTS", info)
        self.assertIn("shell   fish 3.7.0", info)
        self.assertTrue(any("░" in line[:28] for line in lines))

    def test_stacked_at_70_and_info_only_at_39(self):
        stacked = self.run_cli(["--full"], columns=70).splitlines()
        self.assertTrue(all("░" in line or "▒" in line for line in stacked[1:10]))  # the art first
        self.assertEqual(stacked[11:13], ["", "Good evening, eimi"])  # then a blank line and the info
        narrow = self.run_cli(["--full"], columns=39).splitlines()
        self.assertEqual(narrow[0], "Good evening, eimi")
        self.assertFalse(any("░" in line for line in narrow))

    def test_no_line_is_wider_than_the_terminal(self):
        for columns in (100, 80, 70, 40, 39, 30):
            for when in (SAMHAIN_NIGHT, datetime(2026, 5, 31, 23, 0, tzinfo=CEST)):
                with self.subTest(columns=columns, when=when):
                    for line in self.run_cli(["--full"], now=when, columns=columns).splitlines():
                        self.assertLessEqual(layout.cell_width(line), columns, line)

    def test_countdown_lunar_line_and_salutations(self):
        text = self.run_cli(["--full"], now=datetime(2026, 10, 26, 8, 0, tzinfo=CET))
        self.assertIn("Good morning, eimi", text)
        self.assertIn("⋆ Samhain in 5 days", text)
        self.assertIn("🌕 Full moon — charge your crystals", text)
        self.assertIn("⋆ Samhain tomorrow", self.run_cli(["--full"], now=datetime(2026, 10, 30, 13, 0, tzinfo=CET)))
        blue = self.run_cli(["--full"], now=datetime(2026, 5, 31, 2, 0, tzinfo=CEST))
        self.assertIn("Good witching hour, eimi", blue)
        self.assertIn("🌕 Blue moon — a rare moon; make a bold wish", blue)

    def test_salutation_hours(self):
        expected = {0: "Good witching hour", 3: "Good witching hour", 4: "Good morning", 11: "Good morning",
                    12: "Good afternoon", 17: "Good afternoon", 18: "Good evening", 23: "Good evening"}
        self.assertEqual({hour: cli.salutation(hour) for hour in expected}, expected)

    def test_colours_and_the_sabbat_accent(self):
        text = self.run_cli(["--full"], env={"FISH_VERSION": "3.7.0"})
        self.assertIn("\x1b[1;38;2;255;184;107mGood evening, eimi", text)  # Samhain's accent, bold
        self.assertIn("\x1b[38;2;255;103;183m✦ XVII · The Star", text)
        plain = self.run_cli(["--full"], env={"FISH_VERSION": "3.7.0"}, now=datetime(2026, 10, 3, 9, tzinfo=CEST))
        self.assertIn("\x1b[1;38;2;255;212;119mGood morning, eimi", plain)

    def test_no_color(self):
        self.assertNotRegex(self.run_cli(["--full"]), ESCAPE)
        self.assertNotRegex(self.run_cli(["--omen"]), ESCAPE)

    def test_the_date_flag_previews_another_day(self):
        text = self.run_cli(["--full", "--date", "2026-10-26"], now=datetime(2026, 10, 3, 21, 30, tzinfo=CET))
        self.assertIn("⋆ Samhain in 5 days", text)


class OmenTest(CliTestCase):
    def test_one_line(self):
        self.assertEqual(self.run_cli(["--omen"]),
                         "🌗 Last Quarter 67% · ✦ The Star · 🕯️ Samhain\n\n")
        text = self.run_cli(["--omen"], now=datetime(2026, 10, 26, 8, 0, tzinfo=CET))
        self.assertEqual(text, "🌕 Full 100% · ✦ The Devil (reversed) · ⋆ Samhain in 5 days\n\n")

    def test_cut_to_the_terminal(self):
        line = self.run_cli(["--omen"], columns=20).splitlines()[0]
        self.assertEqual(layout.cell_width(line), 20)
        self.assertTrue(line.endswith("…"))


class AutoModeTest(CliTestCase):
    def test_first_shell_gets_the_full_ritual_then_the_omen(self):
        first = self.run_cli()
        self.assertIn("Good evening, eimi", first)
        self.assertTrue(self.stamp.is_file())
        self.assertEqual(len(self.run_cli().splitlines()), 2)

    def test_full_again_after_ten_minutes(self):
        self.run_cli()
        old = SAMHAIN_NIGHT.timestamp() - cli.FULL_EVERY - 1
        os.utime(self.stamp, (old, old))
        self.assertIn("Good evening, eimi", self.run_cli())

    def test_narrow_terminals_get_the_omen(self):
        self.assertEqual(len(self.run_cli(columns=59).splitlines()), 2)
        self.assertFalse(self.stamp.exists())

    def test_explicit_full_ignores_the_stamp(self):
        self.run_cli()
        self.assertIn("Good evening, eimi", self.run_cli(["--full"]))


class FailureTest(CliTestCase):
    def test_any_error_prints_nothing_and_is_logged(self):
        with mock.patch.object(cli, "DATA_FILES", (self.home / "missing.json",)):
            self.assertEqual(self.run_cli(["--full"]), "")
        self.assertIn("greeting: FileNotFoundError", self.log.read_text(encoding="utf-8"))

    def test_bad_data_prints_nothing(self):
        bad = self.home / "data.json"
        bad.parent.mkdir(parents=True)
        bad.write_text(json.dumps({"name": "eimi"}), encoding="utf-8")
        with mock.patch.object(cli, "DATA_FILES", (bad,)):
            self.assertEqual(self.run_cli(["--omen"]), "")
        self.assertIn("KeyError", self.log.read_text(encoding="utf-8"))

    def test_debug_prints_stage_timings(self):
        last = self.run_cli(["--full", "--debug"]).splitlines()[-1]
        self.assertRegex(last, r"^debug: data [0-9.]+ ms · fetch [0-9.]+ ms · compose [0-9.]+ ms · "
                               r"render [0-9.]+ ms · total [0-9.]+ ms$")

    def test_data_comes_from_the_package_then_content(self):
        self.assertEqual(cli.DATA_FILES[0].name, "data.json")
        self.assertEqual(cli.load_data()["name"], "eimi")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_ritual_cli -v`
Expected: ERROR `ImportError: cannot import name 'cli' from 'witchy.ritual'`.

- [ ] **Step 3: Implement**

Create `witchy/ritual/cli.py`:

```python
"""The greeting: the full ritual, the one-line omen, or the sky job (spec 6)."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import textwrap
import time
from datetime import date, datetime
from pathlib import Path
from typing import Mapping, TextIO

from . import art, fetch, layout, log, moon, palette, sky, tarot, wheel

HERE = Path(__file__).resolve().parent
# The installed copy carries data.json; in the repository the texts are still in content/.
DATA_FILES = (HERE / "data.json", HERE.parent.parent / "content" / "ritual.json")
CACHE = Path(".cache/witchy")
STAMP = "last-ritual"
FULL_EVERY = 600  # seconds between two full rituals in auto mode
MIN_FULL_COLUMNS = 60
SIDE_BY_SIDE = 80
STACKED = 40
# (first hour after the greeting ends, greeting)
SALUTATIONS = ((4, "Good witching hour"), (12, "Good morning"), (18, "Good afternoon"), (24, "Good evening"))
LUNAR = {"new": ("🌑", "New moon"), "full": ("🌕", "Full moon"), "blue": ("🌕", "Blue moon")}
SEPARATOR = (" · ", "label", False)


def load_data() -> dict:
    path = next((path for path in DATA_FILES if path.is_file()), DATA_FILES[0])
    return json.loads(path.read_text(encoding="utf-8"))


def salutation(hour: int) -> str:
    return next(text for end, text in SALUTATIONS if hour < end)


def _countdown(name: str, days: int) -> str:
    return f"⋆ {name} tomorrow" if days == 1 else f"⋆ {name} in {days} days"


def info_lines(now: datetime, data: dict, fetched: list[tuple[str, str]], width: int) -> list[layout.Line]:
    """The column beside the moon: salutation, sabbat, lunar events, phase, tarot, system."""
    day, tz = now.date(), now.tzinfo
    sabbat = wheel.upcoming(day, tz)
    on_sabbat = sabbat is not None and sabbat[1] == 0
    lines = [[(f"{salutation(now.hour)}, {fetch.clean(data['name'])}",
               sabbat[0].lower() if on_sabbat else "salutation", True)]]
    if sabbat:
        name, days = sabbat
        text = f"🕯️ {name} — {data['sabbats'][name]}" if days == 0 else _countdown(name, days)
        lines.append([(text, name.lower(), False)])
    for event in moon.lunar_events(day, tz):
        glyph, label = LUNAR[event]
        lines.append([(f"{glyph} {label} — {data['lunar'][event]}", "moon", False)])
    phase = moon.phase_bin(now)
    lines.append([(f"⋆ {moon.NAMES[phase]}  {moon.illumination(now)}%", "moon", False)])
    card, reversed_ = tarot.card_of(day, data["tarot"])
    title = [(f"✦ {tarot.NUMERALS[card['number']]} · {card['name']}", "tarot", False)]
    lines.append(title + ([(" (reversed)", "muted", False)] if reversed_ else []))
    meaning = card["reversed"] if reversed_ else card["upright"]
    lines += [[("  " + part, "muted", False)] for part in textwrap.wrap(meaning, max(10, width - 2))]
    lines += [[(label.ljust(fetch.LABEL_WIDTH), "label", False), (value, "value", False)] for label, value in fetched]
    return [layout.fit(line, width) for line in lines]


def omen_line(now: datetime, data: dict, width: int) -> layout.Line:
    """One line: phase, card of the day and, near a sabbat, the sabbat."""
    phase = moon.phase_bin(now)
    card, reversed_ = tarot.card_of(now.date(), data["tarot"])
    line = [(f"{moon.GLYPHS[phase]} {moon.NAMES[phase]} {moon.illumination(now)}%", "moon", False), SEPARATOR,
            (f"✦ {card['name']}", "tarot", False)]
    if reversed_:
        line.append((" (reversed)", "muted", False))
    sabbat = wheel.upcoming(now.date(), now.tzinfo)
    if sabbat:
        name, days = sabbat
        line += [SEPARATOR, (f"🕯️ {name}" if days == 0 else _countdown(name, days), name.lower(), False)]
    return layout.fit(line, width)


def art_lines(now: datetime) -> list[layout.Line]:
    rows = []
    for cells in art.picture(moon.age(now) / moon.SYNODIC_DAYS, now.date()):
        line: layout.Line = []
        for char, key in cells:
            if line and line[-1][1] == key:
                line[-1] = (line[-1][0] + char, key, False)
            else:
                line.append((char, key, False))
        rows.append(line)
    return rows


def full_ritual(now: datetime, data: dict, fetched: list[tuple[str, str]], columns: int) -> list[layout.Line]:
    if columns >= SIDE_BY_SIDE:
        info = info_lines(now, data, fetched, columns - art.WIDTH - layout.GAP)
        return layout.side_by_side(art_lines(now), info, art.WIDTH)
    info = info_lines(now, data, fetched, columns)
    return art_lines(now) + [[]] + info if columns >= STACKED else info


def _auto(stamp: Path, now: datetime, columns: int) -> str:
    try:
        recent = now.timestamp() - stamp.stat().st_mtime < FULL_EVERY
    except OSError:
        recent = False
    return "full" if not recent and columns >= MIN_FULL_COLUMNS else "omen"


def _stamp(path: Path, now: datetime) -> None:
    """Remember when the full ritual last ran (the file's mtime), so auto mode shows the omen for a while."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        os.utime(path, (now.timestamp(), now.timestamp()))
    except OSError:
        pass


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ritual", description="The Moonlit Candle greeting")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--full", action="store_true", help="always show the full ritual")
    mode.add_argument("--omen", action="store_true", help="show the one-line omen")
    mode.add_argument("--sky", action="store_true", help="move the Windows Terminal sky to tonight's phase")
    parser.add_argument("--debug", action="store_true", help="print the time each stage took")
    parser.add_argument("--date", type=date.fromisoformat, help="preview another day (YYYY-MM-DD)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, env: Mapping[str, str] | None = None, out: TextIO | None = None,
         now: datetime | None = None, home: Path | None = None, root: Path = Path("/"),
         columns: int | None = None) -> int:
    """Print the greeting. Any error prints nothing, is logged, and still exits 0."""
    env = os.environ if env is None else env
    out = sys.stdout if out is None else out
    home = Path.home() if home is None else home
    cache = home / CACHE
    args = _arguments(argv)
    try:
        marks = [("start", time.perf_counter())]
        now = now or datetime.now().astimezone()
        if args.date:
            now = datetime.combine(args.date, now.timetz())
        if args.sky:
            return sky.run(home, now)
        columns = columns or shutil.get_terminal_size((80, 24)).columns
        data = load_data()
        marks.append(("data", time.perf_counter()))
        mode = "full" if args.full else "omen" if args.omen else _auto(cache / STAMP, now, columns)
        if mode == "full":
            fetched = fetch.lines(env, root)
            marks.append(("fetch", time.perf_counter()))
            lines = full_ritual(now, data, fetched, columns)
        else:
            lines = [omen_line(now, data, columns)]
        marks.append(("compose", time.perf_counter()))
        colours = None if env.get("NO_COLOR") else palette.PALETTE
        text = "".join(layout.render(line, colours) + "\n" for line in lines) + "\n"
        marks.append(("render", time.perf_counter()))
        if args.debug:
            stages = [f"{name} {(end - start) * 1000:.1f} ms" for (_, start), (name, end) in zip(marks, marks[1:])]
            text += "debug: " + " · ".join(stages) + f" · total {(marks[-1][1] - marks[0][1]) * 1000:.1f} ms\n"
        out.write(text)
        if mode == "full":
            _stamp(cache / STAMP, now)
    except Exception as exc:  # the greeting must never break a shell: log and stay silent
        log.append(cache / log.NAME, f"greeting: {exc!r}", datetime.now())
    return 0
```

Create `witchy/ritual/__main__.py`:

```python
"""python3 -I ~/.claude/witchy/ritual [--full | --omen | --sky] [--debug] [--date YYYY-MM-DD]"""
import sys
from pathlib import Path

if __package__:  # python3 -m witchy.ritual, from the repository
    from .cli import main
else:  # the installed copy, run as a directory
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from ritual.cli import main

sys.exit(main())
```

- [ ] **Step 4: Run the whole suite on both Pythons, and preview**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .` and `/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .`
Expected: OK on both (356 tests).

Run: `/usr/bin/python3 -B -m witchy.ritual --full --date 2026-10-31`
Expected: the moon on the left, `Good …, eimi` and `🕯️ Samhain — the veil is thin tonight` on the right, in colour, then one blank line. This only reads `/etc/os-release` and `/proc`; with `--full` it also touches `~/.cache/witchy/last-ritual`, which is disposable.

- [ ] **Step 5: Commit**

```bash
git add witchy/ritual/cli.py witchy/ritual/__main__.py tests/test_ritual_cli.py
git commit -m "feat: add the greeting: full ritual, omen and auto mode

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

### Task 8: The package as installed, and the spec record

**Files:**
- Modify: `witchy/build.py`, `docs/superpowers/specs/2026-10-02-shell-ritual-design.md`
- Create: `tests/test_ritual_package.py`

**Interfaces:**
- Consumes: `build.with_palette`, `build.RITUAL_SOURCE` (Task 3); the whole package (Tasks 1–7).
- Produces: `build.ritual_package(variant: str = palette.DEFAULT_VARIANT, content_dir: Path = content.CONTENT_DIR, source: Path = RITUAL_SOURCE) -> dict[str, bytes]` — file name → bytes: every `witchy/ritual/*.py` (with `palette.py` rewritten from `variant`) plus `data.json` (a copy of `content/ritual.json`). Plan D installs these into `~/.claude/witchy/ritual/`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ritual_package.py`:

```python
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from witchy import build, content, palette

PYTHON = "/usr/bin/python3" if Path("/usr/bin/python3").is_file() else sys.executable


class PackageTest(unittest.TestCase):
    def test_every_module_and_the_texts(self):
        files = build.ritual_package()
        modules = {path.name for path in build.RITUAL_SOURCE.glob("*.py")}
        self.assertEqual(set(files), modules | {"data.json"})
        self.assertEqual(files["data.json"], (content.CONTENT_DIR / content.RITUAL).read_bytes())

    def test_palette_comes_from_the_variant(self):
        dawn = palette.Variant(**{**palette.VARIANTS["midnight"].__dict__, "name": "dawn",
                                  "ritual": dict(palette.RITUAL, salutation="#FFE3A3")})
        with mock.patch.dict(palette.VARIANTS, {"dawn": dawn}):
            text = build.ritual_package("dawn")["palette.py"].decode("utf-8")
        self.assertIn('"salutation": "#FFE3A3",', text)

    def test_imports_nothing_from_witchy(self):
        for name, data in build.ritual_package().items():
            if name.endswith(".py"):
                self.assertNotRegex(data.decode("utf-8"), re.compile(r"^\s*(from|import)\s+witchy", re.M), name)


class InstalledCopyTest(unittest.TestCase):
    def test_runs_isolated_from_its_own_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / ".claude" / "witchy" / "ritual"
            target.mkdir(parents=True)
            for name, data in build.ritual_package().items():
                (target / name).write_bytes(data)
            env = {"HOME": tmp, "NO_COLOR": "1", "PATH": os.environ.get("PATH", "")}
            started = time.monotonic()
            done = subprocess.run([PYTHON, "-I", "-B", str(target), "--omen", "--date", "2026-10-31"],
                                  capture_output=True, text=True, env=env, cwd=tmp, timeout=10)
            elapsed = time.monotonic() - started
            self.assertEqual((done.returncode, done.stderr), (0, ""))
            self.assertIn("🕯️ Samhain", done.stdout)
            self.assertLess(elapsed, 1.0)  # a regression guard; the real budget is 200 ms (spec 6.7)
            self.assertEqual(sorted(path.name for path in target.iterdir()), sorted(build.ritual_package()))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_ritual_package -v`
Expected: ERROR `AttributeError: module 'witchy.build' has no attribute 'ritual_package'`.

- [ ] **Step 3: Implement**

In `witchy/build.py`, add directly above `def _json(`:

```python
def ritual_package(variant: str = palette.DEFAULT_VARIANT, content_dir: Path = content.CONTENT_DIR,
                   source: Path = RITUAL_SOURCE) -> dict[str, bytes]:
    """The greeting package as installed: its modules, palette.py from ``variant``, and data.json from content/."""
    files = {}
    for module in sorted(source.glob("*.py")):
        text = (with_palette(module, palette.VARIANTS[variant].ritual) if module.name == "palette.py"
                else module.read_text(encoding="utf-8"))
        files[module.name] = text.encode("utf-8")
    files["data.json"] = (content_dir / content.RITUAL).read_bytes()
    return files
```

- [ ] **Step 4: Record the decisions in the spec**

In `docs/superpowers/specs/2026-10-02-shell-ritual-design.md`, check that each anchor appears exactly once (`grep -cF`), then:

1. Section 4.5: replace ``start `@PYTHON@ -I @WITCHY_DIR@/ritual --sky` `` with ``start `@PYTHON@ -I -B @WITCHY_DIR@/ritual --sky` ``.
2. Section 4.5: after the bullet beginning `- The job takes the lock`, add the bullet: `- The job edits only that value in the file's text (it must appear exactly once), re-parses the result and requires it to match; Windows Terminal's own layout survives. When the profile already shows tonight's image it only writes \`sky-bin\`.`
3. Section 6.1: replace ``and run as `@PYTHON@ -I @WITCHY_DIR@/ritual`.`` with ``and run as `@PYTHON@ -I -B @WITCHY_DIR@/ritual` (`-B`: no `__pycache__` under `~/.claude`).``
4. Section 6.1 table: after the row ``| `data.json` | copied from `content/ritual.json` |`` add the row ``| `cli.py` | the greeting itself; `__main__.py` only finds it, in the repository or the installed copy |``.
5. Section 6.3: after the bullet beginning `- Event days (6.6) use Meeus ch. 49`, add the bullet: `- ΔT (TT − UTC) is taken as 69 s, good to a few seconds through the 2020s.`
6. Section 6.5: replace ``and `fish $FISH_VERSION`.`` with ``and `fish $FISH_VERSION` (fish passes `FISH_VERSION` in the environment).``

- [ ] **Step 5: Run the whole suite on both Pythons, and validate**

Run: `/usr/bin/python3 -m unittest discover -s tests -t .`, `/home/eimi/.pyenv/versions/3.10.0/bin/python3 -m unittest discover -s tests -t .` and `/usr/bin/python3 -m witchy validate`
Expected: OK on both (360 tests); `Moonlit Candle: all checks passed`.

- [ ] **Step 6: Commit**

```bash
git add witchy/build.py tests/test_ritual_package.py docs/superpowers/specs/2026-10-02-shell-ritual-design.md
git commit -m "feat: build the greeting package as installed; record plan C decisions in the spec

Co-Authored-By: <the trailer for the model writing this commit>"
```

---

## For Plan D

What Plan D consumes from this plan:

- `build.ritual_package(variant)` → install each file into `~/.claude/witchy/ritual/` and record it like the claude component's files (backup, `installed_sha256`).
- Run it as `@PYTHON@ -I -B @WITCHY_DIR@/ritual [--full | --omen | --sky]`, with `env FISH_VERSION=$FISH_VERSION` so the fetch can show the fish version.
- `fish_greeting` checks the spec 6.2 conditions; the package only decides full or omen (auto mode, `~/.cache/witchy/last-ritual`).
- The sky job's files: `~/.cache/witchy/sky-bin` (`"<bin>\n"`), `~/.cache/witchy/sky-fail` (`"YYYY-MM-DD\n"`), log lines starting `sky: ` or `greeting: ` in `~/.cache/witchy/ritual.log` (`log.last()` for doctor).
- `_witchy_moon_bin` must match `witchy.ritual.moon.phase_bin` over 60 days (spec 5.1).
- Still open for Plan D: Tide and eza colours and their validation (11.3, 11.4), the Plan A carry-overs (uninstall commands in `Plan`; R7), and the deferred minors in the handoff `~/.claude/handoffs/witchyterm-2026-10-03-0347.md`.
