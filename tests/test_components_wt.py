import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy.components.base import ComponentFailed, apply_changes
from witchy.components.windows_terminal import WindowsTerminalComponent
from witchy.context import Context

UBUNTU = "{05f3f843-450a-55ad-a264-cacf368dafe5}"
WT = {"profiles": {"defaults": {}, "list": [
    {"guid": UBUNTU, "name": "Ubuntu", "source": "Microsoft.WSL", "colorScheme": "One Half Dark"}]}, "schemes": []}


def refuse_cmd(*args, **kwargs):
    raise AssertionError("cmd.exe must not run in tests")


class WindowsTerminalComponentTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.wt = self.root / "settings.json"
        self.wt.write_text(json.dumps(WT, indent=4) + "\n", encoding="utf-8")
        self.component = WindowsTerminalComponent()

    def ctx(self, wt_settings=None, stamp="20261002-120000"):
        self.out = io.StringIO()
        return Context(home=self.root / "home", env={"WT_PROFILE_ID": UBUNTU}, out=self.out,
                       wt_settings=wt_settings or self.wt, stamp=stamp, run=refuse_cmd, variant="midnight")

    def ubuntu(self):
        return json.loads(self.wt.read_text(encoding="utf-8"))["profiles"]["list"][0]

    def install(self):
        ctx = self.ctx()
        return ctx, self.component.apply(ctx, self.component.plan(ctx, None))

    def test_apply_sets_the_scheme_and_returns_the_record(self):
        _, entry = self.install()
        self.assertEqual(self.component.name, "windows-terminal")
        self.assertEqual(self.ubuntu()["colorScheme"], "Moonlit Candle")
        self.assertEqual(entry["profile_guid"], UBUNTU)
        self.assertEqual(entry["previous_color_scheme"], {"value": "One Half Dark"})

    def test_missing_settings_file_is_skipped(self):
        plan = self.component.plan(self.ctx(wt_settings=self.root / "nope.json"), None)
        self.assertEqual(plan.skip, "settings.json not found")

    def test_settings_with_comments_are_skipped_with_a_snippet(self):
        self.wt.write_text('{\n  // comment\n  "profiles": []\n}\n', encoding="utf-8")
        plan = self.component.plan(self.ctx(), None)
        self.assertEqual(plan.skip, "settings.json is not plain JSON")
        self.assertIn('"schemes"', self.out.getvalue())

    def test_failed_write_raises_component_failed(self):
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        with mock.patch("witchy.jsonio.write_atomic_bytes", side_effect=PermissionError(13, "denied")):
            with self.assertRaises(ComponentFailed):
                self.component.apply(ctx, plan)

    def test_restore_gives_back_the_previous_scheme(self):
        ctx, entry = self.install()
        apply_changes(ctx, self.component.restore(self.ctx(stamp="20261002-130000"), entry).changes)
        self.assertEqual(self.ubuntu()["colorScheme"], "One Half Dark")

    def test_check_is_ok_then_fails_when_the_scheme_changes(self):
        ctx, entry = self.install()
        self.assertEqual({c.level for c in self.component.check(ctx, entry)}, {"ok"})
        data = json.loads(self.wt.read_text(encoding="utf-8"))
        data["profiles"]["list"][0]["colorScheme"] = "Campbell"
        self.wt.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        fails = [c for c in self.component.check(ctx, entry) if c.level == "fail"]
        self.assertEqual(len(fails), 1)
        self.assertIn("Campbell", fails[0].message)
        self.assertEqual(fails[0].fix, "python3 -m witchy install --only windows-terminal")


if __name__ == "__main__":
    unittest.main()
