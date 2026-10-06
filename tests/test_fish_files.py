import re
import shutil
import subprocess
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from witchy import build, palette
from witchy.ritual import caret, moon

FISH = shutil.which("fish")
# Where the tests look for tools: fish's own folder and the system ones, not the user's whole PATH.
TOOL_DIRS = list(dict.fromkeys([str(Path(FISH).parent) if FISH else "/usr/bin", "/usr/bin", "/bin"]))
NAMES = {"functions/fish_greeting.fish", "functions/ritual.fish", "functions/_witchy_moon_bin.fish",
         "functions/_tide_item_moon.fish", "functions/ll.fish", "functions/lt.fish", "conf.d/witchy.fish"}
# Stands in for Python: records its arguments and FISH_VERSION, and prints a line so callers can be heard.
STUB_PYTHON = """#!/bin/sh
printf '%s\\n' "$@" "FISH_VERSION=$FISH_VERSION" > "$HOME/python-args"
echo "python ran"
"""


class RenderTest(unittest.TestCase):
    def test_every_template_is_rendered_without_placeholders(self):
        files = build.fish_files("/usr/bin/python3", Path("/home/eimi/.claude/witchy"))
        self.assertEqual(set(files), NAMES)
        for name, data in files.items():
            self.assertNotIn("@", data.decode("utf-8"), name)

    def test_paths_are_quoted_for_fish(self):
        files = build.fish_files("/opt/py thon/bin/python3", Path("/home/o'neil/.claude/witchy"))
        greeting = files["functions/fish_greeting.fish"].decode("utf-8")
        self.assertIn("env FISH_VERSION=$FISH_VERSION '/opt/py thon/bin/python3' -I -B "
                      "'/home/o\\'neil/.claude/witchy'/ritual 2>/dev/null", greeting)

    def test_eza_colours_come_from_the_variant(self):
        self.assertEqual(build.eza_colors({**palette.EZA, "directory": "#B99AFF"}).split(":")[0], "di=38;2;185;154;255")
        codes = [part.split("=")[0] for part in build.eza_colors(palette.EZA).split(":")]
        self.assertEqual(codes, ["di", "ex", "ln", "sn", "sb", "da", "ga", "gm", "gv", "gt", "gd"])
        conf = build.fish_files("/usr/bin/python3", Path("/w"))["conf.d/witchy.fish"].decode("utf-8")
        self.assertIn(f"set -gx EZA_COLORS '{build.eza_colors(palette.EZA)}'", conf)

    def test_fish_quote(self):
        self.assertEqual(build.fish_quote("a b"), "'a b'")
        self.assertEqual(build.fish_quote("it's \\ here"), "'it\\'s \\\\ here'")


@unittest.skipUnless(FISH, "fish is not installed")
class FishTestCase(unittest.TestCase):
    """Runs the rendered files in a real fish, inside a throwaway HOME and XDG_CONFIG_HOME."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "my home"  # a space, so the quoting is exercised for real
        self.config = Path(tmp.name) / "config" / "fish"
        self.witchy = self.home / ".claude" / "witchy"
        self.cache = self.home / ".cache" / "witchy"
        (self.witchy / "ritual").mkdir(parents=True)
        # Today's caret cache, so no shell starts the caret job unless a test means it to.
        self.cache.mkdir(parents=True)
        self.write_caret(f"{date.today().isoformat()}\n")
        (self.witchy / "ritual" / "__main__.py").write_text("", encoding="utf-8")
        self.python = Path(tmp.name) / "bin" / "python3"
        self.python.parent.mkdir()
        self.python.write_text(STUB_PYTHON, encoding="utf-8")
        self.python.chmod(0o755)
        for name, data in build.fish_files(str(self.python), self.witchy).items():
            path = self.config / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config.parent), "TERM": "dumb",
                    "PATH": ":".join([str(self.python.parent), *TOOL_DIRS])}

    def write_caret(self, text):
        (self.cache / "caret").write_text(text, encoding="utf-8")

    def fish(self, script, *args, interactive=False, env=None):
        command = [FISH, *(["-i"] if interactive else []), "-c", script, "--", *args]
        return subprocess.run(command, capture_output=True, text=True, timeout=20, env={**self.env, **(env or {})},
                              stdin=subprocess.DEVNULL)

    def python_args(self):
        path = self.home / "python-args"
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else None


class SyntaxTest(FishTestCase):
    def test_every_file_parses(self):
        for name in NAMES:
            done = subprocess.run([FISH, "--no-execute", str(self.config / name)], capture_output=True, text=True,
                                  timeout=10, env=self.env)
            self.assertEqual((done.returncode, done.stderr), (0, ""), name)


class MoonBinTest(FishTestCase):
    def test_matches_the_python_moon_over_60_days_and_at_every_bin_edge(self):
        start = datetime(2026, 10, 3, tzinfo=timezone.utc)
        times = [start + timedelta(hours=3 * step) for step in range(60 * 8)]
        for edge in range(1, 33):
            middle = moon.EPOCH + timedelta(days=moon.SYNODIC_DAYS * (edge / 16) + moon.SYNODIC_DAYS * 324)
            times += [middle - timedelta(seconds=60), middle + timedelta(seconds=60)]
        seconds = [str(int(when.timestamp())) for when in times]
        done = self.fish("for t in $argv; _witchy_moon_bin $t; end", *seconds)
        self.assertEqual(done.stderr, "")
        expected = [str(moon.phase_bin(datetime.fromtimestamp(int(s), timezone.utc))) for s in seconds]
        self.assertEqual(done.stdout.split(), expected)

    def test_without_an_argument_it_uses_now(self):
        done = self.fish("_witchy_moon_bin")
        self.assertIn(done.stdout.strip(), {str(moon.phase_bin(datetime.now(timezone.utc) + timedelta(seconds=s)))
                                           for s in (-5, 5)})

    def test_the_tide_item_prints_the_glyph(self):
        done = self.fish("function _tide_print_item; echo $argv; end; _tide_item_moon")
        self.assertEqual(done.stdout.split(), ["moon", moon.GLYPHS[moon.phase_bin(datetime.now(timezone.utc))]])


class GreetingTest(FishTestCase):
    WT = {"WT_SESSION": "f00d"}

    def greet(self):
        return self.fish("fish_greeting; echo shown=$WITCHY_RITUAL_SHOWN", interactive=True, env=self.WT)

    def test_a_top_level_windows_terminal_shell_runs_the_package(self):
        done = self.greet()
        self.assertEqual(done.stdout, "python ran\nshown=1\n")
        args = self.python_args()
        self.assertEqual(args[:3], ["-I", "-B", f"{self.witchy}/ritual"])
        self.assertTrue(args[3].startswith("FISH_VERSION=3"), args)

    def test_quiet_unless_every_condition_holds(self):
        cases = {"not interactive": (self.WT, False), "no WT_SESSION": ({}, True),
                 "tmux": ({**self.WT, "TMUX": "/tmp/tmux"}, True), "Claude Code": ({**self.WT, "CLAUDECODE": "1"}, True),
                 "nested": ({**self.WT, "WITCHY_RITUAL_SHOWN": "1"}, True),
                 "VS Code": ({**self.WT, "TERM_PROGRAM": "vscode"}, True),
                 "doctor's shell": ({**self.WT, "WITCHY_DOCTOR": "1"}, True)}
        for label, (env, interactive) in cases.items():
            done = self.fish("fish_greeting", interactive=interactive, env=env)
            self.assertEqual((done.stdout, done.stderr), ("", ""), label)
            self.assertIsNone(self.python_args(), label)

    def test_the_doctors_new_shell_never_greets(self):
        # doctor reads the prompt variables with `fish -i -c`, which must stay silent (spec 9.1).
        done = self.fish("true", interactive=True, env={**self.WT, "WITCHY_DOCTOR": "1"})
        self.assertEqual((done.stdout, done.stderr), ("", ""))
        self.assertIsNone(self.python_args())

    def test_a_missing_package_prints_nothing_but_still_marks_the_shell(self):
        (self.witchy / "ritual" / "__main__.py").unlink()
        done = self.greet()
        self.assertEqual((done.stdout, done.stderr), ("shown=1\n", ""))

    def test_a_missing_python_prints_nothing(self):
        self.python.unlink()
        done = self.greet()
        self.assertEqual((done.stdout, done.stderr), ("shown=1\n", ""))

    def test_ritual_always_runs_the_full_ritual_with_its_arguments(self):
        done = self.fish("ritual --date 2026-10-31", env={"TMUX": "/tmp/tmux"})
        self.assertEqual(done.stdout, "python ran\n")
        self.assertEqual(self.python_args()[:5], ["-I", "-B", f"{self.witchy}/ritual", "--full", "--date"])


class ListingTest(FishTestCase):
    def setUp(self):
        super().setUp()
        self.folder = self.home / "folder"
        (self.folder / "inner").mkdir(parents=True)
        (self.folder / "inner" / "deep.txt").write_text("", encoding="utf-8")

    def test_without_eza_they_fall_back_to_ls(self):
        long = self.fish("ll $argv[1]", str(self.folder))
        self.assertIn("inner", long.stdout)
        self.assertRegex(long.stdout, r"(?m)^d")  # ls -la: one line per entry, directories start with d
        tree = self.fish("lt $argv[1]", str(self.folder))
        self.assertIn("deep.txt", tree.stdout)

    def test_with_eza_they_run_it(self):
        eza = self.python.parent / "eza"
        eza.write_text('#!/bin/sh\necho "eza $*"\n', encoding="utf-8")
        eza.chmod(0o755)
        self.assertEqual(self.fish("ll x").stdout, "eza -la --icons --group-directories-first --git x\n")
        self.assertEqual(self.fish("lt").stdout, "eza --tree --level=2 --icons\n")

    def test_eza_colours_are_exported(self):
        done = self.fish("printenv EZA_COLORS")
        self.assertEqual(done.stdout.strip(), build.eza_colors(palette.EZA))


class JobStartTestCase(FishTestCase):
    """Whether the job started is read from fish_trace, which prints every command before it runs. That is
    synchronous, so a job that was not started is a fact, not a timeout. The starting cases are the controls
    that prove the trace can see the job."""

    WT = {"WT_SESSION": "f00d"}

    def setUp(self):
        super().setUp()
        (self.witchy / "ritual-config.json").write_text("{}", encoding="utf-8")
        self.bin = moon.phase_bin(datetime.now(timezone.utc))

    def start_shell(self, env=None, interactive=True, session=True):
        return self.fish("true", interactive=interactive, env={**(self.WT if session else {}), **(env or {})})

    def sky_job_started(self, interactive=True, session=True, mode="--sky", env=None):
        """Starts a shell with tracing on and says whether it ran the job with ``mode``. It also checks that the
        trace saw the file that decides, so that an empty trace cannot pass for "did not start"."""
        done = self.start_shell({"fish_trace": "1", **(env or {})}, interactive, session)
        lines = done.stderr.splitlines()
        self.assertTrue(any(re.search(r"source .*conf\.d/witchy\.fish$", line) for line in lines), done.stderr[-500:])
        return any(re.search(rf"^-+> .*/ritual'? {mode}$", line) for line in lines)

    def wait_for_python(self):
        deadline = time.monotonic() + 5
        while self.python_args() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        return self.python_args()


class SkyJobStartTest(JobStartTestCase):
    def test_starts_the_job_when_the_phase_moved(self):
        (self.cache / "sky-bin").write_text(f"{(self.bin + 1) % 8}\n", encoding="utf-8")
        done = self.start_shell()
        self.assertEqual((done.stdout, done.stderr), ("", ""))
        self.assertEqual(self.wait_for_python()[:4], ["-I", "-B", f"{self.witchy}/ritual", "--sky"])
        (self.home / "python-args").unlink()
        self.assertTrue(self.sky_job_started())

    def test_starts_the_job_when_there_is_no_stamp_yet(self):
        self.assertTrue(self.sky_job_started())
        self.assertEqual(self.wait_for_python()[3], "--sky")

    def test_does_nothing_when_the_stamp_is_current(self):
        (self.cache / "sky-bin").write_text(f"{self.bin}\n", encoding="utf-8")
        self.assertFalse(self.sky_job_started())
        self.assertIsNone(self.python_args())

    def test_does_nothing_after_a_failure_today(self):
        (self.cache / "sky-fail").write_text(date.today().isoformat() + "\n", encoding="utf-8")
        self.assertFalse(self.sky_job_started())
        self.assertIsNone(self.python_args())

    def test_retries_the_day_after_a_failure(self):
        (self.cache / "sky-fail").write_text((date.today() - timedelta(days=1)).isoformat() + "\n", encoding="utf-8")
        self.assertTrue(self.sky_job_started())
        self.assertEqual(self.wait_for_python()[3], "--sky")

    def test_the_doctors_new_shell_never_starts_the_job(self):
        self.assertTrue(self.sky_job_started())  # the control: a normal shell starts it
        self.wait_for_python()
        done = self.start_shell({"fish_trace": "1", "WITCHY_DOCTOR": "1"})
        self.assertTrue(any(re.search(r"source .*conf\.d/witchy\.fish$", line) for line in done.stderr.splitlines()))
        self.assertFalse(any(re.search(r"^-+> .*/ritual'? --sky$", line) for line in done.stderr.splitlines()))

    def test_needs_an_interactive_windows_terminal_shell_and_the_config(self):
        self.assertFalse(self.sky_job_started(interactive=False))
        self.assertFalse(self.sky_job_started(session=False))
        (self.witchy / "ritual-config.json").unlink()
        self.assertFalse(self.sky_job_started())
        self.assertIsNone(self.python_args())


class CaretJobStartTest(JobStartTestCase):
    """The same job, started once a day for the caret cache (prompt takeover spec 15.3)."""

    def setUp(self):
        super().setUp()
        (self.cache / "sky-bin").write_text(f"{self.bin}\n", encoding="utf-8")  # the sky is current
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        self.write_caret(f"{yesterday}\n{date.today().isoformat()}\n")

    def test_starts_the_caret_job_when_the_cache_is_not_from_today(self):
        self.assertTrue(self.sky_job_started(mode="--caret"))
        self.assertEqual(self.wait_for_python()[:4], ["-I", "-B", f"{self.witchy}/ritual", "--caret"])

    def test_starts_it_outside_windows_terminal_and_without_the_sky_config(self):
        (self.witchy / "ritual-config.json").unlink()
        self.assertTrue(self.sky_job_started(session=False, mode="--caret"))

    def test_starts_it_when_there_is_no_cache_yet(self):
        (self.cache / "caret").unlink()
        self.assertTrue(self.sky_job_started(mode="--caret"))

    def test_a_moved_phase_starts_only_the_sky_job_which_writes_the_caret_too(self):
        (self.cache / "sky-bin").write_text(f"{(self.bin + 1) % 8}\n", encoding="utf-8")
        self.assertTrue(self.sky_job_started())
        self.assertFalse(self.sky_job_started(mode="--caret"))

    def test_nothing_after_a_failure_today_in_the_doctors_shell_or_a_non_interactive_one(self):
        (self.cache / "sky-fail").write_text(date.today().isoformat() + "\n", encoding="utf-8")
        self.assertFalse(self.sky_job_started(mode="--caret"))
        (self.cache / "sky-fail").unlink()
        self.assertFalse(self.sky_job_started(mode="--caret", env={"WITCHY_DOCTOR": "1"}))
        self.assertFalse(self.sky_job_started(mode="--caret", interactive=False))
        self.assertIsNone(self.python_args())

    def test_nothing_without_python_or_the_greeting_package(self):
        (self.witchy / "ritual" / "__main__.py").unlink()
        self.assertFalse(self.sky_job_started(mode="--caret"))
        self.python.unlink()
        self.assertFalse(self.sky_job_started(mode="--caret"))


class CaretTest(FishTestCase):
    """conf.d/witchy.fish sets the caret colour from today's line of the cache, in every shell that reads conf.d."""

    def caret(self, interactive=False, env=None):
        done = self.fish("set -q -U tide_character_color; and echo universal; "
                         "set -q -g tide_character_color; and echo $tide_character_color; or echo gold",
                         interactive=interactive, env=env)
        self.assertEqual(done.stderr, "")
        return done.stdout.strip()

    def day(self, offset=0):
        return (date.today() + timedelta(days=offset)).isoformat()

    def test_todays_line_sets_a_global_in_tides_child_shell_and_in_a_new_tab(self):
        self.write_caret(f"{self.day()} FFB86B samhain\n{self.day(1)}\n")
        self.assertEqual(self.caret(), "FFB86B")  # Tide draws the prompt in a non-interactive fish -c
        self.assertEqual(self.caret(interactive=True), "FFB86B")
        self.assertEqual(self.caret(interactive=True, env={"WITCHY_DOCTOR": "1"}), "FFB86B")

    def test_yesterdays_second_line_covers_the_first_shell_of_today(self):
        self.write_caret(f"{self.day(-1)} FFB86B samhain\n{self.day()} FFB86B samhain\n")
        self.assertEqual(self.caret(), "FFB86B")

    def test_other_days_leave_it_gold(self):
        for text in (f"{self.day(-1)} FFB86B samhain\n{self.day()}\n", f"{self.day(-2)} FFB86B samhain\n",
                     f"{self.day(1)} FFB86B samhain\n", f"{self.day()}\n{self.day(1)} FFB86B samhain\n"):
            with self.subTest(text=text):
                self.write_caret(text)
                self.assertEqual(self.caret(), "gold")

    def test_a_damaged_cache_leaves_it_gold(self):
        for text in (f"{self.day()} #FFB86B samhain\n", f"{self.day()} ffb86b samhain\n",
                     f"{self.day()} FFB86B; echo hacked\n", f"{self.day()} (echo FFB86B)\n", "", "\n\n",
                     f"\xff\xfe {self.day()} FFB86B\n"):
            with self.subTest(text=text):
                self.write_caret(text)
                self.assertEqual(self.caret(), "gold")

    def test_samhain_eve_and_day_are_amber_and_the_day_after_gold(self):
        """Acceptance criterion 10: the cache the job wrote, read by a shell on a later day or the same one."""
        fake = Path(self.home.parent) / "fake-date"
        fake.mkdir()
        cases = (("2026-10-29", "2026-10-30", "FFB86B"), ("2026-10-30", "2026-10-30", "FFB86B"),
                 ("2026-10-31", "2026-10-31", "FFB86B"), ("2026-10-31", "2026-11-01", "gold"),
                 ("2026-11-01", "2026-11-01", "gold"))
        for written, today, expected in cases:
            with self.subTest(written=written, today=today):
                caret.write(self.cache / "caret", date.fromisoformat(written), None)
                (fake / "date").write_text(f"#!/bin/sh\necho {today}\n", encoding="utf-8")
                (fake / "date").chmod(0o755)
                self.assertEqual(self.caret(env={"PATH": f"{fake}:{self.env['PATH']}"}), expected)

    def test_a_missing_or_unreadable_cache_leaves_it_gold(self):
        (self.cache / "caret").unlink()
        self.assertEqual(self.caret(), "gold")
        (self.cache / "caret").mkdir()
        self.assertEqual(self.caret(), "gold")
        (self.cache / "caret").rmdir()
        self.write_caret(f"{self.day()} FFB86B samhain\n")
        (self.cache / "caret").chmod(0)
        self.addCleanup((self.cache / "caret").chmod, 0o644)
        self.assertEqual(self.caret(), "gold")


if __name__ == "__main__":
    unittest.main()
