import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import build, content, palette, validate
from witchy.ritual import layout

# The 156 names of Tide's v6.1.1 release tag (its icons.fish and configs/rainbow.fish), the version the spec
# targets. Tide's development branch, which also calls itself 6.1.1, adds tide_bun_bg_color, _color and _icon.
TIDE_6_1_1_VARIABLES = frozenset("""
tide_aws_bg_color tide_aws_color tide_aws_icon tide_character_color
tide_character_color_failure tide_character_icon tide_character_vi_icon_default tide_character_vi_icon_replace
tide_character_vi_icon_visual tide_cmd_duration_bg_color tide_cmd_duration_color tide_cmd_duration_decimals
tide_cmd_duration_icon tide_cmd_duration_threshold tide_context_always_display tide_context_bg_color
tide_context_color_default tide_context_color_root tide_context_color_ssh tide_context_hostname_parts
tide_crystal_bg_color tide_crystal_color tide_crystal_icon tide_direnv_bg_color tide_direnv_bg_color_denied
tide_direnv_color tide_direnv_color_denied tide_direnv_icon tide_distrobox_bg_color tide_distrobox_color
tide_distrobox_icon tide_docker_bg_color tide_docker_color tide_docker_default_contexts tide_docker_icon
tide_elixir_bg_color tide_elixir_color tide_elixir_icon tide_gcloud_bg_color tide_gcloud_color tide_gcloud_icon
tide_git_bg_color tide_git_bg_color_unstable tide_git_bg_color_urgent tide_git_color_branch tide_git_color_conflicted
tide_git_color_dirty tide_git_color_operation tide_git_color_staged tide_git_color_stash tide_git_color_untracked
tide_git_color_upstream tide_git_icon tide_git_truncation_length tide_git_truncation_strategy tide_go_bg_color
tide_go_color tide_go_icon tide_java_bg_color tide_java_color tide_java_icon tide_jobs_bg_color tide_jobs_color
tide_jobs_icon tide_jobs_number_threshold tide_kubectl_bg_color tide_kubectl_color tide_kubectl_icon
tide_left_prompt_frame_enabled tide_left_prompt_items tide_left_prompt_prefix tide_left_prompt_separator_diff_color
tide_left_prompt_separator_same_color tide_left_prompt_suffix tide_nix_shell_bg_color tide_nix_shell_color
tide_nix_shell_icon tide_node_bg_color tide_node_color tide_node_icon tide_os_bg_color tide_os_color tide_os_icon
tide_php_bg_color tide_php_color tide_php_icon tide_private_mode_bg_color tide_private_mode_color
tide_private_mode_icon tide_prompt_add_newline_before tide_prompt_color_frame_and_connection
tide_prompt_color_separator_same_color tide_prompt_icon_connection tide_prompt_min_cols tide_prompt_pad_items
tide_prompt_transient_enabled tide_pulumi_bg_color tide_pulumi_color tide_pulumi_icon tide_pwd_bg_color
tide_pwd_color_anchors tide_pwd_color_dirs tide_pwd_color_truncated_dirs tide_pwd_icon tide_pwd_icon_home
tide_pwd_icon_unwritable tide_pwd_markers tide_python_bg_color tide_python_color tide_python_icon
tide_right_prompt_frame_enabled tide_right_prompt_items tide_right_prompt_prefix
tide_right_prompt_separator_diff_color tide_right_prompt_separator_same_color tide_right_prompt_suffix
tide_ruby_bg_color tide_ruby_color tide_ruby_icon tide_rustc_bg_color tide_rustc_color tide_rustc_icon
tide_shlvl_bg_color tide_shlvl_color tide_shlvl_icon tide_shlvl_threshold tide_status_bg_color
tide_status_bg_color_failure tide_status_color tide_status_color_failure tide_status_icon tide_status_icon_failure
tide_terraform_bg_color tide_terraform_color tide_terraform_icon tide_time_bg_color tide_time_color tide_time_format
tide_toolbox_bg_color tide_toolbox_color tide_toolbox_icon tide_vi_mode_bg_color_default tide_vi_mode_bg_color_insert
tide_vi_mode_bg_color_replace tide_vi_mode_bg_color_visual tide_vi_mode_color_default tide_vi_mode_color_insert
tide_vi_mode_color_replace tide_vi_mode_color_visual tide_vi_mode_icon_default tide_vi_mode_icon_insert
tide_vi_mode_icon_replace tide_vi_mode_icon_visual tide_zig_bg_color tide_zig_color tide_zig_icon
""".split())
# The release's prompt items: its _tide_item_* functions, plus pwd and newline from _tide_2_line_prompt.
TIDE_6_1_1_ITEMS = frozenset("""
aws character cmd_duration context crystal direnv distrobox docker elixir gcloud git go java jobs kubectl
nix_shell node os php private_mode pulumi python ruby rustc shlvl status terraform time toolbox vi_mode zig pwd newline
""".split())
# The moon item is witchy's own; _tide_print_item reads tide_<item>_bg_color and tide_<item>_color.
MOON_VARIABLES = {"tide_moon_bg_color", "tide_moon_color"}


def pairs(failures):
    return {(f.rule, f.item) for f in failures}


class TideNamesTest(unittest.TestCase):
    def test_every_variable_exists_in_tide_6_1_1(self):
        self.assertEqual(set(palette.TIDE) - MOON_VARIABLES - TIDE_6_1_1_VARIABLES, set())
        self.assertTrue(MOON_VARIABLES <= set(palette.TIDE))

    def test_items_are_tide_items_or_the_moon(self):
        items = set(palette.TIDE["tide_left_prompt_items"]) | set(palette.TIDE["tide_right_prompt_items"])
        self.assertEqual(items - TIDE_6_1_1_ITEMS, {"moon"})

    def test_every_tide_colour_is_validated_for_contrast_or_exempt(self):
        checked = {name for pair in validate.TIDE_TEXT_PAIRS + validate.TIDE_ITEM_PAIRS + validate.TIDE_SECONDARY_PAIRS
                   for name in pair if name}
        colours = {key for key in build.tide() if validate.is_tide_colour(key)}
        # It sits between segments that share a background, so no single background exists to test it on.
        self.assertEqual(colours - checked, {"tide_prompt_color_separator_same_color"})

    def test_colour_keys_are_the_ones_with_a_colour_word(self):
        for key in ("tide_pwd_bg_color", "tide_git_color_branch", "tide_context_color_default",
                    "tide_prompt_color_separator_same_color"):
            self.assertTrue(validate.is_tide_colour(key), key)
        for key in ("tide_left_prompt_items", "tide_cmd_duration_threshold", "tide_colorful_icon", "tide_pwd_decolor"):
            self.assertFalse(validate.is_tide_colour(key), key)

    def test_the_separator_glyphs_are_not_colours(self):
        # Tide names them with "color", but they hold the glyph drawn between two segments.
        for key in ("tide_left_prompt_separator_diff_color", "tide_left_prompt_separator_same_color",
                    "tide_right_prompt_separator_diff_color", "tide_right_prompt_separator_same_color"):
            self.assertFalse(validate.is_tide_colour(key), key)
        self.assertEqual(validate.validate_tide(dict(palette.TIDE, tide_left_prompt_separator_diff_color="\ue0bc")),
                         [])


# The unused items of spec 6.4 and their icons.
UNUSED_ICONS = {
    "aws": "🏺", "crystal": "💠", "direnv": "🍃", "distrobox": "📦", "docker": "🐳", "elixir": "💧",
    "gcloud": "⛅", "go": "🐹", "java": "☕", "kubectl": "🎡", "nix_shell": "🧊", "node": "🍄", "os": "🐧",
    "php": "🐘", "private_mode": "🎭", "pulumi": "🧬", "python": "🐍", "ruby": "💎", "rustc": "🦀", "shlvl": "🌀",
    "terraform": "🧱", "toolbox": "🧰", "zig": "⚡",
}


class TideLookTest(unittest.TestCase):
    """The prompt the spec draws (spec 6.2-6.4)."""

    def test_two_framed_lines_with_slanted_caps(self):
        expected = {
            "tide_left_prompt_items": ("moon", "pwd", "git", "newline", "character"),
            "tide_right_prompt_items": ("status", "cmd_duration", "jobs", "time"),
            "tide_left_prompt_prefix": "\ue0ba", "tide_left_prompt_suffix": "\ue0bc",
            "tide_right_prompt_prefix": "\ue0ba", "tide_right_prompt_suffix": "\ue0bc",
            "tide_left_prompt_separator_diff_color": "\ue0bc", "tide_right_prompt_separator_diff_color": "\ue0ba",
            "tide_left_prompt_frame_enabled": "true", "tide_right_prompt_frame_enabled": "true",
            "tide_prompt_transient_enabled": "true", "tide_prompt_add_newline_before": "true",
            "tide_prompt_icon_connection": "·", "tide_prompt_color_frame_and_connection": "6E5A80",
            "tide_cmd_duration_threshold": "3000",
        }
        self.assertEqual({name: palette.TIDE[name] for name in expected}, expected)

    def test_same_colour_separators_keep_tides_rainbow_default(self):
        defaults = content.load_tide_defaults()
        for name in ("tide_left_prompt_separator_same_color", "tide_right_prompt_separator_same_color"):
            self.assertNotIn(name, palette.TIDE)
            self.assertEqual(build.tide()[name], defaults[name])

    def test_the_glyph_map(self):
        expected = {
            "tide_pwd_icon": "🧹", "tide_pwd_icon_home": "🔮", "tide_pwd_icon_unwritable": "🪦", "tide_git_icon": "🌿",
            "tide_status_icon": "🧪", "tide_status_icon_failure": "💀", "tide_cmd_duration_icon": "🔥",
            "tide_jobs_icon": "🐈", "tide_time_format": "%H:%M 🦉", "tide_character_icon": "❯",
            "tide_character_vi_icon_default": "❮", "tide_character_vi_icon_replace": "▶",
            "tide_character_vi_icon_visual": "V",
        }
        self.assertEqual({name: palette.TIDE[name] for name in expected}, expected)

    def test_prompt_icons_come_from_the_shared_table(self):
        uses = {"tide_pwd_icon": "cwd", "tide_pwd_icon_home": "home", "tide_pwd_icon_unwritable": "unwritable",
                "tide_git_icon": "branch", "tide_status_icon": "ok", "tide_status_icon_failure": "fail",
                "tide_cmd_duration_icon": "duration", "tide_jobs_icon": "jobs", "tide_character_icon": "caret"}
        for name, key in uses.items():
            self.assertEqual(palette.TIDE[name], palette.GLYPHS[key], name)
        self.assertEqual(palette.TIDE["tide_time_format"], "%H:%M " + palette.GLYPHS["time"])

    def test_the_caret_is_candle_gold_and_rose_red_on_failure(self):
        self.assertEqual((palette.TIDE["tide_character_color"], palette.TIDE["tide_character_color_failure"]),
                         ("FFD477", "FF6B9F"))

    def test_jobs_and_unused_items_wear_witchy_icons_on_the_muted_pair(self):
        self.assertEqual((palette.TIDE["tide_jobs_bg_color"], palette.TIDE["tide_jobs_color"]), ("1D1230", "A99AB9"))
        for item, icon in UNUSED_ICONS.items():
            with self.subTest(item=item):
                self.assertEqual((palette.TIDE[f"tide_{item}_icon"], palette.TIDE[f"tide_{item}_bg_color"],
                                  palette.TIDE[f"tide_{item}_color"]), (icon, "1D1230", "A99AB9"))

    def test_context_and_vi_mode_keep_tides_text_in_palette_colours(self):
        self.assertNotIn("tide_vi_mode_icon_default", palette.TIDE)
        expected = {
            "tide_context_bg_color": "1D1230", "tide_context_color_default": "A99AB9",
            "tide_context_color_root": "FF6B9F", "tide_context_color_ssh": "FF6B9F",
            "tide_direnv_bg_color_denied": "1D1230", "tide_direnv_color_denied": "FF6B9F",
            **{f"tide_vi_mode_bg_color_{mode}": "1D1230" for mode in ("default", "insert", "replace", "visual")},
            **{f"tide_vi_mode_color_{mode}": "A99AB9" for mode in ("default", "insert", "replace", "visual")},
        }
        self.assertEqual({name: palette.TIDE[name] for name in expected}, expected)

    def test_every_colour_tide_defines_is_a_palette_colour(self):
        colours = {name for name in content.load_tide_defaults() if validate.is_tide_colour(name)}
        self.assertEqual(colours - set(palette.TIDE), set())


class SharedTablesTest(unittest.TestCase):
    def test_the_glyph_table(self):
        self.assertEqual(palette.GLYPHS, {
            "candle": "\U0001F56F\uFE0F", "scroll": "📜", "branch": "🌿", "dirty": "✦", "separator": "⋆",
            "cwd": "🧹", "home": "🔮", "unwritable": "🪦", "ok": "🧪", "fail": "💀", "duration": "🔥", "jobs": "🐈",
            "time": "🦉", "caret": "❯",
        })

    def test_fish_draws_emoji_two_cells_wide(self):
        self.assertEqual(palette.FISH, {"fish_emoji_width": "2"})


class TideValidateTest(unittest.TestCase):
    def test_real_variables_pass(self):
        self.assertEqual(validate.validate_tide(palette.TIDE), [])

    def test_a_name_that_only_contains_color_is_not_a_colour(self):
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_colorful_icon="x")))
        self.assertEqual(found, {("unknown-variable", "tide.tide_colorful_icon")})

    def test_the_exempt_separator_colour_is_still_format_checked(self):
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_prompt_color_separator_same_color="grey")))
        self.assertIn(("format", "tide.tide_prompt_color_separator_same_color"), found)

    def test_colours_need_six_hex_digits_without_a_hash(self):
        for bad in ("#B99AFF", "b99aff", "B99AF"):
            found = pairs(validate.validate_tide(dict(palette.TIDE, tide_pwd_bg_color=bad)))
            self.assertIn(("format", "tide.tide_pwd_bg_color"), found, bad)

    def test_segment_text_must_read_on_its_background(self):
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_time_color="2A1F3D")))
        self.assertIn(("text-contrast", "tide.tide_time_color on tide_time_bg_color"), found)

    def test_git_text_must_read_on_every_git_background(self):
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_git_bg_color_urgent="7A1F45")))
        self.assertIn(("text-contrast", "tide.tide_git_color_branch on tide_git_bg_color_urgent"), found)

    def test_the_character_reads_on_the_terminal_background(self):
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_character_color="2A1F3D")))
        self.assertIn(("text-contrast", "tide.tide_character_color on background"), found)

    def test_truncated_dirs_and_frame_need_3_to_1(self):
        lenient = dict(palette.TIDE, tide_pwd_color_truncated_dirs="5A4470")  # 3.66:1 on B99AFF
        self.assertEqual(validate.validate_tide(lenient), [])
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_prompt_color_frame_and_connection="3A2E47")))
        self.assertIn(("secondary-contrast", "tide.tide_prompt_color_frame_and_connection on background"), found)

    def test_unused_items_and_jobs_read_on_their_background(self):
        dark = "2A1F3D"
        tide = dict(palette.TIDE, tide_aws_color=dark, tide_jobs_color=dark, tide_direnv_color_denied=dark,
                    tide_context_color_root=dark, tide_vi_mode_color_insert=dark)
        self.assertLessEqual({("text-contrast", "tide.tide_aws_color on tide_aws_bg_color"),
                              ("text-contrast", "tide.tide_jobs_color on tide_jobs_bg_color"),
                              ("text-contrast", "tide.tide_direnv_color_denied on tide_direnv_bg_color_denied"),
                              ("text-contrast", "tide.tide_context_color_root on tide_context_bg_color"),
                              ("text-contrast", "tide.tide_vi_mode_color_insert on tide_vi_mode_bg_color_insert")},
                             pairs(validate.validate_tide(tide)))

    def test_a_missing_variable_is_reported(self):
        tide = {key: value for key, value in palette.TIDE.items() if key != "tide_moon_color"}
        self.assertIn(("missing-token", "tide.tide_moon_color"), pairs(validate.validate_tide(tide)))

    def test_items_must_be_strings(self):
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_left_prompt_items=("moon", 3))))
        self.assertIn(("format", "tide.tide_left_prompt_items"), found)


class EzaDerivedTest(unittest.TestCase):
    def test_git_colours_are_tides_git_colours(self):
        tide = palette.TIDE
        self.assertEqual(palette.EZA["git_new"], "#" + tide["tide_git_bg_color"])
        for role in ("git_modified", "git_renamed", "git_typechange"):
            self.assertEqual(palette.EZA[role], "#" + tide["tide_git_bg_color_unstable"])
        self.assertEqual(palette.EZA["git_deleted"], "#" + tide["tide_git_bg_color_urgent"])

    def test_the_rendered_string_is_unchanged(self):
        self.assertEqual(build.eza_colors(palette.EZA),
                         "di=38;2;185;154;255:ex=38;2;116;232;184:ln=38;2;119;217;255:sn=38;2;169;154;185"
                         ":sb=38;2;169;154;185:da=38;2;169;154;185:ga=38;2;255;212;119:gm=38;2;255;184;107"
                         ":gv=38;2;255;184;107:gt=38;2;255;184;107:gd=38;2;255;107;159")


class EzaValidateTest(unittest.TestCase):
    def test_real_colours_pass(self):
        self.assertEqual(validate.validate_eza(palette.EZA), [])

    def test_format_contrast_and_presence(self):
        found = pairs(validate.validate_eza(dict(palette.EZA, directory="B99AFF", date="#2A1F3D")))
        self.assertIn(("format", "eza.directory"), found)
        self.assertIn(("text-contrast", "eza.date"), found)
        eza = {key: value for key, value in palette.EZA.items() if key != "symlink"}
        self.assertIn(("missing-token", "eza.symlink"), pairs(validate.validate_eza(eza)))


class PromptGlyphRuleTest(unittest.TestCase):
    """Spec 11.1: a prompt icon is at most one emoji, one code point, no selector, joiner or skin tone."""

    def test_a_variation_selector_a_joiner_or_a_skin_tone_fails(self):
        for bad in ("\U0001F56F\uFE0F", "\U0001F9D9\u200D\u2640", "\U0001F44D\U0001F3FD"):
            with self.subTest(bad=bad):
                found = pairs(validate.validate_tide(dict(palette.TIDE, tide_pwd_icon=bad)))
                self.assertIn(("prompt-glyph", "tide.tide_pwd_icon"), found)

    def test_two_emoji_fail_and_text_glyphs_pass(self):
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_time_format="%H:%M 🦉🦉")))
        self.assertIn(("prompt-glyph", "tide.tide_time_format"), found)
        fine = dict(palette.TIDE, tide_character_icon="❯", tide_prompt_icon_connection="·", tide_pwd_icon="\uf07c")
        self.assertEqual(validate.validate_tide(fine), [])

    def test_tides_own_icons_are_checked_too(self):
        defaults = dict(content.load_tide_defaults(), tide_vi_mode_icon_insert="🐍🐍")
        found = pairs(validate.validate_tide(palette.TIDE, defaults=defaults))
        self.assertIn(("prompt-glyph", "tide.tide_vi_mode_icon_insert"), found)


class CompletenessRuleTest(unittest.TestCase):
    """Spec 11.2: every override names a Tide 6.1.1 variable or one of witchy's own."""

    def test_a_typo_is_an_unknown_variable(self):
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_pwd_bg_colour="B99AFF")))
        self.assertIn(("unknown-variable", "tide.tide_pwd_bg_colour"), found)

    def test_the_moon_items_variables_are_witchys_own(self):
        self.assertEqual(validate.validate_tide({**palette.TIDE, "tide_moon_color": "FFD477"}), [])


class PastelRuleTest(unittest.TestCase):
    """Spec 11.3: no value of the old pastel prompt comes back."""

    def test_the_list_holds_the_recorded_values(self):
        self.assertLessEqual({"FFB7C5", "F8A4C9", "FF6EC7", "FBAED2", "F5C6E0", "FFC8DD",
                              "🎀", "🏰", "🌷", "💖", "💔", "✨", "🍰", "🌸"}, validate.PASTEL)

    def test_no_witchy_glyph_is_on_the_list(self):
        used = set("".join(palette.GLYPHS.values())) | set("".join(palette.UNUSED_ICONS.values()))
        self.assertEqual(used & validate.PASTEL, set())

    def test_a_pastel_colour_or_icon_in_the_prompt_fails(self):
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_pwd_bg_color="FFB7C5", tide_git_icon="🌷",
                                                  tide_time_format="%H:%M 🍰")))
        self.assertLessEqual({("pastel", "tide.tide_pwd_bg_color"), ("pastel", "tide.tide_git_icon"),
                              ("pastel", "tide.tide_time_format")}, found)

    def test_a_pastel_tide_default_fails(self):
        defaults = dict(content.load_tide_defaults(), tide_vi_mode_icon_insert="🎀")
        found = pairs(validate.validate_tide(palette.TIDE, defaults=defaults))
        self.assertIn(("pastel", "tide.tide_vi_mode_icon_insert"), found)

    def test_a_pastel_terminal_colour_fails(self):
        found = pairs(validate.validate_palette(scheme=dict(palette.WT_SCHEME, brightPurple="#FBAED2")))
        self.assertIn(("pastel", "wt.brightPurple"), found)


class WidthRuleTest(unittest.TestCase):
    """Spec 11.5: the greeting measures every emoji of the glyph table two cells wide."""

    def test_the_real_table_passes(self):
        self.assertEqual(validate.validate_glyphs(palette.GLYPHS), [])

    def test_an_emoji_unicode_calls_narrow_must_be_in_wide(self):
        with mock.patch.object(layout, "WIDE", frozenset()):
            found = pairs(validate.validate_glyphs(palette.GLYPHS))
        # 🕯 is narrow in Unicode; every other emoji of the table is East Asian Wide.
        self.assertEqual(found, {("width", "glyphs.candle")})

    def test_text_glyphs_are_not_emoji(self):
        self.assertEqual(validate.validate_glyphs({"dirty": "✦", "caret": "❯", "separator": "⋆"}), [])


class VariantPromptTest(unittest.TestCase):
    def test_validate_all_checks_every_variant_prompt_and_eza(self):
        midnight = palette.VARIANTS["midnight"]
        broken = palette.Variant(**{**midnight.__dict__, "name": "broken",
                                    "tide": dict(midnight.tide, tide_moon_color="1D1230"),
                                    "eza": dict(midnight.eza, size="#1D1230")})
        with mock.patch.dict(palette.VARIANTS, {"broken": broken}):
            found = pairs(validate.validate_all())
        self.assertIn(("text-contrast", "tide.tide_moon_color on tide_moon_bg_color"), found)
        self.assertIn(("text-contrast", "eza.size"), found)

    def test_validate_all_checks_the_merged_prompt_and_the_glyph_table(self):
        midnight = palette.VARIANTS["midnight"]
        broken = palette.Variant(**{**midnight.__dict__, "name": "broken",
                                    "tide": dict(midnight.tide, tide_pwd_bg_colour="B99AFF")})
        with mock.patch.dict(palette.VARIANTS, {"broken": broken}), mock.patch.object(layout, "WIDE", frozenset()):
            found = pairs(validate.validate_all())
        self.assertIn(("unknown-variable", "tide.tide_pwd_bg_colour"), found)
        self.assertIn(("width", "glyphs.candle"), found)

    def test_validate_all_reports_defaults_it_cannot_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in (content.SPINNER, content.OUTPUT_STYLE, content.RITUAL):
                (Path(tmp) / name).write_bytes((content.CONTENT_DIR / name).read_bytes())
            failures = validate.validate_all(Path(tmp))
        self.assertEqual([(f.rule, f.item) for f in failures],
                         [("content", str(Path(tmp) / content.TIDE_DEFAULTS))])


if __name__ == "__main__":
    unittest.main()
