import shutil
import subprocess
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from witchy import build, palette
from witchy.ritual import moon

FISH = shutil.which("fish")
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
                    "PATH": f"{self.python.parent}:/usr/bin:/bin"}

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
                 "VS Code": ({**self.WT, "TERM_PROGRAM": "vscode"}, True)}
        for label, (env, interactive) in cases.items():
            done = self.fish("fish_greeting", interactive=interactive, env=env)
            self.assertEqual((done.stdout, done.stderr), ("", ""), label)
            self.assertIsNone(self.python_args(), label)

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


class SkyJobStartTest(FishTestCase):
    WT = {"WT_SESSION": "f00d"}

    def setUp(self):
        super().setUp()
        (self.witchy / "ritual-config.json").write_text("{}", encoding="utf-8")
        self.cache.mkdir(parents=True)
        self.bin = moon.phase_bin(datetime.now(timezone.utc))

    def start_shell(self, env=None, interactive=True):
        return self.fish("true", interactive=interactive, env={**self.WT, **(env or {})})

    def wait_for_python(self):
        deadline = time.monotonic() + 5
        while self.python_args() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        return self.python_args()

    def test_starts_the_job_when_the_phase_moved(self):
        (self.cache / "sky-bin").write_text(f"{(self.bin + 1) % 8}\n", encoding="utf-8")
        done = self.start_shell()
        self.assertEqual((done.stdout, done.stderr), ("", ""))
        self.assertEqual(self.wait_for_python()[:4], ["-I", "-B", f"{self.witchy}/ritual", "--sky"])

    def test_starts_the_job_when_there_is_no_stamp_yet(self):
        self.start_shell()
        self.assertEqual(self.wait_for_python()[3], "--sky")

    def test_does_nothing_when_the_stamp_is_current(self):
        (self.cache / "sky-bin").write_text(f"{self.bin}\n", encoding="utf-8")
        self.start_shell()
        time.sleep(0.3)
        self.assertIsNone(self.python_args())

    def test_does_nothing_after_a_failure_today(self):
        (self.cache / "sky-fail").write_text(date.today().isoformat() + "\n", encoding="utf-8")
        self.start_shell()
        time.sleep(0.3)
        self.assertIsNone(self.python_args())

    def test_retries_the_day_after_a_failure(self):
        (self.cache / "sky-fail").write_text((date.today() - timedelta(days=1)).isoformat() + "\n", encoding="utf-8")
        self.start_shell()
        self.assertEqual(self.wait_for_python()[3], "--sky")

    def test_needs_an_interactive_windows_terminal_shell_and_the_config(self):
        self.start_shell(interactive=False)
        self.fish("true", interactive=True)  # no WT_SESSION
        (self.witchy / "ritual-config.json").unlink()
        self.start_shell()
        time.sleep(0.3)
        self.assertIsNone(self.python_args())


if __name__ == "__main__":
    unittest.main()
