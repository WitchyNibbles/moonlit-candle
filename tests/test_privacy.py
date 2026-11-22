"""Guard: no tracked file carries a real person's account name in a path, nor this machine's own login."""
import getpass
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Names the repository uses on purpose as made-up accounts in tests and docs. Anything that looks like a real
# person's name is scrubbed from the file, never added here.
GENERIC_NAMES = frozenset({"user", "u", "x", "a", "o", "gone"})
# Logins that tell nothing about a person; the login rule skips them (and every name under three characters).
GENERIC_LOGINS = frozenset({"root", "runner", "user", "ubuntu", "admin"})

# The account folder after /home/ or Users/. `<user>`, `$USER`, `%USERNAME%`, `.config` and regular-expression
# pieces do not start with a letter or digit, so they never count as a name.
ACCOUNT = r"([^/\\\s\"'`)\]:,;|]+)"
HOME_PATH = re.compile(r"(?<![\w.$}\u2026])/home/" + ACCOUNT)
WSL_USERS_PATH = re.compile(r"/mnt/[a-z]/Users/" + ACCOUNT, re.IGNORECASE)
WINDOWS_USERS_PATH = re.compile(r"[a-z]:\\{1,4}Users\\{1,4}" + ACCOUNT, re.IGNORECASE)
PATH_RULES = (HOME_PATH, WSL_USERS_PATH, WINDOWS_USERS_PATH)
NAME_LIKE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


def tracked_text_files() -> list[tuple[str, str]]:
    """(path, text) for each tracked file that is text; skips the test when there is no git checkout."""
    try:
        listing = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True)
    except FileNotFoundError:
        raise unittest.SkipTest("git is not installed") from None
    except subprocess.CalledProcessError:
        raise unittest.SkipTest("the tests are not running from a git checkout") from None
    files = []
    for name in listing.stdout.decode("utf-8", errors="replace").split("\0"):
        path = ROOT / name
        if not name or not path.is_file():
            continue
        raw = path.read_bytes()
        if b"\0" not in raw:
            files.append((name, raw.decode("utf-8", errors="replace")))
    return files


def account_names(line: str) -> list[str]:
    """The real-looking account folders in ``line``, lower-cased."""
    names = []
    for rule in PATH_RULES:
        for match in rule.finditer(line):
            name = match.group(1).rstrip(".")
            if NAME_LIKE.fullmatch(name) and name.lower() not in GENERIC_NAMES:
                names.append(name.lower())
    return names


def machine_names() -> set[str]:
    names = set()
    try:
        names.add(getpass.getuser())
    except (OSError, KeyError):
        pass
    names.add(Path.home().name)
    return {name.lower() for name in names if len(name) >= 3 and name.lower() not in GENERIC_LOGINS}


class PrivacyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = tracked_text_files()

    def lines(self):
        for name, text in self.files:
            for number, line in enumerate(text.splitlines(), 1):
                yield name, number, line

    def report(self, found: list[str]) -> str:
        return f"{len(found)} line(s):\n" + "\n".join(found[:25])

    def test_home_and_user_paths_hold_a_placeholder_not_a_name(self):
        found = [f"{name}:{number}" for name, number, line in self.lines() if account_names(line)]
        self.assertEqual(found, [], self.report(found))

    def test_this_machines_login_and_home_folder_name_appear_nowhere(self):
        names = machine_names()
        if not names:
            self.skipTest("the login and home folder names are generic here, so there is nothing to look for")
        pattern = re.compile(r"\b(?:" + "|".join(re.escape(name) for name in sorted(names)) + r")\b", re.IGNORECASE)
        found = [f"{name}:{number}" for name, number, line in self.lines() if pattern.search(line)]
        self.assertEqual(found, [], self.report(found))

    def test_the_rules_tell_names_from_placeholders(self):
        # The folders are joined here so that these samples are not paths the guard would flag in this very file.
        home, wsl_users, windows_users = "/home/", "/mnt/c/Users/", "C:\\Users\\"
        self.assertEqual(account_names(f"{home}wren/.claude {windows_users}Wren {wsl_users}wren"), ["wren"] * 3)
        self.assertEqual(account_names(windows_users.replace("\\", "\\\\") + "wren"), ["wren"])
        self.assertEqual(account_names(f"wren:x:1000:1000::{home}wren:/bin/sh"), ["wren"])
        for fine in ("/home/<user>/x", "/mnt/c/Users/<U>", "C:\\Users\\%USERNAME%", "/home/user/", "$E/home/.config",
                     "/tmp/t/home/b.txt", "/home/o'neil", "/mnt/c/Users/[^/]+", "/home/…/x"):
            with self.subTest(fine=fine):
                self.assertEqual(account_names(fine), [])


if __name__ == "__main__":
    unittest.main()
