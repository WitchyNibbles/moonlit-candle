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

    def test_an_equal_scheme_keeps_its_key_order(self):
        data = settings()
        data["schemes"] = [dict(sorted(palette.WT_SCHEME.items()))]  # what Windows Terminal saves
        result, _ = wt.apply_scheme(data, palette.WT_SCHEME, UBUNTU, None)
        self.assertEqual(list(result["schemes"][0]), sorted(palette.WT_SCHEME))

    def test_manual_snippet(self):
        snippet = wt.manual_snippet(palette.WT_SCHEME, UBUNTU)
        self.assertIn('"name": "Moonlit Candle"', snippet)
        self.assertIn(UBUNTU, snippet)
        self.assertIn('"colorScheme": "Moonlit Candle"', snippet)


CMD = "{0caa0dad-35be-5f56-a8ff-afceeeaa6101}"
PASTEL = {"name": "PastelOneDark", "background": "#282C34", "foreground": "#F5C6E0"}
CAMPBELL = {"name": "Campbell", "background": "#0C0C0C", "foreground": "#CCCCCC"}


def pastel_settings():
    """This PC before the purge: PastelOneDark is the default scheme, set on PowerShell and cmd, and defined."""
    data = settings()
    data["profiles"]["defaults"] = {"colorScheme": "PastelOneDark", "font": {"face": "Cascadia Mono"}}
    for profile in data["profiles"]["list"][:2]:
        profile["colorScheme"] = "PastelOneDark"
    data["schemes"] = [copy.deepcopy(PASTEL), copy.deepcopy(CAMPBELL)]
    return data


def installed(data, recorded=None):
    """apply_scheme, then the purge, as the component does."""
    result, record = wt.apply_scheme(data, palette.WT_SCHEME, UBUNTU, recorded)
    result, record["purged"] = wt.purge_schemes(result, palette.PURGED_SCHEMES, palette.THEME_NAME,
                                                (recorded or {}).get("purged"))
    return result, record


def uninstalled(data, record):
    """restore_purged, then restore_scheme, as the component does."""
    result, warnings = wt.restore_purged(data, record["purged"])
    result, more = wt.restore_scheme(result, record)
    return result, warnings + more


class PurgeTest(unittest.TestCase):
    def test_the_default_profiles_and_definition_lose_the_purged_scheme(self):
        result, record = installed(pastel_settings())
        self.assertEqual(result["profiles"]["defaults"], {"colorScheme": "Moonlit Candle",
                                                          "font": {"face": "Cascadia Mono"}})
        profiles = {p["guid"]: p for p in result["profiles"]["list"]}
        self.assertNotIn("colorScheme", profiles[POWERSHELL])
        self.assertNotIn("colorScheme", profiles[CMD])
        self.assertEqual(result["schemes"], [CAMPBELL, palette.WT_SCHEME])
        self.assertEqual(record["purged"], {
            "defaults": {"previous": {"value": "PastelOneDark"}, "installed": "Moonlit Candle"},
            "profiles": {POWERSHELL: {"value": "PastelOneDark"}, CMD: {"value": "PastelOneDark"}},
            "schemes": [{"index": 0, "value": PASTEL}],
        })
        self.assertEqual([wt.purged_uses(result, name) for name in palette.PURGED_SCHEMES], [[]])

    def test_uninstall_gives_every_value_back_in_place(self):
        original = pastel_settings()
        restored, warnings = uninstalled(*installed(original))
        self.assertEqual((restored, warnings), (original, []))
        self.assertEqual(list(restored["profiles"]["list"][0]), ["guid", "name", "colorScheme"])

    def test_a_light_and_dark_pair_that_names_a_purged_scheme_is_purged_whole(self):
        data = pastel_settings()
        data["profiles"]["list"][0]["colorScheme"] = {"light": "Campbell", "dark": "PastelOneDark"}
        result, record = installed(data)
        self.assertNotIn("colorScheme", wt.profile(result, POWERSHELL))
        self.assertEqual(record["purged"]["profiles"][POWERSHELL],
                         {"value": {"light": "Campbell", "dark": "PastelOneDark"}})
        self.assertEqual(uninstalled(result, record), (data, []))

    def test_settings_without_the_purged_scheme_record_nothing(self):
        result, record = installed(settings())
        self.assertEqual(record["purged"], {"defaults": None, "profiles": {}, "schemes": []})
        self.assertEqual(result["profiles"]["defaults"], {})
        self.assertEqual(uninstalled(result, record), (settings(), []))

    def test_a_reinstall_keeps_the_first_record(self):
        first_data, first = installed(pastel_settings())
        again = copy.deepcopy(first_data)
        again["profiles"]["defaults"]["colorScheme"] = "PastelOneDark"  # put back by hand, then reinstalled
        again["schemes"].append({"name": "PastelOneDark", "background": "#000000"})
        second_data, second = installed(again, first)
        self.assertEqual(second["purged"], first["purged"])
        self.assertEqual(second_data, first_data)

    def test_a_reinstall_records_a_profile_that_took_the_scheme_since(self):
        first_data, first = installed(pastel_settings())
        again = copy.deepcopy(first_data)
        wt.profile(again, UBUNTU)["colorScheme"] = "Moonlit Candle"
        again["profiles"]["list"].append({"guid": "{22222222-2222-2222-2222-222222222222}", "name": "Azure",
                                          "colorScheme": "PastelOneDark"})
        _, second = installed(again, first)
        self.assertEqual(second["purged"]["profiles"]["{22222222-2222-2222-2222-222222222222}"],
                         {"value": "PastelOneDark"})
        self.assertEqual(second["purged"]["profiles"][POWERSHELL], {"value": "PastelOneDark"})

    def test_uninstall_leaves_what_the_user_changed_since(self):
        result, record = installed(pastel_settings())
        result["profiles"]["defaults"]["colorScheme"] = "Campbell"
        wt.profile(result, POWERSHELL)["colorScheme"] = "Campbell"
        result["schemes"].insert(0, {"name": "PastelOneDark", "background": "#111111"})
        restored, warnings = uninstalled(result, record)
        self.assertEqual(restored["profiles"]["defaults"]["colorScheme"], "Campbell")
        self.assertEqual(wt.profile(restored, POWERSHELL)["colorScheme"], "Campbell")
        self.assertEqual(wt.profile(restored, CMD)["colorScheme"], "PastelOneDark")
        self.assertEqual(restored["schemes"][0], {"name": "PastelOneDark", "background": "#111111"})
        self.assertEqual(len(warnings), 3)
        self.assertTrue(all("after install" in warning for warning in warnings), warnings)

    def test_uninstall_twice_is_silent_and_a_deleted_profile_is_skipped(self):
        original = pastel_settings()
        result, record = installed(original)
        once, _ = uninstalled(result, record)
        self.assertEqual(wt.restore_purged(once, record["purged"]), (original, []))
        result["profiles"]["list"] = [p for p in result["profiles"]["list"] if p["guid"] != CMD]
        restored, warnings = uninstalled(result, record)
        self.assertEqual((len(restored["profiles"]["list"]), warnings), (2, []))

    def test_uninstall_puts_back_a_schemes_list_the_user_deleted(self):
        result, record = installed(pastel_settings())
        del result["schemes"]
        restored, _ = wt.restore_purged(result, record["purged"])
        self.assertEqual(restored["schemes"], [PASTEL])

    def test_an_entry_from_before_the_purge_restores_as_before(self):
        result, _ = installed(pastel_settings())
        self.assertEqual(wt.restore_purged(result, None), (result, []))

    def test_the_witchy_scheme_is_never_purged(self):
        self.assertNotIn(palette.WT_SCHEME["name"], palette.PURGED_SCHEMES)

    def test_purged_uses_names_every_place(self):
        data = pastel_settings()
        self.assertEqual(wt.purged_uses(data, "PastelOneDark"),
                         ["schemes", "profiles.defaults", "profile 'Windows PowerShell'",
                          "profile 'Símbolo del sistema'"])
        self.assertEqual(wt.purged_uses(data, "Campbell"), ["schemes"])
        self.assertEqual(wt.purged_uses({"profiles": "odd", "schemes": {}}, "PastelOneDark"), [])



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
        calls = []
        run = fake_windows(echo={"USERPROFILE": "C:\\Users\\manue\r\n", "USERNAME": "Manuel\r\n"}, calls=calls)
        found = wt.locate_settings(None, run=run, users_root=self.mnt / "c" / "Users", mount_root=self.mnt)
        self.assertEqual(found, self.settings)
        self.assertNotIn(["cmd.exe", "/c", "echo %USERNAME%"], calls)

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


if __name__ == "__main__":
    unittest.main()
