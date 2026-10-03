import copy
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import build, content, palette, validate
from witchy.ritual import palette as ritual_palette
from witchy.ritual import wheel

RITUAL_PALETTE_SOURCE = Path(build.RITUAL_SOURCE) / "palette.py"


def items(failures):
    return {failure.item for failure in failures}


class SabbatNamesTest(unittest.TestCase):
    def test_every_list_of_sabbats_agrees(self):
        self.assertEqual(validate.SABBATS, wheel.SABBATS)
        for name in wheel.SABBATS:
            self.assertIn(name.lower(), palette.RITUAL)
            self.assertIn(name.lower(), ritual_palette.PALETTE)
        self.assertEqual(set(content.load_ritual()["sabbats"]), set(wheel.SABBATS))

    def test_a_variant_without_ritual_colours_fails(self):
        bare = palette.Variant(**{**palette.VARIANTS["midnight"].__dict__, "name": "dawn", "ritual": {}})
        with mock.patch.dict(palette.VARIANTS, {"dawn": bare}):
            failures = validate.validate_all()
        self.assertTrue([f for f in failures if f.rule == "missing-token" and f.item == "ritual.salutation"])


class RitualTextTest(unittest.TestCase):
    def setUp(self):
        self.data = content.load_ritual()

    def check(self, change):
        data = copy.deepcopy(self.data)
        change(data)
        return items(validate.validate_ritual(data))

    def test_real_content_passes(self):
        self.assertEqual(validate.validate_ritual(self.data), [])

    def test_name(self):
        self.assertIn("ritual.name", self.check(lambda d: d.update(name="")))
        self.assertIn("ritual.name", self.check(lambda d: d.update(name="x" * 25)))

    def test_sabbats_and_lunar_lines(self):
        self.assertIn("ritual.sabbats.Yule", self.check(lambda d: d["sabbats"].pop("Yule")))
        self.assertIn("ritual.sabbats.Samhain", self.check(lambda d: d["sabbats"].update(Samhain="x" * 49)))
        self.assertIn("ritual.lunar.blue", self.check(lambda d: d["lunar"].pop("blue")))

    def test_tarot(self):
        self.assertIn("ritual.tarot", self.check(lambda d: d["tarot"].pop()))
        self.assertIn("ritual.tarot", self.check(lambda d: d["tarot"][1].update(number=0)))
        self.assertIn("ritual.tarot", self.check(lambda d: d["tarot"][1].update(name="The Fool")))
        self.assertIn("ritual.tarot.17.reversed", self.check(lambda d: d["tarot"][17].update(reversed="x" * 61)))
        self.assertIn("ritual.tarot.0.upright", self.check(lambda d: d["tarot"][0].update(upright="")))


class RitualPaletteTest(unittest.TestCase):
    def test_midnight_holds_the_module_colours(self):
        self.assertIs(palette.VARIANTS["midnight"].ritual, palette.RITUAL)

    def test_the_package_block_matches_the_palette(self):
        self.assertIn(build.palette_block(palette.RITUAL), RITUAL_PALETTE_SOURCE.read_text(encoding="utf-8"))

    def test_real_palette_passes(self):
        self.assertEqual(validate.validate_ritual_palette(palette.RITUAL), [])

    def test_text_and_accents_need_contrast_but_the_art_does_not(self):
        dark = dict(palette.RITUAL, label="#38234D", samhain="#503762", earthshine="#1D1230")
        self.assertEqual(items(validate.validate_ritual_palette(dark)), {"ritual.label", "ritual.samhain"})

    def test_format_and_missing_keys(self):
        broken = dict(palette.RITUAL, moon="violet")
        del broken["yule"]
        self.assertEqual(items(validate.validate_ritual_palette(broken)), {"ritual.moon", "ritual.yule"})


class ValidateAllTest(unittest.TestCase):
    def test_a_broken_ritual_file_fails_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(content.CONTENT_DIR, tmp, dirs_exist_ok=True)
            (Path(tmp) / content.RITUAL).write_text('{"name": ""}', encoding="utf-8")
            self.assertIn("ritual.name", items(validate.validate_all(Path(tmp))))


if __name__ == "__main__":
    unittest.main()
