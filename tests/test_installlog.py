import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import fonts, installlog
from witchy.components.base import Command, ComponentFailed
from witchy.context import Context


class InstallLogTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)

    def ctx(self, stamp="20261005-120000", run=None):
        return Context(home=self.home, env={}, out=io.StringIO(), stamp=stamp, run=run or subprocess.run)

    def log(self):
        return (self.home / ".cache" / "witchy" / "install.log").read_text(encoding="utf-8")


class AppendTest(InstallLogTestCase):
    def test_one_header_per_run(self):
        installlog.append(self.ctx(), "first")
        installlog.append(self.ctx(), "second\n")
        installlog.append(self.ctx("20261005-130000"), "third")
        self.assertEqual(self.log(), "=== witchy install 20261005-120000 ===\nfirst\nsecond\n"
                                     "=== witchy install 20261005-130000 ===\nthird\n")

    def test_the_oldest_runs_go_first(self):
        for hour in range(10, 15):
            installlog.append(self.ctx(f"20261005-{hour}0000"), "x" * 60_000)
        log = self.log()
        self.assertLessEqual(len(log.encode("utf-8")), installlog.LIMIT)
        self.assertEqual(installlog.RUN.findall(log),
                         [f"=== witchy install 20261005-{hour}0000 ===" for hour in (12, 13, 14)])

    def test_a_run_too_large_alone_keeps_its_end_from_a_line_start(self):
        installlog.append(self.ctx(), "".join(f"line {number}\n" for number in range(40_000)))
        log = self.log()
        self.assertLessEqual(len(log.encode("utf-8")), installlog.LIMIT)
        self.assertTrue(log.startswith("line "))
        self.assertTrue(log.endswith("line 39999\n"))

    def test_a_log_that_cannot_be_written_is_no_error(self):
        (self.home / ".cache").write_text("a file where the folder should be", encoding="utf-8")
        installlog.append(self.ctx(), "lost")

    def test_shown_with_a_tilde(self):
        self.assertEqual(installlog.shown(self.ctx()), "~/.cache/witchy/install.log")


class RunTest(InstallLogTestCase):
    def test_logs_the_label_the_exit_code_and_the_output_without_colours(self):
        def run(args, **kwargs):
            return subprocess.CompletedProcess(args, 1, stdout="\x1b[1mfisher install version 4.4.5\x1b(B\x1b[m\n",
                                               stderr="fisher: Invalid plugin name or host unavailable\n")

        done = installlog.run(self.ctx(run=run), Command(("fish", "-c", "fisher install x"), "install Tide",
                                                         timeout=120))
        self.assertEqual(done.returncode, 1)
        self.assertEqual(self.log(), "=== witchy install 20261005-120000 ===\n--- install Tide (exit 1)\n"
                                     "fisher install version 4.4.5\nfisher: Invalid plugin name or host unavailable\n")

    def test_a_timeout_is_logged_and_still_raised(self):
        def run(args, **kwargs):
            raise subprocess.TimeoutExpired(args, kwargs["timeout"])

        with self.assertRaisesRegex(ComponentFailed, r"could not install Tide \(timed out after 120 s\)"):
            installlog.run(self.ctx(run=run), Command(("fish",), "install Tide", timeout=120))
        self.assertIn("--- install Tide: could not install Tide (timed out after 120 s)\n", self.log())

    def test_a_failure_names_the_last_error_line_and_the_log(self):
        done = subprocess.CompletedProcess([], 1, stdout="Fetching x\n",
                                           stderr="\x1b[31mfisher: Cannot install\x1b[m\n  conflict\n\n")
        self.assertEqual(installlog.failure(self.ctx(), "install Tide", done),
                         "could not install Tide (exit 1): conflict (details: ~/.cache/witchy/install.log)")
        quiet = subprocess.CompletedProcess([], 2, stdout="", stderr="")
        self.assertEqual(installlog.failure(self.ctx(), "install Tide", quiet),
                         "could not install Tide (exit 2) (details: ~/.cache/witchy/install.log)")


class DownloadTimeoutTest(unittest.TestCase):
    def test_downloads_wait_120_seconds(self):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b"data"
        with mock.patch("urllib.request.urlopen", return_value=response) as urlopen:
            self.assertEqual(fonts.fetch_url("https://example.invalid/x"), b"data")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 120)


if __name__ == "__main__":
    unittest.main()
