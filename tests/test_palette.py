import unittest

from witchy import palette, tokens


class TokensTest(unittest.TestCase):
    def test_rule_groups_do_not_overlap(self):
        groups = [tokens.TEXT, tokens.SECONDARY, tokens.BACKGROUNDS, (tokens.ON_ACCENT,), tuple(tokens.EXEMPT)]
        self.assertEqual(sum(len(group) for group in groups), len(tokens.ALL))

    def test_documented_token_count(self):
        self.assertEqual(len(tokens.ALL), 62)

    def test_accent_fills_are_tokens(self):
        self.assertTrue(set(tokens.ACCENT_FILLS) <= tokens.ALL)


class PaletteTest(unittest.TestCase):
    def test_every_token_has_a_colour(self):
        self.assertEqual(set(palette.CLAUDE_OVERRIDES), set(tokens.ALL))

    def test_spec_anchor_colours(self):
        overrides = palette.CLAUDE_OVERRIDES
        self.assertEqual(overrides["claude"], "#FFD477")
        self.assertEqual(overrides["permission"], "#FF67B7")
        self.assertEqual(overrides["planMode"], "#B99AFF")
        self.assertEqual(overrides["success"], "#74E8B8")
        self.assertEqual(overrides["promptBorder"], "#6E5A80")
        self.assertEqual(overrides["text"], "#F3EAF7")
        self.assertEqual(overrides["inverseText"], "#0D0916")

    def test_windows_terminal_scheme_matches_spec(self):
        scheme = palette.WT_SCHEME
        self.assertEqual(len(scheme), 21)
        self.assertEqual(scheme["name"], "Moonlit Candle")
        self.assertEqual(scheme["background"], "#0D0916")
        self.assertEqual(scheme["cursorColor"], "#FF67B7")
        self.assertEqual(scheme["black"], "#1D1230")
        self.assertEqual(scheme["brightBlack"], "#6E5A80")
        self.assertEqual(scheme["brightWhite"], "#FFFFFF")

    def test_statusline_colour_names_and_order(self):
        self.assertEqual(
            list(palette.STATUSLINE),
            ["model", "muted", "divider", "repo", "branch", "dirty",
             "context_low", "context_mid", "context_high", "left_high", "left_mid", "left_low"],
        )


if __name__ == "__main__":
    unittest.main()
