import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from witchy import palette, runner
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
set -U tide_pwd_bg_color FFB7C5
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
        (self.config / "functions").mkdir(parents=True)
        (self.config / "functions" / "tide.fish").write_text("function tide\nend\n", encoding="utf-8")
        # Tide's own cache of usable items, rebuilt when a shell starts (a stand-in with the same effect).
        (self.config / "functions" / "_tide_remove_unusable_items.fish").write_text(
            "function _tide_remove_unusable_items\n    set -U _tide_left_items $tide_left_prompt_items\nend\n",
            encoding="utf-8")
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config.parent), "PATH": ":".join(TOOL_DIRS)}
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
        self.fish("_tide_remove_unusable_items")  # a new shell starts and caches the moon item
        self.assertEqual(runner.uninstall(self.ctx("20261003-130000")), 0, self.out.getvalue())
        self.assertEqual(self.universal(), before)
        self.assertEqual(self.fish("printf '%s\\n' $_tide_left_items").split(), ["os", "pwd", "git", "newline",
                                                                                 "character"])
        self.assertFalse((self.home / ".claude" / "witchy").exists())
        self.assertEqual(sorted(path.name for path in (self.config / "functions").iterdir()),
                         ["_tide_remove_unusable_items.fish", "tide.fish"])
        self.assertEqual(sorted(path.name for path in (self.config / "conf.d").iterdir()), [])

    def test_snapshot_reads_values_with_spaces_and_empty_lists(self):
        self.fish("set -U tide_a 'two words' ''; set -U tide_b; set -Ux tide_c x")
        tide, found = fish.snapshot(self.ctx("20261003-120000"), ["tide_a", "tide_b", "tide_c", "tide_none"])
        self.assertTrue(tide)
        self.assertEqual(found, {"tide_a": {"value": ["two words", ""], "exported": False},
                                 "tide_b": {"value": [], "exported": False},
                                 "tide_c": {"value": ["x"], "exported": True},
                                 "tide_none": {"absent": True}})

    def test_the_set_script_sets_exports_and_erases(self):
        ctx = self.ctx("20261003-120000")
        done = run_command(ctx, fish.set_command([("tide_a", "set", ["a b", ""]), ("tide_c", "exported", ["x"]),
                                                    ("tide_pwd_bg_color", "erase", [])], "set three"))
        self.assertEqual(done.returncode, 0)
        _, found = fish.snapshot(ctx, ["tide_a", "tide_c", "tide_pwd_bg_color"])
        self.assertEqual(found, {"tide_a": {"value": ["a b", ""], "exported": False},
                                 "tide_c": {"value": ["x"], "exported": True},
                                 "tide_pwd_bg_color": {"absent": True}})

    def test_the_set_script_stops_at_the_first_failure(self):
        ctx = self.ctx("20261003-120000")
        done = run_command(ctx, fish.set_command([("tide_a", "set", ["1"]), ("status", "set", ["read-only"]),
                                                    ("tide_b", "set", ["2"])], "set three"), check=False)
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(fish._fields(done.stdout), ["tide_a"])
        self.assertEqual(fish.snapshot(ctx, ["tide_b"])[1], {"tide_b": {"absent": True}})


if __name__ == "__main__":
    unittest.main()
