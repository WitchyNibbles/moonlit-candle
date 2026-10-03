import fcntl
import io
import tempfile
import unittest
from pathlib import Path

import subprocess

from witchy.components.base import Change, Command, ComponentFailed, file_lock, run_command, show_changes

PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


class Ctx:
    def __init__(self):
        self.out = io.StringIO()

    def say(self, message):
        print(message, file=self.out)


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
