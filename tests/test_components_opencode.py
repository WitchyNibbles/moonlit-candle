import io
import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import build, runner
from witchy.components import opencode
from witchy.components.base import apply_changes, sha
from witchy.components.opencode import (JSONC_WARNING, NO_OPENCODE_NOTE, THEME, TUI_JSONC_WARNING,
                                        OpenCodeComponent, config_dir)
from witchy.context import Context

OLD_TUI = {"$schema": "https://opencode.ai/tui.json", "theme": "tokyonight", "keybinds": {"leader": "ctrl+x"}}


class OpenCodeComponentTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.config = self.home / ".config" / "opencode"
        self.theme = self.config / "themes" / "moonlit-candle.json"
        self.tui = self.config / "tui.json"
        self.home.mkdir()
        self.component = OpenCodeComponent()
        self.env = {"PATH": ""}

    def ctx(self, stamp="20261102-120000", env=None):
        self.out = io.StringIO()
        ctx = Context(home=self.home, env=self.env if env is None else env, out=self.out, python="/usr/bin/python3",
                      stamp=stamp, dist=self.root / "dist", variant="midnight")
        ctx.outputs = build.render_outputs(variant="midnight")
        return ctx

    def install(self, env=None):
        ctx = self.ctx(env=env)
        plan = self.component.plan(ctx, None)
        return ctx, plan, self.component.apply(ctx, plan)

    def uninstall(self, entry):
        ctx = self.ctx(stamp="20261102-130000")
        plan = self.component.restore(ctx, entry)
        apply_changes(ctx, plan.changes)
        return plan

    def write_tui(self, data, name="tui.json"):
        self.config.mkdir(parents=True, exist_ok=True)
        (self.config / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def tui_data(self):
        return json.loads(self.tui.read_text(encoding="utf-8"))

    def at_level(self, ctx, entry, level):
        return [check for check in self.component.check(ctx, entry) if check.level == level]

    def levels(self, ctx, entry):
        return {check.level for check in self.component.check(ctx, entry)}

    def fails(self, ctx, entry):
        return self.at_level(ctx, entry, "fail")

    def test_install_writes_the_theme_and_selects_it(self):
        ctx, plan, entry = self.install()
        self.assertEqual(self.component.name, "opencode")
        self.assertEqual(self.theme.read_bytes(), ctx.outputs[build.OPENCODE_THEME].encode("utf-8"))
        self.assertEqual(self.tui_data(), {"theme": "moonlit-candle"})
        self.assertIsNone(plan.skip)
        self.assertEqual([record["path"] for record in entry["files"]], [str(self.theme)])
        self.assertEqual(entry["settings"]["path"], str(self.tui))

    def test_install_keeps_other_tui_keys_and_uninstall_restores_the_old_theme(self):
        self.write_tui(OLD_TUI)
        before = self.tui.read_text(encoding="utf-8")
        _, _, entry = self.install()
        self.assertEqual(self.tui_data(), {**OLD_TUI, "theme": THEME})
        self.assertEqual(list(self.tui_data()), list(OLD_TUI))
        self.assertEqual(self.tui.read_text(encoding="utf-8").count("\n"), before.count("\n"))
        self.uninstall(entry)
        self.assertEqual(self.tui_data(), OLD_TUI)
        self.assertFalse(self.theme.exists())

    def test_uninstall_removes_the_theme_key_when_there_was_none(self):
        self.write_tui({"keybinds": {"leader": "ctrl+x"}})
        _, _, entry = self.install()
        self.tui.write_text(json.dumps({**self.tui_data(), "scroll_speed": 3}, indent=2) + "\n", encoding="utf-8")
        self.uninstall(entry)
        self.assertEqual(self.tui_data(), {"keybinds": {"leader": "ctrl+x"}, "scroll_speed": 3})

    def test_uninstall_removes_a_tui_json_it_created(self):
        _, _, entry = self.install()
        plan = self.uninstall(entry)
        self.assertFalse(self.tui.exists())
        self.assertFalse(self.theme.exists())
        self.assertEqual(plan.warnings, [])

    def test_uninstall_gives_back_a_theme_file_it_replaced(self):
        self.theme.parent.mkdir(parents=True)
        self.theme.write_text('{"theme": {}}\n', encoding="utf-8")
        _, _, entry = self.install()
        self.assertNotEqual(self.theme.read_text(encoding="utf-8"), '{"theme": {}}\n')
        self.uninstall(entry)
        self.assertEqual(self.theme.read_text(encoding="utf-8"), '{"theme": {}}\n')

    def test_jsonc_tui_json_is_left_alone(self):
        self.config.mkdir(parents=True)
        text = '{\n  // my keys\n  "theme": "nord",\n}\n'
        self.tui.write_text(text, encoding="utf-8")
        ctx, plan, entry = self.install()
        self.assertEqual(self.tui.read_text(encoding="utf-8"), text)
        self.assertTrue(self.theme.is_file())
        self.assertIsNone(plan.skip)
        self.assertIsNone(plan.outcome)
        self.assertIn(JSONC_WARNING.format(path=self.tui), self.out.getvalue())
        self.assertNotIn("settings", entry)
        fails = self.fails(ctx, entry)
        self.assertEqual(len(fails), 1)
        self.assertIn(f"theme not selected in {self.tui}", fails[0].message)
        self.assertEqual(fails[0].fix, "python3 -m witchy install --only opencode")
        self.assertEqual(self.uninstall(entry).warnings, [])
        self.assertFalse(self.theme.exists())
        self.assertEqual(self.tui.read_text(encoding="utf-8"), text)

    def test_a_reinstall_over_a_jsonc_tui_json_keeps_the_earlier_settings_record(self):
        self.write_tui(OLD_TUI)
        _, _, first = self.install()
        text = '{\n  // now with a comment\n  "theme": "moonlit-candle"\n}\n'
        self.tui.write_text(text, encoding="utf-8")
        ctx = self.ctx()
        plan = self.component.plan(ctx, first)
        second = self.component.apply(ctx, plan)
        self.assertEqual(second["settings"], first["settings"])
        self.assertEqual(self.tui.read_text(encoding="utf-8"), text)

    def test_tui_jsonc_theme_is_reported(self):
        self.config.mkdir(parents=True)
        jsonc = self.config / "tui.jsonc"
        jsonc.write_text('{\n  // mine\n  "theme": "nord", /* wins */\n}\n', encoding="utf-8")
        ctx, _, entry = self.install()
        self.assertIn(TUI_JSONC_WARNING.format(path=jsonc), self.out.getvalue())
        warns = self.at_level(ctx, entry, "warn")
        self.assertEqual(len(warns), 1)
        self.assertIn(str(jsonc), warns[0].message)
        self.assertEqual(self.fails(ctx, entry), [])
        self.assertEqual(self.tui_data(), {"theme": THEME})

    def test_a_tui_jsonc_without_a_theme_or_with_ours_or_only_in_a_comment_is_not_reported(self):
        self.config.mkdir(parents=True)
        jsonc = self.config / "tui.jsonc"
        for text in ('{\n  "keybinds": {}\n}\n', '{ "theme": "moonlit-candle", }\n',
                     '{\n  // "theme": "nord"\n  "keybinds": {}\n}\n'):
            jsonc.write_text(text, encoding="utf-8")
            ctx, _, entry = self.install()
            self.assertNotIn("tui.jsonc", self.out.getvalue(), text)
            levels = self.levels(ctx, entry) - {"info"}
            self.assertEqual(levels, {"ok"}, text)

    def test_no_opencode_anywhere_still_installs(self):
        ctx, plan, entry = self.install()
        self.assertIsNone(plan.skip)
        self.assertIn(NO_OPENCODE_NOTE, plan.notes)
        self.assertTrue(self.theme.is_file())
        infos = self.at_level(ctx, entry, "info")
        self.assertEqual([check.message for check in infos], [NO_OPENCODE_NOTE])
        self.assertEqual(self.fails(ctx, entry), [])

    def test_opencode_on_path_gives_no_note(self):
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "opencode"
        fake.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        env = {"PATH": str(bin_dir)}
        ctx, plan, entry = self.install(env=env)
        self.assertNotIn(NO_OPENCODE_NOTE, plan.notes)
        self.assertEqual(self.levels(ctx, entry), {"ok"})

    def test_xdg_config_home(self):
        elsewhere = self.root / "xdg"
        self.assertEqual(config_dir(self.ctx(env={"XDG_CONFIG_HOME": str(elsewhere)})), elsewhere / "opencode")
        for value in ("relative/dir", ""):
            self.assertEqual(config_dir(self.ctx(env={"XDG_CONFIG_HOME": value})), self.config, value)
        self.assertEqual(config_dir(self.ctx(env={})), self.config)
        _, _, entry = self.install(env={"PATH": "", "XDG_CONFIG_HOME": str(elsewhere)})
        self.assertTrue((elsewhere / "opencode" / "themes" / "moonlit-candle.json").is_file())
        self.assertTrue((elsewhere / "opencode" / "tui.json").is_file())
        self.assertFalse(self.config.exists())
        self.assertEqual(entry["settings"]["path"], str(elsewhere / "opencode" / "tui.json"))

    def test_check_ok(self):
        ctx, _, entry = self.install()
        levels = self.levels(ctx, entry) - {"info"}
        self.assertEqual(levels, {"ok"})

    def test_check_drift_theme_key(self):
        self.write_tui(OLD_TUI)
        ctx, _, entry = self.install()
        self.tui.write_text(json.dumps({**self.tui_data(), "theme": "nord"}, indent=2) + "\n", encoding="utf-8")
        fails = self.fails(ctx, entry)
        self.assertEqual(len(fails), 1)
        self.assertIn("theme", fails[0].message)
        self.assertEqual(fails[0].fix, "python3 -m witchy install --only opencode")
        plan = self.uninstall(entry)
        self.assertEqual(self.tui_data()["theme"], "nord")
        self.assertTrue(any("theme was changed after install" in warning for warning in plan.warnings))

    def test_check_missing_and_changed_theme_file(self):
        ctx, _, entry = self.install()
        self.theme.write_text("{}\n", encoding="utf-8")
        fails = self.fails(ctx, entry)
        self.assertEqual(len(fails), 1)
        self.assertIn(str(self.theme), fails[0].message)
        self.theme.unlink()
        fails = self.fails(ctx, entry)
        self.assertEqual(len(fails), 1)
        self.assertIn("changed or missing", fails[0].message)
        self.assertEqual(fails[0].fix, "python3 -m witchy install --only opencode")

    def test_check_warns_when_the_tui_backup_is_gone(self):
        self.write_tui(OLD_TUI)
        ctx, _, entry = self.install()
        Path(entry["settings"]["backup"]).unlink()
        warns = self.at_level(ctx, entry, "warn")
        self.assertTrue(any("backup" in check.message for check in warns))

    def test_reinstall_keeps_the_first_previous_value(self):
        self.write_tui(OLD_TUI)
        _, _, first = self.install()
        ctx = self.ctx(stamp="20261102-125000")
        plan = self.component.plan(ctx, first)
        second = self.component.apply(ctx, plan)
        self.assertEqual(second["settings"]["keys"]["theme"]["previous"], {"value": "tokyonight"})
        self.assertEqual(second["files"][0]["backup"], first["files"][0]["backup"])
        self.uninstall(second)
        self.assertEqual(self.tui_data(), OLD_TUI)

    def test_a_write_that_fails_part_way_is_recorded(self):
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)

        def fail_on_settings(ctx_, changes, backups=None):
            apply_changes(ctx_, changes[:1], backups)
            raise PermissionError(13, "Permission denied", str(self.tui))

        with mock.patch.object(opencode, "apply_changes", fail_on_settings):
            entry = self.component.apply(ctx, plan)
        self.assertTrue(plan.outcome.startswith("failed: could not write ("))
        self.assertEqual([record["path"] for record in entry["files"]], [str(self.theme)])
        self.assertNotIn("settings", entry)
        self.assertEqual(entry["files"][0]["installed_sha256"], sha(self.theme.read_bytes()))


def refuse(*args, **kwargs):
    raise AssertionError("no subprocess may run in tests")


def install_context(root, home, out=None, **kwargs):
    return Context(home=home, env={"PATH": ""}, out=out or io.StringIO(), python="/usr/bin/python3",
                   stamp="20261102-120000", run=refuse, dist=root / "dist", lock_path=root / "witchy.lock",
                   only=("opencode",), **kwargs)


class OpenCodeInstallTest(unittest.TestCase):
    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            out = io.StringIO()
            ctx = install_context(root, home, out, dry_run=True)
            self.assertEqual(runner.install(ctx), 0)
            self.assertEqual(list(home.iterdir()), [])
            self.assertFalse((root / "dist").exists())
            self.assertIn("Dry run: nothing was written.", out.getvalue())
            self.assertIn("themes/moonlit-candle.json", out.getvalue())

    def test_install_and_uninstall_through_the_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            first = install_context(root, home)
            self.assertEqual(runner.install(first), 0)
            self.assertIn(NO_OPENCODE_NOTE, first.out.getvalue())
            self.assertTrue((home / ".config/opencode/themes/moonlit-candle.json").is_file())
            self.assertEqual(runner.uninstall(install_context(root, home)), 0)
            leftovers = [str(p.relative_to(home)) for p in home.rglob("*") if p.is_file()]
            self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
