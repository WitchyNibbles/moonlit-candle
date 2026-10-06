import io
import json
import os
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

    def tampered_tide(self, **more):
        bad = {**TIDE_FILES, "functions/tide.fish": b"function tide\n    echo 'tide, version 6.1.1'; evil\nend\n"}
        return {**RELEASES, "ilancosman/tide@v6.1.1": bad, **more}

    def result(self):
        return self.state()["last_install"]["results"]["tide"]

    def fisher_calls(self):
        """Each fisher call: its script's kind and its arguments."""
        kinds = {tide.FISHER_SCRIPT: "fisher", tide.BOOTSTRAP_SCRIPT: "bootstrap", tide.SWAP_SCRIPT: "swap"}
        return [(kinds[args[2]], *args[4:]) for args in self.fake.calls if args[:2] == ["fish", "-c"]
                and args[2] in kinds]

    def log(self):
        return (self.home / ".cache" / "witchy" / "install.log").read_text(encoding="utf-8")

    def write(self, name, data):
        path = self.config / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def backups(self):
        return sorted(path.name for path in self.config.rglob("*.bak-witchy-*"))


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
                                               ("fisher", "remove", "ilancosman/tide@v6.1.1")])
        self.assertFalse((self.config / "functions" / "tide.fish").exists())
        self.assertNotIn("tide", self.state()["components"])

    def test_a_fresh_tide_that_did_not_match_takes_its_variables_with_it(self):
        self.variables.update({"tide_pwd_icon": {"value": ["x"], "exported": False}})
        self.fisher({"jorgebucaran/fisher": FISHER}, served=self.tampered_tide())
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.variables, {})  # no Tide was there before, so none of its variables stays

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

    def test_an_updated_tide_that_does_not_match_is_removed_with_its_variables_and_recorded(self):
        self.variables.update({"tide_pwd_icon": {"value": ["x"], "exported": False}})
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide@v6.1.1": TIDE_FILES}, served=self.tampered_tide())
        (self.config / "functions" / "tide" / "configure" / "icons.fish").write_bytes(b"edited\n")
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "failed: ilancosman/tide files do not match the pinned release")
        self.assertEqual(self.fisher_calls(), [("fisher", "install", "ilancosman/tide@v6.1.1"),
                                               ("swap", "ilancosman/tide@v6.1.1", "")])
        self.assertEqual(self.variables, {"tide_pwd_icon": {"value": ["x"], "exported": False}})
        self.assertEqual(self.entry()["previous_tide_plugin"], "ilancosman/tide@v6.1.1")  # uninstall puts it back
        self.assertFalse(self.entry()["installed_tide"])

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

    def test_a_plugin_whose_remove_fails_is_still_recorded(self):
        self.fisher({"jorgebucaran/fisher": FISHER, "pure-fish/pure": PURE})
        ctx = self.ctx()
        real = ctx.run

        def run(args, **kwargs):
            done = real(args, **kwargs)
            if args[2:5] == [tide.FISHER_SCRIPT, "--", "remove"]:  # the files are gone, and fisher still fails
                error = "pure: uninstall failed\n"
                return subprocess.CompletedProcess(args, 1, stdout=done.stdout,
                                                   stderr=error if kwargs.get("text") else error.encode())
            return done

        ctx.run = run
        self.assertEqual(self.install(ctx), 2)
        self.assertTrue(self.result().startswith("failed: could not remove pure-fish/pure (exit 1)"), self.result())
        self.assertEqual(self.entry()["removed_plugins"], ["pure-fish/pure"])

    @unittest.skipIf(os.geteuid() == 0, "root reads every file")
    def test_an_unreadable_prompt_fails_and_what_was_installed_stays_recorded(self):
        prompt = self.write("functions/fish_prompt.fish", b"function fish_prompt\nend\n")
        prompt.chmod(0)
        self.addCleanup(prompt.chmod, 0o644)
        self.fisher()
        self.assertEqual(self.install(), 2)
        self.assertTrue(self.result().startswith("failed: could not move ~/.config/fish/functions/fish_prompt.fish "
                                                 "aside"), self.result())
        self.assertTrue(self.entry()["installed_fisher"])
        self.assertTrue(prompt.is_file())

    def test_tides_own_prompt_stays_when_fisher_lists_the_folder_a_symlink_points_to(self):
        real = self.root / "dotfiles" / "fish"
        real.parent.mkdir()
        self.config.rmdir()
        self.config.symlink_to(real, target_is_directory=True)
        real.mkdir()
        self.fake = FakeFisher(real, PINNED, variables=self.variables)  # fisher_path is the resolved folder
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual((real / "functions" / "fish_prompt.fish").read_bytes(),
                         TIDE_FILES["functions/fish_prompt.fish"])
        self.assertEqual(self.backups(), [])
        self.assertNotIn("moved", self.out.getvalue())

    def test_a_config_edited_while_tide_installs_is_not_overwritten(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher({"jorgebucaran/fisher": FISHER})
        ctx = self.ctx()
        real = ctx.run

        def run(args, **kwargs):
            if args[2:6] == [tide.FISHER_SCRIPT, "--", "install", tide.TIDE_SOURCE]:
                config.write_bytes(b"starship init fish | source\nset -g fish_greeting\n")
            return real(args, **kwargs)

        ctx.run = run
        self.assertEqual(self.install(ctx), 2)
        self.assertEqual(self.result(), "failed: ~/.config/fish/config.fish changed while Tide was installed; "
                                        "its lines were not disabled. Run the command again.")
        self.assertEqual(config.read_bytes(), b"starship init fish | source\nset -g fish_greeting\n")
        self.assertTrue(self.entry()["installed_tide"])
        self.assertEqual(self.backups(), [])

    def test_tide_is_ready_only_once_the_lines_are_disabled(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.assertEqual(config.read_bytes(), b"# witchy-disabled: starship init fish | source\n")
        self.assertTrue(self.entry()["installed_tide"])
        self.assertIsNone(fishprobe.tide_ready(fishprobe.probe(self.ctx())))

    def test_a_prompt_line_it_cannot_disable_fails_and_keeps_the_record(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        # A plugin's own conf.d is fisher's to manage, never edited; this one ships no fish_prompt.
        self.fisher({**PINNED, "someone/starship": {"conf.d/starship.fish": b"starship init fish | source\n"}})
        self.assertEqual(self.install(), 2)
        self.assertEqual(self.result(), "failed: Tide is installed but not ready: fish_prompt is not Tide's (-)")
        self.assertEqual(config.read_bytes(), b"# witchy-disabled: starship init fish | source\n")
        self.assertEqual([record["path"] for record in self.entry()["disabled_files"]], [str(config)])

    def test_a_symlinked_prompt_is_moved_as_a_link_and_its_target_is_untouched(self):
        target = self.root / "dotfiles" / "fish_prompt.fish"
        target.parent.mkdir()
        target.write_bytes(b"function fish_prompt\n    echo dotfiles\nend\n")
        prompt = self.config / "functions" / "fish_prompt.fish"
        prompt.parent.mkdir()
        prompt.symlink_to(target)
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        moved = prompt.with_name("fish_prompt.fish.bak-witchy-20261005-120000")
        self.assertTrue(moved.is_symlink())
        self.assertEqual(moved.resolve(), target)
        self.assertEqual(target.read_bytes(), b"function fish_prompt\n    echo dotfiles\nend\n")
        self.assertEqual(prompt.read_bytes(), TIDE_FILES["functions/fish_prompt.fish"])
        self.assertEqual(self.entry()["moved_prompt"]["installed_sha256"], sha(target.read_bytes()))

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
        self.assertFalse(reprobe(FakeFisher(self.config, PINNED)))
        config = self.write("config.fish", b"starship init fish | source\n")
        self.assertTrue(reprobe(FakeFisher(self.config, PINNED)))  # disabling it gives the prompt back to Tide
        config.write_bytes(b"set -g tide_time_color 5F8787\n")
        self.assertTrue(reprobe(FakeFisher(self.config, PINNED)))  # it hides the universal tide_ variables


class UninstallTest(TideTestCase):
    def uninstall(self, stamp="20261005-130000", dry_run=False):
        return runner.uninstall(self.ctx(stamp=stamp, dry_run=dry_run), [tide.TideComponent(fake_pins())])

    def test_removes_the_tide_and_fisher_it_installed_in_that_order(self):
        self.fisher()
        self.install()
        self.fake.calls.clear()
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("fisher", "remove", "ilancosman/tide@v6.1.1"),
                                               ("fisher", "remove", "jorgebucaran/fisher@4.4.5")])
        self.assertEqual(self.fake.plugins, {})
        self.assertFalse((self.home / ".claude" / "witchy" / "state.json").exists())

    def test_removing_the_tide_it_installed_takes_its_variables_with_it(self):
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.install()
        self.variables.update({"tide_pwd_icon": {"value": ["x"], "exported": False}})
        self.fake.calls.clear()
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("fisher", "remove", "ilancosman/tide@v6.1.1")])
        self.assertEqual(self.variables, {})

    def test_puts_back_the_tide_that_was_there_and_leaves_the_users_fisher(self):
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide": OLD_TIDE},
                    served={**RELEASES, "ilancosman/tide": OLD_TIDE})
        self.install()
        self.fake.calls.clear()
        self.variables.update({"tide_pwd_icon": {"value": ["x"], "exported": False}})
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("swap", "ilancosman/tide@v6.1.1", "ilancosman/tide")])
        self.assertEqual(sorted(self.fake.plugins), ["ilancosman/tide", "jorgebucaran/fisher"])
        self.assertEqual(self.variables, {"tide_pwd_icon": {"value": ["x"], "exported": False}})

    def failed_update(self):
        """An install whose update of the user's Tide 6.1.1 did not match the pins, so that Tide was removed."""
        self.variables.update({"tide_pwd_icon": {"value": ["x"], "exported": False}})
        self.fisher({"jorgebucaran/fisher": FISHER, "ilancosman/tide@v6.1.1": TIDE_FILES}, served=self.tampered_tide())
        (self.config / "functions" / "tide" / "configure" / "icons.fish").write_bytes(b"edited\n")
        self.assertEqual(self.install(), 2)
        self.fake.calls.clear()

    def test_a_tide_removed_after_a_failed_update_is_put_back_with_its_variables(self):
        self.failed_update()
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("swap", "", "ilancosman/tide@v6.1.1")])
        self.assertIn("ilancosman/tide@v6.1.1", self.fake.plugins)
        self.assertEqual(self.variables, {"tide_pwd_icon": {"value": ["x"], "exported": False}})

    def test_a_tide_removed_after_a_failed_update_that_is_back_already_is_left(self):
        self.failed_update()
        self.fake.run(["fish", "-c", tide.FISHER_SCRIPT, "--", "install", "ilancosman/tide@v6.1.1"])
        self.fake.calls.clear()
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [])

    def test_a_retried_install_after_a_failed_update_keeps_the_users_tide_on_uninstall(self):
        self.failed_update()
        self.fake.served["ilancosman/tide@v6.1.1"] = TIDE_FILES
        self.assertEqual(self.install(self.ctx(stamp="20261005-121000")), 0, self.out.getvalue())
        self.fake.calls.clear()
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [])
        self.assertIn("ilancosman/tide@v6.1.1", self.fake.plugins)
        self.assertEqual(self.variables, {"tide_pwd_icon": {"value": ["x"], "exported": False}})

    def test_puts_back_a_removed_prompt_plugin_after_tide_is_gone(self):
        self.fisher({"jorgebucaran/fisher": FISHER, "pure-fish/pure": PURE},
                    served={**RELEASES, "pure-fish/pure": PURE})
        self.install()
        self.fake.calls.clear()
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("fisher", "remove", "ilancosman/tide@v6.1.1"),
                                               ("fisher", "install", "pure-fish/pure")])
        self.assertEqual((self.config / "functions" / "fish_prompt.fish").read_bytes(),
                         PURE["functions/fish_prompt.fish"])

    def test_a_retry_after_a_failed_command_does_not_repeat_what_worked(self):
        self.fisher({"jorgebucaran/fisher": FISHER, "pure-fish/pure": PURE},
                    served={**RELEASES, "pure-fish/pure": PURE})
        self.install()
        del self.fake.served["pure-fish/pure"]  # offline now
        self.assertEqual(self.uninstall(), 2)
        self.assertIn("tide: could not put back pure-fish/pure (exit 1); run uninstall again.", self.out.getvalue())
        self.assertIn("tide", self.state()["components"])
        self.fake.served["pure-fish/pure"] = PURE
        self.fake.calls.clear()
        self.assertEqual(self.uninstall("20261005-140000"), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [("fisher", "install", "pure-fish/pure")])

    def test_disabled_lines_come_back_byte_for_byte(self):
        original = b"echo \xff\r\nstarship init fish | source\r\nset -g tide_x y\r\n"
        config = self.write("config.fish", original)
        self.fisher(PINNED)
        self.install()
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(config.read_bytes(), original)
        self.assertEqual(self.backups(), ["config.fish.bak-witchy-20261005-120000"])

    def test_the_users_later_edits_stay_and_the_edited_file_is_kept_as_a_backup(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher(PINNED)
        self.install()
        config.write_bytes(config.read_bytes() + b"alias ll 'ls -l'\n")
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(config.read_bytes(), b"starship init fish | source\nalias ll 'ls -l'\n")
        self.assertEqual(self.backups(), ["config.fish.bak-witchy-20261005-120000",
                                          "config.fish.bak-witchy-20261005-130000"])

    def test_a_file_that_became_a_symlink_is_left_with_a_warning(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher(PINNED)
        self.install()
        dotfiles = self.root / "dotfiles.fish"
        dotfiles.write_bytes(config.read_bytes())
        config.unlink()
        config.symlink_to(dotfiles)
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(dotfiles.read_bytes(), b"# witchy-disabled: starship init fish | source\n")
        self.assertIn("tide: ~/.config/fish/config.fish is a symlink now and is not edited; remove "
                      "'# witchy-disabled: ' from its lines yourself.", self.out.getvalue())

    def test_a_moved_prompt_comes_back_once_tide_is_gone(self):
        prompt = self.write("functions/fish_prompt.fish", b"function fish_prompt\n    echo mine\nend\n")
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.install()
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(prompt.read_bytes(), b"function fish_prompt\n    echo mine\nend\n")
        self.assertEqual(self.backups(), [])

    def test_a_moved_prompt_whose_place_is_taken_stays_aside(self):
        prompt = self.write("functions/fish_prompt.fish", b"function fish_prompt\n    echo mine\nend\n")
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.install()
        self.fake.run(["fish", "-c", tide.FISHER_SCRIPT, "--", "remove", "ilancosman/tide@v6.1.1"])
        prompt.write_bytes(b"function fish_prompt\n    echo newer\nend\n")
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(prompt.read_bytes(), b"function fish_prompt\n    echo newer\nend\n")
        self.assertIn("tide: ~/.config/fish/functions/fish_prompt.fish is not witchy's to replace; your fish_prompt "
                      "stays at ~/.config/fish/functions/fish_prompt.fish.bak-witchy-20261005-120000.",
                      self.out.getvalue())

    def test_a_moved_prompt_whose_backup_is_gone_is_a_warning(self):
        prompt = self.write("functions/fish_prompt.fish", b"function fish_prompt\nend\n")
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.install()
        prompt.with_name("fish_prompt.fish.bak-witchy-20261005-120000").unlink()
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertFalse(prompt.exists())
        self.assertIn("so your fish_prompt cannot come back.", self.out.getvalue())

    def test_a_tide_the_user_removed_is_not_removed_again(self):
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.install()
        self.fake.run(["fish", "-c", tide.FISHER_SCRIPT, "--", "remove", "ilancosman/tide@v6.1.1"])
        self.fake.calls.clear()
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [])

    def test_without_fish_the_lines_still_come_back(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher({"jorgebucaran/fisher": FISHER})
        self.install()
        self.fake.missing = True
        self.assertEqual(self.uninstall(), 0, self.out.getvalue())
        self.assertEqual(config.read_bytes(), b"starship init fish | source\n")
        self.assertIn("tide: fish not found, so fisher, Tide and the prompt plugins stay as they are.",
                      self.out.getvalue())

    def test_dry_run_lists_every_step_and_changes_nothing(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher({"pure-fish/pure": PURE}, served={**RELEASES, "pure-fish/pure": PURE})
        self.assertEqual(self.install(), 0, self.out.getvalue())
        self.fake.calls.clear()
        self.assertEqual(self.uninstall(dry_run=True), 0)
        self.assertIn("tide: remove Tide (ilancosman/tide@v6.1.1)\ntide: put back pure-fish/pure\n"
                      "tide: remove fisher (jorgebucaran/fisher@4.4.5)\n", self.out.getvalue())
        self.assertIn("-# witchy-disabled: starship init fish | source", self.out.getvalue())
        self.assertEqual(self.fisher_calls(), [])
        self.assertEqual(config.read_bytes(), b"# witchy-disabled: starship init fish | source\n")


class CheckTest(TideTestCase):
    def doctor(self):
        ctx = self.ctx(stamp="20261005-130000")
        code = runner.doctor(ctx, [tide.TideComponent(fake_pins())])
        return code, [line for line in self.out.getvalue().splitlines()]

    def test_a_healthy_install(self):
        self.fisher()
        self.install()
        code, lines = self.doctor()
        self.assertEqual(code, 0)
        self.assertEqual(lines, [
            "✓ tide              fisher 4.4.5 found",
            "✓ tide              Tide 6.1.1 found",
            "✓ tide              every jorgebucaran/fisher file matches the pinned release",
            "✓ tide              every ilancosman/tide file matches the pinned release",
            "✓ tide              the active fish_prompt is Tide's",
            "✓ tide              no other prompt owner is active",
            "· tide              glyph test: 🧹 🔮 🪦 🌿 🧪 💀 🔥 🐈 🦉 ❯ — each should be one clear symbol"])

    def test_fisher_or_tide_missing_fails_with_the_fix(self):
        self.fisher()
        self.install()
        self.fake.fisher("remove", ["ilancosman/tide@v6.1.1", "jorgebucaran/fisher@4.4.5"])
        code, lines = self.doctor()
        self.assertEqual(code, 1)
        self.assertEqual(lines[:4], ["✗ tide              fisher not found",
                                     "    fix: python3 -m witchy install --only tide",
                                     "✗ tide              Tide not found",
                                     "    fix: python3 -m witchy install --only tide"])

    def test_another_tide_version_fails(self):
        self.fisher(PINNED)
        self.install()
        (self.config / "functions" / "tide.fish").write_bytes(OLD_TIDE["functions/tide.fish"])
        code, lines = self.doctor()
        self.assertIn("✗ tide              Tide is 6.0.0, not 6.1.1", lines)
        self.assertIn("✗ tide              ilancosman/tide files do not match the pinned release: functions/tide.fish",
                      lines)

    def test_a_long_list_of_changed_files_is_cut(self):
        self.fisher(PINNED)
        self.install()
        for number in range(7):
            self.write(f"functions/tide/extra{number}.fish", b"x\n")
        code, lines = self.doctor()
        self.assertIn("✗ tide              ilancosman/tide files do not match the pinned release: "
                      "functions/tide/extra0.fish, functions/tide/extra1.fish, functions/tide/extra2.fish, "
                      "functions/tide/extra3.fish, functions/tide/extra4.fish (and 2 more)", lines)

    def test_a_fish_prompt_that_is_not_tides_fails(self):
        self.fisher(PINNED)
        self.install()
        (self.config / "functions" / "fish_prompt.fish").unlink()
        code, lines = self.doctor()
        self.assertIn("✗ tide              fish_prompt is not Tide's (no fish_prompt)", lines)

    def test_a_disabled_line_turned_back_on_is_drift(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher(PINNED)
        self.install()
        config.write_bytes(b"starship init fish | source\n")
        code, lines = self.doctor()
        self.assertEqual(code, 1)
        self.assertIn("✗ tide              starship init in ~/.config/fish/config.fish line 1 is active", lines)
        self.assertIn("    fix: python3 -m witchy install --only tide", lines)

    def test_a_fish_prompt_function_names_what_to_do_by_hand(self):
        self.fisher(PINNED)
        self.install()
        self.write("config.fish", b"set -g fish_greeting\nfunction fish_prompt\nend\n")
        code, lines = self.doctor()
        self.assertIn("✗ tide              config.fish defines fish_prompt at line 2", lines)
        self.assertIn("    fix: remove that function", lines)

    def test_a_fisher_the_user_installed_at_another_version_is_a_warning(self):
        older = {"functions/fisher.fish": b"function fisher\n    echo 'fisher, version 4.3.0'\nend\n"}
        self.fisher({"jorgebucaran/fisher": older, "ilancosman/tide@v6.1.1": TIDE_FILES})
        self.install()
        code, lines = self.doctor()
        self.assertEqual(code, 0)
        self.assertIn("⚠ tide              fisher is 4.3.0; witchy was tested with 4.4.5", lines)
        self.assertNotIn("jorgebucaran/fisher file", "\n".join(lines))

    def test_without_fish_it_cannot_check(self):
        self.fisher()
        self.install()
        self.fake.missing = True
        code, lines = self.doctor()
        self.assertEqual((code, lines), (0, ["⚠ tide              cannot check fisher and Tide: fish not found "
                                             "(sudo apt install fish)"]))

    def test_a_missing_backup_is_a_warning(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher(PINNED)
        self.install()
        config.with_name("config.fish.bak-witchy-20261005-120000").unlink()
        code, lines = self.doctor()
        self.assertIn(f"⚠ tide              backup {config}.bak-witchy-20261005-120000 is missing; uninstall cannot "
                      "give back the original bytes", lines)


class FreshPcTest(TideTestCase):
    """tide and fish in one run (acceptance criterion 1), through the runner as `install` runs them."""

    def run_install(self, only=("tide", "fish"), dry_run=False, fetch=None):
        ctx = self.ctx(dry_run=dry_run, fetch=fetch)
        ctx.only, ctx.python = only, "/usr/bin/python3"
        return runner.install(ctx, [tide.TideComponent(fake_pins()), fish.FishComponent()])

    def test_a_pc_with_fish_only_ends_with_the_witchy_prompt(self):
        self.fisher()
        self.assertEqual(self.run_install(), 0, self.out.getvalue())
        self.assertEqual(self.state()["last_install"]["results"], {"tide": "ok", "fish": "ok"})
        self.assertEqual(self.variables["tide_pwd_icon"]["value"], ["🧹"])
        self.assertEqual(len(self.state()["components"]["fish"]["variables"]), len(fish.desired("midnight")))

    def test_the_dry_run_says_fish_waits_for_tide(self):
        self.fisher()
        self.assertEqual(self.run_install(dry_run=True), 0)
        self.assertIn(f"fish: set {len(fish.desired('midnight'))} prompt variables once tide has installed Tide "
                      "(fish is asked again then)", self.out.getvalue())

    def test_when_tide_fails_fish_finds_tide_not_ready_by_itself(self):
        def offline(url):
            raise OSError("network is unreachable")

        self.fisher()
        self.assertEqual(self.run_install(fetch=offline), 2)
        self.assertEqual(self.state()["last_install"]["results"], {
            "tide": "failed: could not download fisher (network is unreachable)",
            "fish": "skipped: Tide not ready (run: python3 -m witchy install --only tide)"})
        self.assertIn("✗✗✗ witchy is NOT fully installed ✗✗✗\n"
                      "  tide: failed: could not download fisher (network is unreachable)\n"
                      "  fish: skipped: Tide not ready (run: python3 -m witchy install --only tide)\n",
                      self.out.getvalue())
        self.assertEqual(self.variables, {})

    def test_only_fish_never_waits_for_tide(self):
        self.fisher()
        self.assertEqual(self.run_install(only=("fish",)), 2)
        self.assertEqual(self.state()["last_install"]["results"]["fish"],
                         "skipped: Tide not ready (run: python3 -m witchy install --only tide)")
        self.assertEqual(self.fisher_calls(), [])

    def test_a_line_tide_disables_no_longer_keeps_fish_from_finding_tide_ready(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher(PINNED)
        self.assertEqual(fishprobe.tide_ready(fishprobe.probe(self.ctx())), "fish_prompt is not Tide's (-)")
        self.assertEqual(self.run_install(), 0, self.out.getvalue())
        self.assertEqual(self.state()["last_install"]["results"], {"tide": "ok", "fish": "ok"})
        self.assertEqual(config.read_bytes(), b"# witchy-disabled: starship init fish | source\n")
        self.assertEqual(self.variables["tide_pwd_icon"]["value"], ["🧹"])

    def test_a_fresh_pc_with_a_starship_line_ends_with_the_witchy_prompt(self):
        config = self.write("config.fish", b"starship init fish | source\n")
        self.fisher()
        self.assertEqual(self.run_install(), 0, self.out.getvalue())
        self.assertEqual(self.state()["last_install"]["results"], {"tide": "ok", "fish": "ok"})
        self.assertEqual(config.read_bytes(), b"# witchy-disabled: starship init fish | source\n")
        self.assertEqual(sorted(self.fake.plugins), ["ilancosman/tide@v6.1.1", "jorgebucaran/fisher@4.4.5"])
        self.assertEqual(self.variables["tide_pwd_icon"]["value"], ["🧹"])

    def test_a_ready_tide_lets_fish_plan_once(self):
        self.fisher(PINNED)
        self.assertEqual(self.run_install(), 0, self.out.getvalue())
        probes = [args for args in self.fake.calls if args[2:3] == [fishprobe.PROBE_SCRIPT]]
        self.assertEqual(len(probes), 2)  # one for tide, one for fish


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
