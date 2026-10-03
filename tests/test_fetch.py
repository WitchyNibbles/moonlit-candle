import tempfile
import unittest
from pathlib import Path

from witchy.ritual import fetch


class FetchTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "etc").mkdir()
        (self.root / "proc").mkdir()

    def write(self, rel, text):
        (self.root / rel).write_text(text, encoding="utf-8")

    def lines(self, env=None, release="6.6.87.2-microsoft-standard-WSL2"):
        return dict(fetch.lines({"FISH_VERSION": "3.7.0"} if env is None else env, self.root, lambda: release))

    def test_every_value(self):
        self.write("etc/os-release", 'NAME="Ubuntu"\nPRETTY_NAME="Ubuntu 24.04.4 LTS"\n')
        self.write("proc/uptime", "11532.40 40000.00\n")
        self.write("proc/meminfo", "MemTotal:       16357904 kB\nMemFree: 1 kB\nMemAvailable:   12058624 kB\n")
        self.assertEqual(self.lines(), {"os": "Ubuntu 24.04.4 LTS", "kernel": "6.6.87.2-microsoft-standard-WSL2",
                                        "uptime": "3h 12m", "memory": "4.1 / 15.6 GiB", "shell": "fish 3.7.0"})

    def test_missing_values_show_a_dash(self):
        self.assertEqual(self.lines(env={}), {"os": "--", "kernel": "6.6.87.2-microsoft-standard-WSL2",
                                              "uptime": "--", "memory": "--", "shell": "--"})

    def test_uptime_formats(self):
        for seconds, expected in (("59.0", "0m"), ("754.2", "12m"), ("11532.4", "3h 12m"), ("273600.0", "3d 4h")):
            self.write("proc/uptime", f"{seconds} 1.0\n")
            self.assertEqual(self.lines()["uptime"], expected)

    def test_control_characters_are_stripped(self):
        self.write("etc/os-release", 'PRETTY_NAME="Ubuntu\x1b[31m 24.04\x07"\n')
        self.assertEqual(self.lines(release="6.6\x1b]0;x\x07")["os"], "Ubuntu[31m 24.04")
        self.assertEqual(self.lines(release="6.6\x1b]0;x\x07")["kernel"], "6.6]0;x")
        self.assertEqual(fetch.clean("  a\tb\n "), "ab")


if __name__ == "__main__":
    unittest.main()
