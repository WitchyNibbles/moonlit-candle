import unittest

from witchy import content, validate


class OutputStyleTest(unittest.TestCase):
    def test_output_style_names_no_diagnosis(self):
        # The repo is public; the voice rules are what matter, not personal health details.
        self.assertNotIn("ADHD", content.read_output_style())

    def test_output_style_keeps_the_reply_shape_rules(self):
        text = content.read_output_style()
        self.assertIn("## Shape every reply", text)
        self.assertIn("Write for a reader who skims", text)

    def test_content_still_validates(self):
        self.assertEqual([f for f in validate.validate_all() if f.rule == "content"], [])


if __name__ == "__main__":
    unittest.main()
