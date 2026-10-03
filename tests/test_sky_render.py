import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from witchy import palette, sky_render

SMALL = (256, 144)


def decode(png):
    width, height = struct.unpack(">II", png[16:24])
    length = struct.unpack(">I", png[33:37])[0]
    return width, height, zlib.decompress(png[41:41 + length])


def pixel(width, raw, x, y):
    offset = y * (1 + 3 * width) + 1 + 3 * x
    return "#%02X%02X%02X" % tuple(raw[offset:offset + 3])


class RenderTest(unittest.TestCase):
    def test_small_renders_are_deterministic(self):
        self.assertEqual(sky_render.render(3, palette.SKY, SMALL), sky_render.render(3, palette.SKY, SMALL))

    def test_moon_sits_bottom_right_lit_on_the_right_when_waxing(self):
        width, height, raw = decode(sky_render.render(2, palette.SKY, SMALL))  # first quarter
        cx, cy = width - 26, height - 26  # 260 px from the edges at full size, scaled by 256/2560
        self.assertEqual(pixel(width, raw, cx + 7, cy), palette.SKY["moon"])
        self.assertEqual(pixel(width, raw, cx - 7, cy), palette.SKY["moon_dark"])

    def test_new_moon_is_dark(self):
        width, height, raw = decode(sky_render.render(0, palette.SKY, SMALL))
        self.assertEqual(pixel(width, raw, width - 26, height - 26), palette.SKY["moon_dark"])

    def test_the_starfield_is_shared_by_every_phase(self):
        _, height, one = decode(sky_render.render(1, palette.SKY, SMALL))
        _, _, five = decode(sky_render.render(5, palette.SKY, SMALL))
        half = (height // 2) * (1 + 3 * SMALL[0])  # the moon and its glow stay in the lower half
        self.assertEqual(one[:half], five[:half])

    def test_one_full_size_render(self):
        width, height, raw = decode(sky_render.render(4, palette.SKY))
        self.assertEqual((width, height), sky_render.SIZE)
        self.assertEqual(pixel(width, raw, width - 260, height - 260), palette.SKY["moon"])


class CacheTest(unittest.TestCase):
    def test_second_call_uses_the_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = sky_render.cached(Path(tmp), palette.SKY, SMALL)
            with mock.patch.object(sky_render, "render", side_effect=AssertionError("must not render")):
                second = sky_render.cached(Path(tmp), palette.SKY, SMALL)
        self.assertEqual(len(first), 8)
        self.assertEqual(first, second)

    def test_no_write_leaves_no_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            sky_render.cached(Path(tmp), palette.SKY, SMALL, write=False)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_an_unreadable_cache_file_is_a_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = sky_render.cached(Path(tmp), palette.SKY, SMALL)
            real = Path.read_bytes

            def read_bytes(path):
                if path.name == "sky-3.png":
                    raise PermissionError("denied")
                return real(path)

            with mock.patch.object(Path, "read_bytes", read_bytes):
                second = sky_render.cached(Path(tmp), palette.SKY, SMALL)
        self.assertEqual(first, second)

    def test_a_cache_file_that_is_not_a_whole_png_is_rendered_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = sky_render.cached(Path(tmp), palette.SKY, SMALL)
            files = sorted(Path(tmp).glob("*/sky-*.png"))
            files[0].write_bytes(b"not a png")
            files[1].write_bytes(first[1][:-5])  # cut short, so no IEND
            second = sky_render.cached(Path(tmp), palette.SKY, SMALL)
            self.assertEqual(files[0].read_bytes(), first[0])
        self.assertEqual(first, second)

    def test_older_cache_directories_are_pruned_after_a_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "0123456789abcdef").mkdir()
            (root / "0123456789abcdef" / "sky-0.png").write_bytes(b"old")
            (root / "notes").mkdir()
            (root / "ABCDEF0123456789").mkdir()  # not a key: keys are lowercase hex
            (root / "0123456789abcde0").write_text("a file, not a directory")
            sky_render.cached(root, palette.SKY, SMALL)
            names = sorted(path.name for path in root.iterdir())
            self.assertEqual(len(names), 4)
            self.assertNotIn("0123456789abcdef", names)
            self.assertEqual(sum(1 for name in names if len(name) == 16 and (root / name / "sky-0.png").is_file()), 1)
            for kept in ("notes", "ABCDEF0123456789", "0123456789abcde0"):
                self.assertIn(kept, names)

    def test_a_dry_run_prunes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "0123456789abcdef").mkdir()
            sky_render.cached(Path(tmp), palette.SKY, SMALL, write=False)
            self.assertTrue((Path(tmp) / "0123456789abcdef").is_dir())


if __name__ == "__main__":
    unittest.main()
