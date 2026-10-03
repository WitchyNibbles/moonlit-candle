import fcntl
import json
import stat
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from witchy import wt
from witchy.components import windows_terminal
from witchy.ritual import log, moon, sky

GUID = "{51855cb2-8cce-5362-8f54-464b92b32386}"
FULL_MOON = datetime(2026, 10, 26, 8, 0, tzinfo=timezone(timedelta(hours=1)))  # phase bin 4
# Windows Terminal's own layout: containers on their own line, ASCII escapes, no final newline.
WT_TEXT = """{
    "profiles": 
    {
        "list": 
        [
            {
                "guid": "{2c4de342-38b7-51cf-b940-2309a097f518}",
                "hidden": true,
                "name": "Ubuntu"
            },
            {
                "backgroundImage": "ms-appdata:///local/moonlit-candle-sky-1.png",
                "guid": "%s",
                "icon": "\\ud83c\\udf19",
                "name": "Ubuntu"
            }
        ]
    }
}""" % GUID


class SkyJobTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        self.settings = Path(tmp.name) / "LocalState" / "settings.json"
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(WT_TEXT, encoding="utf-8")
        config = self.home / sky.CONFIG
        config.parent.mkdir(parents=True)
        config.write_bytes(windows_terminal.ritual_config(self.settings, GUID))
        self.cache = self.home / sky.CACHE

    def run_job(self, now=FULL_MOON):
        self.assertEqual(sky.run(self.home, now), 0)

    def background(self):
        data = json.loads(self.settings.read_text(encoding="utf-8"))
        return data["profiles"]["list"][1]["backgroundImage"]

    def test_moves_the_sky_and_keeps_the_file_layout(self):
        self.run_job()
        self.assertEqual(self.background(), wt.SKY_VALUES[4])
        self.assertEqual(self.settings.read_text(encoding="utf-8"),
                         WT_TEXT.replace("moonlit-candle-sky-1.png", "moonlit-candle-sky-4.png"))
        self.assertEqual((self.cache / sky.STAMP).read_text(encoding="utf-8"), "4\n")
        self.assertFalse((self.cache / sky.FAIL).exists())

    def test_already_showing_tonight_writes_only_the_stamp(self):
        text = WT_TEXT.replace("sky-1.png", "sky-4.png")
        self.settings.write_text(text, encoding="utf-8")
        before = self.settings.stat().st_mtime_ns
        self.run_job()
        self.assertEqual((self.settings.read_text(encoding="utf-8"), self.settings.stat().st_mtime_ns), (text, before))
        self.assertEqual((self.cache / sky.STAMP).read_text(encoding="utf-8"), "4\n")

    def test_windows_line_endings_survive(self):
        crlf = WT_TEXT.replace("\n", "\r\n")
        self.settings.write_bytes(crlf.encode("utf-8"))
        self.run_job()
        self.assertEqual(self.settings.read_bytes(),
                         crlf.replace("moonlit-candle-sky-1.png", "moonlit-candle-sky-4.png").encode("utf-8"))

    def test_the_stamp_is_written_before_the_lock_is_released(self):
        # a shell opening right after the job must see the new stamp, or it starts the job again
        stamp, real, seen = self.cache / sky.STAMP, sky._locked, []

        @contextmanager
        def locked(path):
            with real(path):
                yield
                seen.append(stamp.read_text(encoding="utf-8") if stamp.exists() else None)

        for case, image in (("moved", "sky-1.png"), ("already showing tonight", "sky-4.png")):
            with self.subTest(case):
                stamp.unlink(missing_ok=True)
                self.settings.write_text(WT_TEXT.replace("sky-1.png", image), encoding="utf-8")
                with mock.patch.object(sky, "_locked", locked):
                    self.run_job()
                self.assertEqual(seen.pop(), "4\n")

    def assert_failed(self, reason, text=WT_TEXT):
        self.assertEqual(self.settings.read_text(encoding="utf-8"), text)
        self.assertEqual((self.cache / sky.FAIL).read_text(encoding="utf-8"), "2026-10-26\n")
        self.assertIn(reason, log.last(self.cache / log.NAME))
        self.assertFalse((self.cache / sky.STAMP).exists())

    def test_the_file_mode_survives(self):
        self.settings.chmod(0o644)
        self.run_job()
        self.assertEqual(self.background(), wt.SKY_VALUES[4])
        self.assertEqual(stat.S_IMODE(self.settings.stat().st_mode), 0o644)

    def test_a_malformed_config_is_reported_as_such(self):
        config = self.home / sky.CONFIG
        data = json.loads(config.read_text(encoding="utf-8"))
        data["sky"] = "abc"
        config.write_text(json.dumps(data), encoding="utf-8")
        self.run_job()
        self.assertEqual((self.cache / sky.FAIL).read_text(encoding="utf-8"), "2026-10-26\n")
        self.assertIn("is not usable", log.last(self.cache / log.NAME))
        self.assertEqual(self.settings.read_text(encoding="utf-8"), WT_TEXT)

    def test_a_config_that_is_not_an_object_is_reported_as_such(self):
        (self.home / sky.CONFIG).write_text("[]", encoding="utf-8")
        self.run_job()
        self.assert_failed(f"{sky.CONFIG} is not usable: it must be a JSON object")

    def test_a_value_the_user_chose_is_left_alone(self):
        text = WT_TEXT.replace("ms-appdata:///local/moonlit-candle-sky-1.png", "C:\\\\pics\\\\cat.png")
        self.settings.write_text(text, encoding="utf-8")
        self.run_job()
        self.assert_failed("was changed by hand", text)

    def test_comments_are_never_rewritten(self):
        text = "// my settings\n" + WT_TEXT
        self.settings.write_text(text, encoding="utf-8")
        self.run_job()
        self.assert_failed("is not plain JSON", text)

    def test_a_missing_profile(self):
        text = WT_TEXT.replace(GUID, "{00000000-0000-0000-0000-000000000000}")
        self.settings.write_text(text, encoding="utf-8")
        self.run_job()
        self.assert_failed("not found", text)

    def test_a_value_that_appears_twice_is_not_rewritten(self):
        text = WT_TEXT.replace('"hidden": true,', '"backgroundImage": "ms-appdata:///local/moonlit-candle-sky-1.png",\n'
                                                  '                "hidden": true,')
        self.settings.write_text(text, encoding="utf-8")
        self.run_job()
        self.assert_failed("appears 2 times", text)

    def test_a_file_changed_during_the_job_is_not_overwritten(self):
        real, reads = Path.read_bytes, []

        def read_bytes(path):
            data = real(path)
            if path == self.settings and not reads:
                reads.append(path)
                path.write_text(WT_TEXT + " ", encoding="utf-8")  # another writer, right after our read
            return data

        with mock.patch.object(Path, "read_bytes", read_bytes):
            self.run_job()
        self.assert_failed("changed while the sky job ran", WT_TEXT + " ")

    def test_a_held_lock_fails_for_today(self):
        lock = self.cache / sky.LOCK
        lock.parent.mkdir(parents=True)
        with open(lock, "a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with mock.patch.object(sky, "LOCK_TIMEOUT", 0.2):
                self.run_job()
        self.assert_failed("held by another process")

    def test_the_fail_marker_stops_retries_until_tomorrow(self):
        self.cache.mkdir(parents=True)
        (self.cache / sky.FAIL).write_text("2026-10-26\n", encoding="utf-8")
        self.run_job()
        self.assertEqual(self.background(), wt.SKY_VALUES[1])
        self.run_job(FULL_MOON + timedelta(days=1))
        self.assertEqual(self.background(), wt.SKY_VALUES[moon.phase_bin(FULL_MOON + timedelta(days=1))])

    def test_a_corrupt_fail_marker_does_not_stop_the_job(self):
        self.cache.mkdir(parents=True)
        (self.cache / sky.FAIL).write_bytes(b"\xff\xfe2026")
        self.run_job()
        self.assertEqual(self.background(), wt.SKY_VALUES[4])
        self.assertEqual((self.cache / sky.STAMP).read_text(encoding="utf-8"), "4\n")

    def test_no_config_fails_quietly(self):
        (self.home / sky.CONFIG).unlink()
        self.run_job()
        self.assertTrue((self.cache / sky.FAIL).is_file())

    def test_shares_names_with_the_installer(self):
        self.assertEqual(sky.LOCK, windows_terminal.WT_LOCK)
        self.assertEqual(sky.CONFIG, windows_terminal.RITUAL_CONFIG)


if __name__ == "__main__":
    unittest.main()
