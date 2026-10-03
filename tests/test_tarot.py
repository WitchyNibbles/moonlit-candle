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
