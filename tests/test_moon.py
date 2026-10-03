import unittest
from datetime import datetime, timedelta, timezone

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


if __name__ == "__main__":
    unittest.main()
