import tempfile
import unittest
from datetime import date, timedelta, timezone
from pathlib import Path

from witchy import palette as theme
from witchy.ritual import caret, palette, wheel

UTC = timezone.utc


class ColourTest(unittest.TestCase):
    def test_the_sabbat_and_its_eve_take_its_colour(self):
        self.assertEqual(caret.colour(date(2026, 10, 30), UTC), ("samhain", "FFB86B"))
        self.assertEqual(caret.colour(date(2026, 10, 31), UTC), ("samhain", "FFB86B"))

    def test_other_days_are_gold(self):
        for day in (date(2026, 10, 29), date(2026, 11, 1), date(2026, 10, 5)):
            with self.subTest(day=day):
                self.assertIsNone(caret.colour(day, UTC))

    def test_every_sabbat_wears_its_greeting_colour(self):
        for name, day in wheel.sabbat_dates(2027, UTC).items():
            with self.subTest(name=name):
                expected = (name.lower(), theme.RITUAL[name.lower()].lstrip("#"))
                self.assertEqual(caret.colour(day, UTC), expected)
                self.assertEqual(caret.colour(day - timedelta(days=1), UTC), expected)
                self.assertIsNone(caret.colour(day + timedelta(days=1), UTC))

    def test_a_time_zone_moves_a_season_date(self):
        # The 2026 December solstice is 2026-12-21 20:50 UTC, already 12-22 east of UTC+3:10.
        east = timezone(timedelta(hours=9))
        self.assertIsNone(caret.colour(date(2026, 12, 22), UTC))
        self.assertEqual(caret.colour(date(2026, 12, 22), east), ("yule", "E6DCEE"))

    def test_the_colours_come_from_the_installed_palette_block(self):
        self.assertEqual(palette.PALETTE["samhain"], "#FFB86B")


class TextTest(unittest.TestCase):
    def test_today_and_tomorrow(self):
        self.assertEqual(caret.text(date(2026, 10, 30), UTC), "2026-10-30 FFB86B samhain\n2026-10-31 FFB86B samhain\n")
        self.assertEqual(caret.text(date(2026, 10, 31), UTC), "2026-10-31 FFB86B samhain\n2026-11-01\n")
        self.assertEqual(caret.text(date(2026, 10, 5), UTC), "2026-10-05\n2026-10-06\n")

    def test_across_new_year_and_into_imbolc(self):
        self.assertEqual(caret.text(date(2026, 12, 31), UTC), "2026-12-31\n2027-01-01\n")
        self.assertEqual(caret.text(date(2027, 1, 30), UTC), "2027-01-30\n2027-01-31 F3EAF7 imbolc\n")


class FileTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "cache" / "witchy" / caret.NAME

    def test_write_creates_the_folder_and_replaces_the_file_whole(self):
        caret.write(self.path, date(2026, 10, 30), UTC)
        self.assertEqual(self.path.read_text(encoding="utf-8"),
                         "2026-10-30 FFB86B samhain\n2026-10-31 FFB86B samhain\n")
        caret.write(self.path, date(2026, 11, 1), UTC)
        self.assertEqual(self.path.read_text(encoding="utf-8"), "2026-11-01\n2026-11-02\n")
        self.assertEqual([p.name for p in self.path.parent.iterdir()], [caret.NAME])

    def test_read_returns_each_well_formed_line(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("2026-10-31 FFB86B samhain\n2026-11-01\n", encoding="utf-8")
        self.assertEqual(caret.read(self.path), {"2026-10-31": ("samhain", "FFB86B"), "2026-11-01": None})

    def test_read_skips_damaged_lines(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b"2026-10-31 #FFB86B samhain\n2026-10-31 ffb86b samhain\n\xff\xfe\n"
                              b"2026-11-01 FFB86B\n2026-11-02 FFB86B samhain; rm\n2026-11-03\n")
        self.assertEqual(caret.read(self.path), {"2026-11-03": None})

    def test_read_raises_when_there_is_no_file(self):
        with self.assertRaises(OSError):
            caret.read(self.path)


if __name__ == "__main__":
    unittest.main()
