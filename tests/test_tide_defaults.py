import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import build, content, palette

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "tide_defaults.py"
_spec = importlib.util.spec_from_file_location("tide_defaults", SCRIPT)
tide_defaults = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tide_defaults)

# A Tide 6.1.1 tree cut down to the lines the generator must understand.
TIDE_FISH = "function tide\n    if set -q _flag_version\n        echo 'tide, version 6.1.1'\n    end\nend\n"
SUB_CONFIGURE = "set -g _tide_color_gold D7AF00\nset -g _tide_color_green 5FD700\n\nfunction _tide_sub_configure\nend\n"
DETECT_OS = "function _tide_detect_os\n    set -lx defaultColor 080808 CED7CF\nend\n"
ICONS = ("tide_aws_icon \uf270 # Actual aws glyph is harder to see\n"
         "tide_os_icon $os_branding_icon\n"
         "tide_prompt_icon_connection ' '\n"
         "tide_status_icon \u2714\n")
RAINBOW = ("tide_character_color $_tide_color_green\n"
           "tide_context_color_root $_tide_color_gold\n"
           "tide_git_truncation_strategy\n"
           "tide_left_prompt_prefix ''\n"
           "tide_os_bg_color $os_branding_bg_color\n"
           "tide_pwd_bg_color 3465A4\n"
           "tide_pwd_markers .bzr .git build.zig\n"
           "tide_right_prompt_suffix 'it\\'s'\n")


class TreeTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.write("functions/tide.fish", TIDE_FISH)
        self.write("functions/_tide_sub_configure.fish", SUB_CONFIGURE)
        self.write("functions/_tide_detect_os.fish", DETECT_OS)
        self.write("functions/tide/configure/icons.fish", ICONS)
        self.write("functions/tide/configure/configs/rainbow.fish", RAINBOW)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def release(self):
        """Pins that make this tree count as the release, as it is now."""
        return {source: hashlib.sha256((self.root / source).read_bytes()).hexdigest()
                for source in tide_defaults.SOURCES}

    def defaults(self):
        return tide_defaults.defaults(self.root, self.release())


class GeneratorTest(TreeTestCase):
    def test_reads_the_rainbow_preset_with_tides_own_colours_and_generic_os_branding(self):
        self.assertEqual(self.defaults(), {
            "tide_aws_icon": ["\uf270"],
            "tide_character_color": ["5FD700"],
            "tide_context_color_root": ["D7AF00"],
            "tide_git_truncation_strategy": [],
            "tide_left_prompt_prefix": [""],
            "tide_os_bg_color": ["CED7CF"],
            "tide_os_icon": ["\uf17c"],
            "tide_prompt_icon_connection": [" "],
            "tide_pwd_bg_color": ["3465A4"],
            "tide_pwd_markers": [".bzr", ".git", "build.zig"],
            "tide_right_prompt_suffix": ["it's"],
            "tide_status_icon": ["\u2714"],
        })

    def test_refuses_a_tree_that_is_not_tide_6_1_1(self):
        self.write("functions/tide.fish", TIDE_FISH.replace("6.1.1", "6.0.0"))
        with self.assertRaisesRegex(ValueError, r"is not Tide 6\.1\.1"):
            self.defaults()

    def test_refuses_a_development_build_that_also_says_6_1_1(self):
        with self.assertRaisesRegex(ValueError, r"icons\.fish is not the one in the Tide 6\.1\.1 release "
                                                r"\(a development build of Tide\?\)"):
            tide_defaults.defaults(self.root)

    def test_the_release_pins_are_the_two_files_read(self):
        self.assertEqual(set(tide_defaults.RELEASE), set(tide_defaults.SOURCES))

    def test_refuses_os_branding_it_does_not_know(self):
        self.write("functions/_tide_detect_os.fish", DETECT_OS.replace("CED7CF", "FFFFFF"))
        with self.assertRaisesRegex(ValueError, r"generic Linux branding"):
            self.defaults()

    def test_refuses_fish_syntax_it_cannot_read_safely(self):
        for line in ('tide_a "double"\n', "tide_a (command)\n", "tide_a x$y\n", "tide_a $unknown\n",
                     "tide_a 'open\n", "tide_a back\\slash\n"):
            with self.subTest(line=line):
                self.write("functions/tide/configure/configs/rainbow.fish", RAINBOW + line)
                with self.assertRaises(ValueError):
                    self.defaults()

    def test_refuses_a_name_set_twice(self):
        self.write("functions/tide/configure/configs/rainbow.fish", RAINBOW + "tide_status_icon x\n")
        with self.assertRaisesRegex(ValueError, r"tide_status_icon is set twice"):
            self.defaults()

    def test_main_writes_sorted_ascii_json_and_reports_errors(self):
        out = self.root / "out.json"
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr), \
                mock.patch.dict(tide_defaults.RELEASE, self.release()):
            self.assertEqual(tide_defaults.main([str(self.root), str(out)]), 0)
            self.assertEqual(tide_defaults.main([str(self.root / "missing"), str(out)]), 1)
        text = out.read_text(encoding="ascii")
        self.assertEqual(json.loads(text), self.defaults())
        self.assertEqual(list(json.loads(text)), sorted(json.loads(text)))
        self.assertTrue(text.endswith("}\n"))
        self.assertIn(f"wrote 12 Tide variables to {out}", stdout.getvalue())
        self.assertIn("tide_defaults: ", stderr.getvalue())


class CheckedInDefaultsTest(unittest.TestCase):
    def test_holds_every_tide_6_1_1_variable_once(self):
        from tests.test_prompt_palette import TIDE_6_1_1_VARIABLES
        raw = json.loads((content.CONTENT_DIR / content.TIDE_DEFAULTS).read_text(encoding="utf-8"))
        self.assertEqual(set(raw), TIDE_6_1_1_VARIABLES)
        self.assertEqual(len(raw), 156)

    def test_holds_tides_rainbow_values(self):
        defaults = content.load_tide_defaults()
        self.assertEqual(defaults["tide_pwd_bg_color"], "3465A4")
        self.assertEqual(defaults["tide_character_color"], "5FD700")
        self.assertEqual(defaults["tide_left_prompt_separator_diff_color"], "\ue0b0")
        self.assertEqual(defaults["tide_time_format"], "%T")
        self.assertEqual(defaults["tide_git_truncation_strategy"], ())
        self.assertEqual(defaults["tide_left_prompt_items"], ("pwd", "git", "newline"))
        self.assertEqual(defaults["tide_os_icon"], "\uf17c")

    def test_a_file_that_is_not_names_and_lists_of_strings_is_refused(self):
        for text in ("[]", '{"tide_a": "x"}', '{"tide_a": [1]}', '{"": ["x"]}', "not json"):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / content.TIDE_DEFAULTS).write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    content.load_tide_defaults(Path(tmp))


class MergeTest(unittest.TestCase):
    def test_every_default_plus_witchys_own_items(self):
        defaults = content.load_tide_defaults()
        merged = build.tide()
        self.assertEqual(set(merged), set(defaults) | set(palette.TIDE_OWN))
        self.assertEqual(len(merged), 158)

    def test_every_override_names_a_tide_variable_or_witchys_own(self):
        defaults = content.load_tide_defaults()
        self.assertEqual(set(palette.TIDE) - set(defaults) - set(palette.TIDE_OWN), set())

    def test_overrides_win_and_the_rest_keeps_tides_default(self):
        merged = build.tide()
        self.assertEqual(merged["tide_pwd_bg_color"], palette.TIDE["tide_pwd_bg_color"])
        self.assertEqual(merged["tide_pwd_markers"], content.load_tide_defaults()["tide_pwd_markers"])
        self.assertEqual(merged["tide_prompt_min_cols"], "34")

    def test_the_variant_supplies_the_overrides(self):
        midnight = palette.VARIANTS["midnight"]
        dawn = palette.Variant(**{**midnight.__dict__, "name": "dawn",
                                  "tide": dict(midnight.tide, tide_pwd_bg_color="D0B8FF")})
        with mock.patch.dict(palette.VARIANTS, {"dawn": dawn}):
            self.assertEqual(build.tide("dawn")["tide_pwd_bg_color"], "D0B8FF")
        self.assertEqual(build.tide(), build.tide(palette.DEFAULT_VARIANT))

    def test_the_path_constant_points_at_the_checked_in_file(self):
        self.assertEqual(build.TIDE_DEFAULTS, content.CONTENT_DIR / "tide-6.1.1-defaults.json")
        self.assertTrue(build.TIDE_DEFAULTS.is_file())


if __name__ == "__main__":
    unittest.main()
