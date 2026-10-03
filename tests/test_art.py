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
