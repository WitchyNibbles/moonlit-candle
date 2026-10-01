import json
import tempfile
import unittest
from pathlib import Path

from witchy import jsonio, records


class ReadJsonTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def write(self, name, text):
        path = self.dir / name
        path.write_bytes(text.encode("utf-8"))
        return path

    def test_reads_data_and_exact_text(self):
        text = '{\r\n    "a": 1\r\n}\r\n'
        data, raw = jsonio.read_json(self.write("a.json", text))
        self.assertEqual(data, {"a": 1})
        self.assertEqual(raw, text)

    def test_comments_trailing_commas_and_bom_are_not_plain_json(self):
        for text in ('{\n  // note\n  "a": 1\n}\n', '{"a": 1,}\n', '﻿{"a": 1}\n'):
            with self.assertRaises(jsonio.StrictJsonError, msg=text):
                jsonio.read_json(self.write("bad.json", text))

    def test_urls_with_double_slashes_are_fine(self):
        data, _ = jsonio.read_json(self.write("url.json", '{"$help": "https://aka.ms/terminal-documentation"}'))
        self.assertEqual(data["$help"], "https://aka.ms/terminal-documentation")


class DumpsLikeTest(unittest.TestCase):
    def test_detect_indent(self):
        self.assertEqual(jsonio.detect_indent('{\n  "a": 1\n}'), "  ")
        self.assertEqual(jsonio.detect_indent('{\n    "a": 1\n}'), "    ")
        self.assertEqual(jsonio.detect_indent('{\n\t"a": 1\n}'), "\t")
        self.assertEqual(jsonio.detect_indent("{}"), "  ")

    def test_round_trips_claude_style(self):
        text = json.dumps({"env": {"A": "1"}, "theme": "dark", "name": "Símbolo"}, indent=2, ensure_ascii=False) + "\n"
        self.assertEqual(jsonio.dumps_like(json.loads(text), text), text)

    def test_dumps_like_keeps_ascii_escapes_and_indent(self):
        text = json.dumps({"profiles": {"list": [{"name": "Símbolo del sistema"}]}}, indent=4) + "\n"
        self.assertIn("\\u00ed", text)
        self.assertEqual(jsonio.dumps_like(json.loads(text), text), text)

    def test_keeps_crlf_and_missing_final_newline(self):
        self.assertEqual(jsonio.dumps_like({"a": 1}, '{\r\n  "a": 0\r\n}\r\n'), '{\r\n  "a": 1\r\n}\r\n')
        self.assertEqual(jsonio.dumps_like({"a": 1}, '{\n  "a": 0\n}'), '{\n  "a": 1\n}')

    def test_fresh_file_style(self):
        self.assertEqual(jsonio.dumps_like({"a": "í"}, None), '{\n  "a": "í"\n}\n')


class WriteAndBackupTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def test_write_atomic_creates_parents_and_leaves_no_temp_files(self):
        path = self.dir / "a" / "b" / "file.json"
        jsonio.write_atomic_bytes(path, b"one")
        jsonio.write_atomic_bytes(path, b"two")
        self.assertEqual(path.read_bytes(), b"two")
        self.assertEqual([p.name for p in path.parent.iterdir()], ["file.json"])

    def test_backup_is_dated_and_never_overwrites(self):
        path = self.dir / "settings.json"
        path.write_bytes(b"original")
        first = jsonio.backup(path, "20260930-120000")
        second = jsonio.backup(path, "20260930-120000")
        self.assertEqual(first.name, "settings.json.bak-witchy-20260930-120000")
        self.assertEqual(second.name, "settings.json.bak-witchy-20260930-120000-1")
        self.assertEqual(first.read_bytes(), b"original")


class RecordsTest(unittest.TestCase):
    def test_snapshot_and_put_back(self):
        data = {"a": {"x": 1}}
        present, absent = records.snapshot(data, "a"), records.snapshot(data, "b")
        self.assertEqual(present, {"value": {"x": 1}})
        self.assertEqual(absent, {"absent": True})
        data["a"]["x"] = 2
        self.assertEqual(present, {"value": {"x": 1}})  # a deep copy, not a live reference
        data["b"] = 5
        records.put_back(data, "a", present)
        records.put_back(data, "b", absent)
        self.assertEqual(data, {"a": {"x": 1}})


if __name__ == "__main__":
    unittest.main()
