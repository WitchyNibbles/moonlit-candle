import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.fakes import FISHER_FILE, RELEASES, TIDE_FILES, FakeFisher, fake_pins
from witchy import content, fishprobe, runner
from witchy.components import fish, tide
from witchy.components.base import run_command, sha
from witchy.context import Context

FISHER = RELEASES["jorgebucaran/fisher@4.4.5"]
REAL_FISH = shutil.which("fish")
ROOT = Path(__file__).resolve().parent.parent
OLD_TIDE = {**TIDE_FILES, "functions/tide.fish": b"function tide\n    echo 'tide, version 6.0.0'\nend\n"}


class TideTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.config = self.home / ".config" / "fish"
        self.config.mkdir(parents=True)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.bin / "curl").write_text("#!/bin/sh\n", encoding="utf-8")
        (self.bin / "curl").chmod(0o755)
        self.fetched = []
        self.variables = {}

    def fisher(self, installed=None, served=None, **kwargs):
        self.fake = FakeFisher(self.config, installed=installed, served=served, variables=self.variables, **kwargs)
        return self.fake

    def fetch(self, url):
        self.fetched.append(url)
        return FISHER_FILE

    def ctx(self, fake=None, dry_run=False, stamp="20261005-120000", fetch=None, path=None):
        self.out = io.StringIO()
        fake = fake or getattr(self, "fake", None) or self.fisher()
        return Context(home=self.home, env={"PATH": str(self.bin) if path is None else path}, out=self.out,
                       dry_run=dry_run, stamp=stamp, run=fake.run, dist=self.root / "dist",
                       lock_path=self.root / "witchy.lock", only=("tide",), fetch=fetch or self.fetch)

    def install(self, ctx=None, pins=None):
        ctx = ctx or self.ctx()
        return runner.install(ctx, [tide.TideComponent(fake_pins() if pins is None else pins)])

    def state(self):
        return json.loads((self.home / ".claude" / "witchy" / "state.json").read_text(encoding="utf-8"))

    def entry(self):
        return self.state()["components"]["tide"]

    def result(self):
        return self.state()["last_install"]["results"]["tide"]

    def fisher_calls(self):
        """Each fisher call: its script's kind and its arguments."""
        kinds = {tide.FISHER_SCRIPT: "fisher", tide.BOOTSTRAP_SCRIPT: "bootstrap", tide.SWAP_SCRIPT: "swap"}
        return [(kinds[args[2]], *args[4:]) for args in self.fake.calls if args[:2] == ["fish", "-c"]
                and args[2] in kinds]

    def log(self):
        return (self.home / ".cache" / "witchy" / "install.log").read_text(encoding="utf-8")


class BootstrapTest(TideTestCase):
    def test_a_pc_with_fish_only_gets_fisher_and_tide(self):
        self.fisher()
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fetched, ["https://example.invalid/fisher.fish"])
        cached = self.home / ".cache" / "witchy" / "fisher-4.4.5.fish"
        self.assertEqual(cached.read_bytes(), FISHER_FILE)
        self.assertEqual(self.fisher_calls(), [("bootstrap", str(cached), "jorgebucaran/fisher@4.4.5"),
                                               ("fisher", "install", "ilancosman/tide@v6.1.1")])
        self.assertEqual(sorted(self.fake.plugins), ["ilancosman/tide@v6.1.1", "jorgebucaran/fisher@4.4.5"])
        self.assertEqual(self.entry(), {"installed_fisher": True, "installed_tide": True,
                                        "previous_tide_plugin": None, "removed_plugins": [], "disabled_files": [],
                                        "moved_prompt": None})
        self.assertEqual(self.result(), "ok")

    def test_a_cached_bootstrap_file_with_the_pinned_hash_is_not_downloaded_again(self):
        cached = self.home / ".cache" / "witchy" / "fisher-4.4.5.fish"
        cached.parent.mkdir(parents=True)
        cached.write_bytes(FISHER_FILE)
        self.fisher()
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fetched, [])

    def test_a_bootstrap_file_that_does_not_match_its_pin_is_never_run(self):
        self.fisher()
        self.assertEqual(self.install(self.ctx(fetch=lambda url: b"function fisher\n    rm -rf ~\nend\n")), 2)
        self.assertEqual(self.result(), "failed: the downloaded fisher.fish does not match the pinned release")
        self.assertEqual(self.fisher_calls(), [])
        self.assertFalse((self.home / ".cache" / "witchy" / "fisher-4.4.5.fish").exists())
        self.assertNotIn("tide", self.state()["components"])

    def test_no_network_fails_with_the_reason(self):
        def offline(url):
            raise OSError("network is unreachable")

        self.fisher()
        self.assertEqual(self.install(self.ctx(fetch=offline)), 2)
        self.assertEqual(self.result(), "failed: could not download fisher (network is unreachable)")
        self.assertIn("--- download https://example.invalid/fisher.fish: network is unreachable", self.log())

    def test_tide_missing_installs_only_tide(self):
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("fisher", "install", "ilancosman/tide@v6.1.1")])
        self.assertEqual((self.entry()["installed_fisher"], self.entry()["installed_tide"]), (False, True))

    def test_another_tide_version_is_replaced_and_its_name_recorded(self):
        self.variables.update({"tide_pwd_icon": {"value": ["x"], "exported": False}})
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide": OLD_TIDE})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("swap", "ilancosman/tide", "ilancosman/tide@v6.1.1")])
        self.assertEqual(sorted(self.fake.plugins), ["ilancosman/tide@v6.1.1", "jorgebucaran/fisher"])
        self.assertEqual(self.entry()["previous_tide_plugin"], "ilancosman/tide")
        self.assertFalse(self.entry()["installed_tide"])
        self.assertEqual(self.variables, {"tide_pwd_icon": {"value": ["x"], "exported": False}})

    def test_tide_6_1_1_with_files_that_differ_from_the_release_is_replaced(self):
        # This PC: Tide's development branch, which also says 6.1.1.
        changed = {**TIDE_FILES, "functions/tide/configure/icons.fish": b"tide_bun_icon x\ntide_pwd_icon x\n"}
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide": changed})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("swap", "ilancosman/tide", "ilancosman/tide@v6.1.1")])

    def test_witchys_own_tide_with_a_changed_file_is_installed_again(self):
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide@v6.1.1": TIDE_FILES})
        (self.config / "functions" / "tide" / "configure" / "icons.fish").write_bytes(b"edited\n")
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("fisher", "install", "ilancosman/tide@v6.1.1")])
        self.assertEqual((self.config / "functions" / "tide" / "configure" / "icons.fish").read_bytes(),
                         TIDE_FILES["functions/tide/configure/icons.fish"])

    def test_pinned_tide_is_left_alone(self):
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide@v6.1.1": TIDE_FILES})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [])
        self.assertEqual(self.result(), "ok")

    def test_a_fisher_the_user_installed_is_never_pinned(self):
        older = {"functions/fisher.fish": b"function fisher\n    echo 'fisher, version 4.3.0'\nend\n"}
        self.fisher({"jorgebucaran/fisher": older, "ilancosman/tide@v6.1.1": TIDE_FILES})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [])

    def test_witchys_own_fisher_with_a_changed_file_is_installed_again(self):
        self.fisher({"jorgebucaran/fisher@4.4.5": FISHER, "ilancosman/tide@v6.1.1": TIDE_FILES})
        (self.config / "completions" / "fisher.fish").write_bytes(b"edited\n")
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("fisher", "install", "jorgebucaran/fisher@4.4.5")])

    def test_without_curl_nothing_is_downloaded(self):
        self.fisher()
        self.assertEqual(self.install(self.ctx(path=str(self.root / "empty"))), 2)
        self.assertEqual(self.result(), "failed: curl not found (sudo apt install curl)")
        self.assertEqual((self.fetched, self.fisher_calls()), ([], []))
        self.assertIn("tide: curl not found (sudo apt install curl); nothing was changed.", self.out.getvalue())

    def test_without_curl_a_ready_tide_is_fine(self):
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide@v6.1.1": TIDE_FILES})
        self.assertEqual(self.install(self.ctx(path=str(self.root / "empty"))), 0, self.out.getvalue())

    def test_files_that_do_not_match_the_pins_are_removed_again(self):
        served = {**RELEASES, "ilancosman/tide@v6.1.1": {**TIDE_FILES, "functions/tide.fish":
                                                         b"function tide\n    echo 'tide, version 6.1.1'; evil\nend\n"}}
        self.fisher({"jorgebucaran/fisher": FISHER}, served=served)
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "failed: ilancosman/tide files do not match the pinned release")
        self.assertEqual(self.fisher_calls(), [("fisher", "install", "ilancosman/tide@v6.1.1"),
                                               ("fisher", "remove", "ilancosman/tide@v6.1.1")])
        self.assertFalse((self.config / "functions" / "tide.fish").exists())
        self.assertNotIn("tide", self.state()["components"])

    def test_a_fisher_error_names_its_last_line_and_the_log(self):
        self.fisher({"jorgebucaran/fisher": FISHER}, served={})
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), 'failed: could not install Tide (exit 1): fisher: Invalid plugin name or host '
                                        'unavailable: "ilancosman/tide@v6.1.1" (details: ~/.cache/witchy/install.log)')
        self.assertIn("--- install Tide (exit 1)\nfisher install version 4.4.5\nfisher: Invalid plugin name",
                      self.log())

    def test_what_installed_before_a_failure_stays_recorded(self):
        self.fisher(served={"jorgebucaran/fisher@4.4.5": FISHER})
        self.assertEqual(self.install(), 2)
        self.assertTrue(self.result().startswith("failed: could not install Tide (exit 1)"))
        self.assertEqual((self.entry()["installed_fisher"], self.entry()["installed_tide"]), (True, False))

    def test_every_fisher_call_has_120_seconds_and_empty_standard_input(self):
        seen = []
        ctx = self.ctx()
        real = ctx.run

        def run(args, **kwargs):
            if args[2:3] in ([tide.FISHER_SCRIPT], [tide.BOOTSTRAP_SCRIPT]):
                seen.append((kwargs["timeout"], kwargs["input"]))
            return real(args, **kwargs)

        ctx.run = run
        self.assertEqual(self.install(ctx), 0, self.out.getvalue())
        self.assertEqual(seen, [(120, ""), (120, "")])

    def test_dry_run_lists_the_downloads_and_fisher_commands_and_runs_none(self):
        self.fisher()
        self.assertEqual(self.install(self.ctx(dry_run=True)), 0)
        self.assertIn("tide: download https://example.invalid/fisher.fish (sha256 ", self.out.getvalue())
        self.assertIn("tide: fisher install jorgebucaran/fisher@4.4.5\ntide: fisher install ilancosman/tide@v6.1.1\n",
                      self.out.getvalue())
        self.assertEqual((self.fetched, self.fisher_calls()), ([], []))
        self.assertFalse((self.home / ".claude").exists())
        self.assertFalse((self.home / ".cache").exists())

    def test_dry_run_of_a_replacement_names_both_tides(self):
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide": OLD_TIDE})
        self.install(self.ctx(dry_run=True))
        self.assertIn("tide: fisher remove ilancosman/tide, then fisher install ilancosman/tide@v6.1.1 "
                      "(Tide is 6.0.0); the Tide variables keep their values", self.out.getvalue())

    def test_a_reinstall_keeps_what_the_first_install_recorded(self):
        self.fisher()
        self.install()
        self.assertEqual(self.install(self.ctx(stamp="20261005-130000")), 0)
        self.assertEqual((self.entry()["installed_fisher"], self.entry()["installed_tide"]), (True, True))

    def test_without_fish_it_is_skipped(self):
        self.fisher(missing=True)
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "skipped: fish not found (sudo apt install fish)")

    def test_a_tide_fisher_does_not_know_is_not_touched(self):
        (self.config / "functions").mkdir()
        (self.config / "functions" / "tide.fish").write_bytes(TIDE_FILES["functions/tide.fish"])
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "failed: Tide is installed without fisher, so witchy can neither check nor "
                                        "replace it; remove it")
        self.assertEqual(self.fisher_calls(), [])


class PinsTest(unittest.TestCase):
    def test_the_installed_sources_are_the_pinned_ones(self):
        self.assertEqual(tuple(content.load_pins()["plugins"]), (tide.FISHER_SOURCE, tide.TIDE_SOURCE))
        self.assertEqual(tide.FISHER_SOURCE, f"{fishprobe.FISHER_PLUGIN}@{tide.FISHER_VERSION}")
        self.assertEqual(tide.TIDE_SOURCE, f"{fishprobe.TIDE_PLUGIN}@v{fishprobe.TIDE_VERSION}")

    def test_each_new_module_can_be_imported_first(self):
        for module in ("witchy.fishprobe", "witchy.takeover", "witchy.installlog", "witchy.components.tide"):
            done = subprocess.run([sys.executable, "-c", f"import {module}"], cwd=ROOT, capture_output=True,
                                  text=True, timeout=60)
            self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_listed_folder_counts_with_every_file_below_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            functions = Path(tmp) / "functions"
            (functions / "tide" / "configure").mkdir(parents=True)
            (functions / "tide" / "configure" / "icons.fish").write_bytes(b"a")
            (functions / "tide.fish").write_bytes(b"b")
            self.assertEqual(tide.file_hashes([str(functions / "tide"), str(functions / "tide.fish"),
                                               str(functions / "gone.fish")]),
                             {"functions/tide/configure/icons.fish": sha(b"a"), "functions/tide.fish": sha(b"b")})


# Stands in for fisher where only its effect on the variables matters: removing Tide erases every universal tide_
# variable and installing it sets Tide's defaults, as Tide's own uninstall and install handlers do.
FAKE_FISHER_FUNCTION = """\
function fisher
    switch $argv[1]
        case remove
            set -e -U (set -U --names | string match 'tide_*')
        case install
            set -U tide_pwd_icon lean
            test "$argv[2]" = ilancosman/tide@v6.1.1
    end
end
"""


@unittest.skipUnless(REAL_FISH, "fish is not installed")
class RealFishSwapTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        functions = Path(tmp.name) / "config" / "fish" / "functions"
        functions.mkdir(parents=True)
        self.home.mkdir()
        (functions / "fisher.fish").write_text(FAKE_FISHER_FUNCTION, encoding="utf-8")
        env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(functions.parent.parent), "PATH": "/usr/bin:/bin"}
        self.ctx = Context(home=self.home, env=env, out=io.StringIO())
        run_command(self.ctx, fish.set_command([("tide_pwd_icon", "set", ["x", "two words"]),
                                                ("tide_time_color", "exported", ["5F8787"]),
                                                ("tide_empty", "set", [])], "set three"))
        self.before = fish.snapshot(self.ctx, [])

    def test_a_swap_keeps_every_tide_variable(self):
        done = run_command(self.ctx, tide.swap_command("install Tide", "ilancosman/tide", "ilancosman/tide@v6.1.1"),
                           check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(fish.snapshot(self.ctx, []), self.before)

    def test_a_swap_whose_install_fails_still_keeps_them(self):
        done = run_command(self.ctx, tide.swap_command("install Tide", "ilancosman/tide", "ilancosman/tide@v9"),
                           check=False)
        self.assertEqual(done.returncode, 1)
        self.assertEqual(fish.snapshot(self.ctx, []), self.before)


if __name__ == "__main__":
    unittest.main()
