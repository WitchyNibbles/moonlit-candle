import unittest
from pathlib import Path

from witchy import claude_settings, records

ORIGINAL = {
    "env": {"A": "1"},
    "statusLine": {"type": "command", "command": "archon statusline", "padding": 0},
    "theme": "dark",
    "agentPushNotifEnabled": True,
}


class DesiredKeysTest(unittest.TestCase):
    def test_exact_values(self):
        desired = claude_settings.desired_keys(Path("/home/u"), "/usr/bin/python3", ["Brewing"])
        self.assertEqual(tuple(desired), claude_settings.KEYS)
        self.assertEqual(desired, {
            "theme": "custom:moonlit-candle",
            "statusLine": {"type": "command", "command": "/usr/bin/python3 -I /home/u/.claude/witchy/statusline.py",
                           "padding": 0},
            "spinnerVerbs": {"mode": "replace", "verbs": ["Brewing"]},
            "spinnerTipsOverride": {"label": "Grimoire", "tipsFile": "~/.claude/witchy/tips.json", "excludeDefault": False},
            "outputStyle": "WitchyNibbles",
        })

    def test_paths_with_spaces_are_quoted(self):
        desired = claude_settings.desired_keys(Path("/home/a b"), "/usr/bin/python3", [])
        self.assertEqual(desired["statusLine"]["command"], "/usr/bin/python3 -I '/home/a b/.claude/witchy/statusline.py'")


class ApplyRestoreTest(unittest.TestCase):
    def setUp(self):
        self.desired = claude_settings.desired_keys(Path("/home/u"), "/usr/bin/python3", ["Brewing"])

    def test_apply_keeps_unrelated_keys_and_order(self):
        result, recs = claude_settings.apply_keys(ORIGINAL, self.desired, None)
        self.assertEqual(list(result), ["env", "statusLine", "theme", "agentPushNotifEnabled",
                                        "spinnerVerbs", "spinnerTipsOverride", "outputStyle"])
        self.assertEqual(result["env"], {"A": "1"})
        self.assertEqual(recs["theme"], {"previous": {"value": "dark"}, "installed": "custom:moonlit-candle"})
        self.assertEqual(recs["outputStyle"]["previous"], {"absent": True})
        self.assertEqual(ORIGINAL["theme"], "dark")  # input untouched

    def test_reinstall_keeps_the_first_previous_value(self):
        installed, first = claude_settings.apply_keys(ORIGINAL, self.desired, None)
        _, second = claude_settings.apply_keys(dict(installed, theme="light"), self.desired, first)
        self.assertEqual(second["theme"]["previous"], {"value": "dark"})

    def test_restore_round_trip(self):
        installed, recs = claude_settings.apply_keys(ORIGINAL, self.desired, None)
        restored, warnings = claude_settings.restore_keys(installed, recs)
        self.assertEqual(restored, ORIGINAL)
        self.assertEqual(list(restored), list(ORIGINAL))
        self.assertEqual(warnings, [])

    def test_restore_leaves_a_key_the_user_changed(self):
        installed, recs = claude_settings.apply_keys(ORIGINAL, self.desired, None)
        restored, warnings = claude_settings.restore_keys(dict(installed, outputStyle="Concise"), recs)
        self.assertEqual(restored["outputStyle"], "Concise")
        self.assertEqual(restored["theme"], "dark")
        self.assertEqual(len(warnings), 1)
        self.assertIn("outputStyle", warnings[0])


    def test_restore_is_silent_for_a_key_that_is_already_restored(self):
        installed, recs = claude_settings.apply_keys(ORIGINAL, self.desired, None)
        once, _ = claude_settings.restore_keys(installed, recs)
        again, warnings = claude_settings.restore_keys(once, recs)
        self.assertEqual(again, ORIGINAL)
        self.assertEqual(warnings, [])
        # a key restored by hand is skipped; a key the user changed still warns
        partial = dict(installed, outputStyle="Concise", theme="dark")
        restored, warnings = claude_settings.restore_keys(partial, recs)
        self.assertEqual(restored["outputStyle"], "Concise")
        self.assertEqual(len(warnings), 1)
        self.assertIn("outputStyle", warnings[0])


class EqualValueTest(unittest.TestCase):
    def setUp(self):
        self.desired = claude_settings.desired_keys(Path("/home/u"), "/usr/bin/python3", ["Brewing"])

    def test_an_equal_value_keeps_its_member_order(self):
        tips = self.desired["spinnerTipsOverride"]
        reordered = dict(reversed(list(tips.items())))
        result, recs = claude_settings.apply_keys({"spinnerTipsOverride": reordered}, self.desired, None)
        self.assertEqual(list(result["spinnerTipsOverride"]), list(reordered))
        self.assertEqual(recs["spinnerTipsOverride"]["previous"], {"value": reordered})

    def test_restore_accepts_other_values_that_count_as_installed(self):
        recs = {"backgroundImage": {"previous": {"absent": True}, "installed": "sky-1.png"}}
        restored, warnings = records.restore_keys({"backgroundImage": "sky-3.png"}, recs,
                                                  also_installed={"backgroundImage": ("sky-3.png",)})
        self.assertEqual((restored, warnings), ({}, []))

    def test_is_installed(self):
        record = {"previous": {"absent": True}, "installed": "a"}
        self.assertTrue(records.is_installed({"k": "a"}, "k", record))
        self.assertTrue(records.is_installed({"k": "b"}, "k", record, also=("b",)))
        self.assertFalse(records.is_installed({}, "k", record))


if __name__ == "__main__":
    unittest.main()
