import unittest

from tests.fakes import make_ttf, make_zip, reg_listing
from witchy import fonts


class FullNameTest(unittest.TestCase):
    def test_reads_the_full_font_name(self):
        self.assertEqual(fonts.full_name(make_ttf("Maple Mono NF Bold Italic")), "Maple Mono NF Bold Italic")

    def test_not_a_font(self):
        with self.assertRaises(fonts.FontArchiveError):
            fonts.full_name(b"not a font")


class ExtractTest(unittest.TestCase):
    def members(self):
        return {name: make_ttf(name) for name in fonts.MEMBERS}

    def test_extracts_only_the_named_members(self):
        archive = make_zip({**self.members(), "MapleMono-NF-Thin.ttf": b"x", "../evil.ttf": b"x"})
        self.assertEqual(set(fonts.extract(archive)), set(fonts.MEMBERS))

    def test_missing_member(self):
        members = self.members()
        del members["MapleMono-NF-Bold.ttf"]
        with self.assertRaises(fonts.FontArchiveError):
            fonts.extract(make_zip(members))

    def test_oversized_member(self):
        with self.assertRaises(fonts.FontArchiveError):
            fonts.extract(make_zip(self.members()), limit=10)

    def test_not_a_zip(self):
        with self.assertRaises(fonts.FontArchiveError):
            fonts.extract(b"not a zip")


class RegistryTest(unittest.TestCase):
    def test_parse(self):
        text = reg_listing({"Fira Code Light (TrueType)": "C:\\Users\\u\\Fonts\\Fira.ttf", "Arial (TrueType)": "arial.ttf"})
        self.assertEqual(fonts.parse_registry(text), {"Fira Code Light (TrueType)": "C:\\Users\\u\\Fonts\\Fira.ttf",
                                                      "Arial (TrueType)": "arial.ttf"})

    def test_no_reg_exe_is_none(self):
        def missing(args, **kwargs):
            raise FileNotFoundError("reg.exe")
        self.assertIsNone(fonts.registered(missing))

    def test_register_command(self):
        self.assertEqual(fonts.register_command("Maple Mono NF Regular (TrueType)", "C:\\F\\a.ttf"),
                         ["reg.exe", "add", fonts.REGISTRY_KEY, "/v", "Maple Mono NF Regular (TrueType)",
                          "/t", "REG_SZ", "/d", "C:\\F\\a.ttf", "/f"])


if __name__ == "__main__":
    unittest.main()
