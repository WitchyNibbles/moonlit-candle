import json
import tempfile
import unittest
from pathlib import Path

from witchy import state
from witchy.errors import Abort

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "state-v1.json"


class MigrateTest(unittest.TestCase):
    def test_migrates_the_real_v1_state_keeping_every_record(self):
        v1 = json.loads(FIXTURE.read_text(encoding="utf-8"))
        v2 = state.migrate(v1)
        self.assertEqual(v2["version"], 2)
        self.assertEqual(v2["variant"], "midnight")
        self.assertIsNone(v2["last_install"])
        self.assertEqual(v2["components"]["claude"], {"files": v1["files"], "settings": v1["claude_settings"]})
        self.assertEqual(v2["components"]["windows-terminal"], v1["windows_terminal"])

    def test_v1_without_windows_terminal_has_no_entry(self):
        v1 = {"version": 1, "files": [], "claude_settings": {"keys": {}}, "windows_terminal": None}
        self.assertNotIn("windows-terminal", state.migrate(v1)["components"])


class LoadSaveTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "witchy" / "state.json"

    def test_missing_file_is_none(self):
        self.assertIsNone(state.load(self.path))

    def test_save_then_load_round_trips(self):
        data = dict(state.empty("midnight"), components={"claude": {"files": []}})
        state.save(self.path, data)
        self.assertEqual(state.load(self.path), data)

    def test_v1_file_loads_as_v2(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
        self.assertEqual(state.load(self.path)["version"], 2)

    def test_damaged_file_aborts(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{", encoding="utf-8")
        with self.assertRaises(Abort) as raised:
            state.load(self.path)
        self.assertIn("The state file is damaged", str(raised.exception))

    def test_unknown_version_aborts(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"version": 9}', encoding="utf-8")
        with self.assertRaises(Abort) as raised:
            state.load(self.path)
        self.assertIn("unknown format", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
