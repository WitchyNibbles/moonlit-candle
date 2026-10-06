import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

from tests.fakes import fake_tide
from witchy import build, fishprobe, palette, runner
from witchy.components import fish
from witchy.components.base import run_command
from witchy.context import Context

FISH = shutil.which("fish")
# fish's own folder and the system ones, not the user's whole PATH.
TOOL_DIRS = list(dict.fromkeys([str(Path(FISH).parent) if FISH else "/usr/bin", "/usr/bin", "/bin"]))
# What a user's Tide set-up looks like before witchy: a few colours of their own, one exported variable,
# a config.fish that prints something and sets a global that would hide a universal value.
BEFORE = """\
set -U tide_left_prompt_items os pwd git newline character
set -U tide_pwd_bg_color 3465A4
set -Ux tide_time_color 5F8787
set -U tide_cmd_duration_threshold 3000
"""
CONFIG = """\
echo "hello from config.fish"
set -g tide_pwd_bg_color 000000
"""


@unittest.skipUnless(FISH, "fish is not installed")
class RealFishRoundTripTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.config = self.root / "config" / "fish"
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config.parent), "PATH": ":".join(TOOL_DIRS)}
        fake_tide(self.config, self.env)
        # Tide's own cache of usable items, rebuilt when a shell starts (a stand-in with the same effect).
        (self.config / "functions" / "_tide_remove_unusable_items.fish").write_text(
            "function _tide_remove_unusable_items\n    set -U _tide_left_items $tide_left_prompt_items\nend\n",
            encoding="utf-8")
        self.fish(BEFORE)
        (self.config / "config.fish").write_text(CONFIG, encoding="utf-8")

    def fish(self, script):
        done = subprocess.run([FISH, "-c", script], capture_output=True, text=True, env=self.env, timeout=20)
        self.assertEqual(done.stderr, "")
        return done.stdout.replace("hello from config.fish\n", "", 1)

    def universal(self):
        """Every universal tide_ variable with its value, and the exported ones, as fish lists them."""
        listing = self.fish("set -U; echo exported:; set -U -x")
        return [line for line in listing.splitlines() if line.startswith(("tide_", "exported:"))]

    def ctx(self, stamp):
        self.out = io.StringIO()
        return Context(home=self.home, env=self.env, out=self.out, python=sys.executable, stamp=stamp,
                       dist=self.root / "dist", lock_path=self.root / "witchy.lock", only=("fish",))

    def test_install_recolours_tide_and_uninstall_gives_every_variable_back(self):
        before = self.universal()
        self.assertEqual(runner.install(self.ctx("20261003-120000")), 0, self.out.getvalue())
        self.assertEqual(self.fish("set -e -g tide_pwd_bg_color; printf '%s\\n' $tide_pwd_bg_color"), "B99AFF\n")
        self.assertEqual(self.fish("printf '%s\\n' $tide_left_prompt_items").split(),
                         list(palette.TIDE["tide_left_prompt_items"]))
        self.assertIn("tide_time_color A99AB9", self.fish("set -U -x"))
        self.assertEqual(self.fish("printf '%s\\n' $tide_moon_bg_color"), "1D1230\n")
        self.assertEqual(self.fish("printf '%s\\n' $tide_pwd_icon $fish_emoji_width"), "🧹\n2\n")
        self.assertEqual(self.fish("set -U --names | string match 'tide_*'").split(), sorted(build.tide()))
        self.fish("_tide_remove_unusable_items")  # a new shell starts and caches the moon item
        self.assertEqual(runner.uninstall(self.ctx("20261003-130000")), 0, self.out.getvalue())
        self.assertEqual(self.universal(), before)
        self.assertEqual(self.fish("printf '%s\\n' $_tide_left_items").split(), ["os", "pwd", "git", "newline",
                                                                                 "character"])
        self.assertFalse((self.home / ".claude" / "witchy").exists())
        self.assertEqual(sorted(path.name for path in (self.config / "functions").iterdir()),
                         ["_tide_remove_unusable_items.fish", "fish_prompt.fish", "tide.fish"])
        self.assertEqual(sorted(path.name for path in (self.config / "conf.d").iterdir()), [])

    def test_doctor_sees_globals_that_only_a_new_interactive_shell_sets(self):
        self.assertEqual(runner.install(self.ctx("20261003-120000")), 0, self.out.getvalue())
        (self.config / "conf.d").mkdir(exist_ok=True)
        (self.config / "conf.d" / "mine.fish").write_text(
            "status is-interactive; or exit\nset -g tide_time_color 5F8787\n", encoding="utf-8")
        ctx = self.ctx("20261003-130000")
        self.assertEqual(runner.doctor(ctx, [fish.FishComponent()]), 1)
        output = self.out.getvalue()
        self.assertIn(f"✓ fish              {len(build.tide()) + 1} prompt variables match", output)
        self.assertIn("✗ fish              tide_pwd_bg_color is overridden by a global in config.fish or conf.d", output)
        self.assertIn("✗ fish              tide_time_color is overridden by a global in config.fish or conf.d", output)
        self.assertNotIn("hello from config.fish", output)

    def test_doctor_accepts_the_caret_global_only_while_it_holds_todays_colour(self):
        self.assertEqual(runner.install(self.ctx("20261003-120000")), 0, self.out.getvalue())
        cache = self.home / ".cache" / "witchy"
        cache.mkdir(parents=True)
        (cache / "caret").write_text(f"{date.today().isoformat()} FFB86B samhain\n", encoding="utf-8")
        runner.doctor(self.ctx("20261003-130000"), [fish.FishComponent()])
        self.assertIn("· fish              caret: samhain FFB86B (today's cache)", self.out.getvalue())
        self.assertNotIn("tide_character_color is overridden", self.out.getvalue())
        with (self.config / "config.fish").open("a", encoding="utf-8") as config:
            config.write("set -g tide_character_color 123456\n")
        runner.doctor(self.ctx("20261003-140000"), [fish.FishComponent()])
        self.assertIn("✗ fish              tide_character_color is overridden by a global", self.out.getvalue())

    def test_snapshot_reads_values_with_spaces_and_empty_lists(self):
        self.fish("set -U tide_a 'two words' ''; set -U tide_b; set -Ux tide_c x; set -U _tide_private x")
        asked = ["tide_a", "tide_b", "tide_c", "tide_none"]
        found = fish.snapshot(self.ctx("20261003-120000"), asked)
        self.assertEqual({name: found[name] for name in asked},
                         {"tide_a": {"value": ["two words", ""], "exported": False},
                          "tide_b": {"value": [], "exported": False},
                          "tide_c": {"value": ["x"], "exported": True},
                          "tide_none": {"absent": True}})
        # Every other universal tide_ variable comes too, so install can erase it; Tide's private ones never do.
        self.assertEqual(set(found) - set(asked), {"tide_left_prompt_items", "tide_pwd_bg_color", "tide_time_color",
                                                   "tide_cmd_duration_threshold"})

    def test_the_set_script_sets_exports_and_erases(self):
        ctx = self.ctx("20261003-120000")
        done = run_command(ctx, fish.set_command([("tide_a", "set", ["a b", ""]), ("tide_c", "exported", ["x"]),
                                                    ("tide_pwd_bg_color", "erase", [])], "set three"))
        self.assertEqual(done.returncode, 0)
        found = fish.snapshot(ctx, ["tide_a", "tide_c", "tide_pwd_bg_color"])
        self.assertEqual({name: found[name] for name in ("tide_a", "tide_c", "tide_pwd_bg_color")},
                         {"tide_a": {"value": ["a b", ""], "exported": False},
                          "tide_c": {"value": ["x"], "exported": True},
                          "tide_pwd_bg_color": {"absent": True}})

    def test_the_set_script_stops_at_the_first_failure(self):
        ctx = self.ctx("20261003-120000")
        done = run_command(ctx, fish.set_command([("tide_a", "set", ["1"]), ("status", "set", ["read-only"]),
                                                    ("tide_b", "set", ["2"])], "set three"), check=False)
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(fishprobe.fields(done.stdout), ["tide_a"])
        self.assertEqual(fish.snapshot(ctx, ["tide_b"])["tide_b"], {"absent": True})


if __name__ == "__main__":
    unittest.main()
