import json
import tempfile
import unittest
from pathlib import Path

from witchy import build, content, palette


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.outputs = build.render_outputs()

    def test_outputs_cover_every_artifact(self):
        self.assertEqual(set(self.outputs), {build.THEME, build.OUTPUT_STYLE, build.STATUSLINE, build.TIPS, build.WT_SCHEME})

    def test_theme_file(self):
        self.assertEqual(json.loads(self.outputs[build.THEME]),
                         {"name": "Moonlit Candle", "base": "dark", "overrides": palette.CLAUDE_OVERRIDES})

    def test_scheme_file(self):
        self.assertEqual(json.loads(self.outputs[build.WT_SCHEME]), palette.WT_SCHEME)

    def test_tips_file(self):
        data = json.loads(self.outputs[build.TIPS])
        self.assertEqual(list(data), ["tips"])
        self.assertEqual(data["tips"], content.load_spinner()["tips"])

    def test_output_style_is_copied_verbatim(self):
        self.assertEqual(self.outputs[build.OUTPUT_STYLE], content.read_output_style())

    def test_source_palette_block_matches_palette(self):
        self.assertEqual(build.statusline_source(), build.STATUSLINE_SOURCE.read_text(encoding="utf-8"))

    def test_palette_block_is_rewritten(self):
        source = build.statusline_source(dict(palette.STATUSLINE, model="#123456"))
        self.assertIn('    "model": "#123456",\n', source)

    def test_generated_statusline_compiles(self):
        compile(self.outputs[build.STATUSLINE], "statusline.py", "exec")

    def test_missing_palette_block_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "statusline.py"
            source.write_text("PALETTE = {}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                build.statusline_source(source=source)

    def test_write_dist(self):
        with tempfile.TemporaryDirectory() as tmp:
            build.write_dist(self.outputs, Path(tmp))
            for rel, text in self.outputs.items():
                self.assertEqual((Path(tmp) / rel).read_text(encoding="utf-8"), text)

    def test_build_refuses_invalid_content(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as empty:
            failures = build.build(dist=Path(tmp) / "dist", content_dir=Path(empty))
            self.assertTrue(failures)
            self.assertFalse((Path(tmp) / "dist").exists())

    def test_build_writes_dist_when_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(build.build(dist=Path(tmp)), [])
            self.assertTrue((Path(tmp) / build.THEME).is_file())


if __name__ == "__main__":
    unittest.main()
