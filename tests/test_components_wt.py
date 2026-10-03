import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from witchy import jsonio, palette, wt
from witchy.components.base import ComponentFailed, Plan, apply_changes
from witchy.components.windows_terminal import NO_FONT_NOTE, RITUAL_CONFIG, WindowsTerminalComponent
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
                       wt_settings=wt_settings or self.wt, stamp=stamp, run=refuse_cmd, variant="midnight",
                       sky_size=(256, 144), now=lambda: datetime(2024, 9, 18, 12, tzinfo=timezone.utc))

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

    def test_recorded_settings_path_is_reused_without_cmd_exe(self):
        _, entry = self.install()
        ctx = Context(home=self.root / "home", env={"WT_PROFILE_ID": UBUNTU}, out=io.StringIO(), run=refuse_cmd,
                      variant="midnight", sky_size=(256, 144),
                      now=lambda: datetime(2024, 9, 18, 12, tzinfo=timezone.utc))
        plan = self.component.plan(ctx, entry)
        self.assertIsNone(plan.skip)
        self.assertEqual(plan.data["json"].change.path, self.wt)

    def with_font(self, face):
        data = json.loads(self.wt.read_text(encoding="utf-8"))
        data["profiles"]["list"][0]["font"] = {"face": face}
        self.wt.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")

    def test_profile_keys_are_set_and_recorded(self):
        ctx = self.ctx()
        plan = self.component.plan(ctx, None)
        entry = self.component.apply(ctx, plan)
        ubuntu = self.ubuntu()
        self.assertEqual((ubuntu["cursorShape"], ubuntu["tabTitle"], ubuntu["opacity"]), ("filledBox", "witchyterm", 93))
        self.assertNotIn("font", ubuntu)
        self.assertEqual(ubuntu["backgroundImageOpacity"], 0.12)
        self.assertEqual(entry["profile_keys"]["cursorShape"], {"previous": {"absent": True}, "installed": "filledBox"})
        self.assertIn(NO_FONT_NOTE, plan.notes)

    def test_font_is_set_when_the_font_component_installs_it(self):
        ctx = self.ctx()
        ctx.planned["font"] = Plan()
        plan = self.component.plan(ctx, None)
        ctx.results["font"] = "ok"
        self.component.apply(ctx, plan)
        self.assertEqual(self.ubuntu()["font"], palette.WT_PROFILE["font"])

    def test_failed_font_install_leaves_the_font_alone(self):
        self.with_font("FiraCode Nerd Font")
        ctx = self.ctx()
        ctx.planned["font"] = Plan()
        plan = self.component.plan(ctx, None)
        ctx.results["font"] = "failed: download failed (offline)"
        entry = self.component.apply(ctx, plan)
        self.assertEqual(self.ubuntu()["font"], {"face": "FiraCode Nerd Font"})
        self.assertNotIn("font", entry["profile_keys"])
        self.assertIn(NO_FONT_NOTE, self.out.getvalue())

    def test_font_recorded_in_state_counts(self):
        ctx = self.ctx()
        ctx.entries = {"font": {"preexisting": True, "registered": {}, "files": []}}
        self.component.apply(ctx, self.component.plan(ctx, None))
        self.assertEqual(self.ubuntu()["font"], palette.WT_PROFILE["font"])

    def test_reinstall_over_a_plan_a_entry_adds_keys_and_keeps_the_first_scheme(self):
        original = self.ubuntu()
        with mock.patch.dict(palette.WT_PROFILE, {}, clear=True):
            _, entry = self.install()
        entry.pop("profile_keys")  # what a Plan A install recorded
        ctx = self.ctx(stamp="20261002-120500")
        entry = self.component.apply(ctx, self.component.plan(ctx, entry))
        self.assertEqual(entry["previous_color_scheme"], {"value": "One Half Dark"})
        self.assertEqual(entry["profile_keys"]["cursorShape"]["previous"], {"absent": True})
        apply_changes(ctx, self.component.restore(self.ctx(stamp="20261002-130000"), entry).changes)
        self.assertEqual(self.ubuntu(), original)

    def test_a_key_the_user_changed_is_kept_on_restore(self):
        ctx, entry = self.install()
        data = json.loads(self.wt.read_text(encoding="utf-8"))
        data["profiles"]["list"][0]["cursorShape"] = "bar"
        self.wt.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        plan = self.component.restore(self.ctx(stamp="20261002-130000"), entry)
        apply_changes(ctx, plan.changes)
        self.assertEqual(self.ubuntu()["cursorShape"], "bar")
        self.assertNotIn("tabTitle", self.ubuntu())
        self.assertIn("Windows Terminal: cursorShape was changed after install; leaving it as it is.", plan.warnings)

    def test_check_reports_a_drifted_profile_key(self):
        ctx, entry = self.install()
        data = json.loads(self.wt.read_text(encoding="utf-8"))
        data["profiles"]["list"][0]["tabTitle"] = "mine"
        self.wt.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        fails = [c for c in self.component.check(ctx, entry) if c.level == "fail"]
        self.assertEqual([c.message for c in fails], ["profile keys changed: tabTitle"])

    def config(self):
        return self.root / "home" / RITUAL_CONFIG

    def test_sky_images_background_and_ritual_config(self):
        _, entry = self.install()
        for bin_ in range(8):
            self.assertTrue((self.root / wt.sky_file(bin_)).is_file(), bin_)
        ubuntu = self.ubuntu()
        self.assertEqual(ubuntu["backgroundImage"], wt.SKY_VALUES[4])
        self.assertEqual(ubuntu["backgroundImageOpacity"], 0.12)
        self.assertEqual(json.loads(self.config().read_text(encoding="utf-8")),
                         {"settings": str(self.wt), "profile_guid": UBUNTU, "sky": list(wt.SKY_VALUES)})
        self.assertEqual(len(entry["files"]), 9)

    def test_failed_image_copy_sets_no_background(self):
        real = jsonio.write_atomic_bytes

        def write(path, data):
            if Path(path).suffix == ".png":
                raise PermissionError(13, "Permission denied", str(path))
            return real(path, data)

        with mock.patch("witchy.jsonio.write_atomic_bytes", side_effect=write):
            _, entry = self.install()
        self.assertNotIn("backgroundImage", self.ubuntu())
        self.assertEqual(self.ubuntu()["cursorShape"], "filledBox")
        self.assertIn("sky images not copied", self.out.getvalue())
        self.assertFalse(self.config().exists())
        self.assertEqual(entry["files"], [])

    def test_moved_sky_still_counts_as_installed(self):
        ctx, entry = self.install()
        data = json.loads(self.wt.read_text(encoding="utf-8"))
        data["profiles"]["list"][0]["backgroundImage"] = wt.SKY_VALUES[6]  # what the sky job does
        self.wt.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        self.assertEqual({c.level for c in self.component.check(ctx, entry)}, {"ok"})
        plan = self.component.restore(self.ctx(stamp="20261002-130000"), entry)
        apply_changes(ctx, plan.changes)
        self.assertNotIn("backgroundImage", self.ubuntu())
        self.assertFalse(any("changed after install" in warning for warning in plan.warnings))
        self.assertFalse((self.root / wt.sky_file(4)).exists())
        self.assertFalse(self.config().exists())

    def test_failed_reinstall_copy_keeps_the_files_recorded(self):
        ctx, entry = self.install()
        real = jsonio.write_atomic_bytes

        def write(path, data):
            if Path(path).suffix == ".png":
                raise PermissionError(13, "Permission denied", str(path))
            return real(path, data)

        again = self.ctx(stamp="20261002-130000")
        again.sky_size = (128, 72)
        with mock.patch("witchy.jsonio.write_atomic_bytes", side_effect=write):
            entry2 = self.component.apply(again, self.component.plan(again, entry))
        self.assertEqual(len(entry2["files"]), 9)
        plan = self.component.restore(again, entry2)
        apply_changes(again, plan.changes)
        for bin_ in range(8):
            self.assertFalse((self.root / wt.sky_file(bin_)).exists(), bin_)
        self.assertFalse(self.config().exists())

    def test_restore_writes_settings_first_under_the_lock(self):
        ctx, entry = self.install()
        plan = self.component.restore(ctx, entry)
        self.assertEqual(plan.changes[0].path, self.wt)
        self.assertEqual(plan.lock, ctx.cache_dir / "wt.lock")


if __name__ == "__main__":
    unittest.main()
