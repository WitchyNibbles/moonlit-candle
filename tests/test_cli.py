import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import build
from witchy.__main__ import main

ROOT = Path(__file__).resolve().parent.parent
UBUNTU = "{05f3f843-450a-55ad-a264-cacf368dafe5}"


class CliTest(unittest.TestCase):
    def test_validate_command_passes(self):
        done = subprocess.run([sys.executable, "-m", "witchy", "validate"], cwd=ROOT, capture_output=True, text=True,
                              timeout=60)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("all checks passed", done.stdout)

    def test_build_command_writes_dist(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(build, "DIST", Path(tmp)):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["build"]), 0)
            self.assertTrue((Path(tmp) / build.THEME).is_file())

    def test_install_and_uninstall_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, wt_file = Path(tmp) / "home", Path(tmp) / "wt.json"
            home.mkdir()
            wt_file.write_text(json.dumps({"profiles": {"list": [
                {"guid": UBUNTU, "name": "Ubuntu", "source": "Microsoft.WSL"}]}}, indent=4) + "\n")
            env = {"HOME": str(home), "WT_PROFILE_ID": UBUNTU}
            with mock.patch.dict(os.environ, env), mock.patch.object(build, "DIST", Path(tmp) / "dist"), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["install", "--wt-settings", str(wt_file)]), 0)
                self.assertTrue((home / ".claude" / "themes" / "moonlit-candle.json").is_file())
                self.assertEqual(main(["uninstall"]), 0)
            self.assertFalse((home / ".claude" / "themes" / "moonlit-candle.json").exists())

    def test_command_is_required(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main([])
        self.assertEqual(raised.exception.code, 2)

    def test_help_lists_commands(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            main(["--help"])
        for command in ("validate", "build", "install", "uninstall"):
            self.assertIn(command, out.getvalue())


if __name__ == "__main__":
    unittest.main()
