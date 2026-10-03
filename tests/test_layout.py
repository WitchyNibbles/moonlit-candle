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
