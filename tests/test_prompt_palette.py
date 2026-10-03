import unittest
from unittest import mock

from witchy import palette, validate

# `fish -c 'set -U | string match -r "^tide_\S+"'` on Tide 6.1.1 (2026-10-03), the version the spec targets.
TIDE_6_1_1_VARIABLES = frozenset("""
tide_aws_bg_color tide_aws_color tide_aws_icon tide_bun_bg_color tide_bun_color tide_bun_icon tide_character_color
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
# Tide 6.1.1's prompt items: its _tide_item_* functions, plus pwd and newline from _tide_2_line_prompt.
TIDE_6_1_1_ITEMS = frozenset("""
aws bun character cmd_duration context crystal direnv distrobox docker elixir gcloud git go java jobs kubectl
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

    def test_the_spec_variables_are_all_there(self):
        self.assertEqual(len(palette.TIDE), 32)
        self.assertEqual(palette.TIDE["tide_left_prompt_items"], ("moon", "pwd", "git", "newline", "character"))
        self.assertEqual(palette.TIDE["tide_right_prompt_items"], ("status", "cmd_duration", "time"))
        self.assertEqual(palette.TIDE["tide_cmd_duration_threshold"], "3000")

    def test_items_are_tide_items_or_the_moon(self):
        items = set(palette.TIDE["tide_left_prompt_items"]) | set(palette.TIDE["tide_right_prompt_items"])
        self.assertEqual(items - TIDE_6_1_1_ITEMS, {"moon"})

    def test_every_tide_colour_is_validated_for_contrast_or_exempt(self):
        checked = {name for pair in validate.TIDE_TEXT_PAIRS + validate.TIDE_SECONDARY_PAIRS for name in pair if name}
        colours = {key for key in palette.TIDE if "color" in key}
        self.assertEqual(colours - checked, {"tide_prompt_color_separator_same_color"})


class TideValidateTest(unittest.TestCase):
    def test_real_variables_pass(self):
        self.assertEqual(validate.validate_tide(palette.TIDE), [])

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

    def test_a_missing_variable_is_reported(self):
        tide = {key: value for key, value in palette.TIDE.items() if key != "tide_moon_color"}
        self.assertIn(("missing-token", "tide.tide_moon_color"), pairs(validate.validate_tide(tide)))

    def test_items_must_be_strings(self):
        found = pairs(validate.validate_tide(dict(palette.TIDE, tide_left_prompt_items=("moon", 3))))
        self.assertIn(("format", "tide.tide_left_prompt_items"), found)


class EzaValidateTest(unittest.TestCase):
    def test_real_colours_pass(self):
        self.assertEqual(validate.validate_eza(palette.EZA), [])

    def test_format_contrast_and_presence(self):
        found = pairs(validate.validate_eza(dict(palette.EZA, directory="B99AFF", date="#2A1F3D")))
        self.assertIn(("format", "eza.directory"), found)
        self.assertIn(("text-contrast", "eza.date"), found)
        eza = {key: value for key, value in palette.EZA.items() if key != "symlink"}
        self.assertIn(("missing-token", "eza.symlink"), pairs(validate.validate_eza(eza)))


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


if __name__ == "__main__":
    unittest.main()
