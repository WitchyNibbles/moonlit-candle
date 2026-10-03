import tempfile
import unittest
from pathlib import Path

from tests.fakes import fake_windows
from witchy import windows


class ToWslTest(unittest.TestCase):
    def test_drive_paths(self):
        self.assertEqual(windows.to_wsl("C:\\Users\\manue"), Path("/mnt/c/Users/manue"))
        self.assertEqual(windows.to_wsl("D:\\Data\\x\\", Path("/m")), Path("/m/d/Data/x"))

    def test_other_paths_are_not_mapped(self):
        self.assertIsNone(windows.to_wsl("arial.ttf"))
        self.assertIsNone(windows.to_wsl("\\\\server\\share\\x"))


class UserHomeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.mnt = Path(tmp.name) / "mnt"

    def test_profile_folder_from_userprofile(self):
        (self.mnt / "c" / "Users" / "manue").mkdir(parents=True)
        run = fake_windows(echo={"USERPROFILE": "C:\\Users\\manue\r\n"})
        self.assertEqual(windows.user_home(run, self.mnt),
                         windows.WindowsHome("C:\\Users\\manue", self.mnt / "c" / "Users" / "manue"))

    def test_a_percent_sign_in_the_profile_path_is_a_value_not_an_unset_variable(self):
        (self.mnt / "c" / "Users" / "100%").mkdir(parents=True)
        run = fake_windows(echo={"USERPROFILE": "C:\\Users\\100%\r\n"})
        self.assertEqual(windows.echo("USERPROFILE", run), "C:\\Users\\100%")
        self.assertEqual(windows.user_home(run, self.mnt),
                         windows.WindowsHome("C:\\Users\\100%", self.mnt / "c" / "Users" / "100%"))
        self.assertIsNone(windows.echo("USERPROFILE", fake_windows()))  # cmd.exe prints %USERPROFILE% back

    def test_missing_folder_or_variable_is_none(self):
        self.assertIsNone(windows.user_home(fake_windows(echo={"USERPROFILE": "C:\\Users\\gone\r\n"}), self.mnt))
        self.assertIsNone(windows.user_home(fake_windows(), self.mnt))

    def test_no_cmd_exe_is_none(self):
        def missing(args, **kwargs):
            raise FileNotFoundError("cmd.exe")
        self.assertIsNone(windows.user_home(missing, self.mnt))


if __name__ == "__main__":
    unittest.main()
