import io
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.fakes import FAKE_PROMPT, FAKE_TIDE_FILES, fake_fish
from witchy import fishprobe
from witchy.components.base import ComponentFailed
from witchy.context import Context

FISH = shutil.which("fish")
TOOL_DIRS = list(dict.fromkeys([str(Path(FISH).parent) if FISH else "/usr/bin", "/usr/bin", "/bin"]))


def ctx(run, home=Path("/home/user"), env=None):
    return Context(home=home, env=env or {"PATH": "/nowhere"}, out=io.StringIO(), run=run)


class ProbeTest(unittest.TestCase):
    def test_a_machine_with_fisher_and_tide(self):
        calls = []
        found = fishprobe.probe(ctx(fake_fish(calls=calls)))
        self.assertEqual(found, fishprobe.Probe(
            fisher="4.4.5", tide="6.1.1", prompt_path=FAKE_PROMPT,
            plugins={"jorgebucaran/fisher": ["/home/user/.config/fish/functions/fisher.fish"],
                     "ilancosman/tide": FAKE_TIDE_FILES}))
        self.assertEqual([args for args, _ in calls], [["fish", "-c", fishprobe.PROBE_SCRIPT]])
        self.assertIsNone(fishprobe.tide_ready(found))

    def test_nothing_installed(self):
        found = fishprobe.probe(ctx(fake_fish(fisher=None, tide=None, prompt=None)))
        self.assertEqual(found, fishprobe.Probe(fisher=None, tide=None, prompt_path=None, plugins={}))
        self.assertEqual(fishprobe.tide_ready(found), "Tide not found")

    def test_what_config_fish_prints_is_ignored(self):
        found = fishprobe.probe(ctx(fake_fish(noise="Welcome!\n\0stray\0")))
        self.assertEqual((found.fisher, found.tide), ("4.4.5", "6.1.1"))

    def test_a_version_in_another_format_is_kept_as_printed(self):
        def run(args, **kwargs):
            out = "\0".join(["witchy-fish", "no-fisher", "tide", "tide 5.6.0 (dev)", "n/a", ""])
            return subprocess.CompletedProcess(args, 0, stdout=out.encode(), stderr=b"")

        self.assertEqual(fishprobe.probe(ctx(run)).tide, "tide 5.6.0 (dev)")

    def test_missing_fish_keeps_the_cause(self):
        with self.assertRaises(ComponentFailed) as caught:
            fishprobe.probe(ctx(fake_fish(missing=True)))
        self.assertIsInstance(caught.exception.__cause__, FileNotFoundError)

    def test_an_answer_without_the_marker_or_cut_short_fails(self):
        for stdout in (b"garbage", b"witchy-fish\0fisher\0"):
            def run(args, **kwargs):
                return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr=b"")

            with self.subTest(stdout=stdout), self.assertRaisesRegex(ComponentFailed,
                                                                     r"^could not read fisher and Tide \("):
                fishprobe.probe(ctx(run))


class TideReadyTest(unittest.TestCase):
    def probe(self, **changes):
        healthy = dict(fisher="4.4.5", tide="6.1.1", prompt_path=FAKE_PROMPT,
                       plugins={"ilancosman/tide": FAKE_TIDE_FILES})
        return fishprobe.Probe(**{**healthy, **changes})

    def test_ready(self):
        self.assertIsNone(fishprobe.tide_ready(self.probe()))

    def test_the_reasons(self):
        cases = (
            ({"tide": None}, "Tide not found"),
            ({"tide": "6.0.0"}, "Tide is 6.0.0, not 6.1.1"),
            ({"tide": ""}, "Tide is of an unknown version, not 6.1.1"),
            ({"prompt_path": "/home/user/.config/fish/functions/fish_prompt.fish.mine"},
             "fish_prompt is not Tide's (/home/user/.config/fish/functions/fish_prompt.fish.mine)"),
            ({"prompt_path": None}, "fish_prompt is not Tide's (no fish_prompt)"),
            ({"plugins": {}}, f"fish_prompt is not Tide's ({FAKE_PROMPT})"),
        )
        for changes, reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(fishprobe.tide_ready(self.probe(**changes)), reason)

    def test_tide_installed_from_a_tag_or_in_another_case_counts(self):
        for name in ("ilancosman/tide@v6.1.1", "IlanCosman/tide"):
            with self.subTest(name=name):
                self.assertIsNone(fishprobe.tide_ready(self.probe(plugins={name: FAKE_TIDE_FILES})))
        self.assertEqual(fishprobe.plugin_files(self.probe(plugins={"ilancosman/tide-fork": FAKE_TIDE_FILES}),
                                                fishprobe.TIDE_PLUGIN), None)


@unittest.skipUnless(FISH, "fish is not installed")
class RealFishProbeTest(unittest.TestCase):
    """Real fish with a temporary HOME holding a stand-in fisher and Tide."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        self.functions = self.home / ".config" / "fish" / "functions"
        self.functions.mkdir(parents=True)
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config"),
                    "PATH": ":".join(TOOL_DIRS)}

    def function(self, name, body):
        (self.functions / f"{name}.fish").write_text(f"function {name}\n    {body}\nend\n", encoding="utf-8")

    def fish(self, script, *args):
        subprocess.run([FISH, "-c", script, "--", *args], env=self.env, check=True, timeout=20, capture_output=True)

    def test_reads_versions_the_prompt_and_each_plugins_files(self):
        self.function("fisher", "echo 'fisher, version 4.4.5'")
        self.function("tide", "echo 'tide, version 6.1.1'")
        self.function("fish_prompt", "echo '> '")
        # As fisher records them: ~ for HOME, one list per plugin, named after the plugin as it was installed.
        self.fish("set -U _fisher_plugins jorgebucaran/fisher ilancosman/tide@v6.1.1 empty/plugin; "
                  "set -U _fisher_jorgebucaran_2F_fisher_files $argv[1]; "
                  "set -U _fisher_(string escape --style=var -- ilancosman/tide@v6.1.1)_files $argv[2..]; "
                  "set -U _fisher_empty_2F_plugin_files",
                  "~/.config/fish/functions/fisher.fish", "~/.config/fish/functions/fish_prompt.fish",
                  "~/.config/fish/functions/tide.fish")
        found = fishprobe.probe(ctx(subprocess.run, home=self.home, env=self.env))
        self.assertEqual(found, fishprobe.Probe(
            fisher="4.4.5", tide="6.1.1", prompt_path=str(self.functions / "fish_prompt.fish"),
            plugins={"jorgebucaran/fisher": [str(self.functions / "fisher.fish")],
                     "ilancosman/tide@v6.1.1": [str(self.functions / "fish_prompt.fish"),
                                                str(self.functions / "tide.fish")],
                     "empty/plugin": []}))
        self.assertIsNone(fishprobe.tide_ready(found))

    def test_without_fisher_or_tide_fish_keeps_its_own_prompt(self):
        found = fishprobe.probe(ctx(subprocess.run, home=self.home, env=self.env))
        self.assertEqual((found.fisher, found.tide, found.plugins), (None, None, {}))
        self.assertEqual(fishprobe.tide_ready(found), "Tide not found")
        self.assertTrue(found.prompt_path.endswith("/functions/fish_prompt.fish"), found.prompt_path)


if __name__ == "__main__":
    unittest.main()
