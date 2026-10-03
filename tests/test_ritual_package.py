import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from witchy import build, content, palette

PYTHON = "/usr/bin/python3" if Path("/usr/bin/python3").is_file() else sys.executable


class PackageTest(unittest.TestCase):
    def test_every_module_and_the_texts(self):
        files = build.ritual_package()
        modules = {path.name for path in build.RITUAL_SOURCE.glob("*.py")}
        self.assertEqual(set(files), modules | {"data.json"})
        self.assertEqual(files["data.json"], (content.CONTENT_DIR / content.RITUAL).read_bytes())

    def test_palette_comes_from_the_variant(self):
        dawn = palette.Variant(**{**palette.VARIANTS["midnight"].__dict__, "name": "dawn",
                                  "ritual": dict(palette.RITUAL, salutation="#FFE3A3")})
        with mock.patch.dict(palette.VARIANTS, {"dawn": dawn}):
            text = build.ritual_package("dawn")["palette.py"].decode("utf-8")
        self.assertIn('"salutation": "#FFE3A3",', text)

    def test_imports_nothing_from_witchy(self):
        for name, data in build.ritual_package().items():
            if name.endswith(".py"):
                self.assertNotRegex(data.decode("utf-8"), re.compile(r"^\s*(from|import)\s+witchy", re.M), name)


class InstalledCopyTest(unittest.TestCase):
    def test_runs_isolated_from_its_own_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / ".claude" / "witchy" / "ritual"
            target.mkdir(parents=True)
            for name, data in build.ritual_package().items():
                (target / name).write_bytes(data)
            env = {"HOME": tmp, "NO_COLOR": "1", "PATH": os.environ.get("PATH", "")}
            started = time.monotonic()
            done = subprocess.run([PYTHON, "-I", "-B", str(target), "--omen", "--date", "2026-10-31"],
                                  capture_output=True, text=True, env=env, cwd=tmp, timeout=10)
            elapsed = time.monotonic() - started
            self.assertEqual((done.returncode, done.stderr), (0, ""))
            self.assertIn("🕯️ Samhain", done.stdout)
            self.assertLess(elapsed, 1.0)  # a regression guard; the real budget is 200 ms (spec 6.7)
            self.assertEqual(sorted(path.name for path in target.iterdir()), sorted(build.ritual_package()))
            started = time.monotonic()
            done = subprocess.run([PYTHON, "-I", "-B", str(target), "--full", "--date", "2026-10-31"],
                                  capture_output=True, text=True, env=env, cwd=tmp, timeout=10)
            elapsed = time.monotonic() - started
            self.assertEqual((done.returncode, done.stderr), (0, ""))
            self.assertIn("Samhain", done.stdout)
            self.assertLess(elapsed, 1.0)

    def test_a_missing_module_is_logged_not_shown(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / ".claude" / "witchy" / "ritual"
            target.mkdir(parents=True)
            for name, data in build.ritual_package().items():
                (target / name).write_bytes(data)
            (target / "wheel.py").unlink()
            env = {"HOME": tmp, "NO_COLOR": "1", "PATH": os.environ.get("PATH", "")}
            done = subprocess.run([PYTHON, "-I", "-B", str(target), "--omen"],
                                  capture_output=True, text=True, env=env, cwd=tmp, timeout=10)
            self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
            lines = (Path(tmp) / ".cache" / "witchy" / "ritual.log").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertIn("greeting:", lines[0])
            self.assertIn("wheel", lines[0])


if __name__ == "__main__":
    unittest.main()
