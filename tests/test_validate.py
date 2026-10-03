import copy
import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import content, palette, sky_render, validate


def pairs(failures):
    return {(f.rule, f.item) for f in failures}


def triples(failures):
    return {(f.rule, f.item, f.value) for f in failures}


class PaletteRulesTest(unittest.TestCase):
    def test_real_palette_passes(self):
        self.assertEqual(validate.validate_palette(), [])

    def test_low_contrast_text_fails(self):
        overrides = dict(palette.CLAUDE_OVERRIDES, claude="#3A2E47")
        self.assertIn(("text-contrast", "claude.claude"), pairs(validate.validate_palette(overrides=overrides)))

    def test_mockup_prompt_border_fails_the_secondary_rule(self):
        overrides = dict(palette.CLAUDE_OVERRIDES, promptBorder="#503762")
        self.assertIn(("secondary-contrast", "claude.promptBorder"), pairs(validate.validate_palette(overrides=overrides)))

    def test_background_too_light_for_text_fails(self):
        overrides = dict(palette.CLAUDE_OVERRIDES, diffAdded="#A0A0A0")
        self.assertIn(("background-contrast", "claude.diffAdded"), pairs(validate.validate_palette(overrides=overrides)))

    def test_inverse_text_must_read_on_accent_fills(self):
        overrides = dict(palette.CLAUDE_OVERRIDES, inverseText="#FFFFFF")
        self.assertIn(("on-accent-contrast", "claude.inverseText on claude"),
                      pairs(validate.validate_palette(overrides=overrides)))

    def test_exempt_tokens_are_not_contrast_checked(self):
        overrides = dict(palette.CLAUDE_OVERRIDES, rate_limit_empty="#0E0A17", claudeShimmer="#0E0A17")
        self.assertEqual(validate.validate_palette(overrides=overrides), [])

    def test_unknown_token_fails(self):
        overrides = dict(palette.CLAUDE_OVERRIDES, claudee="#FFD477")
        self.assertIn(("unknown-token", "claudee"), pairs(validate.validate_palette(overrides=overrides)))

    def test_missing_token_fails(self):
        overrides = dict(palette.CLAUDE_OVERRIDES)
        del overrides["merged"]
        self.assertIn(("missing-token", "merged"), pairs(validate.validate_palette(overrides=overrides)))

    def test_bad_format_fails(self):
        for bad in ("#ffd477", "gold", "#FFD47", None):
            overrides = dict(palette.CLAUDE_OVERRIDES, claude=bad)
            self.assertIn(("format", "claude.claude"), pairs(validate.validate_palette(overrides=overrides)), bad)

    def test_windows_terminal_text_and_consistency(self):
        scheme = dict(palette.WT_SCHEME, red="#301020", background="#000000")
        found = pairs(validate.validate_palette(scheme=scheme))
        self.assertIn(("text-contrast", "wt.red"), found)
        self.assertIn(("consistency", "wt.background"), found)

    def test_windows_terminal_missing_colour_fails(self):
        scheme = dict(palette.WT_SCHEME)
        del scheme["brightCyan"]
        self.assertIn(("missing-token", "wt.brightCyan"), pairs(validate.validate_palette(scheme=scheme)))

    def test_windows_terminal_black_is_exempt(self):
        scheme = dict(palette.WT_SCHEME, black="#0D0916")
        self.assertEqual(validate.validate_palette(scheme=scheme), [])

    def test_statusline_divider_is_exempt_but_text_is_not(self):
        self.assertEqual(validate.validate_palette(statusline=dict(palette.STATUSLINE, divider="#0E0A17")), [])
        found = pairs(validate.validate_palette(statusline=dict(palette.STATUSLINE, repo="#2A1F35")))
        self.assertIn(("text-contrast", "statusline.repo"), found)

    def test_failure_prints_rule_item_value_detail(self):
        failure = validate.Failure("text-contrast", "claude.claude", "#3A2E47", "1.60:1 < 4.5:1")
        self.assertEqual(str(failure), "text-contrast: claude.claude #3A2E47 1.60:1 < 4.5:1")


class ContentRulesTest(unittest.TestCase):
    def setUp(self):
        self.spinner = content.load_spinner()
        self.style = content.read_output_style()

    def check(self, spinner=None, style=None):
        return validate.validate_content(spinner if spinner is not None else self.spinner,
                                         style if style is not None else self.style)

    def test_real_content_passes(self):
        self.assertEqual(self.check(), [])

    def test_verb_count_bounds(self):
        few = dict(self.spinner, verbs=self.spinner["verbs"][:35])
        self.assertIn(("content", "spinner.verbs", "35"), triples(self.check(spinner=few)))
        many = dict(self.spinner, verbs=self.spinner["verbs"] + [f"Brewing batch {c}" for c in "abcdefghi"])
        self.assertIn(("content", "spinner.verbs", "49"), triples(self.check(spinner=many)))

    def test_bad_verbs_fail(self):
        for verb in ("Hexing things…", "Hexing...", "Consulting the ancient grimoire", "brewing", "Brewed"):
            spinner = dict(self.spinner, verbs=self.spinner["verbs"][:-1] + [verb])
            self.assertIn(("content", "spinner.verbs", verb), triples(self.check(spinner=spinner)), verb)

    def test_duplicate_verb_fails(self):
        spinner = dict(self.spinner, verbs=self.spinner["verbs"][:-1] + ["Brewing"])
        self.assertIn(("content", "spinner.verbs", "Brewing"), triples(self.check(spinner=spinner)))

    def test_missing_required_verb_fails(self):
        verbs = [v for v in self.spinner["verbs"] if v != "Scrying the query plan"]
        spinner = dict(self.spinner, verbs=verbs)
        self.assertIn(("content", "spinner.verbs", "Scrying the query plan"), triples(self.check(spinner=spinner)))

    def test_tip_rules(self):
        tips = copy.deepcopy(self.spinner["tips"])
        tips = [t for t in tips if t["id"] != "keep-the-receipts"]
        tips.append({"id": "Bad ID", "text": "fine"})
        tips.append({"id": "too-long", "text": "x" * 121})
        tips.append({"id": "two-lines", "text": "one\ntwo"})
        tips.append({"id": "boring-code", "text": "Boring code is good code."})
        found = pairs(self.check(spinner=dict(self.spinner, tips=tips)))
        for item in ("spinner.tips.keep-the-receipts", "spinner.tips.Bad ID", "spinner.tips.too-long",
                     "spinner.tips.two-lines", "spinner.tips.boring-code"):
            self.assertIn(("content", item), found, item)

    def test_required_tip_text_must_match(self):
        tips = [dict(t, text="Keep receipts.") if t["id"] == "keep-the-receipts" else t for t in self.spinner["tips"]]
        self.assertIn(("content", "spinner.tips.keep-the-receipts"), pairs(self.check(spinner=dict(self.spinner, tips=tips))))

    def test_tip_count_bounds(self):
        few = dict(self.spinner, tips=self.spinner["tips"][:17])
        self.assertIn(("content", "spinner.tips", "17"), triples(self.check(spinner=few)))

    def test_output_style_frontmatter(self):
        no_keep = self.style.replace("keep-coding-instructions: true\n", "")
        self.assertIn(("content", "output-style.keep-coding-instructions"), pairs(self.check(style=no_keep)))
        renamed = self.style.replace("name: WitchyNibbles", "name: Witchy")
        self.assertIn(("content", "output-style.name"), pairs(self.check(style=renamed)))
        self.assertIn(("content", "output-style"), pairs(self.check(style="# no frontmatter\n")))

    def test_split_frontmatter(self):
        fields, body = content.split_frontmatter("---\nname: X\nkeep-coding-instructions: true\n---\nBody\n")
        self.assertEqual(fields, {"name": "X", "keep-coding-instructions": "true"})
        self.assertEqual(body, "Body\n")
        self.assertIsNone(content.split_frontmatter("no frontmatter"))


class ValidateAllTest(unittest.TestCase):
    def test_repository_passes(self):
        self.assertEqual(validate.validate_all(), [])

    def test_unreadable_content_is_a_failure(self):
        with tempfile.TemporaryDirectory() as empty:
            failures = validate.validate_all(Path(empty))
        self.assertEqual({f.rule for f in failures}, {"content"})


class VariantValidateTest(unittest.TestCase):
    def test_every_variant_is_validated(self):
        midnight = palette.VARIANTS["midnight"]
        broken = palette.Variant("broken", "dark", midnight.background, midnight.foreground,
                                 dict(midnight.claude_overrides, claude="#111111"), midnight.wt_scheme,
                                 midnight.statusline)
        with mock.patch.dict(palette.VARIANTS, {"broken": broken}):
            failures = validate.validate_all()
        self.assertIn(("text-contrast", "claude.claude"), {(f.rule, f.item) for f in failures})


class SkyValidateTest(unittest.TestCase):
    def test_sky_colours_must_be_hex(self):
        with mock.patch.dict(palette.SKY, {"moon": "gold"}):
            failures = validate.validate_all()
        self.assertIn(("format", "sky.moon"), {(f.rule, f.item) for f in failures})

    def test_every_colour_the_renderer_reads_must_be_present(self):
        colours = {key: "#FFFFFF" for key in sky_render.COLOURS}
        sky_render.render(0, colours, (64, 36))  # these are exactly the keys the renderer indexes
        self.assertEqual(validate.validate_sky(colours), [])
        for key in sky_render.COLOURS:
            failures = validate.validate_sky({k: v for k, v in colours.items() if k != key})
            self.assertEqual([(f.rule, f.item) for f in failures], [("missing-token", f"sky.{key}")])

    def test_validate_all_reports_a_missing_sky_colour(self):
        sky = {key: value for key, value in palette.SKY.items() if key != "moon_rim"}
        variant = dataclasses.replace(palette.VARIANTS["midnight"], sky=sky)
        with mock.patch.dict(palette.VARIANTS, {"midnight": variant}):
            failures = validate.validate_all()
        self.assertIn(("missing-token", "sky.moon_rim"), {(f.rule, f.item) for f in failures})


if __name__ == "__main__":
    unittest.main()
