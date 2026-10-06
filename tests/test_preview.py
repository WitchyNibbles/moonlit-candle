import io
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from witchy import __main__ as cli
from witchy import build, palette, preview, validate

GOLDEN = Path(__file__).resolve().parent / "golden"
NOW = datetime(2026, 10, 31, 21, 13, tzinfo=timezone.utc)  # a waning moon, 🌗
TIDE = {name: value if isinstance(value, str) else " ".join(value) for name, value in build.tide().items()}
COLOUR = re.compile(r"\x1b\[[34]8;2;(\d+);(\d+);(\d+)m")


def plain(line):
    return preview.ESCAPE.sub("", line)


def colours(text):
    return {"%02X%02X%02X" % tuple(int(part) for part in match) for match in COLOUR.findall(text)}


def sample(name):
    return next(sample for sample in preview.SAMPLES if sample.name == name)


class GoldenTest(unittest.TestCase):
    def test_every_sample_matches_its_golden_file(self):
        self.assertEqual([s.name for s in preview.SAMPLES], ["home", "git", "unwritable", "failed", "jobs"])
        for found in preview.SAMPLES:
            with self.subTest(sample=found.name):
                expected = (GOLDEN / f"prompt-{found.name}.txt").read_text(encoding="utf-8").splitlines()
                self.assertEqual(preview.prompt(TIDE, found, NOW, 80), expected)


class PromptTest(unittest.TestCase):
    def lines(self, name, columns=80):
        return preview.prompt(TIDE, sample(name), NOW, columns)

    def test_each_state_shows_its_items(self):
        left = (TIDE["tide_left_prompt_prefix"], TIDE["tide_left_prompt_separator_diff_color"],
                TIDE["tide_left_prompt_suffix"])
        right = (TIDE["tide_right_prompt_prefix"], TIDE["tide_right_prompt_suffix"])
        expected = {
            "home": ["{} 🌗 {} 🔮 ~ {}".format(*left), "{} 21:13 🦉 {}".format(*right)],
            "git": ["🧹 ~/projects/witchyterm", "🌿 main !2 ?1"],
            "unwritable": ["🪦 /etc/ssl"],
            "failed": ["🌿 main", "💀 2", "🔥 4s", "21:13 🦉"],
            "jobs": ["🧹 ~/projects", " 🐈 ", "21:13 🦉"],
        }
        for name, parts in expected.items():
            with self.subTest(sample=name):
                top, bottom = (plain(line) for line in self.lines(name))
                self.assertTrue(top.startswith("╭─") and top.endswith("─╮"), top)
                self.assertTrue(bottom.startswith("╰─❯ ") and bottom.endswith("─╯"), bottom)
                for part in parts:
                    self.assertIn(part, top)

    def test_items_that_show_nothing_are_left_out(self):
        top = plain(self.lines("home")[0])
        for glyph in ("🌿", "💀", "🧪", "🔥", "🐈"):
            self.assertNotIn(glyph, top)

    def test_the_caret_is_gold_and_rose_red_after_a_failure(self):
        gold, red = preview.fg(TIDE["tide_character_color"]), preview.fg(TIDE["tide_character_color_failure"])
        self.assertIn(gold + "❯", self.lines("home")[1])
        self.assertIn(red + "❯", self.lines("failed")[1])

    def test_a_dirty_repository_takes_the_unstable_background(self):
        self.assertIn(preview.bg(TIDE["tide_git_bg_color_unstable"]), self.lines("git")[0])
        self.assertIn(preview.bg(TIDE["tide_git_bg_color"]), self.lines("failed")[0])

    def test_every_line_fills_the_terminal_exactly(self):
        for columns in (80, 120):
            for found in preview.SAMPLES:
                with self.subTest(columns=columns, sample=found.name):
                    self.assertEqual([preview.width(line) for line in self.lines(found.name, columns)],
                                     [columns, columns])

    def test_a_narrow_terminal_gets_no_connection_dots(self):
        top = plain(self.lines("git", 40)[0])
        self.assertNotIn(TIDE["tide_prompt_icon_connection"], top)

    def test_every_colour_comes_from_the_prompt_and_none_is_pastel(self):
        text = "".join(line for found in preview.SAMPLES for line in preview.prompt(TIDE, found, NOW, 80))
        values = {value for value in TIDE.values() if re.fullmatch(r"[0-9A-F]{6}", value)}
        self.assertLessEqual(colours(text), values)
        self.assertFalse([part for part in colours(text) | set(plain(text)) if validate.is_pastel(part)])

    def test_durations(self):
        self.assertEqual([preview.duration(ms) for ms in (4321, 65000, 3723000)], ["4s", "1m 5s", "1h 2m 3s"])


class CommandTest(unittest.TestCase):
    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch("subprocess.run", side_effect=AssertionError("preview runs nothing")), \
                mock.patch("pathlib.Path.home", return_value=Path(tmp)), \
                mock.patch("shutil.get_terminal_size", return_value=mock.Mock(columns=100)), \
                redirect_stdout(out), redirect_stderr(err):
            try:
                code = cli.main(argv)
            except SystemExit as exc:
                code = exc.code
            self.assertEqual(list(Path(tmp).iterdir()), [])  # writes nothing
        return code, out.getvalue(), err.getvalue()

    def test_preview_prints_every_sample_and_exits_0(self):
        code, out, _ = self.run_cli(["preview"])
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(lines[0], "Moonlit Candle prompt (midnight), drawn from the palette; a sketch, Tide itself "
                                   "does not run.")
        for found in preview.SAMPLES:
            self.assertIn(found.title, lines)
        self.assertEqual({preview.width(line) for line in lines if line.startswith("\x1b")}, {100})

    def test_a_variant_can_be_named(self):
        self.assertEqual(self.run_cli(["preview", "--variant", "midnight"])[0], 0)
        code, _, err = self.run_cli(["preview", "--variant", "noon"])
        self.assertEqual(code, 2)
        self.assertIn("invalid choice: 'noon'", err)


if __name__ == "__main__":
    unittest.main()
