import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from witchy.ritual import log


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


if __name__ == "__main__":
    unittest.main()
