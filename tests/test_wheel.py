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
