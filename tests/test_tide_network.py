"""The real download path (spec 12, D24): opt in with WITCHY_NETWORK_TESTS=1. CI runs it weekly (network.yml)."""
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from witchy import content, runner
from witchy.components import tide
from witchy.context import Context

FISH = shutil.which("fish")
ROOT = Path(__file__).resolve().parent.parent
NETWORK = os.environ.get("WITCHY_NETWORK_TESTS") == "1"


@unittest.skipUnless(NETWORK, "set WITCHY_NETWORK_TESTS=1 to download fisher and Tide")
class RealReleasesTest(unittest.TestCase):
    def test_the_pins_match_the_real_releases(self):
        spec = importlib.util.spec_from_file_location("pins", ROOT / "scripts" / "pins.py")
        pins = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pins)
        self.assertEqual(pins.pins(pins.download), content.load_pins())

    @unittest.skipUnless(FISH and shutil.which("curl"), "fish and curl are needed")
    def test_bootstraps_the_real_fisher_and_tide_into_a_throwaway_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            env = {"HOME": str(home), "XDG_CONFIG_HOME": str(Path(tmp) / "config"), "PATH": os.environ["PATH"]}
            out = io.StringIO()

            def ctx(stamp):
                return Context(home=home, env=env, out=out, python=sys.executable, stamp=stamp,
                               dist=Path(tmp) / "dist", lock_path=Path(tmp) / "witchy.lock", only=("tide",))

            self.assertEqual(runner.install(ctx("20261005-120000"), [tide.TideComponent()]), 0, out.getvalue())
            done = subprocess.run([FISH, "-c", "fisher --version; tide --version; printf '%s\\n' $_fisher_plugins"],
                                  capture_output=True, text=True, env=env, timeout=30)
            self.assertEqual(done.stdout, "fisher, version 4.4.5\ntide, version 6.1.1\n"
                                          "jorgebucaran/fisher@4.4.5\nilancosman/tide@v6.1.1\n")
            self.assertEqual(runner.doctor(ctx("20261005-130000"), [tide.TideComponent()]), 0, out.getvalue())
            self.assertIn("every ilancosman/tide file matches the pinned release", out.getvalue())
            self.assertEqual(runner.uninstall(ctx("20261005-140000"), [tide.TideComponent()]), 0, out.getvalue())
            done = subprocess.run([FISH, "-c", "functions -q fisher tide; or echo gone"], capture_output=True,
                                  text=True, env=env, timeout=30)
            self.assertEqual(done.stdout, "gone\n")


class WorkflowTest(unittest.TestCase):
    def test_ci_runs_this_file_weekly_and_on_demand(self):
        text = (ROOT / ".github" / "workflows" / "network.yml").read_text(encoding="utf-8")
        for line in ("  schedule:", '    - cron: "17 6 * * 1"  # Mondays', "  workflow_dispatch:",
                     "\npermissions:\n  contents: read", "    timeout-minutes: 10",
                     '          WITCHY_NETWORK_TESTS: "1"',
                     "        run: python -m unittest tests.test_tide_network -v"):
            self.assertIn(line + "\n", text)


if __name__ == "__main__":
    unittest.main()
