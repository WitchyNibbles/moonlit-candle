import io
import json
import os
import re
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from witchy.ritual import cli, layout, palette, sky, wheel

CET = timezone(timedelta(hours=1))
CEST = timezone(timedelta(hours=2))
SAMHAIN_NIGHT = datetime(2026, 10, 31, 21, 30, tzinfo=CET)
ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
PLAIN = {"NO_COLOR": "1", "FISH_VERSION": "3.7.0"}
LOG_LINE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d greeting: bad arguments: (.*)$")


class Terminal(io.StringIO):
    """A stderr that a person reads."""

    def isatty(self):
        return True


class CliTestCase(unittest.TestCase):
    def setUp(self):
        login = mock.patch.dict(os.environ, {"LOGNAME": "wren"})
        login.start()
        self.addCleanup(login.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        self.root = Path(tmp.name) / "root"
        (self.root / "etc").mkdir(parents=True)
        (self.root / "etc" / "os-release").write_text('PRETTY_NAME="Ubuntu 24.04.4 LTS"\n', encoding="utf-8")

    def run_cli(self, argv=(), env=None, now=SAMHAIN_NIGHT, columns=100):
        out = io.StringIO()
        code = cli.main(list(argv), env=PLAIN if env is None else env, out=out, now=now, home=self.home,
                        root=self.root, columns=columns)
        self.assertEqual(code, 0)
        return out.getvalue()

    def bad_arguments(self, argv, tty=False):
        """Run with arguments argparse rejects; return what went to stderr."""
        err = Terminal() if tty else io.StringIO()
        with mock.patch("sys.stderr", err), self.assertRaises(SystemExit) as caught:
            cli.main(list(argv), env=PLAIN, out=io.StringIO(), now=SAMHAIN_NIGHT, home=self.home, root=self.root)
        self.assertEqual(caught.exception.code, 2)
        return err.getvalue()

    @property
    def stamp(self):
        return self.home / ".cache" / "witchy" / cli.STAMP

    @property
    def log(self):
        return self.home / ".cache" / "witchy" / "ritual.log"


class FullRitualTest(CliTestCase):
    def test_side_by_side_at_100_columns(self):
        lines = self.run_cli(["--full"]).splitlines()
        self.assertEqual(lines[-1], "")  # one blank line after the greeting
        info = [line[31:] for line in lines if len(line) > 31]
        self.assertIn("Good evening, wren", info)
        self.assertIn("🕯️ Samhain — the veil is thin tonight", info)
        self.assertIn("✦ XVII · The Star", info)
        self.assertIn("  hope and renewal after the storm", info)
        self.assertIn("os      Ubuntu 24.04.4 LTS", info)
        self.assertIn("shell   fish 3.7.0", info)
        self.assertTrue(any("░" in line[:28] for line in lines))

    def test_stacked_at_70_and_info_only_at_39(self):
        stacked = self.run_cli(["--full"], columns=70).splitlines()
        self.assertTrue(all("░" in line or "▒" in line for line in stacked[1:10]))  # the art first
        self.assertEqual(stacked[11:13], ["", "Good evening, wren"])  # then a blank line and the info
        narrow = self.run_cli(["--full"], columns=39).splitlines()
        self.assertEqual(narrow[0], "Good evening, wren")
        self.assertFalse(any("░" in line for line in narrow))

    def test_no_line_is_wider_than_the_terminal(self):
        for columns in (100, 80, 70, 40, 39, 30):
            for when in (SAMHAIN_NIGHT, datetime(2026, 5, 31, 23, 0, tzinfo=CEST)):
                with self.subTest(columns=columns, when=when):
                    for line in self.run_cli(["--full"], now=when, columns=columns).splitlines():
                        self.assertLessEqual(layout.cell_width(line), columns, line)

    def test_countdown_lunar_line_and_salutations(self):
        text = self.run_cli(["--full"], now=datetime(2026, 10, 26, 8, 0, tzinfo=CET))
        self.assertIn("Good morning, wren", text)
        self.assertIn("⋆ Samhain in 5 days", text)
        self.assertIn("🌕 Full moon — charge your crystals", text)
        self.assertIn("⋆ Samhain tomorrow", self.run_cli(["--full"], now=datetime(2026, 10, 30, 13, 0, tzinfo=CET)))
        blue = self.run_cli(["--full"], now=datetime(2026, 5, 31, 2, 0, tzinfo=CEST))
        self.assertIn("Good witching hour, wren", blue)
        self.assertIn("🌕 Blue moon — a rare moon; make a bold wish", blue)

    def test_the_greeting_names_the_login_from_the_environment(self):
        with mock.patch.dict(os.environ, {"LOGNAME": "sparrow"}):
            self.assertIn("Good evening, sparrow", self.run_cli(["--full"]))

    def test_no_login_name_leaves_the_salutation_alone(self):
        for failure in (OSError("no passwd entry"), KeyError("uid")):
            with self.subTest(failure=failure), mock.patch.object(cli.getpass, "getuser", side_effect=failure):
                text = self.run_cli(["--full"])
                self.assertIn("Good evening", text)
                self.assertNotIn("Good evening,", text)

    def test_a_name_with_nothing_printable_leaves_the_salutation_alone(self):
        with mock.patch.dict(os.environ, {"LOGNAME": "\x1b\x07 \t"}):
            text = self.run_cli(["--full"])
        self.assertIn("Good evening", text)
        self.assertNotIn("Good evening,", text)

    def test_control_characters_are_stripped_from_the_name(self):
        with mock.patch.dict(os.environ, {"LOGNAME": "wr\x1b[2Jen\x07"}):
            text = self.run_cli(["--full"])
        self.assertIn("Good evening, wr[2Jen", text)
        self.assertNotIn("\x07", text)
        self.assertNotIn("\x1b[2J", text)

    def test_a_long_name_is_cut_to_the_limit(self):
        with mock.patch.dict(os.environ, {"LOGNAME": "w" * 40}):
            text = self.run_cli(["--full"])
        self.assertIn("Good evening, " + "w" * cli.NAME_MAX, text)
        self.assertNotIn("w" * (cli.NAME_MAX + 1), text)

    def test_salutation_hours(self):
        expected = {0: "Good witching hour", 3: "Good witching hour", 4: "Good morning", 11: "Good morning",
                    12: "Good afternoon", 17: "Good afternoon", 18: "Good evening", 23: "Good evening"}
        self.assertEqual({hour: cli.salutation(hour) for hour in expected}, expected)

    def test_colours_and_the_sabbat_accent(self):
        text = self.run_cli(["--full"], env={"FISH_VERSION": "3.7.0"})
        self.assertIn("\x1b[1;38;2;255;184;107mGood evening, wren", text)  # Samhain's accent, bold
        self.assertIn("\x1b[38;2;255;103;183m✦ XVII · The Star", text)
        plain = self.run_cli(["--full"], env={"FISH_VERSION": "3.7.0"}, now=datetime(2026, 10, 3, 9, tzinfo=CEST))
        self.assertIn("\x1b[1;38;2;255;212;119mGood morning, wren", plain)

    def test_every_sabbat_day_shows_its_line(self):
        for name, day in wheel.sabbat_dates(2026, CET).items():
            now = datetime.combine(day, SAMHAIN_NIGHT.timetz())
            text = self.run_cli(["--full"], env={"FISH_VERSION": "3.7.0"}, now=now)
            self.assertIn(f"🕯️ {name} —", ESCAPE.sub("", text))

    def test_no_color(self):
        self.assertNotRegex(self.run_cli(["--full"]), ESCAPE)
        self.assertNotRegex(self.run_cli(["--omen"]), ESCAPE)

    def test_the_date_flag_previews_another_day(self):
        text = self.run_cli(["--full", "--date", "2026-10-26"], now=datetime(2026, 10, 3, 21, 30, tzinfo=CET))
        self.assertIn("⋆ Samhain in 5 days", text)


class OmenTest(CliTestCase):
    def test_candle_dirty_and_separator_come_from_the_glyph_table(self):
        with mock.patch.dict(palette.GLYPHS, {"candle": "C", "dirty": "D", "separator": "S"}):
            self.assertEqual(self.run_cli(["--omen"]), "🌗 Last Quarter 67% · D The Star · C Samhain\n\n")
            text = self.run_cli(["--full"], now=datetime(2026, 10, 26, 8, 0, tzinfo=CET))
        self.assertIn("S Samhain in 5 days", text)
        self.assertIn("S Full  100%", text)
        self.assertIn("D XV · The Devil", text)

    def test_one_line(self):
        self.assertEqual(self.run_cli(["--omen"]),
                         "🌗 Last Quarter 67% · ✦ The Star · 🕯️ Samhain\n\n")
        text = self.run_cli(["--omen"], now=datetime(2026, 10, 26, 8, 0, tzinfo=CET))
        self.assertEqual(text, "🌕 Full 100% · ✦ The Devil (reversed) · ⋆ Samhain in 5 days\n\n")

    def test_cut_to_the_terminal(self):
        line = self.run_cli(["--omen"], columns=20).splitlines()[0]
        self.assertEqual(layout.cell_width(line), 20)
        self.assertTrue(line.endswith("…"))


class AutoModeTest(CliTestCase):
    def test_first_shell_gets_the_full_ritual_then_the_omen(self):
        first = self.run_cli()
        self.assertIn("Good evening, wren", first)
        self.assertTrue(self.stamp.is_file())
        self.assertEqual(len(self.run_cli().splitlines()), 2)

    def test_full_again_after_ten_minutes(self):
        self.run_cli()
        old = SAMHAIN_NIGHT.timestamp() - cli.FULL_EVERY - 1
        os.utime(self.stamp, (old, old))
        self.assertIn("Good evening, wren", self.run_cli())

    def test_narrow_terminals_get_the_omen(self):
        self.assertEqual(len(self.run_cli(columns=59).splitlines()), 2)
        self.assertFalse(self.stamp.exists())

    def test_a_date_preview_leaves_no_stamp(self):
        self.run_cli(["--full", "--date", "2026-12-24"])
        self.assertFalse(self.stamp.exists())

    def test_a_stamp_from_the_future_is_stale(self):
        self.run_cli()
        future = SAMHAIN_NIGHT.timestamp() + 86400
        os.utime(self.stamp, (future, future))
        self.assertIn("Good evening, wren", self.run_cli())

    def test_explicit_full_ignores_the_stamp(self):
        self.run_cli()
        self.assertIn("Good evening, wren", self.run_cli(["--full"]))


class SkyModeTest(CliTestCase):
    def test_the_sky_job_ignores_the_date_flag(self):
        with mock.patch.object(sky, "run", return_value=0) as run:
            self.run_cli(["--sky", "--date", "2026-12-24"])
        run.assert_called_once_with(self.home, SAMHAIN_NIGHT)

    def test_runs_the_job_on_now_and_prints_nothing(self):
        with mock.patch.object(sky, "run", return_value=0) as run:
            self.assertEqual(self.run_cli(["--sky"]), "")
        run.assert_called_once_with(self.home, SAMHAIN_NIGHT)
        self.assertFalse(self.stamp.exists())

    def test_an_error_from_the_job_is_logged(self):
        with mock.patch.object(sky, "run", side_effect=OSError("disk full")):
            self.assertEqual(self.run_cli(["--sky"]), "")
        self.assertIn("greeting: OSError('disk full')", self.log.read_text(encoding="utf-8"))
        self.assertFalse(self.stamp.exists())

    def test_caret_runs_the_job_without_the_sky_on_now(self):
        with mock.patch.object(sky, "run", return_value=0) as run:
            self.assertEqual(self.run_cli(["--caret", "--date", "2026-12-24"]), "")
        run.assert_called_once_with(self.home, SAMHAIN_NIGHT, move_sky=False)
        self.assertFalse(self.stamp.exists())

    def test_sky_and_another_mode_is_an_argument_error(self):
        for mode in ("--full", "--omen", "--caret"):
            with self.subTest(mode), mock.patch.object(sky, "run") as run:
                self.assertIn(f"argument {mode}: not allowed with argument --sky", self.bad_arguments(["--sky", mode]))
                run.assert_not_called()


class ArgumentErrorTest(CliTestCase):
    def test_a_typed_ritual_shows_usage_and_logs_nothing(self):
        err = self.bad_arguments(["--full", "--omen"], tty=True)
        self.assertTrue(err.startswith("usage: ritual "), err)
        self.assertIn("ritual: error: argument --omen: not allowed with argument --full", err)
        self.assertFalse(self.log.exists())

    def test_the_greeting_logs_what_nobody_sees(self):
        # fish_greeting sends stderr to /dev/null: the error must reach doctor through the log
        err = self.bad_arguments(["--full", "--omen"])
        self.assertTrue(err.startswith("usage: ritual "), err)
        lines = self.log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(LOG_LINE.match(lines[0]).group(1), "argument --omen: not allowed with argument --full")

    def test_the_date_must_be_yyyy_mm_dd(self):
        for text in ("20261031", "2026-W44-6", "2026-1-5", "2026-02-30", "２０２６-10-31"):
            with self.subTest(text):
                self.assertIn(f"argument --date: {text!r} is not a date in the form YYYY-MM-DD",
                              self.bad_arguments(["--date", text], tty=True))
        self.assertEqual(cli.iso_day("2026-10-31"), date(2026, 10, 31))


class PreviewZoneTest(CliTestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(time.tzset)  # runs last, once TZ is back
        zone = mock.patch.dict(os.environ, {"TZ": "CET-1CEST,M3.5.0,M10.5.0/3"})  # Europe/Madrid's rules
        zone.start()
        self.addCleanup(zone.stop)
        time.tzset()

    def test_a_preview_takes_the_offset_of_its_own_day(self):
        today = datetime(2026, 10, 3, 21, 30, tzinfo=CEST)
        for day, hours in (("2026-12-01", 1), ("2026-10-10", 2)):
            with self.subTest(day), mock.patch.object(cli, "omen_line", wraps=cli.omen_line) as omen:
                self.run_cli(["--omen", "--date", day], now=today)
                shown = omen.call_args.args[0]
                self.assertEqual((shown.replace(tzinfo=None), shown.utcoffset()),
                                 (datetime.combine(date.fromisoformat(day), today.time()), timedelta(hours=hours)))


class EntryPointTest(unittest.TestCase):
    def test_ctrl_c_handler_is_installed_before_the_import(self):
        lines = (Path(cli.__file__).parent / "__main__.py").read_text(encoding="utf-8").splitlines()
        handler = next(i for i, line in enumerate(lines) if line.startswith("signal.signal(signal.SIGINT, signal.SIG_DFL)"))
        self.assertLess(handler, next(i for i, line in enumerate(lines) if "from .cli import main" in line))


class FailureTest(CliTestCase):
    def test_any_error_prints_nothing_and_is_logged(self):
        with mock.patch.object(cli, "DATA_FILES", (self.home / "missing.json",)):
            self.assertEqual(self.run_cli(["--full"]), "")
        self.assertIn("greeting: FileNotFoundError", self.log.read_text(encoding="utf-8"))

    def test_bad_data_prints_nothing(self):
        bad = self.home / "data.json"
        bad.parent.mkdir(parents=True)
        bad.write_text(json.dumps({"lunar": {}}), encoding="utf-8")
        with mock.patch.object(cli, "DATA_FILES", (bad,)):
            self.assertEqual(self.run_cli(["--omen"]), "")
        self.assertIn("KeyError", self.log.read_text(encoding="utf-8"))

    def test_debug_prints_stage_timings(self):
        last = self.run_cli(["--full", "--debug"]).splitlines()[-1]
        self.assertRegex(last, r"^debug: data [0-9.]+ ms · fetch [0-9.]+ ms · compose [0-9.]+ ms · "
                               r"render [0-9.]+ ms · total [0-9.]+ ms$")

    def test_data_comes_from_the_package_then_content(self):
        self.assertEqual(cli.DATA_FILES[0].name, "data.json")
        self.assertIn("tarot", cli.load_data())


if __name__ == "__main__":
    unittest.main()
