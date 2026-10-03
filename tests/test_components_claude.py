import io
import json
import tempfile
import unittest
from pathlib import Path

from witchy import build
from witchy.components.base import Abort, apply_changes
from witchy.components.claude import RESTART_NOTE, ClaudeComponent
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

    def test_settings_with_comments_abort_the_plan(self):
        self.settings.write_text('{\n  // a comment\n  "theme": "dark"\n}\n', encoding="utf-8")
        with self.assertRaises(Abort):
            self.component.plan(self.ctx(), None)


if __name__ == "__main__":
    unittest.main()
