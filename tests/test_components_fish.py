import io
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.fakes import fake_fish
from witchy import build, components, jsonio, palette, runner
from witchy.components import fish
from witchy.components.base import ComponentFailed, sha
from witchy.context import Context

FISH = shutil.which("fish")

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

    def write_fails(self, target):
        """``target`` cannot be written; everything else writes."""
        real = jsonio.write_atomic_bytes

        def write(path, data):
            if Path(path) == target:
                raise PermissionError(13, "Permission denied", str(path))
            return real(path, data)

        return mock.patch.object(jsonio, "write_atomic_bytes", side_effect=write)

    def fish_files_change(self):
        """A later witchy version that ships different fish files."""
        real = build.fish_files

        def render(*args, **kwargs):
            return {name: data + b"\n" for name, data in real(*args, **kwargs).items()}

        return mock.patch.object(build, "fish_files", side_effect=render)


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

    def test_the_new_tab_note_promises_only_what_this_install_changes(self):
        def slow(args, **kwargs):
            raise subprocess.TimeoutExpired(args, 5)

        cases = ((fake_fish(self.variables), [fish.NEW_TAB_NOTE]),
                 (fake_fish(self.variables, tide=False), [fish.GREETING_NOTE]),
                 (slow, [fish.GREETING_NOTE]),
                 (fake_fish(missing=True), []))
        for run, notes in cases:
            with self.subTest(notes=notes):
                plan = fish.FishComponent().plan(self.ctx(run=run), None)
                self.assertEqual(plan.notes, notes + [fish.NO_EZA_NOTE])

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

    def unknown_outcome(self, answer):
        answers = fake_fish(self.variables)

        def run(args, **kwargs):
            if args == ["fish", "-c", fish.SET_SCRIPT]:
                return answer(args)
            return answers(args, **kwargs)

        self.assertEqual(runner.install(self.ctx(run=run)), 2)
        self.assertEqual(self.state()["last_install"]["results"]["fish"],
                         "failed: fish did not finish setting the Tide variables")
        self.assertEqual(set(self.entry()["variables"]), set(palette.TIDE))

    def test_a_set_call_killed_by_a_signal_is_an_unknown_outcome(self):
        name = next(iter(palette.TIDE))
        self.unknown_outcome(lambda args: subprocess.CompletedProcess(
            args, -9, stdout=f"{fish.SENTINEL}\0{name}\0".encode(), stderr=b""))
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.variables, USER_TIDE)

    def test_a_set_call_with_no_marker_is_an_unknown_outcome(self):
        self.unknown_outcome(lambda args: subprocess.CompletedProcess(args, 0, stdout=b"garbage", stderr=b""))

    def test_what_config_fish_prints_is_ignored(self):
        run = fake_fish(self.variables, noise="Welcome!\n\0stray\0", calls=self.calls)
        self.assertEqual(runner.install(self.ctx(run=run)), 0)
        self.assertEqual(self.entry()["variables"]["tide_pwd_bg_color"]["previous"]["value"], ["FFB7C5"])

    def test_a_value_comes_back_byte_for_byte(self):
        # A carriage return, a line break and a byte that is not UTF-8 (0xFF, held as the surrogate U+DCFF).
        odd = {"value": ["FF\rB7\udcffC5", "two\r\nlines"], "exported": False}
        self.variables["tide_pwd_bg_color"] = odd
        self.assertEqual(runner.install(self.ctx()), 0)
        self.assertEqual(self.entry()["variables"]["tide_pwd_bg_color"]["previous"], odd)
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.variables["tide_pwd_bg_color"], odd)
        self.assertIn("tide_pwd_bg_color\0set\0" "2\0FF\rB7\udcffC5\0two\r\nlines\0", self.set_calls()[-1])

    def test_a_dry_run_shows_bytes_that_are_not_utf8_as_replacement_characters(self):
        self.variables["tide_pwd_bg_color"] = {"value": ["FF\udcff"], "exported": False}
        self.assertEqual(runner.install(self.ctx(dry_run=True)), 0)
        self.assertIn("fish: set -U tide_pwd_bg_color B99AFF (now: FF\ufffd)", self.out.getvalue())
        self.out.getvalue().encode("utf-8")  # printable on a strict UTF-8 terminal

    def test_reinstall_keeps_the_first_previous_value(self):
        runner.install(self.ctx())
        with mock.patch.dict(palette.TIDE, {"tide_pwd_bg_color": "D0B8FF"}):
            self.assertEqual(runner.install(self.ctx(stamp="20261003-130000")), 0)
        record = self.entry()["variables"]["tide_pwd_bg_color"]
        self.assertEqual(record, {"previous": {"value": ["FFB7C5"], "exported": False}, "installed": ["D0B8FF"]})
        self.assertEqual(self.value("tide_pwd_bg_color"), ["D0B8FF"])

    def test_uninstall_gives_back_a_function_the_user_replaced_between_installs(self):
        function = self.home / ".config" / "fish" / "functions" / "ll.fish"
        self.assertFalse(function.exists())
        runner.install(self.ctx())
        function.write_text("function ll; echo mine; end\n", encoding="utf-8")
        runner.install(self.ctx(stamp="20261003-130000"))
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-140000")), 0)
        self.assertEqual(function.read_text(encoding="utf-8"), "function ll; echo mine; end\n")

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

    def test_a_prompt_item_list_that_still_lists_moon_says_how_to_remove_it(self):
        runner.install(self.ctx())
        self.variables["tide_left_prompt_items"]["value"] = ["moon", "pwd", "time"]
        self.variables["tide_right_prompt_items"]["value"] = ["status", "time"]
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.value("tide_left_prompt_items"), ["moon", "pwd", "time"])
        self.assertIn("tide_left_prompt_items was changed after install; leaving it as it is, but it still lists "
                      "moon. Remove it with: set -U tide_left_prompt_items "
                      "(string match -v moon $tide_left_prompt_items)", self.out.getvalue())
        self.assertIn("tide_right_prompt_items was changed after install; leaving it as it is.", self.out.getvalue())

    def test_tide_removed_before_uninstall_gives_one_warning(self):
        runner.install(self.ctx())
        self.variables.clear()  # Tide's own uninstall erases every tide_ variable
        self.calls.clear()
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        output = self.out.getvalue()
        self.assertIn("fish: Tide's variables are gone (was Tide removed?); nothing to restore.", output)
        self.assertNotIn("changed after install", output)
        self.assertEqual(self.set_calls(), [])
        self.assertFalse((self.home / ".claude" / "witchy").exists())

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
        self.assertIn("fish: fish not found, so Tide keeps witchy's colours and the moon item; to reset them, run "
                      "tide configure in fish.", self.out.getvalue())
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


class PartialWriteTest(FishTestCase):
    """A fish file that cannot be written: what was written stays recorded, so uninstall still undoes it."""

    def setUp(self):
        super().setUp()
        self.functions = self.home / ".config" / "fish" / "functions"

    def snapshot(self):
        return {str(path): path.read_bytes() for path in sorted(self.home.rglob("*"))
                if path.is_file() and ".bak-witchy-" not in path.name}

    def test_a_write_that_fails_part_way_records_what_was_written(self):
        ctx = self.ctx()
        component = fish.FishComponent()
        plan = component.plan(ctx, None)
        first, second = plan.changes[0].path, plan.changes[1].path
        with self.write_fails(second):
            entry = component.apply(ctx, plan)
        self.assertEqual(entry, {"files": [{"path": str(first), "backup": None,
                                            "installed_sha256": sha(first.read_bytes())}], "variables": {}})
        self.assertRegex(plan.outcome, r"^failed: could not write the fish files "
                                       r"\(\[Errno 13\] Permission denied: '.*'\)$")
        self.assertIn("fish: could not write the fish files (", self.out.getvalue())
        self.assertEqual(self.set_calls(), [])
        self.assertEqual(self.variables, USER_TIDE)
        self.assertEqual(plan.notes, [fish.NO_EZA_NOTE])

    def test_a_first_write_that_fails_records_nothing(self):
        ctx = self.ctx()
        component = fish.FishComponent()
        plan = component.plan(ctx, None)
        with self.write_fails(plan.changes[0].path):
            with self.assertRaisesRegex(ComponentFailed, r"^could not write the fish files \("):
                component.apply(ctx, plan)

    def test_a_failed_reinstall_keeps_the_variables_and_the_records_it_did_not_replace(self):
        runner.install(self.ctx())
        first = self.entry()
        ctx = self.ctx(stamp="20261003-130000")
        component = fish.FishComponent()
        with self.fish_files_change():
            plan = component.plan(ctx, first)
        with self.write_fails(self.functions / "lt.fish"):
            entry = component.apply(ctx, plan)
        self.assertEqual(entry["variables"], first["variables"])
        earlier = {record["path"]: record for record in first["files"]}
        records = {record["path"]: record for record in entry["files"]}
        self.assertEqual(list(records), list(earlier))
        for name in ("lt.fish", "ritual.fish"):
            self.assertEqual(records[str(self.functions / name)], earlier[str(self.functions / name)])
        ll = str(self.functions / "ll.fish")
        self.assertEqual(records[ll]["installed_sha256"], sha(Path(ll).read_bytes()))
        self.assertNotEqual(records[ll]["installed_sha256"], earlier[ll]["installed_sha256"])

    def install_after_a_failed_write(self):
        """lt.fish cannot be written (ll.fish just was); then a later version reinstalls, then uninstall."""
        with self.write_fails(self.functions / "lt.fish"):
            self.assertEqual(runner.install(self.ctx()), 2)
        self.assertIn("fish: could not write the fish files (", self.out.getvalue())
        self.assertRegex(self.state()["last_install"]["results"]["fish"],
                         r"^failed: could not write the fish files \(.*lt\.fish'\)$")
        self.assertEqual(self.variables, USER_TIDE)
        with self.fish_files_change():
            self.assertEqual(runner.install(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-140000")), 0)

    def test_a_retry_after_a_failed_write_still_removes_what_witchy_wrote(self):
        before = self.snapshot()
        self.install_after_a_failed_write()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.variables, USER_TIDE)

    def test_a_retry_after_a_failed_write_gives_back_the_users_function(self):
        mine = self.functions / "ll.fish"
        mine.parent.mkdir(parents=True)
        mine.write_text("function ll; ls -lh $argv; end\n", encoding="utf-8")
        before = self.snapshot()
        self.install_after_a_failed_write()
        self.assertEqual(self.snapshot(), before)

    def test_uninstall_after_a_failed_write_removes_what_witchy_wrote(self):
        before = self.snapshot()
        with self.write_fails(self.functions / "lt.fish"):
            self.assertEqual(runner.install(self.ctx()), 2)
        self.assertEqual(runner.uninstall(self.ctx(stamp="20261003-130000")), 0)
        self.assertEqual(self.snapshot(), before)


class DoctorTest(FishTestCase):
    NOW = datetime(2026, 10, 3, 21, 0)

    def doctor(self, run=None, env=None):
        ctx = self.ctx(run=run, env=env)
        ctx.now = lambda: self.NOW
        code = runner.doctor(ctx, [fish.FishComponent()])
        return code, self.out.getvalue()

    def log(self, *lines):
        path = self.home / ".cache" / "witchy" / "ritual.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")

    def test_a_healthy_install(self):
        runner.install(self.ctx())
        code, output = self.doctor()
        self.assertEqual(code, 0)
        self.assertIn(f"✓ fish              {len(self.files())} files match", output)
        self.assertIn(f"✓ fish              {len(palette.TIDE)} Tide variables match", output)
        self.assertIn("✓ fish              no greeting or sky errors in the last 7 days", output)

    def test_a_changed_file_and_a_changed_variable_fail(self):
        runner.install(self.ctx())
        (self.home / ".config" / "fish" / "functions" / "ll.fish").write_text("function ll; end\n", encoding="utf-8")
        self.variables["tide_pwd_bg_color"]["value"] = ["123456"]
        code, output = self.doctor()
        self.assertEqual(code, 1)
        self.assertIn("✗ fish              changed or missing: ", output)
        self.assertIn("ll.fish", output)
        self.assertIn("✗ fish              Tide variables changed: tide_pwd_bg_color", output)
        self.assertIn("fix: python3 -m witchy install --only fish", output)

    def test_fish_that_does_not_answer_is_a_warning(self):
        runner.install(self.ctx())
        code, output = self.doctor(run=fake_fish(missing=True))
        self.assertEqual(code, 0)
        self.assertIn("⚠ fish              cannot check the Tide variables: could not read the Tide variables", output)

    def test_eza(self):
        runner.install(self.ctx())
        self.assertIn("⚠ fish              eza missing — sudo apt install eza", self.doctor()[1])
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        (bin_dir / "eza").write_text("#!/bin/sh\n", encoding="utf-8")
        (bin_dir / "eza").chmod(0o755)
        self.assertIn("✓ fish              eza found", self.doctor(env={"PATH": str(bin_dir)})[1])

    def test_the_newest_greeting_error_of_the_week(self):
        runner.install(self.ctx())
        self.log("2026-10-01T08:00:00 greeting: OldError()",
                 "2026-10-03T09:14:00 greeting: KeyError('name')",
                 "2026-10-02T23:59:00 sky: older than the greeting line but still recent")
        output = self.doctor()[1]
        self.assertIn("⚠ fish              greeting: last run failed today at 09:14: KeyError('name')", output)
        self.assertIn("⚠ fish              sky: last run failed yesterday: older than the greeting line", output)
        self.assertNotIn("OldError", output)

    def test_errors_older_than_a_week_are_history(self):
        runner.install(self.ctx())
        self.log("2026-09-20T09:14:00 greeting: KeyError('name')", "2026-09-26T21:00:00 sky: boom")
        output = self.doctor()[1]
        self.assertNotIn("KeyError", output)
        self.assertIn("no greeting or sky errors in the last 7 days", output)

    def test_long_messages_are_cut(self):
        runner.install(self.ctx())
        self.log("2026-10-03T09:14:00 greeting: UnicodeEncodeError(" + "x" * 300 + ")")
        line = next(line for line in self.doctor()[1].splitlines() if "greeting:" in line)
        message = line.split("today at 09:14: ", 1)[1]
        self.assertEqual(len(message), fish.MESSAGE_MAX)
        self.assertTrue(message.endswith("…"))

    def test_the_sky_fail_marker(self):
        runner.install(self.ctx())
        self.log("2026-10-03T08:00:00 sky: backgroundImage was changed by hand ('C:/me.png'); leaving it")
        (self.home / ".cache" / "witchy" / "sky-fail").write_text("2026-10-03\n", encoding="utf-8")
        output = self.doctor()[1]
        self.assertIn("sky: last run failed today at 08:00: backgroundImage was changed by hand ('C:/me.png'); "
                      "leaving it (it retries tomorrow)", output)
        self.assertIn("fix: python3 -m witchy install --only windows-terminal", output)
        (self.home / ".cache" / "witchy" / "ritual.log").unlink()
        self.assertIn("⚠ fish              sky: the sky job failed today (it retries tomorrow)", self.doctor()[1])

    def test_a_sky_fail_marker_from_yesterday_adds_nothing(self):
        runner.install(self.ctx())
        self.log("2026-10-02T08:00:00 sky: boom")
        (self.home / ".cache" / "witchy" / "sky-fail").write_text("2026-10-02\n", encoding="utf-8")
        output = self.doctor()[1]
        self.assertIn("⚠ fish              sky: last run failed yesterday: boom\n", output)
        self.assertNotIn("retries tomorrow", output)
        (self.home / ".cache" / "witchy" / "ritual.log").unlink()
        output = self.doctor()[1]
        self.assertNotIn("sky:", output)
        self.assertIn("✓ fish              no greeting or sky errors in the last 7 days", output)

    def test_only_a_sky_error_from_today_retries_tomorrow(self):
        runner.install(self.ctx())
        self.log("2026-10-01T08:00:00 sky: boom")
        (self.home / ".cache" / "witchy" / "sky-fail").write_text("2026-10-03\n", encoding="utf-8")
        output = self.doctor()[1]
        self.assertIn("⚠ fish              sky: last run failed 2 days ago: boom\n", output)
        self.assertIn("⚠ fish              sky: the sky job failed today (it retries tomorrow)\n", output)

    def test_the_fix_for_a_log_line_shows_the_log(self):
        self.home = self.root / "my home"
        self.home.mkdir()
        runner.install(self.ctx())
        self.log("2026-10-03T09:14:00 greeting: KeyError('name')")
        (self.home / ".cache" / "witchy" / "sky-fail").write_text("2026-10-03\n", encoding="utf-8")
        output = self.doctor()[1]
        fix = f"    fix: tail -n 20 '{self.home}/.cache/witchy/ritual.log'\n"
        self.assertEqual(output.count(fix), 2, output)  # the greeting line and the fail-marker line

    def test_damaged_log_lines_are_skipped(self):
        runner.install(self.ctx())
        self.log("2026-10-03T09:14:00 greeting: KeyError('name')", "2026-13-03T09:15:00 greeting: bad month",
                 "not a log line")
        path = self.home / ".cache" / "witchy" / "ritual.log"
        path.write_bytes(path.read_bytes() + b"\xff\xfe broken bytes\n")
        output = self.doctor()[1]
        self.assertNotIn("check crashed", output)
        self.assertIn("greeting: last run failed today at 09:14: KeyError('name')", output)

    def test_an_aware_now_compares_with_the_local_log(self):
        runner.install(self.ctx())
        self.log("2026-10-03T09:14:00 greeting: KeyError('name')")
        local = self.NOW.astimezone()  # 21:00 in this machine's zone, whatever it is
        ahead = local.astimezone(timezone(local.utcoffset() + timedelta(hours=9)))  # 06:00 the next day there
        ctx = self.ctx()
        ctx.now = lambda: ahead
        runner.doctor(ctx, [fish.FishComponent()])
        self.assertIn("greeting: last run failed today at 09:14", self.out.getvalue())


@unittest.skipUnless(FISH, "fish is not installed")
class RealFishBytesTest(unittest.TestCase):
    """Real fish with a temporary HOME and config folder, never the user's own."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        config = self.root / "config"
        (config / "fish" / "functions").mkdir(parents=True)
        (config / "fish" / "functions" / "tide.fish").write_text("function tide\nend\n", encoding="utf-8")
        tools = dict.fromkeys([str(Path(FISH).parent), "/usr/bin", "/bin"])
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(config), "PATH": os.pathsep.join(tools)}

    def fish(self, script):
        return subprocess.run([FISH, "-c", script], capture_output=True, env=self.env, timeout=20, check=True).stdout

    def ctx(self, stamp):
        return Context(home=self.home, env=self.env, out=io.StringIO(), python=sys.executable, stamp=stamp,
                       dist=self.root / "dist", lock_path=self.root / "witchy.lock", only=("fish",))

    def test_a_value_with_carriage_returns_comes_back_byte_for_byte(self):
        self.fish("set -U tide_pwd_bg_color (printf 'FF\\rB7C5\\r\\0two\\r ❯\\0' | string split0)")
        read = "printf '%s\\0' $tide_pwd_bg_color"
        before = self.fish(read)
        self.assertEqual(before, "FF\rB7C5\r\0two\r ❯\0".encode())
        self.assertEqual(runner.install(self.ctx("20261003-120000")), 0)
        self.assertEqual(self.fish(read), b"B99AFF\0")
        self.assertEqual(runner.uninstall(self.ctx("20261003-130000")), 0)
        self.assertEqual(self.fish(read), before)


if __name__ == "__main__":
    unittest.main()
