import contextlib
import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from witchy import content

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "pins.py"
_spec = importlib.util.spec_from_file_location("pins", SCRIPT)
pins = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pins)


def tarball(members, links=()):
    """A gzip tarball like GitHub's: every path below one top folder; ``links`` are symlinks."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(f"owner-repo-abc1234/{name}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for name in links:
            info = tarfile.TarInfo(f"owner-repo-abc1234/{name}")
            info.type, info.linkname = tarfile.SYMTYPE, "../README.md"
            tar.addfile(info)
    return buffer.getvalue()


def digest(data):
    return hashlib.sha256(data).hexdigest()


class PluginFilesTest(unittest.TestCase):
    def test_hashes_every_file_fisher_copies(self):
        archive = tarball({"functions/tide.fish": b"a", "functions/tide/configure/icons.fish": b"b",
                           "conf.d/_tide_init.fish": b"c", "completions/tide.fish": b"d", "themes/x.theme": b"e",
                           "functions/.hidden.fish": b"f", "README.md": b"g", "tests/tide.fish": b"h"})
        self.assertEqual(pins.plugin_files(archive), {
            "completions/tide.fish": digest(b"d"), "conf.d/_tide_init.fish": digest(b"c"),
            "functions/tide.fish": digest(b"a"), "functions/tide/configure/icons.fish": digest(b"b"),
            "themes/x.theme": digest(b"e")})

    def test_refuses_a_link(self):
        with self.assertRaisesRegex(ValueError, "functions/x.fish is a link"):
            pins.plugin_files(tarball({"functions/tide.fish": b"a"}, links=["functions/x.fish"]))

    def test_refuses_an_archive_with_nothing_to_install(self):
        with self.assertRaisesRegex(ValueError, "no file fisher would install"):
            pins.plugin_files(tarball({"README.md": b"a"}))

    def test_the_urls_are_the_ones_fisher_downloads(self):
        self.assertEqual(pins.tarball_url("ilancosman/tide@v6.1.1"),
                         "https://api.github.com/repos/ilancosman/tide/tarball/v6.1.1")


class MainTest(unittest.TestCase):
    def test_writes_the_bootstrap_hash_and_every_plugins_files(self):
        served = {pins.BOOTSTRAP: b"function fisher\nend\n",
                  pins.tarball_url("jorgebucaran/fisher@4.4.5"): tarball({"functions/fisher.fish": b"f"}),
                  pins.tarball_url("ilancosman/tide@v6.1.1"): tarball({"functions/tide.fish": b"t"})}
        fetched = []

        def fetch(url):
            fetched.append(url)
            return served[url]

        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as out:
            output = Path(tmp) / "pins.json"
            self.assertEqual(pins.main([str(output)], fetch=fetch), 0)
            written = json.loads(output.read_text(encoding="ascii"))
            loaded = content.load_pins(Path(tmp))
        self.assertEqual(fetched, list(served))
        self.assertEqual(written, loaded)
        self.assertEqual(written, {
            "bootstrap": {"url": pins.BOOTSTRAP, "sha256": digest(b"function fisher\nend\n")},
            "plugins": {"jorgebucaran/fisher@4.4.5": {"functions/fisher.fish": digest(b"f")},
                        "ilancosman/tide@v6.1.1": {"functions/tide.fish": digest(b"t")}}})
        self.assertIn("wrote the pins of 2 files to", out.getvalue())

    def test_a_download_that_fails_writes_nothing(self):
        def fetch(url):
            raise OSError("network is unreachable")

        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()) as err:
            output = Path(tmp) / "pins.json"
            self.assertEqual(pins.main([str(output)], fetch=fetch), 1)
            self.assertFalse(output.exists())
        self.assertEqual(err.getvalue(), "pins: network is unreachable\n")


class CheckedInPinsTest(unittest.TestCase):
    def test_pins_fisher_4_4_5_and_tide_6_1_1(self):
        data = content.load_pins()
        self.assertEqual(data["bootstrap"]["url"], pins.BOOTSTRAP)
        self.assertEqual(tuple(data["plugins"]), pins.PLUGINS)
        fisher, tide = data["plugins"].values()
        # The bootstrap file is the one fisher then installs as its own function.
        self.assertEqual(fisher["functions/fisher.fish"], data["bootstrap"]["sha256"])
        self.assertEqual(sorted(fisher), ["completions/fisher.fish", "functions/fisher.fish"])
        for name in ("functions/fish_prompt.fish", "functions/tide.fish", "conf.d/_tide_init.fish",
                     "functions/tide/configure/icons.fish"):
            self.assertIn(name, tide)
        self.assertEqual(len(tide), 83)

    def test_a_file_without_every_hash_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            for broken in ({}, {"bootstrap": {"url": "u", "sha256": "x"}, "plugins": {"a@1": {"f": "0" * 64}}},
                           {"bootstrap": {"url": "u", "sha256": "0" * 64}, "plugins": {"a@1": {}}}):
                (Path(tmp) / content.PINS).write_text(json.dumps(broken), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "pins.json must hold"):
                    content.load_pins(Path(tmp))


if __name__ == "__main__":
    unittest.main()
