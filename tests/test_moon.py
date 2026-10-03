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
