import unittest

from witchy.contrast import contrast_ratio, luminance


class ContrastTest(unittest.TestCase):
    def test_black_and_white_are_21_to_1(self):
        self.assertAlmostEqual(contrast_ratio("#FFFFFF", "#000000"), 21.0, places=6)

    def test_order_does_not_matter(self):
        self.assertAlmostEqual(contrast_ratio("#000000", "#FFFFFF"), 21.0, places=6)

    def test_known_pair_from_the_palette(self):
        self.assertAlmostEqual(contrast_ratio("#6E5A80", "#0D0916"), 3.22, delta=0.01)

    def test_luminance_extremes(self):
        self.assertEqual(luminance("#000000"), 0.0)
        self.assertAlmostEqual(luminance("#FFFFFF"), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
