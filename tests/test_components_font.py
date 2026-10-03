import hashlib
import io
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from tests.fakes import fake_windows, make_ttf, make_zip, reg_listing
from witchy import fonts
from witchy.components.base import ComponentFailed
from witchy.components.font import KEPT_WARNING, RESTART_WT_NOTE, FontComponent
from witchy.context import Context

STYLES = ("Regular", "Italic", "Bold", "Bold Italic")
FONTS_WIN = "C:\\Users\\user\\AppData\\Local\\Microsoft\\Windows\\Fonts"
OTHER_FONT = {"Fira Code Light (TrueType)": f"{FONTS_WIN}\\FiraCode.ttf"}


class FontComponentTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.mnt = self.root / "mnt"
        self.folder = self.mnt / "c" / "Users" / "user" / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"
        self.folder.mkdir(parents=True)
        self.archive = make_zip({name: make_ttf(f"Maple Mono NF {style}") for name, style in zip(fonts.MEMBERS, STYLES)})
        patcher = mock.patch.object(fonts, "SHA256", hashlib.sha256(self.archive).hexdigest())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.calls, self.fetched = [], []
        self.component = FontComponent()

    def fetch(self, url):
        self.fetched.append(url)
        return self.archive

    def ctx(self, reg=None, reg_add_code=0, fetch=None, echo=None):
        self.out = io.StringIO()
        run = fake_windows(echo={"USERPROFILE": "C:\\Users\\user\r\n"} if echo is None else echo,
                           reg_query=reg_listing(OTHER_FONT if reg is None else reg), reg_add_code=reg_add_code,
                           calls=self.calls)
        return Context(home=self.root / "home", env={}, out=self.out, run=run, mount_root=self.mnt,
                       fetch=fetch or self.fetch)

    def install(self, **kwargs):
        ctx = self.ctx(**kwargs)
        plan = self.component.plan(ctx, None)
        return ctx, plan, self.component.apply(ctx, plan)

    def test_planning_only_reads(self):
        # A dry run stops after planning: no download, no copy, no reg.exe add.
        self.component.plan(self.ctx(), None)
        self.assertEqual(self.fetched, [])
        self.assertEqual(list(self.folder.iterdir()), [])
        self.assertEqual([call[:2] for call in self.calls], [["cmd.exe", "/c"], ["reg.exe", "query"]])

    def test_installs_and_registers_four_fonts(self):
        _, plan, entry = self.install()
        self.assertEqual(self.component.name, "font")
        self.assertIn(RESTART_WT_NOTE, plan.notes)
        self.assertTrue(any(action.startswith("font: download") for action in plan.actions))
        for name in fonts.MEMBERS:
            self.assertTrue((self.folder / name).is_file(), name)
        adds = [call for call in self.calls if call[:2] == ["reg.exe", "add"]]
        self.assertEqual(len(adds), 4)
        self.assertEqual(adds[0], fonts.register_command("Maple Mono NF Regular (TrueType)",
                                                         f"{FONTS_WIN}\\MapleMono-NF-Regular.ttf"))
        self.assertEqual(set(entry["registered"]), {f"Maple Mono NF {style} (TrueType)" for style in STYLES})
        self.assertFalse(entry["preexisting"])
        self.assertEqual(self.fetched, [fonts.URL])

    def test_cached_archive_is_not_downloaded_again(self):
        self.install()
        self.install()
        self.assertEqual(self.fetched, [fonts.URL])

    def test_a_font_already_installed_by_hand_is_left_alone(self):
        (self.folder / "MapleMono-NF-Regular.ttf").write_bytes(b"font")
        present = {"Maple Mono NF Regular (TrueType)": f"{FONTS_WIN}\\MapleMono-NF-Regular.ttf"}
        _, plan, entry = self.install(reg={**OTHER_FONT, **present})
        self.assertEqual(plan.actions, [])
        self.assertEqual(entry, {"preexisting": True, "registered": present, "files": []})
        self.assertEqual(self.fetched, [])
        self.assertFalse(any(call[:2] == ["reg.exe", "add"] for call in self.calls))

    def test_offline_fails_and_copies_nothing(self):
        def offline(url):
            raise urllib.error.URLError("no network")
        with self.assertRaises(ComponentFailed):
            self.install(fetch=offline)
        self.assertIn("font: download failed", self.out.getvalue())
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_checksum_mismatch_fails_and_keeps_no_cache(self):
        with self.assertRaises(ComponentFailed):
            self.install(fetch=lambda url: b"not the release")
        self.assertIn("font: checksum mismatch, nothing installed", self.out.getvalue())
        self.assertFalse((self.root / "home" / ".cache" / "witchy" / f"MapleMono-NF-{fonts.RELEASE}.zip").exists())

    def test_registry_failure_fails(self):
        with self.assertRaises(ComponentFailed):
            self.install(reg_add_code=1)
        self.assertIn("could not register", self.out.getvalue())

    def test_no_windows_profile_is_skipped(self):
        plan = self.component.plan(self.ctx(echo={}), None)
        self.assertEqual(plan.skip, "Windows user folder not found")

    def test_restore_keeps_the_font(self):
        ctx, _, entry = self.install()
        plan = self.component.restore(ctx, entry)
        self.assertEqual((plan.changes, plan.warnings), ([], [KEPT_WARNING]))

    def test_check_is_ok_then_fails_when_unregistered(self):
        _, _, entry = self.install()
        self.assertEqual({c.level for c in self.component.check(self.ctx(reg=entry["registered"]), entry)}, {"ok"})
        fails = [c for c in self.component.check(self.ctx(), entry) if c.level == "fail"]
        self.assertEqual(len(fails), 1)
        self.assertIn("not registered", fails[0].message)
        self.assertEqual(fails[0].fix, "python3 -m witchy install --only font")


if __name__ == "__main__":
    unittest.main()
