import fcntl
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

from witchy.components.base import (Change, Command, ComponentFailed, applied_records, apply_changes, file_lock,
                                    file_record, run_command, sha, show_changes)

PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


class Ctx:
    def __init__(self):
        self.out = io.StringIO()
        self.stamp = "20261003-120000"

    def say(self, message):
        print(message, file=self.out)


class FileRecordTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "ll.fish"
        self.path.write_bytes(b"new")
        self.change = Change(self.path, b"old", b"new")
        self.earlier = {self.path: {"path": str(self.path), "backup": None, "installed_sha256": sha(b"first")}}

    def test_a_backup_made_this_run_wins_over_the_previous_one(self):
        record = file_record(self.change, self.earlier, {self.path: Path("/x/ll.fish.bak-witchy-1")})
        self.assertEqual(record, {"path": str(self.path), "backup": "/x/ll.fish.bak-witchy-1",
                                  "installed_sha256": sha(b"new")})

    def test_without_a_backup_this_run_the_previous_one_stays(self):
        self.earlier[self.path]["backup"] = "/x/first.bak"
        self.assertEqual(file_record(self.change, self.earlier, {})["backup"], "/x/first.bak")
        self.assertIsNone(file_record(self.change, {}, {})["backup"])


class AppliedRecordsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_a_file_holding_this_runs_bytes_gets_a_new_record(self):
        path = self.root / "theme.json"
        path.write_bytes(b"new")
        backups = {path: self.root / "theme.json.bak"}
        self.assertEqual(applied_records([Change(path, b"mine", b"new")], {}, backups),
                         [{"path": str(path), "backup": str(backups[path]), "installed_sha256": sha(b"new")}])

    def test_a_file_the_run_did_not_write_keeps_its_earlier_record(self):
        path = self.root / "style.md"
        path.write_bytes(b"edited by the user")
        earlier = {path: {"path": str(path), "backup": "/x/style.md.bak", "installed_sha256": sha(b"old")}}
        self.assertEqual(applied_records([Change(path, b"edited by the user", b"new")], earlier, {}), [earlier[path]])

    def test_a_file_witchy_never_wrote_is_left_out(self):
        path = self.root / "tips.json"
        self.assertEqual(applied_records([Change(path, None, b"new")], {}, {}), [])
        path.write_bytes(b"the user's own")
        self.assertEqual(applied_records([Change(path, b"the user's own", b"new")], {}, {}), [])


class ApplyChangesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.first = self.root / "a.json"
        self.first.write_bytes(b"mine")

    def test_the_backups_made_before_a_failure_stay_with_the_caller(self):
        blocker = self.root / "blocker"
        blocker.write_bytes(b"a file, so nothing can be created inside it")
        backups = {}
        with self.assertRaises(OSError):
            apply_changes(Ctx(), [Change(self.first, b"mine", b"ours"), Change(blocker / "b.json", None, b"ours")],
                          backups)
        self.assertEqual(list(backups), [self.first])
        self.assertEqual(backups[self.first].read_bytes(), b"mine")
        self.assertEqual(self.first.read_bytes(), b"ours")

    def test_the_given_dict_is_filled_and_returned(self):
        backups = {Path("/x/earlier.json"): Path("/x/earlier.json.bak")}
        self.assertIs(apply_changes(Ctx(), [Change(self.first, b"mine", b"ours")], backups), backups)
        self.assertEqual(list(backups), [Path("/x/earlier.json"), self.first])

    def test_without_a_dict_a_new_one_is_returned(self):
        backups = apply_changes(Ctx(), [Change(self.first, b"mine", b"ours")])
        self.assertEqual(backups, {self.first: self.root / "a.json.bak-witchy-20261003-120000"})


class ShowChangesTest(unittest.TestCase):
    def test_binary_files_are_summarised(self):
        ctx = Ctx()
        show_changes(ctx, [Change(Path("/x/new.png"), None, PNG), Change(Path("/x/old.png"), PNG, PNG + b"\x00")])
        self.assertEqual(ctx.out.getvalue().splitlines(),
                         ["create /x/new.png (binary, 16 bytes)", "update /x/old.png (binary, 16 → 17 bytes)"])

    def test_text_files_still_show_a_diff(self):
        ctx = Ctx()
        show_changes(ctx, [Change(Path("/x/a.json"), b'{"a": 1}\n', b'{"a": 2}\n')])
        self.assertIn('+{"a": 2}', ctx.out.getvalue())


class RunCommandTest(unittest.TestCase):
    def ctx(self, run):
        ctx = Ctx()
        ctx.env, ctx.run = {"HOME": "/tmp/h"}, run
        return ctx

    def test_passes_list_arguments_input_env_and_a_timeout(self):
        seen = {}

        def run(args, **kwargs):
            seen.update(kwargs, args=args)
            return subprocess.CompletedProcess(args, 0, stdout="out", stderr="")

        done = run_command(self.ctx(run), Command(("fish", "-c", "x"), "do x", "in"))
        self.assertEqual(done.stdout, "out")
        self.assertEqual((seen["args"], seen["input"], seen["timeout"], seen["env"]),
                         (["fish", "-c", "x"], "in", 5, {"HOME": "/tmp/h"}))

    def test_an_exact_command_sends_and_reads_every_byte_unchanged(self):
        seen = {}

        def run(args, **kwargs):
            seen.update(kwargs)
            return subprocess.CompletedProcess(args, 0, stdout=b"a\r\nb\xff\0", stderr=b"")

        done = run_command(self.ctx(run), Command(("fish", "-c", "x"), "do x", "c\r\udcff", exact=True))
        self.assertEqual(seen["input"], b"c\r\xff")
        self.assertNotIn("text", seen)
        self.assertEqual(done.stdout, "a\r\nb\udcff\0")

    def test_a_non_zero_exit_fails_unless_unchecked(self):
        def run(args, **kwargs):
            return subprocess.CompletedProcess(args, 3, stdout="partial", stderr="")

        with self.assertRaisesRegex(ComponentFailed, r"^could not do x \(exit 3\)$"):
            run_command(self.ctx(run), Command(("x",), "do x"))
        self.assertEqual(run_command(self.ctx(run), Command(("x",), "do x"), check=False).stdout, "partial")

    def test_a_timeout_or_missing_program_fails_and_keeps_the_cause(self):
        for error in (subprocess.TimeoutExpired(["x"], 5), FileNotFoundError(2, "No such file", "x")):
            def run(args, **kwargs):
                raise error

            with self.assertRaises(ComponentFailed) as caught:
                run_command(self.ctx(run), Command(("x",), "do x"))
            self.assertIs(caught.exception.__cause__, error)

    def test_the_reason_is_short_whatever_the_error(self):
        script = "echo " + "x" * 1400
        cases = ((subprocess.TimeoutExpired(["fish", "-c", script], 5), "timed out after 5 s"),
                 (FileNotFoundError(2, "No such file or directory", "x"), "No such file or directory"))
        for error, reason in cases:
            def run(args, **kwargs):
                raise error

            with self.assertRaises(ComponentFailed) as caught:
                run_command(self.ctx(run), Command(("x",), "do x"))
            self.assertEqual(str(caught.exception), f"could not do x ({reason})")

    def test_any_other_error_text_is_cut_to_100_characters(self):
        def run(args, **kwargs):
            raise ValueError("y" * 500)

        with self.assertRaises(ComponentFailed) as caught:
            run_command(self.ctx(run), Command(("x",), "do x"))
        self.assertEqual(str(caught.exception), f"could not do x ({'y' * 100})")


class FileLockTest(unittest.TestCase):
    def test_busy_lock_times_out_as_a_component_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wt.lock"
            with open(path, "a") as handle:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(ComponentFailed):
                    with file_lock(path, timeout=0.2):
                        pass

    def test_a_lock_that_cannot_be_opened_is_a_component_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "cache"
            blocker.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ComponentFailed, "cannot open .*wt.lock"):
                with file_lock(blocker / "wt.lock"):
                    pass

    def test_an_os_error_inside_the_lock_is_not_relabelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PermissionError):
                with file_lock(Path(tmp) / "wt.lock"):
                    raise PermissionError(13, "denied")

    def test_no_path_is_a_no_op(self):
        with file_lock(None):
            pass


if __name__ == "__main__":
    unittest.main()
