import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.fakes import fake_fish
from witchy import build, components, palette, runner
from witchy.components import fish
from witchy.context import Context

# The prompt as Tide's own "lean" setup and the user left it: a pink pwd, an exported variable, no moon.
USER_TIDE = {
    "tide_left_prompt_items": {"value": ["os", "pwd", "git", "newline", "character"], "exported": False},
    "tide_pwd_bg_color": {"value": ["FFB7C5"], "exported": False},
    "tide_time_color": {"value": ["5F8787"], "exported": True},
    "tide_cmd_duration_threshold": {"value": ["3000"], "exported": False},
}


class FishTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.variables = json.loads(json.dumps(USER_TIDE))
        self.calls = []

    def ctx(self, run=None, dry_run=False, env=None, stamp="20261003-120000"):
        self.out = io.StringIO()
        return Context(home=self.home, env={"PATH": "/nowhere"} if env is None else env, out=self.out,
                       dry_run=dry_run, python="/usr/bin/python3", stamp=stamp, dist=self.root / "dist",
                       lock_path=self.root / "witchy.lock", only=("fish",),
                       run=run or fake_fish(self.variables, calls=self.calls))

    def state(self):
        return json.loads((self.home / ".claude" / "witchy" / "state.json").read_text(encoding="utf-8"))

    def entry(self):
        return self.state()["components"]["fish"]

    def files(self):
        config = self.home / ".config" / "fish"
        ritual = self.home / ".claude" / "witchy" / "ritual"
        return {**{config / name: data for name, data in build.fish_files("/usr/bin/python3",
                                                                           self.home / ".claude" / "witchy").items()},
                **{ritual / name: data for name, data in build.ritual_package().items()}}

    def set_calls(self):
        return [input for args, input in self.calls if args == ["fish", "-c", fish.SET_SCRIPT]]

    def value(self, name):
        return self.variables.get(name, {}).get("value")


class InstallTest(FishTestCase):
    def test_installs_the_files_and_recolours_tide(self):
        self.assertEqual(runner.install(self.ctx()), 0)
        for path, data in self.files().items():
            self.assertEqual(path.read_bytes(), data, path)
        self.assertEqual(self.value("tide_left_prompt_items"), ["moon", "pwd", "git", "newline", "character"])
        self.assertEqual(self.value("tide_moon_color"), ["FFD477"])
        self.assertEqual(self.variables["tide_time_color"], {"value": ["A99AB9"], "exported": True})
        self.assertEqual(len(self.set_calls()), 1)
        self.assertIn(fish.NEW_TAB_NOTE, self.out.getvalue())

    def test_records_what_each_variable_held_before(self):
        runner.install(self.ctx())
        variables = self.entry()["variables"]
        self.assertEqual(set(variables), set(palette.TIDE))
        self.assertEqual(variables["tide_pwd_bg_color"], {"previous": {"value": ["FFB7C5"], "exported": False},
                                                          "installed": ["B99AFF"]})
        self.assertEqual(variables["tide_moon_color"]["previous"], {"absent": True})
        self.assertEqual(variables["tide_time_color"]["previous"]["exported"], True)
        self.assertEqual(len(self.entry()["files"]), len(self.files()))

    def test_a_variable_that_already_holds_the_value_is_not_set_again(self):
        runner.install(self.ctx())
        sent = self.set_calls()[0].split("\0")
        self.assertNotIn("tide_cmd_duration_threshold", sent)
        self.assertEqual(self.entry()["variables"]["tide_cmd_duration_threshold"]["installed"], ["3000"])

    def test_values_are_sent_on_standard_input_never_in_a_shell_string(self):
        runner.install(self.ctx())
        args = [args for args, _ in self.calls]
        self.assertTrue(all(arg[:2] == ["fish", "-c"] for arg in args))
        self.assertTrue(all("B99AFF" not in " ".join(arg) for arg in args))
        self.assertIn("tide_pwd_bg_color\0set\0" "1\0B99AFF\0", self.set_calls()[0])

    def test_without_tide_the_files_still_install(self):
        code = runner.install(self.ctx(run=fake_fish(self.variables, tide=False, calls=self.calls)))
        self.assertEqual(code, 2)
        self.assertEqual(self.set_calls(), [])
        self.assertEqual(self.entry()["variables"], {})
        self.assertTrue((self.home / ".config" / "fish" / "functions" / "fish_greeting.fish").is_file())
        self.assertEqual(self.state()["last_install"]["results"], {"fish": "skipped: Tide not found"})
        self.assertIn("fish: Tide not found; prompt not recoloured.", self.out.getvalue())

    def test_without_fish_the_files_still_install(self):
        self.assertEqual(runner.install(self.ctx(run=fake_fish(missing=True))), 2)
        self.assertEqual(self.state()["last_install"]["results"], {"fish": "skipped: fish not found"})
        self.assertTrue((self.home / ".claude" / "witchy" / "ritual" / "cli.py").is_file())

    def test_a_failed_set_stops_and_records_only_what_was_set(self):
        run = fake_fish(self.variables, fail_at="tide_pwd_bg_color", calls=self.calls)
        self.assertEqual(runner.install(self.ctx(run=run)), 2)
        variables = self.entry()["variables"]
        self.assertIn("tide_moon_color", variables)  # set before the failure
        self.assertNotIn("tide_pwd_bg_color", variables)
        self.assertNotIn("tide_time_color", variables)  # never reached
        self.assertIn("tide_cmd_duration_threshold", variables)  # needed no change
        self.assertEqual(self.value("tide_pwd_bg_color"), ["FFB7C5"])
        self.assertEqual(self.state()["last_install"]["results"], {"fish": "failed: could not set tide_pwd_bg_color"})

    def test_a_fish_that_times_out_while_setting_keeps_the_files_recorded(self):
        answers = fake_fish(self.variables)

        def run(args, **kwargs):
            if args == ["fish", "-c", fish.SET_SCRIPT]:
                raise subprocess.TimeoutExpired(args, 5)
            return answers(args, **kwargs)

        self.assertEqual(runner.install(self.ctx(run=run)), 2)
        self.assertEqual(len(self.entry()["files"]), len(self.files()))
        self.assertEqual(self.state()["last_install"]["results"]["fish"],
                         "failed: fish did not finish setting the Tide variables")
        self.assertEqual(set(self.entry()["variables"]), set(palette.TIDE))
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.variables, USER_TIDE)

    def test_what_config_fish_prints_is_ignored(self):
        run = fake_fish(self.variables, noise="Welcome!\n\0stray\0", calls=self.calls)
        self.assertEqual(runner.install(self.ctx(run=run)), 0)
        self.assertEqual(self.entry()["variables"]["tide_pwd_bg_color"]["previous"]["value"], ["FFB7C5"])

    def test_reinstall_keeps_the_first_previous_value(self):
        runner.install(self.ctx())
        with mock.patch.dict(palette.TIDE, {"tide_pwd_bg_color": "D0B8FF"}):
            self.assertEqual(runner.install(self.ctx(stamp="20261003-130000")), 0)
        record = self.entry()["variables"]["tide_pwd_bg_color"]
        self.assertEqual(record, {"previous": {"value": ["FFB7C5"], "exported": False}, "installed": ["D0B8FF"]})
        self.assertEqual(self.value("tide_pwd_bg_color"), ["D0B8FF"])

    def test_a_reinstall_that_cannot_ask_fish_keeps_the_recorded_variables(self):
        runner.install(self.ctx())
        recorded = self.entry()["variables"]
        self.assertEqual(runner.install(self.ctx(run=fake_fish(missing=True), stamp="20261003-130000")), 2)
        self.assertEqual(self.entry()["variables"], recorded)
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-140000")), 0)
        self.assertEqual(self.variables, USER_TIDE)

    def test_reinstall_without_changes_sets_nothing(self):
        runner.install(self.ctx())
        self.calls.clear()
        self.assertEqual(runner.install(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.set_calls(), [])

    def test_dry_run_reads_but_never_writes(self):
        self.assertEqual(runner.install(self.ctx(dry_run=True)), 0)
        self.assertEqual(self.set_calls(), [])
        self.assertFalse((self.home / ".config").exists())
        self.assertEqual(self.variables, USER_TIDE)
        self.assertIn("fish: set -U tide_pwd_bg_color B99AFF (now: FFB7C5)", self.out.getvalue())
        self.assertIn("fish: set -Ux tide_time_color A99AB9 (now: 5F8787)", self.out.getvalue())
        self.assertIn("fish: set -U tide_moon_color FFD477 (now: unset)", self.out.getvalue())

    def test_fish_config_follows_xdg_config_home(self):
        env = {"PATH": "/nowhere", "XDG_CONFIG_HOME": str(self.root / "xdg")}
        self.assertEqual(runner.install(self.ctx(env=env)), 0)
        self.assertTrue((self.root / "xdg" / "fish" / "conf.d" / "witchy.fish").is_file())
        self.assertFalse((self.home / ".config").exists())

    def test_eza_missing_is_noted(self):
        runner.install(self.ctx())
        self.assertIn(fish.NO_EZA_NOTE, self.out.getvalue())
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        (bin_dir / "eza").write_text("#!/bin/sh\n", encoding="utf-8")
        (bin_dir / "eza").chmod(0o755)
        runner.install(self.ctx(env={"PATH": str(bin_dir)}, stamp="20261003-130000"))
        self.assertNotIn(fish.NO_EZA_NOTE, self.out.getvalue())

    def test_fish_is_a_component_name(self):
        self.assertEqual(components.NAMES, ("claude", "font", "windows-terminal", "fish"))


class UninstallTest(FishTestCase):
    def test_gives_back_every_variable_and_removes_the_files(self):
        runner.install(self.ctx())
        self.calls.clear()
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.variables, USER_TIDE)
        # Read, restore, then rebuild Tide's item cache, all before any file goes.
        self.assertEqual([args[2] for args, _ in self.calls],
                         [fish.SNAPSHOT_SCRIPT, fish.SET_SCRIPT, fish.REFRESH_SCRIPT])
        for path in self.files():
            self.assertFalse(path.exists(), path)
        self.assertFalse((self.home / ".claude" / "witchy").exists())

    def test_a_users_own_function_comes_back(self):
        mine = self.home / ".config" / "fish" / "functions" / "ll.fish"
        mine.parent.mkdir(parents=True)
        mine.write_text("function ll; ls -lh $argv; end\n", encoding="utf-8")
        runner.install(self.ctx())
        self.assertIn(b"eza -la", mine.read_bytes())
        runner.uninstall(self.ctx(stamp="20261003-130000"))
        self.assertEqual(mine.read_text(encoding="utf-8"), "function ll; ls -lh $argv; end\n")

    def test_a_variable_the_user_changed_is_left_with_a_warning(self):
        runner.install(self.ctx())
        self.variables["tide_pwd_bg_color"] = {"value": ["123456"], "exported": False}
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.value("tide_pwd_bg_color"), ["123456"])
        self.assertIn("tide_pwd_bg_color was changed after install; leaving it as it is.", self.out.getvalue())
        self.assertEqual(self.value("tide_time_color"), ["5F8787"])

    def test_a_retry_after_a_partial_restore_is_silent(self):
        runner.install(self.ctx())
        self.variables["tide_pwd_bg_color"] = USER_TIDE["tide_pwd_bg_color"]  # already given back
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        self.assertNotIn("changed after install", self.out.getvalue())
        self.assertEqual(self.variables, USER_TIDE)

    def test_a_failed_restore_keeps_everything_for_a_retry(self):
        runner.install(self.ctx())
        failing = fake_fish(self.variables, fail_at="tide_moon_color")
        self.assertEqual(runner.uninstall(self.ctx(run=failing, stamp="20261003-130000")), 2)
        self.assertIn("fish: could not restore", self.out.getvalue())
        self.assertTrue((self.home / ".config" / "fish" / "functions" / "_tide_item_moon.fish").is_file())
        self.assertIn("fish", self.state()["components"])
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-131000")), 0)
        self.assertEqual(self.variables, USER_TIDE)

    def test_a_fish_that_does_not_answer_keeps_the_component(self):
        runner.install(self.ctx())

        def run(args, **kwargs):
            raise subprocess.TimeoutExpired(args, 5)

        self.assertEqual(runner.uninstall(self.ctx(run=run, stamp="20261003-130000")), 2)
        self.assertIn("fish: could not read the Tide variables", self.out.getvalue())
        self.assertTrue((self.home / ".claude" / "witchy" / "ritual" / "cli.py").is_file())

    def test_without_fish_the_files_still_go(self):
        runner.install(self.ctx())
        self.assertEqual(runner.uninstall(self.ctx(run=fake_fish(missing=True), stamp="20261003-130000")), 0)
        self.assertIn("fish not found; the Tide variables were left as they are.", self.out.getvalue())
        self.assertFalse((self.home / ".claude" / "witchy" / "ritual").exists())

    def test_installed_without_tide_uninstalls_without_fish_calls(self):
        runner.install(self.ctx(run=fake_fish(self.variables, tide=False)))
        self.calls.clear()
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.calls, [])

    def test_dry_run_lists_the_restore_and_changes_nothing(self):
        runner.install(self.ctx())
        installed = json.loads(json.dumps(self.variables))
        self.assertEqual(runner.uninstall(self.ctx(dry_run=True, stamp="20261003-130000")), 0)
        self.assertIn(f"fish: restore {len(palette.TIDE) - 1} Tide variables", self.out.getvalue())
        self.assertEqual(self.variables, installed)
        self.assertTrue((self.home / ".claude" / "witchy" / "ritual" / "cli.py").is_file())


if __name__ == "__main__":
    unittest.main()
