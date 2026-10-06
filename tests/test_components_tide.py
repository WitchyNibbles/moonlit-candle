import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.fakes import FISHER_FILE, RELEASES, TIDE_FILES, FakeFisher, fake_pins, release_tarball
from witchy import content, fishprobe, pinning, runner
from witchy.components import fish, tide
from witchy.components.base import run_command, sha
from witchy.context import Context

FISHER = RELEASES["jorgebucaran/fisher@4.4.5"]
BOOTSTRAP_URL = "https://example.invalid/fisher.fish"
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
        self.releases = dict(RELEASES)  # what the release tarballs hold when witchy downloads them to check them

    def fisher(self, installed=None, served=None, **kwargs):
        self.fake = FakeFisher(self.config, installed=installed, served=served, variables=self.variables, **kwargs)
        return self.fake

    def fetch(self, url):
        self.fetched.append(url)
        if url == BOOTSTRAP_URL:
            return FISHER_FILE
        for source, files in self.releases.items():
            if url == pinning.tarball_url(source):
                return release_tarball(files)
        raise OSError(f"no such download: {url}")

    def downloads(self):
        """The bootstrap file and each release tarball, by what was downloaded."""
        return [url for url in self.fetched if url == BOOTSTRAP_URL] + [
            url.split("/repos/")[1].split("/tarball")[0] for url in self.fetched if "/tarball/" in url]

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
        self.assertEqual(self.downloads(), [BOOTSTRAP_URL, "jorgebucaran/fisher", "ilancosman/tide"])
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
        self.assertEqual(self.downloads(), ["jorgebucaran/fisher", "ilancosman/tide"])

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
                                               ("swap", "ilancosman/tide@v6.1.1", "")])
        self.assertFalse((self.config / "functions" / "tide.fish").exists())
        self.assertNotIn("tide", self.state()["components"])

    def test_a_removed_tide_that_did_not_match_keeps_the_tide_variables(self):
        self.variables.update({"tide_pwd_icon": {"value": ["x"], "exported": False}})
        self.fisher({"jorgebucaran/fisher": FISHER}, served=self.tampered_tide())
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.variables, {"tide_pwd_icon": {"value": ["x"], "exported": False}})

    def tampered_tide(self, **more):
        bad = {**TIDE_FILES, "functions/tide.fish": b"function tide\n    echo 'tide, version 6.1.1'; evil\nend\n"}
        return {**RELEASES, "ilancosman/tide@v6.1.1": bad, **more}

    def test_a_replacement_that_does_not_match_puts_the_previous_tide_back(self):
        self.variables.update({"tide_pwd_icon": {"value": ["x"], "exported": False}})
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide": OLD_TIDE},
                    served=self.tampered_tide(**{"ilancosman/tide": OLD_TIDE}))
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "failed: ilancosman/tide files do not match the pinned release")
        self.assertEqual(self.fisher_calls(), [("swap", "ilancosman/tide", "ilancosman/tide@v6.1.1"),
                                               ("swap", "ilancosman/tide@v6.1.1", "ilancosman/tide")])
        self.assertEqual(sorted(self.fake.plugins), ["ilancosman/tide", "jorgebucaran/fisher"])
        self.assertEqual((self.config / "functions" / "tide.fish").read_bytes(), OLD_TIDE["functions/tide.fish"])
        self.assertEqual(self.variables, {"tide_pwd_icon": {"value": ["x"], "exported": False}})
        self.assertNotIn("tide", self.state()["components"])  # nothing changed, so nothing is recorded

    def test_fisher_that_does_not_match_after_the_bootstrap_is_removed_again(self):
        bad = {**RELEASES["jorgebucaran/fisher@4.4.5"], "completions/fisher.fish": b"evil\n"}
        self.fisher(served={**RELEASES, "jorgebucaran/fisher@4.4.5": bad})
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "failed: jorgebucaran/fisher files do not match the pinned release")
        self.assertEqual([call[0] for call in self.fisher_calls()], ["bootstrap", "fisher"])
        self.assertEqual(self.fisher_calls()[1][:2], ("fisher", "remove"))
        self.assertEqual(self.fake.plugins, {})

    def test_fisher_that_does_not_match_after_an_update_is_removed_again(self):
        bad = {**RELEASES["jorgebucaran/fisher@4.4.5"], "completions/fisher.fish": b"evil\n"}
        self.fisher({"jorgebucaran/fisher@4.4.5": FISHER, "ilancosman/tide@v6.1.1": TIDE_FILES},
                    served={**RELEASES, "jorgebucaran/fisher@4.4.5": bad})
        (self.config / "completions" / "fisher.fish").write_bytes(b"edited\n")
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "failed: jorgebucaran/fisher files do not match the pinned release")
        self.assertEqual(self.fisher_calls(), [("fisher", "install", "jorgebucaran/fisher@4.4.5"),
                                               ("fisher", "remove", "jorgebucaran/fisher@4.4.5")])

    def test_a_release_that_does_not_match_the_pins_is_never_installed(self):
        self.releases["ilancosman/tide@v6.1.1"] = self.tampered_tide()["ilancosman/tide@v6.1.1"]
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "failed: ilancosman/tide release does not match the pinned files")
        self.assertEqual(self.fisher_calls(), [])
        self.assertEqual(sorted(self.fake.plugins), ["jorgebucaran/fisher"])
        self.assertIn("--- download https://api.github.com/repos/ilancosman/tide/tarball/v6.1.1: ", self.log())
        self.assertNotIn("tide", self.state()["components"])

    def test_a_fisher_release_that_does_not_match_stops_before_the_bootstrap_runs(self):
        self.releases["jorgebucaran/fisher@4.4.5"] = {**FISHER, "functions/extra.fish": b"evil\n"}
        self.fisher()
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "failed: jorgebucaran/fisher release does not match the pinned files")
        self.assertEqual(self.fisher_calls(), [])

    def test_a_release_that_does_not_match_never_replaces_the_users_tide(self):
        self.releases["ilancosman/tide@v6.1.1"] = {**TIDE_FILES, "conf.d/evil.fish": b"evil\n"}
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide": OLD_TIDE})
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.fisher_calls(), [])
        self.assertEqual(sorted(self.fake.plugins), ["ilancosman/tide", "jorgebucaran/fisher"])

    def test_a_download_that_is_no_archive_does_not_match(self):
        self.fisher({"jorgebucaran/fisher": FISHER})
        ctx = self.ctx(fetch=lambda url: b"<html>rate limited</html>")
        self.assertEqual(self.install(ctx), 2)
        self.assertEqual(self.result(), "failed: ilancosman/tide release does not match the pinned files")
        self.assertEqual(self.fisher_calls(), [])

    def test_a_release_download_that_fails_installs_nothing(self):
        def offline(url):
            raise OSError("network is unreachable")

        self.fisher({"jorgebucaran/fisher": FISHER})
        self.assertEqual(self.install(self.ctx(fetch=offline)), 2)
        self.assertEqual(self.result(), "failed: could not download ilancosman/tide to check it "
                                        "(network is unreachable)")
        self.assertEqual(self.fisher_calls(), [])
        self.assertIn("--- download https://api.github.com/repos/ilancosman/tide/tarball/v6.1.1: network is "
                      "unreachable", self.log())

    def test_a_file_witchy_cannot_read_ends_the_install_without_a_traceback(self):
        real = Path.read_bytes

        def unreadable(path):
            if path.name == "icons.fish" and path.is_relative_to(self.config):
                raise PermissionError(13, "Permission denied", str(path))
            return real(path)

        self.fisher()
        with mock.patch.object(Path, "read_bytes", unreadable):
            self.assertEqual(self.install(), 2)
        self.assertTrue(self.result().startswith("failed: could not read the files of a plugin (["), self.result())
        self.assertEqual((self.entry()["installed_fisher"], self.entry()["installed_tide"]), (True, False))

    def test_the_swap_has_120_seconds_and_empty_standard_input(self):
        seen = []
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide": OLD_TIDE})
        ctx = self.ctx()
        real = ctx.run

        def run(args, **kwargs):
            if args[2:3] == [tide.SWAP_SCRIPT]:
                seen.append((kwargs["timeout"], kwargs["input"]))
            return real(args, **kwargs)

        ctx.run = run
        self.assertEqual(self.install(ctx), 0, self.out.getvalue())
        self.assertEqual(seen, [(120, "")])

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
        for plugin in ("jorgebucaran/fisher@4.4.5", "ilancosman/tide@v6.1.1"):
            self.assertIn(f"tide: download {pinning.tarball_url(plugin)} and check its files against the pins\n"
                          f"tide: fisher install {plugin}\n", self.out.getvalue())
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


PURE = {"functions/fish_prompt.fish": b"function fish_prompt\n    echo pure\nend\n",
        "conf.d/pure.fish": b"set -g pure_symbol x\n"}
PINNED = {"jorgebucaran/fisher": FISHER, "ilancosman/tide@v6.1.1": TIDE_FILES}


class TakeoverTest(TideTestCase):
    def write(self, name, data):
        path = self.config / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def backups(self):
        return sorted(path.name for path in self.config.rglob("*.bak-witchy-*"))

    def test_a_hand_written_prompt_is_moved_aside_before_tide_goes_in(self):
        prompt = self.write("functions/fish_prompt.fish", b"function fish_prompt\n    echo mine\nend\n")
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        moved = prompt.with_name("fish_prompt.fish.bak-witchy-20261005-120000")
        self.assertEqual(moved.read_bytes(), b"function fish_prompt\n    echo mine\nend\n")
        self.assertEqual(prompt.read_bytes(), TIDE_FILES["functions/fish_prompt.fish"])
        self.assertEqual(self.entry()["moved_prompt"], {"path": str(prompt), "backup": str(moved),
                                                        "installed_sha256": sha(moved.read_bytes())})
        self.assertIn("tide: moved ~/.config/fish/functions/fish_prompt.fish aside, a fish_prompt that was not "
                      "Tide's (backup: ~/.config/fish/functions/fish_prompt.fish.bak-witchy-20261005-120000)",
                      self.out.getvalue())

    def test_another_prompt_plugin_is_removed_before_tide_goes_in(self):
        self.fisher({"jorgebucaran/fisher": FISHER, "pure-fish/pure": PURE})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("fisher", "remove", "pure-fish/pure"),
                                               ("fisher", "install", "ilancosman/tide@v6.1.1")])
        self.assertEqual(self.entry()["removed_plugins"], ["pure-fish/pure"])
        self.assertIn("tide: removed the fisher plugin pure-fish/pure, which shipped its own fish_prompt",
                      self.out.getvalue())

    def test_a_starship_line_is_disabled_with_a_backup(self):
        config = self.write("config.fish", b"if status is-interactive\n    starship init fish | source\nend\n")
        self.fisher(PINNED)
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(config.read_bytes(),
                         b"if status is-interactive\n# witchy-disabled:     starship init fish | source\nend\n")
        backup = config.with_name("config.fish.bak-witchy-20261005-120000")
        self.assertEqual(backup.read_bytes(), b"if status is-interactive\n    starship init fish | source\nend\n")
        self.assertEqual(self.entry()["disabled_files"], [{"path": str(config), "backup": str(backup),
                                                           "installed_sha256": sha(config.read_bytes())}])
        self.assertIn("tide: disabled starship init in ~/.config/fish/config.fish line 2 "
                      "(backup: ~/.config/fish/config.fish.bak-witchy-20261005-120000)", self.out.getvalue())

    def test_lines_are_disabled_only_once_tide_is_in_place(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher({"jorgebucaran/fisher": FISHER}, served={})
        self.assertEqual(self.install(), 2)
        self.assertEqual(config.read_bytes(), b"starship init fish | source\n")

    def test_a_tide_release_that_does_not_match_leaves_the_prompt_and_the_lines_in_place(self):
        prompt = self.write("functions/fish_prompt.fish", b"function fish_prompt\n    echo mine\nend\n")
        config = self.write("config.fish", b"starship init fish | source\n")
        self.releases["ilancosman/tide@v6.1.1"] = {**TIDE_FILES, "conf.d/evil.fish": b"evil\n"}
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "failed: ilancosman/tide release does not match the pinned files")
        self.assertEqual(prompt.read_bytes(), b"function fish_prompt\n    echo mine\nend\n")
        self.assertEqual(config.read_bytes(), b"starship init fish | source\n")
        self.assertEqual(self.backups(), [])

    def test_a_second_run_changes_nothing(self):
        self.write("config.fish", b"starship init fish | source\nset -gx tide_time_color 5F8787\n")
        self.fisher(PINNED)
        self.install()
        first = self.entry()
        self.assertEqual(self.install(self.ctx(stamp="20261005-130000")), 0)
        self.assertEqual(self.entry(), first)
        self.assertEqual(self.backups(), ["config.fish.bak-witchy-20261005-120000"])
        self.assertNotIn("disabled", self.out.getvalue())

    def test_a_line_turned_back_on_is_disabled_again_and_the_first_backup_stays(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher(PINNED)
        self.install()
        first = self.entry()["disabled_files"][0]["backup"]
        config.write_bytes(b"starship init fish | source\n")
        self.assertEqual(self.install(self.ctx(stamp="20261005-130000")), 0)
        self.assertEqual(config.read_bytes(), b"# witchy-disabled: starship init fish | source\n")
        self.assertEqual(self.entry()["disabled_files"][0]["backup"], first)

    def test_a_fish_prompt_function_fails_and_changes_nothing(self):
        config = self.write("config.fish", b"starship init fish | source\nfunction fish_prompt\n    echo x\nend\n")
        self.fisher()
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "failed: config.fish defines fish_prompt at line 2; remove that function")
        self.assertEqual((self.fetched, self.fisher_calls()), ([], []))
        self.assertEqual(config.read_bytes(), b"starship init fish | source\nfunction fish_prompt\n    echo x\nend\n")

    def test_a_symlinked_config_is_never_edited(self):
        dotfiles = self.root / "dotfiles" / "config.fish"
        dotfiles.parent.mkdir()
        dotfiles.write_bytes(b"starship init fish | source\n")
        (self.config / "config.fish").symlink_to(dotfiles)
        self.fisher(PINNED)
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(),
                         f"failed: config.fish is a symlink to {dotfiles}; disable line 1 there yourself")
        self.assertEqual(dotfiles.read_bytes(), b"starship init fish | source\n")

    def test_a_continued_line_fails_naming_file_and_line(self):
        self.write("conf.d/mine.fish", b"set -g tide_left_prompt_items pwd \\\n    git\n")
        self.fisher(PINNED)
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "failed: conf.d/mine.fish line 1 is continued over several lines; "
                                        "disable it yourself")

    def test_crlf_and_bytes_that_are_not_utf8_are_kept(self):
        config = self.write("config.fish", b"echo \xff\r\nstarship init fish | source\r\n")
        self.fisher(PINNED)
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(config.read_bytes(), b"echo \xff\r\n# witchy-disabled: starship init fish | source\r\n")

    def test_witchys_own_and_fishers_files_are_left_alone(self):
        ours = self.write("conf.d/witchy.fish", b"set -g tide_character_color FFB86B\n")
        self.fisher({**PINNED, "pure-fish/pure": {"conf.d/pure.fish": b"set -g tide_x y\n"}})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(ours.read_bytes(), b"set -g tide_character_color FFB86B\n")
        self.assertEqual((self.config / "conf.d" / "pure.fish").read_bytes(), b"set -g tide_x y\n")
        self.assertEqual(self.backups(), [])

    def test_dry_run_shows_the_takeover_and_changes_nothing(self):
        prompt = self.write("functions/fish_prompt.fish", b"function fish_prompt\nend\n")
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher({"jorgebucaran/fisher": FISHER, "pure-fish/pure": {"conf.d/pure.fish": b"x\n"}})
        self.assertEqual(self.install(self.ctx(dry_run=True)), 0)
        output = self.out.getvalue()
        self.assertIn(f"tide: move {prompt} to fish_prompt.fish.bak-witchy-20261005-120000 (a fish_prompt that is "
                      "not Tide's)", output)
        self.assertIn("+# witchy-disabled: starship init fish | source", output)
        self.assertEqual(prompt.read_bytes(), b"function fish_prompt\nend\n")
        self.assertEqual(config.read_bytes(), b"starship init fish | source\n")
        self.assertEqual(self.fisher_calls(), [])

    def test_fish_plans_again_only_after_a_plan_that_changes_which_prompt_runs(self):
        def reprobe(fake):
            return tide.TideComponent(fake_pins()).plan(self.ctx(fake=fake), None).data["reprobe"]

        self.assertTrue(reprobe(FakeFisher(self.config, {"jorgebucaran/fisher": FISHER})))
        self.write("config.fish", b"starship init fish | source\n")
        self.assertFalse(reprobe(FakeFisher(self.config, PINNED)))


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

    def test_a_global_from_config_fish_does_not_shadow_the_saved_value(self):
        config = Path(self.ctx.env["XDG_CONFIG_HOME"]) / "fish" / "config.fish"
        config.write_text("set -g tide_pwd_icon shadowed\nset -g tide_time_color shadowed\n", encoding="utf-8")
        done = run_command(self.ctx, tide.swap_command("install Tide", "ilancosman/tide", "ilancosman/tide@v6.1.1"),
                           check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        config.unlink()
        self.assertEqual(fish.snapshot(self.ctx, []), self.before)

    def test_a_swap_whose_install_fails_still_keeps_them(self):
        done = run_command(self.ctx, tide.swap_command("install Tide", "ilancosman/tide", "ilancosman/tide@v9"),
                           check=False)
        self.assertEqual(done.returncode, 1)
        self.assertEqual(fish.snapshot(self.ctx, []), self.before)


if __name__ == "__main__":
    unittest.main()
