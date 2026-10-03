import fcntl
import re
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from witchy.ritual import log

WRITTEN = re.compile(r"^2026-10-31T21:00:00 greeting: ([AB]) ([0-9]{3}) x{200}$")


class LogTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "cache" / log.NAME

    def test_appends_one_line_per_error_and_keeps_the_last_twenty(self):
        for minute in range(25):
            log.append(self.path, f"greeting: boom {minute}\nsecond line", datetime(2026, 10, 31, 21, minute))
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), log.MAX_LINES)
        self.assertEqual(lines[-1], "2026-10-31T21:24:00 greeting: boom 24 second line")
        self.assertEqual(log.last(self.path), lines[-1])

    def test_no_log(self):
        self.assertIsNone(log.last(self.path))

    def test_an_unwritable_log_is_ignored(self):
        self.path.parent.parent.mkdir(parents=True, exist_ok=True)
        self.path.parent.write_text("a file, not a folder", encoding="utf-8")
        log.append(self.path, "boom", datetime(2026, 10, 31))  # must not raise

    def test_corrupt_utf8_in_log_is_ignored(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(b"\xff\xfe broken\n")
        # append must not raise when reading the corrupt log
        log.append(self.path, "new message", datetime(2026, 10, 31, 12, 0, 0))
        # last must not raise and should return None or a string
        result = log.last(self.path)
        self.assertIsNone(result)

    def test_a_long_message_is_cut(self):
        log.append(self.path, "greeting: UnicodeEncodeError(\n  " + "x" * 1000, datetime(2026, 10, 31, 21, 0))
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        message = ("greeting: UnicodeEncodeError( " + "x" * 1000)[:log.MAX_CHARS]  # whitespace collapsed, then cut
        self.assertEqual(lines[0], "2026-10-31T21:00:00 " + message)

    def test_the_entry_point_cuts_at_the_same_length(self):
        # __main__.py cannot import log (it may be what failed), so it repeats the numbers
        text = (Path(log.__file__).parent / "__main__.py").read_text(encoding="utf-8")
        self.assertEqual(re.search(r"^MAX_LINES = ([0-9]+)", text, re.M).group(1), str(log.MAX_LINES))
        self.assertEqual(re.search(r"^MAX_CHARS = ([0-9]+)", text, re.M).group(1), str(log.MAX_CHARS))

    def append_at_once(self, count):
        """Two writers append ``count`` lines each at the same time, like a greeting and a sky job."""
        def write(name):
            for number in range(count):
                log.append(self.path, f"greeting: {name} {number:03d} " + "x" * 200, datetime(2026, 10, 31, 21, 0))

        writers = [threading.Thread(target=write, args=(name,)) for name in "AB"]
        for writer in writers:
            writer.start()
        for writer in writers:
            writer.join()
        return self.path.read_text(encoding="utf-8").splitlines()

    def test_two_writers_at_once_lose_no_line(self):
        started = time.monotonic()
        with mock.patch.object(log, "MAX_LINES", 1000):
            lines = self.append_at_once(100)
        self.assertLess(time.monotonic() - started, 1.0)
        matches = [WRITTEN.match(line) for line in lines]
        self.assertTrue(all(matches), lines)
        for name in "AB":
            self.assertEqual([int(m.group(2)) for m in matches if m.group(1) == name], list(range(100)))

    def test_two_writers_at_once_keep_the_last_twenty(self):
        lines = self.append_at_once(50)
        self.assertEqual(len(lines), log.MAX_LINES)
        self.assertTrue(all(WRITTEN.match(line) for line in lines), lines)
        self.assertEqual(WRITTEN.match(lines[-1]).group(2), "049")  # the last append of either writer

    def test_a_held_lock_gives_up_quietly(self):
        self.path.parent.mkdir(parents=True)
        with open(self.path.with_name(self.path.name + ".lock"), "a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            with mock.patch.object(log, "LOCK_TIMEOUT", 0.05):
                log.append(self.path, "greeting: boom", datetime(2026, 10, 31))  # must not raise
        self.assertFalse(self.path.exists())
        log.append(self.path, "greeting: boom", datetime(2026, 10, 31))
        self.assertEqual(log.last(self.path), "2026-10-31T00:00:00 greeting: boom")


if __name__ == "__main__":
    unittest.main()
