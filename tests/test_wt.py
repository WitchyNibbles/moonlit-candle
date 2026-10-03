import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.fakes import fake_windows
from witchy import palette, wt

UBUNTU = "{05f3f843-450a-55ad-a264-cacf368dafe5}"
POWERSHELL = "{61c54bbd-c2c6-5271-96e7-009a87ff44bf}"


def settings():
    return {
        "$help": "https://aka.ms/terminal-documentation",
        "profiles": {"defaults": {}, "list": [
            {"guid": POWERSHELL, "name": "Windows PowerShell"},
            {"guid": "{0caa0dad-35be-5f56-a8ff-afceeeaa6101}", "name": "Símbolo del sistema"},
            {"guid": UBUNTU, "name": "Ubuntu", "source": "Microsoft.WSL", "colorScheme": "One Half Dark"},
        ]},
        "schemes": [],
    }


def fake_run(stdout="", returncode=0, error=None):
    def run(args, **kwargs):
        if error:
            raise error
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr="")
    return run


class LocateTest(unittest.TestCase):
    def test_windows_username(self):
        self.assertEqual(wt.windows_username(fake_run("mmarenas\r\n")), "mmarenas")
        self.assertIsNone(wt.windows_username(fake_run("", returncode=1)))
        self.assertIsNone(wt.windows_username(fake_run("%USERNAME%\r\n")))
        self.assertIsNone(wt.windows_username(fake_run(error=FileNotFoundError("cmd.exe"))))

    def test_windows_username_survives_undecodable_output(self):
        # cmd.exe writes in the OEM code page, so a name like "José" is not valid UTF-8.
        error = UnicodeDecodeError("utf-8", b"\xa2", 0, 1, "invalid start byte")
        self.assertIsNone(wt.windows_username(fake_run(error=error)))

    def test_locate_uses_the_current_windows_user_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for user in ("admin", "mmarenas"):
                path = wt.settings_path_for(user, root)
                path.parent.mkdir(parents=True)
                path.write_text("{}")
            found = wt.locate_settings(None, run=fake_run("mmarenas\r\n"), users_root=root)
            self.assertEqual(found, wt.settings_path_for("mmarenas", root))
            self.assertIsNone(wt.locate_settings(None, run=fake_run("nobody\r\n"), users_root=root))

    def test_explicit_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            self.assertIsNone(wt.locate_settings(path, run=fake_run(error=AssertionError("must not run"))))
            path.write_text("{}")
            self.assertEqual(wt.locate_settings(path, run=fake_run(error=AssertionError("must not run"))), path)


class FindProfileTest(unittest.TestCase):
    def test_profile_id_match_is_case_insensitive(self):
        self.assertEqual(wt.find_profile(settings(), {"WT_PROFILE_ID": UBUNTU.upper()}), (UBUNTU, None))

    def test_stale_profile_id_falls_back_to_distro(self):
        env = {"WT_PROFILE_ID": "{00000000-0000-0000-0000-000000000000}", "WSL_DISTRO_NAME": "Ubuntu"}
        self.assertEqual(wt.find_profile(settings(), env), (UBUNTU, None))

    def test_no_profile_id_uses_distro(self):
        self.assertEqual(wt.find_profile(settings(), {"WSL_DISTRO_NAME": "Ubuntu"}), (UBUNTU, None))

    def test_nothing_to_go_on(self):
        guid, reason = wt.find_profile(settings(), {})
        self.assertIsNone(guid)
        self.assertTrue(reason)

    def test_two_matching_wsl_profiles_are_ambiguous(self):
        data = settings()
        data["profiles"]["list"].append({"guid": "{11111111-1111-1111-1111-111111111111}", "name": "Ubuntu",
                                         "source": "Microsoft.WSL"})
        self.assertIsNone(wt.find_profile(data, {"WSL_DISTRO_NAME": "Ubuntu"})[0])

    def test_profiles_as_a_plain_list(self):
        data = settings()
        data["profiles"] = data["profiles"]["list"]
        self.assertEqual(wt.find_profile(data, {"WT_PROFILE_ID": UBUNTU}), (UBUNTU, None))

    def test_missing_profiles(self):
        self.assertIsNone(wt.find_profile({}, {"WT_PROFILE_ID": UBUNTU})[0])


class ApplyRestoreTest(unittest.TestCase):
    def test_apply_sets_only_the_chosen_profile(self):
        result, record = wt.apply_scheme(settings(), palette.WT_SCHEME, UBUNTU, None)
        self.assertEqual(result["schemes"], [palette.WT_SCHEME])
        profiles = {p["guid"]: p for p in result["profiles"]["list"]}
        self.assertEqual(profiles[UBUNTU]["colorScheme"], "Moonlit Candle")
        self.assertNotIn("colorScheme", profiles[POWERSHELL])
        self.assertEqual(record, {
            "profile_guid": UBUNTU,
            "previous_color_scheme": {"value": "One Half Dark"},
            "previous_scheme": {"absent": True},
            "schemes_key_absent": False,
            "installed_color_scheme": "Moonlit Candle",
        })

    def test_apply_replaces_a_scheme_with_the_same_name(self):
        data = settings()
        data["schemes"] = [{"name": "Moonlit Candle", "background": "#000000"}]
        result, record = wt.apply_scheme(data, palette.WT_SCHEME, UBUNTU, None)
        self.assertEqual(result["schemes"], [palette.WT_SCHEME])
        self.assertEqual(record["previous_scheme"], {"value": {"name": "Moonlit Candle", "background": "#000000"}})

    def test_reinstall_keeps_the_first_record(self):
        installed, first = wt.apply_scheme(settings(), palette.WT_SCHEME, UBUNTU, None)
        _, second = wt.apply_scheme(installed, palette.WT_SCHEME, UBUNTU, first)
        self.assertEqual(second, first)

    def test_restore_round_trip(self):
        original = settings()
        installed, record = wt.apply_scheme(original, palette.WT_SCHEME, UBUNTU, None)
        restored, warnings = wt.restore_scheme(installed, record)
        self.assertEqual(restored, original)
        self.assertEqual(warnings, [])

    def test_restore_drops_a_schemes_key_it_created(self):
        original = settings()
        del original["schemes"]
        installed, record = wt.apply_scheme(original, palette.WT_SCHEME, UBUNTU, None)
        self.assertEqual(wt.restore_scheme(installed, record)[0], original)

    def test_restore_leaves_a_changed_profile_and_a_scheme_in_use(self):
        installed, record = wt.apply_scheme(settings(), palette.WT_SCHEME, UBUNTU, None)
        changed = copy.deepcopy(installed)
        for profile in changed["profiles"]["list"]:
            if profile["guid"] == UBUNTU:
                profile["colorScheme"] = "Campbell"
            if profile["guid"] == POWERSHELL:
                profile["colorScheme"] = "Moonlit Candle"
        restored, warnings = wt.restore_scheme(changed, record)
        profiles = {p["guid"]: p for p in restored["profiles"]["list"]}
        self.assertEqual(profiles[UBUNTU]["colorScheme"], "Campbell")
        self.assertEqual(restored["schemes"], [palette.WT_SCHEME])
        self.assertEqual(len(warnings), 2)

    def test_restore_is_silent_when_already_restored(self):
        with_scheme = settings()
        without_scheme = settings()
        del next(p for p in without_scheme["profiles"]["list"] if p["guid"] == UBUNTU)["colorScheme"]
        for original in (with_scheme, without_scheme):
            with self.subTest(previous=original["profiles"]["list"][2].get("colorScheme")):
                installed, record = wt.apply_scheme(original, palette.WT_SCHEME, UBUNTU, None)
                once, warnings = wt.restore_scheme(installed, record)
                again, warnings = wt.restore_scheme(once, record)
                self.assertEqual(again, original)
                self.assertEqual(warnings, [])

    def test_restore_when_the_profile_is_gone(self):
        installed, record = wt.apply_scheme(settings(), palette.WT_SCHEME, UBUNTU, None)
        installed["profiles"]["list"] = [p for p in installed["profiles"]["list"] if p["guid"] != UBUNTU]
        restored, warnings = wt.restore_scheme(installed, record)
        self.assertEqual(restored["schemes"], [])
        self.assertEqual(len(warnings), 1)

    def test_apply_rejects_a_non_list_schemes(self):
        data = dict(settings(), schemes={})
        with self.assertRaises(ValueError):
            wt.apply_scheme(data, palette.WT_SCHEME, UBUNTU, None)

    def test_manual_snippet(self):
        snippet = wt.manual_snippet(palette.WT_SCHEME, UBUNTU)
        self.assertIn('"name": "Moonlit Candle"', snippet)
        self.assertIn(UBUNTU, snippet)
        self.assertIn('"colorScheme": "Moonlit Candle"', snippet)


if __name__ == "__main__":
    unittest.main()


CANONICAL = "{51855cb2-8cce-5362-8f54-464b92b32386}"
HIDDEN = "{2c4de342-38b7-51cf-b940-2309a097f518}"


def store_ubuntu():
    """The two Ubuntu profiles this machine has: a hidden duplicate and the Store distro's own."""
    data = settings()
    data["profiles"]["list"] = [
        {"guid": HIDDEN, "name": "Ubuntu", "source": "Windows.Terminal.Wsl", "hidden": True},
        {"guid": CANONICAL, "name": "Ubuntu", "source": "CanonicalGroupLimited.Ubuntu_79rhkp1fndgsc", "hidden": False},
    ]
    return data


class LookupFixTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.mnt = Path(tmp.name) / "mnt"
        self.settings = wt.settings_path_in(self.mnt / "c" / "Users" / "manue")
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text("{}")

    def test_profile_folder_wins_over_a_renamed_account(self):
        run = fake_windows(echo={"USERPROFILE": "C:\\Users\\manue\r\n", "USERNAME": "Manuel\r\n"})
        found = wt.locate_settings(None, run=run, users_root=self.mnt / "c" / "Users", mount_root=self.mnt)
        self.assertEqual(found, self.settings)

    def test_recorded_path_is_used_without_asking_windows(self):
        calls = []
        found = wt.locate_settings(None, run=fake_windows(calls=calls), recorded=str(self.settings),
                                   mount_root=self.mnt)
        self.assertEqual((found, calls), (self.settings, []))

    def test_stale_recorded_path_falls_back_to_the_profile_folder(self):
        run = fake_windows(echo={"USERPROFILE": "C:\\Users\\manue\r\n"})
        found = wt.locate_settings(None, run=run, recorded=str(self.mnt / "old.json"), mount_root=self.mnt)
        self.assertEqual(found, self.settings)


class StoreProfileTest(unittest.TestCase):
    def test_store_ubuntu_is_found_and_the_hidden_duplicate_ignored(self):
        self.assertEqual(wt.find_profile(store_ubuntu(), {"WSL_DISTRO_NAME": "Ubuntu"}), (CANONICAL, None))

    def test_two_visible_matches_are_ambiguous(self):
        data = store_ubuntu()
        data["profiles"]["list"][0]["hidden"] = False
        self.assertIsNone(wt.find_profile(data, {"WSL_DISTRO_NAME": "Ubuntu"})[0])


class ProfileKeysTest(unittest.TestCase):
    def test_apply_and_restore_round_trip(self):
        data = settings()
        installed, recs = wt.apply_profile_keys(data, UBUNTU, {"cursorShape": "filledBox"}, None)
        self.assertEqual(wt.profile(installed, UBUNTU)["cursorShape"], "filledBox")
        restored, warnings = wt.restore_profile_keys(installed, UBUNTU, recs)
        self.assertEqual((restored, warnings), (data, []))

    def test_any_sky_value_counts_as_installed(self):
        installed, recs = wt.apply_profile_keys(settings(), UBUNTU, {"backgroundImage": wt.SKY_VALUES[1]}, None)
        wt.profile(installed, UBUNTU)["backgroundImage"] = wt.SKY_VALUES[6]
        self.assertTrue(wt.holds_installed(wt.profile(installed, UBUNTU), "backgroundImage", recs["backgroundImage"]))
        restored, warnings = wt.restore_profile_keys(installed, UBUNTU, recs)
        self.assertEqual((restored, warnings), (settings(), []))

    def test_missing_profile(self):
        with self.assertRaises(ValueError):
            wt.apply_profile_keys(settings(), "{00000000-0000-0000-0000-000000000000}", {"icon": "x"}, None)
