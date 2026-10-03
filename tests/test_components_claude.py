import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import build, jsonio
from witchy.components.base import Abort, ComponentFailed, apply_changes, sha
from witchy.components.claude import COPIES, RESTART_NOTE, ClaudeComponent
from witchy.context import Context


class ClaudeComponentTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.claude = self.home / ".claude"
        self.claude.mkdir(parents=True)
        self.settings = self.claude / "settings.json"
        self.settings.write_text(json.dumps({"theme": "dark", "model": "opus"}, indent=2) + "\n", encoding="utf-8")
        self.component = ClaudeComponent()

    def ctx(self, stamp="20261002-120000"):
        self.out = io.StringIO()
        ctx = Context(home=self.home, env={}, out=self.out, python="/usr/bin/python3", stamp=stamp,
                      dist=self.root / "dist", variant="midnight")
        ctx.outputs = build.render_outputs(variant="midnight")
        return ctx

    def install(self):
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        return ctx, plan, self.component.apply(ctx, plan)

    def data(self):
        return json.loads(self.settings.read_text(encoding="utf-8"))

    def write_fails(self, target):
        real = jsonio.write_atomic_bytes

        def write(path, data):
            if Path(path) == target:
                raise PermissionError(13, "Permission denied", str(path))
            return real(path, data)

        return mock.patch.object(jsonio, "write_atomic_bytes", side_effect=write)

    def test_apply_writes_files_and_returns_the_entry(self):
        _, plan, entry = self.install()
        self.assertEqual(self.component.name, "claude")
        self.assertEqual(len(entry["files"]), 4)
        for record in entry["files"]:
            self.assertTrue(Path(record["path"]).is_file(), record["path"])
            self.assertTrue(record["path"].startswith(str(self.claude)))
        self.assertEqual(entry["settings"]["keys"]["theme"]["previous"], {"value": "dark"})
        self.assertEqual(self.data()["theme"], "custom:moonlit-candle")
        self.assertEqual(self.data()["model"], "opus")
        self.assertIn(RESTART_NOTE, plan.notes)

    def test_restore_gives_back_settings_before_removing_copies(self):
        ctx, _, entry = self.install()
        plan = self.component.restore(self.ctx(stamp="20261002-130000"), entry)
        self.assertEqual(plan.changes[0].path, self.settings)
        apply_changes(ctx, plan.changes)
        self.assertEqual(self.data(), {"theme": "dark", "model": "opus"})
        self.assertFalse((self.claude / "themes" / "moonlit-candle.json").exists())

    def test_check_is_ok_after_install(self):
        ctx, _, entry = self.install()
        self.assertEqual({check.level for check in self.component.check(ctx, entry)}, {"ok"})

    def test_check_fails_when_a_key_drifts(self):
        ctx, _, entry = self.install()
        self.settings.write_text(json.dumps(dict(self.data(), theme="light"), indent=2) + "\n", encoding="utf-8")
        fails = [c for c in self.component.check(ctx, entry) if c.level == "fail"]
        self.assertEqual(len(fails), 1)
        self.assertIn("theme", fails[0].message)
        self.assertEqual(fails[0].fix, "python3 -m witchy install --only claude")

    def test_check_fails_when_an_installed_file_changes(self):
        ctx, _, entry = self.install()
        (self.claude / "witchy" / "statusline.py").write_text("# edited\n", encoding="utf-8")
        fails = [c for c in self.component.check(ctx, entry) if c.level == "fail"]
        self.assertTrue(any("statusline.py" in c.message for c in fails))

    def test_check_warns_when_the_settings_backup_is_gone(self):
        ctx, _, entry = self.install()
        Path(entry["settings"]["backup"]).unlink()
        warns = [c for c in self.component.check(ctx, entry) if c.level == "warn"]
        self.assertTrue(any("backup" in c.message for c in warns))

    def test_file_records_do_not_depend_on_the_order_of_the_changes(self):
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        plan.changes.reverse()
        entry = self.component.apply(ctx, plan)
        self.assertEqual(sorted(record["path"] for record in entry["files"]),
                         sorted(str(self.home / target) for target in COPIES.values()))
        self.assertEqual(entry["settings"]["path"], str(self.settings))

    def test_a_write_that_fails_part_way_records_what_was_written(self):
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        with self.write_fails(self.claude / "output-styles" / "witchynibbles.md"):
            entry = self.component.apply(ctx, plan)
        theme = self.claude / "themes" / "moonlit-candle.json"
        self.assertEqual(entry["files"],
                         [{"path": str(theme), "backup": None, "installed_sha256": sha(theme.read_bytes())}])
        self.assertNotIn("settings", entry)
        self.assertRegex(plan.outcome,
                         r"^failed: could not write \(\[Errno 13\] Permission denied: '.*witchynibbles\.md'\)$")
        self.assertIn("claude: could not write (", self.out.getvalue())
        self.assertEqual(self.data(), {"theme": "dark", "model": "opus"})

    def test_settings_written_before_a_failure_are_recorded(self):
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        plan.changes.reverse()
        with self.write_fails(self.claude / "output-styles" / "witchynibbles.md"):
            entry = self.component.apply(ctx, plan)
        self.assertEqual(entry["settings"]["keys"]["theme"]["previous"], {"value": "dark"})
        self.assertEqual([record["path"] for record in entry["files"]],
                         [str(self.claude / "witchy" / "tips.json"), str(self.claude / "witchy" / "statusline.py")])

    def test_a_first_write_that_fails_records_nothing(self):
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        with self.write_fails(self.claude / "themes" / "moonlit-candle.json"):
            with self.assertRaisesRegex(ComponentFailed, r"^could not write \("):
                self.component.apply(ctx, plan)

    def test_a_failed_reinstall_keeps_the_earlier_records_it_did_not_replace(self):
        _, _, first = self.install()
        ctx = self.ctx(stamp="20261002-120500")
        ctx.outputs[build.THEME] += "\n"
        ctx.outputs[build.OUTPUT_STYLE] += "\n"
        plan = self.component.plan(ctx, first)
        with self.write_fails(self.claude / "output-styles" / "witchynibbles.md"):
            entry = self.component.apply(ctx, plan)
        self.assertTrue(plan.outcome.startswith("failed: could not write ("))
        self.assertEqual(entry["settings"], first["settings"])
        theme, *others = entry["files"]
        self.assertEqual(theme["installed_sha256"], sha(ctx.outputs[build.THEME].encode("utf-8")))
        self.assertEqual(others, first["files"][1:])

    def test_without_a_settings_record_restore_and_check_handle_the_copies(self):
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        with self.write_fails(self.claude / "output-styles" / "witchynibbles.md"):
            entry = self.component.apply(ctx, plan)
        fails = [check.message for check in self.component.check(ctx, entry) if check.level == "fail"]
        self.assertEqual(fails, [f"settings keys not installed in {self.settings}"])
        restore = self.component.restore(self.ctx(stamp="20261002-130000"), entry)
        self.assertEqual([change.path for change in restore.changes], [self.claude / "themes" / "moonlit-candle.json"])
        apply_changes(ctx, restore.changes)
        self.assertFalse((self.claude / "themes" / "moonlit-candle.json").exists())
        self.assertEqual(self.data(), {"theme": "dark", "model": "opus"})

    def test_settings_with_comments_abort_the_plan(self):
        self.settings.write_text('{\n  // a comment\n  "theme": "dark"\n}\n', encoding="utf-8")
        with self.assertRaises(Abort):
            self.component.plan(self.ctx(), None)


if __name__ == "__main__":
    unittest.main()
