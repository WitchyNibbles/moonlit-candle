"""The tide and fish components with real fish, a stand-in fisher and a stand-in Tide served from a folder."""
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.fakes import FAKE_FISHER_FISH, fake_pins, fake_tide_tree, release_tarball, serve_plugins
from witchy import pinning, runner
from witchy.components import fish, tide
from witchy.context import Context

FISH = shutil.which("fish")
TOOL_DIRS = list(dict.fromkeys([str(Path(FISH).parent) if FISH else "/usr/bin", "/usr/bin", "/bin"]))
FISHER_TREE = {"functions/fisher.fish": FAKE_FISHER_FISH.encode()}
RELEASES = {"jorgebucaran/fisher@4.4.5": FISHER_TREE, "ilancosman/tide@v6.1.1": fake_tide_tree()}


@unittest.skipUnless(FISH, "fish is not installed")
class RealFishTideTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.config = self.root / "config" / "fish"
        self.config.mkdir(parents=True)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        (bin_dir / "curl").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")  # fisher's stand-in never calls it
        (bin_dir / "curl").chmod(0o755)
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config.parent),
                    "PATH": ":".join([str(bin_dir), *TOOL_DIRS]), "WITCHY_FAKE_PLUGINS": str(self.root / "served")}
        serve_plugins(self.root / "served", {**RELEASES, "ilancosman/tide": fake_tide_tree("6.0.0")}, self.env)

    def fish(self, script):
        done = subprocess.run([FISH, "-c", script], capture_output=True, text=True, env=self.env, timeout=20)
        self.assertEqual(done.stderr, "")
        return done.stdout

    def fetch(self, url):
        """The pinned fisher.fish, and each release's tarball for the check witchy runs before fisher installs it."""
        for source, files in RELEASES.items():
            if url == pinning.tarball_url(source):
                return release_tarball(files)
        if url == fake_pins()["bootstrap"]["url"]:
            return FAKE_FISHER_FISH.encode()
        raise OSError(f"no such download: {url}")

    def components(self):
        return [tide.TideComponent(fake_pins(RELEASES, bootstrap=FAKE_FISHER_FISH.encode())), fish.FishComponent()]

    def ctx(self, stamp):
        self.out = io.StringIO()
        return Context(home=self.home, env=self.env, out=self.out, python=sys.executable, stamp=stamp,
                       dist=self.root / "dist", lock_path=self.root / "witchy.lock", only=("tide", "fish"),
                       fetch=self.fetch)

    def test_a_pc_with_fish_only_gets_fisher_tide_and_the_witchy_prompt_and_gives_them_back(self):
        self.assertEqual(runner.install(self.ctx("20261005-120000"), self.components()), 0, self.out.getvalue())
        self.assertEqual(self.fish("tide --version; functions --details fish_prompt; printf '%s\\n' $tide_pwd_icon"),
                         f"tide, version 6.1.1\n{self.config}/functions/fish_prompt.fish\n🧹\n")
        self.assertEqual(self.fish("printf '%s\\n' $_fisher_plugins"),
                         "jorgebucaran/fisher@4.4.5\nilancosman/tide@v6.1.1\n")
        ctx = self.ctx("20261005-130000")
        self.assertEqual(runner.doctor(ctx, self.components()), 0, self.out.getvalue())
        self.assertNotIn("✗", self.out.getvalue())
        self.assertEqual(runner.uninstall(self.ctx("20261005-140000"), self.components()), 0, self.out.getvalue())
        self.assertEqual(self.fish("functions -q fisher tide; or echo gone; set -U --names | string match '*tide*'"),
                         "gone\n")
        self.assertEqual(sorted(path.name for path in (self.config / "functions").iterdir()), [])

    def test_a_starship_line_is_disabled_and_given_back(self):
        original = b"if type -q starship\r\n    starship init fish | source\r\nend\r\n"
        (self.config / "config.fish").write_bytes(original)
        self.assertEqual(runner.install(self.ctx("20261005-120000"), self.components()), 0, self.out.getvalue())
        self.assertEqual((self.config / "config.fish").read_bytes(),
                         b"if type -q starship\r\n# witchy-disabled:     starship init fish | source\r\nend\r\n")
        self.assertIn("tide: disabled starship init in", self.out.getvalue())
        self.assertEqual(runner.uninstall(self.ctx("20261005-130000"), self.components()), 0, self.out.getvalue())
        self.assertEqual((self.config / "config.fish").read_bytes(), original)

    def test_another_tide_is_replaced_and_comes_back_with_the_users_values(self):
        self.fish("source $WITCHY_FAKE_PLUGINS/jorgebucaran_2F_fisher_40_34_2E_34_2E_35_/functions/fisher.fish; "
                  "fisher install jorgebucaran/fisher@4.4.5 ilancosman/tide >/dev/null; "
                  "set -U tide_pwd_icon mine; set -Ux tide_time_color 5F8787")
        before = self.fish("set -U | string match 'tide_*'; set -U -x | string match 'tide_*'")
        self.assertEqual(runner.install(self.ctx("20261005-120000"), self.components()), 0, self.out.getvalue())
        self.assertEqual(self.fish("printf '%s\\n' $_fisher_plugins $tide_pwd_icon"),
                         "jorgebucaran/fisher@4.4.5\nilancosman/tide@v6.1.1\n🧹\n")
        self.assertEqual(runner.uninstall(self.ctx("20261005-130000"), self.components()), 0, self.out.getvalue())
        self.assertEqual(self.fish("printf '%s\\n' $_fisher_plugins; tide --version"),
                         "jorgebucaran/fisher@4.4.5\nilancosman/tide\ntide, version 6.0.0\n")
        self.assertEqual(self.fish("set -U | string match 'tide_*'; set -U -x | string match 'tide_*'"), before)


if __name__ == "__main__":
    unittest.main()
