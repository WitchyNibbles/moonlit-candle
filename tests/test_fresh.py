import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import fresh
from witchy.__main__ import main
from witchy.context import Context


class FreshTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.bin = Path(tmp.name) / "bin"
        self.bin.mkdir()
        self.home = Path(tmp.name) / "home"
        self.calls, self.asked = [], []
        self.shell, self.codes = "/bin/bash", {}

    def tool(self, name):
        path = self.bin / name
        path.write_text("#!/bin/sh\n", encoding="utf-8")
        path.chmod(0o755)

    def fake_run(self, args, **kwargs):
        if args[:2] == ["getent", "passwd"]:
            return subprocess.CompletedProcess(args, 0, stdout=f"eimi:x:1000:1000::/home/eimi:{self.shell}\n")
        self.calls.append(args)
        if args[-1] == "fish" and "install" in args:
            self.tool("fish")  # apt put it on PATH
        return subprocess.CompletedProcess(args, self.codes.get(" ".join(args), 0))

    def prepare(self, answers=(), dry_run=False, interactive=True):
        replies = list(answers)

        def ask(question):
            self.asked.append(question)
            if not replies:
                raise EOFError
            return replies.pop(0)

        self.out = io.StringIO()
        ctx = Context(home=self.home, env={"PATH": str(self.bin), "USER": "eimi"}, out=self.out, dry_run=dry_run,
                      run=self.fake_run)
        return fresh.prepare(ctx, ask=ask, interactive=interactive)

    def test_nothing_missing_and_fish_already_the_login_shell_asks_nothing(self):
        for name in fresh.PACKAGES:
            self.tool(name)
        self.shell = "/usr/bin/fish"
        self.assertIsNone(self.prepare(interactive=False))
        self.assertEqual((self.asked, self.calls), ([], []))

    def test_asks_once_for_the_missing_packages_then_offers_chsh(self):
        self.tool("curl")
        self.assertIsNone(self.prepare(["y", "y"]))
        self.assertEqual(self.asked, ["sudo apt install fish eza? [y/N] ",
                                      f"make fish your login shell (chsh -s {self.bin / 'fish'})? [y/N] "])
        self.assertEqual(self.calls, [["sudo", "apt-get", "update"], ["sudo", "apt-get", "install", "-y", "fish"],
                                      ["sudo", "apt-get", "install", "-y", "eza"],
                                      ["chsh", "-s", str(self.bin / "fish")]])

    def test_a_refused_install_exits_1_and_runs_nothing(self):
        self.assertEqual(self.prepare(["n"]), 1)
        self.assertEqual(self.calls, [])
        self.assertIn("fresh: nothing was installed.", self.out.getvalue())

    def test_a_failed_apt_exits_1_and_asks_nothing_more(self):
        self.codes["sudo apt-get install -y fish curl"] = 100
        self.assertEqual(self.prepare(["y", "y"]), 1)
        self.assertEqual(len(self.asked), 1)
        self.assertIn("fresh: sudo apt-get install -y fish curl failed (exit 100); nothing else ran.",
                      self.out.getvalue())

    def test_eza_that_cannot_be_installed_is_only_a_note(self):
        self.tool("curl")
        self.tool("fish")
        self.codes["sudo apt-get install -y eza"] = 100
        self.shell = "/usr/bin/fish"
        self.assertIsNone(self.prepare(["y"]))
        self.assertIn("fresh: eza could not be installed (exit 100); ll and lt use ls.", self.out.getvalue())

    def test_chsh_is_offered_only_when_the_login_shell_is_not_fish(self):
        for name in fresh.PACKAGES:
            self.tool(name)
        self.assertIsNone(self.prepare(["n"]))
        self.assertEqual(self.asked, [f"make fish your login shell (chsh -s {self.bin / 'fish'})? [y/N] "])
        self.assertEqual(self.calls, [])  # a refusal is not an error

    def test_a_failed_chsh_is_reported_and_the_install_goes_on(self):
        for name in fresh.PACKAGES:
            self.tool(name)
        self.codes[f"chsh -s {self.bin / 'fish'}"] = 1
        self.assertIsNone(self.prepare(["y"]))
        self.assertIn("fresh: chsh failed (exit 1); your login shell stays as it was.", self.out.getvalue())

    def test_without_a_terminal_it_exits_1_before_asking(self):
        self.assertEqual(self.prepare(["y"], interactive=False), 1)
        self.assertEqual((self.asked, self.calls), ([], []))
        self.assertEqual(self.out.getvalue(), "--fresh needs a terminal to ask before using sudo\n")

    def test_dry_run_lists_the_questions_and_runs_nothing(self):
        self.assertIsNone(self.prepare(dry_run=True, interactive=False))
        self.assertEqual((self.asked, self.calls), ([], []))
        self.assertEqual(self.out.getvalue(), "fresh: would ask: sudo apt install fish curl eza? [y/N]\n"
                                              "fresh: would ask: make fish your login shell (chsh -s <fish>)? [y/N]\n")


class FreshCliTest(unittest.TestCase):
    def test_fresh_runs_before_the_install_and_can_stop_it(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp}), \
                mock.patch("witchy.fresh.prepare", return_value=1) as prepare, \
                mock.patch("witchy.runner.install") as install, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["install", "--fresh"]), 1)
            prepare.return_value = None
            install.return_value = 0
            self.assertEqual(main(["install", "--fresh", "--dry-run"]), 0)
            self.assertEqual(main(["install"]), 0)
        self.assertEqual(prepare.call_count, 2)
        self.assertEqual(install.call_count, 2)


if __name__ == "__main__":
    unittest.main()
