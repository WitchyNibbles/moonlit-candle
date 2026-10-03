import io
import unittest
from pathlib import Path

from witchy.components.base import Change, show_changes

PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


class Ctx:
    def __init__(self):
        self.out = io.StringIO()

    def say(self, message):
        print(message, file=self.out)


class ShowChangesTest(unittest.TestCase):
    def test_binary_files_are_summarised(self):
        ctx = Ctx()
        show_changes(ctx, [Change(Path("/x/new.png"), None, PNG), Change(Path("/x/old.png"), PNG, PNG + b"\x00")])
        self.assertEqual(ctx.out.getvalue().splitlines(),
                         ["create /x/new.png (binary, 16 bytes)", "update /x/old.png (binary, 16 → 17 bytes)"])

    def test_text_files_still_show_a_diff(self):
        ctx = Ctx()
        show_changes(ctx, [Change(Path("/x/a.json"), b'{"a": 1}\n', b'{"a": 2}\n')])
        self.assertIn('+{"a": 2}', ctx.out.getvalue())


if __name__ == "__main__":
    unittest.main()
