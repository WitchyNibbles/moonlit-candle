import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import statusline

ANSI = re.compile(r"\x1b\[[0-9;]*m")
P = statusline.PALETTE
FULL = {
    "model": {"display_name": "Opus 5.5 (1M context)"},
    "effort": {"level": "xhigh"},
    "context_window": {"used_percentage": 48},
    "rate_limits": {"five_hour": {"used_percentage": 29}, "seven_day": {"used_percentage": 12}},
}
EMPTY_LINE = " 🕯️ -- ⋆ 🌑 -- ⋆ 5h -- ⋆ 7d -- \n"


def plain(text):
    return ANSI.sub("", text)


def fg(hex_colour):
    red, green, blue = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return f"\x1b[38;2;{red};{green};{blue}m"


def run(text):
    out = io.StringIO()
    code = statusline.main(io.StringIO(text), out)
    return code, out.getvalue()


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "init.defaultBranch=main", *args],
                   cwd=cwd, check=True, capture_output=True)


class RenderTest(unittest.TestCase):
    def test_full_payload_outside_a_repo(self):
        with tempfile.TemporaryDirectory() as directory:
            code, out = run(json.dumps(dict(FULL, workspace={"current_dir": directory})))
        self.assertEqual(code, 0)
        self.assertEqual(plain(out), " 🕯️ Opus 5.5·xhigh ⋆ 🌓 48% ⋆ 5h 71% ⋆ 7d 88% \n")

    def test_empty_null_and_invalid_payloads(self):
        for text in ("", "null", "{", "[1, 2]", '"x"', "{}"):
            code, out = run(text)
            self.assertEqual(code, 0, text)
            self.assertEqual(plain(out), EMPTY_LINE, text)

    def test_wrong_types_read_as_dashes(self):
        payload = {"model": {"display_name": 5}, "effort": {"level": ""},
                   "context_window": {"used_percentage": "48"},
                   "rate_limits": {"five_hour": {"used_percentage": True}, "seven_day": []}}
        self.assertEqual(plain(run(json.dumps(payload))[1]), EMPTY_LINE)

    def test_nan_reads_as_a_dash(self):
        self.assertEqual(plain(run('{"context_window": {"used_percentage": NaN}}')[1]), EMPTY_LINE)

    def test_weird_nesting_never_raises(self):
        statusline.render({"model": [], "context_window": [], "rate_limits": {"five_hour": []},
                           "workspace": {"current_dir": 7}, "cwd": None})

    def test_model_without_effort(self):
        self.assertTrue(plain(statusline.render({"model": {"display_name": "Sonnet 5.5"}})).startswith(" 🕯️ Sonnet 5.5 ⋆ "))

    def test_moon_boundaries(self):
        cases = [(None, "🌑"), (0, "🌑"), (12, "🌑"), (12.4, "🌑"), (12.6, "🌒"), (13, "🌒"), (37, "🌒"),
                 (38, "🌓"), (62, "🌓"), (63, "🌔"), (87, "🌔"), (88, "🌕"), (100, "🌕")]
        for used, glyph in cases:
            self.assertEqual(statusline.moon(used), glyph, used)

    def test_context_colour_thresholds(self):
        for used, key, bold in ((49, "context_low", False), (50, "context_mid", False),
                                (79, "context_mid", False), (80, "context_high", True)):
            out = statusline.render({"context_window": {"used_percentage": used}})
            painted = fg(P[key]) + f"{used}%"
            self.assertIn(painted, out, used)
            self.assertEqual("\x1b[1m" + painted in out, bold, used)

    def test_remaining_colour_thresholds(self):
        for used, left, key, bold in ((49, 51, "left_high", False), (50, 50, "left_mid", False),
                                      (79, 21, "left_mid", False), (80, 20, "left_low", True)):
            out = statusline.render({"rate_limits": {"five_hour": {"used_percentage": used}}})
            painted = fg(P[key]) + f"{left}%"
            self.assertIn(painted, out, used)
            self.assertEqual("\x1b[1m" + painted in out, bold, used)


class GitSegmentTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "spellbook"
        self.repo.mkdir()
        git(self.repo, "init")
        (self.repo / "a.txt").write_text("a")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "init")

    def line(self, payload=None):
        return plain(statusline.render(payload or {"workspace": {"current_dir": str(self.repo)}}))

    def test_clean_repo(self):
        self.assertTrue(self.line().endswith(" ⋆ 📜 spellbook 🌿 main "), self.line())

    def test_dirty_repo_counts_changes(self):
        (self.repo / "a.txt").write_text("changed")
        (self.repo / "b.txt").write_text("new")
        self.assertTrue(self.line().endswith("🌿 main✦2 "), self.line())

    def test_long_branch_is_cut_to_28(self):
        name = "feature/INC-98560-notificacion-juzgado"
        git(self.repo, "checkout", "-b", name)
        self.assertTrue(self.line().endswith(f"🌿 {name[:27]}… "), self.line())

    def test_detached_head_shows_the_short_hash(self):
        git(self.repo, "checkout", "--detach")
        short = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=self.repo,
                               capture_output=True, text=True, check=True).stdout.strip()
        self.assertTrue(self.line().endswith(f"🌿 {short} "), self.line())

    def test_subdirectory_shows_the_repo_root_name(self):
        deep = self.repo / "deep"
        deep.mkdir()
        self.assertIn("📜 spellbook", self.line({"workspace": {"current_dir": str(deep)}}))

    def test_cwd_is_the_fallback(self):
        self.assertIn("📜 spellbook", self.line({"cwd": str(self.repo)}))

    def test_missing_directory_hides_git(self):
        self.assertNotIn("📜", self.line({"workspace": {"current_dir": "/nonexistent/witchy"}}))

    def test_the_branch_glyph_is_the_herb(self):
        self.assertIn("📜 spellbook 🌿 main", self.line())

    def test_git_segment_colours(self):
        out = statusline.render({"workspace": {"current_dir": str(self.repo)}})
        self.assertIn(fg(P["repo"]) + "📜 spellbook", out)
        self.assertIn(fg(P["branch"]) + "🌿 main", out)

    def assert_git_segment_hidden(self, *failing_args, result=None):
        """Make one git call fail (None) or come back empty inside a real repo; the segment must vanish."""
        real = statusline._git

        def fake(cwd, *args):
            return result if args == failing_args else real(cwd, *args)

        payload = dict(FULL, workspace={"current_dir": str(self.repo)})
        with mock.patch.object(statusline, "_git", side_effect=fake):
            line = plain(statusline.render(payload))
        self.assertNotIn("📜", line)
        self.assertNotIn("🌿", line)
        self.assertTrue(line.endswith(" ⋆ 7d 88% "), line)

    def test_branch_lookup_failure_hides_git(self):
        self.assert_git_segment_hidden("branch", "--show-current")

    def test_detached_head_without_a_short_hash_hides_git(self):
        git(self.repo, "checkout", "--detach")
        for result in (None, ""):
            with self.subTest(result=result):
                self.assert_git_segment_hidden("rev-parse", "--short", "HEAD", result=result)

    def test_status_failure_hides_git(self):
        self.assert_git_segment_hidden("status", "--porcelain")


class ProcessTest(unittest.TestCase):
    SCRIPT = str(Path(statusline.__file__))

    def test_runs_as_a_script_under_the_c_locale(self):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C", "LC_ALL": "C"}
        # utf8=0: Python switches to UTF-8 mode by itself under the C locale, which would hide a missing reconfigure.
        done = subprocess.run([sys.executable, "-I", "-X", "utf8=0", self.SCRIPT],
                              input=json.dumps(FULL).encode("utf-8"), capture_output=True, env=env, timeout=10)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("🌓".encode("utf-8"), done.stdout)
        self.assertTrue(done.stdout.endswith(b"\n"))

    def test_empty_and_closed_stdin_exit_zero(self):
        # The second command closes fd 0, so sys.stdin is None inside the script.
        commands = {
            "devnull": ([sys.executable, "-I", self.SCRIPT], subprocess.DEVNULL),
            "closed": (["/bin/sh", "-c", 'exec "$0" -I "$1" <&-', sys.executable, self.SCRIPT], None),
        }
        for name, (argv, stdin) in commands.items():
            with self.subTest(name):
                done = subprocess.run(argv, stdin=stdin, capture_output=True, timeout=10)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(plain(done.stdout.decode("utf-8")), EMPTY_LINE)
                self.assertEqual(done.stderr, b"")

    def test_reader_that_went_away_still_exits_zero(self):
        proc = subprocess.Popen([sys.executable, "-I", self.SCRIPT], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc.stdout.close()  # the script is still waiting for stdin, so its write hits a broken pipe
        _, stderr = proc.communicate(json.dumps(FULL).encode("utf-8"), timeout=10)
        self.assertEqual(proc.returncode, 0, stderr)
        self.assertEqual(stderr, b"")


class StreamTest(unittest.TestCase):
    def test_missing_stdin_reads_as_no_payload(self):
        out = io.StringIO()
        with mock.patch.object(sys, "stdin", None):
            self.assertEqual(statusline.main(None, out), 0)
        self.assertEqual(plain(out.getvalue()), EMPTY_LINE)

    def test_stream_that_cannot_be_reconfigured_is_used_as_is(self):
        out = io.StringIO()  # has no reconfigure()
        with mock.patch.object(sys, "stdin", io.StringIO("{}")):
            self.assertEqual(statusline.main(None, out), 0)
        self.assertEqual(plain(out.getvalue()), EMPTY_LINE)

    def test_broken_pipe_still_exits_zero(self):
        for method in ("write", "flush"):
            with self.subTest(method):
                out = mock.Mock(spec=io.StringIO)
                getattr(out, method).side_effect = BrokenPipeError
                self.assertEqual(statusline.main(io.StringIO("{}"), out), 0)


if __name__ == "__main__":
    unittest.main()
