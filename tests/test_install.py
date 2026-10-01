import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import content, install, jsonio, validate

UBUNTU = "{05f3f843-450a-55ad-a264-cacf368dafe5}"
CLAUDE_ORIGINAL = {
    "env": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:8787"},
    "statusLine": {"type": "command", "command": "archon statusline", "padding": 0},
    "theme": "dark",
    "agentPushNotifEnabled": True,
}
WT_ORIGINAL = {
    "$help": "https://aka.ms/terminal-documentation",
    "profiles": {"defaults": {}, "list": [
        {"guid": "{61c54bbd-c2c6-5271-96e7-009a87ff44bf}", "name": "Windows PowerShell"},
        {"guid": "{0caa0dad-35be-5f56-a8ff-afceeeaa6101}", "name": "Símbolo del sistema"},
        {"guid": UBUNTU, "name": "Ubuntu", "source": "Microsoft.WSL", "colorScheme": "One Half Dark"},
    ]},
    "schemes": [],
}


def refuse_cmd(*args, **kwargs):
    raise AssertionError("cmd.exe must not run in tests")


class InstallTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.claude = self.home / ".claude"
        self.claude.mkdir(parents=True)
        self.settings = self.claude / "settings.json"
        self.settings.write_text(json.dumps(CLAUDE_ORIGINAL, indent=2) + "\n", encoding="utf-8")
        self.wt = self.root / "wt" / "settings.json"
        self.wt.parent.mkdir()
        # Windows Terminal writes ASCII escapes and 4-space indents.
        self.wt.write_text(json.dumps(WT_ORIGINAL, indent=4) + "\n", encoding="utf-8")

    def ctx(self, dry_run=False, env=None, stamp="20260930-120000"):
        self.out = io.StringIO()
        return install.Context(home=self.home, env={"WT_PROFILE_ID": UBUNTU} if env is None else env, out=self.out,
                               dry_run=dry_run, wt_settings=self.wt, python="/usr/bin/python3", stamp=stamp,
                               run=refuse_cmd, dist=self.root / "dist")

    def snapshot(self):
        files = {}
        for base in (self.home, self.wt.parent):
            for path in sorted(base.rglob("*")):
                if path.is_file() and ".bak-witchy-" not in path.name:
                    files[str(path)] = path.read_bytes()
        return files

    def claude_settings(self):
        return json.loads(self.settings.read_text(encoding="utf-8"))

    def wt_settings(self):
        return json.loads(self.wt.read_text(encoding="utf-8"))

    def ubuntu(self):
        return next(p for p in self.wt_settings()["profiles"]["list"] if p["guid"] == UBUNTU)

    def state(self):
        return json.loads((self.claude / "witchy" / "state.json").read_text(encoding="utf-8"))

    def wt_write_fails(self):
        """Windows Terminal's settings.json cannot be replaced (it holds the file open); everything else writes."""
        real = jsonio.write_atomic_bytes

        def write(path, data):
            if Path(path) == self.wt:
                raise PermissionError(13, "Permission denied", str(path))
            return real(path, data)

        return mock.patch("witchy.install.jsonio.write_atomic_bytes", side_effect=write)


class InstallTest(InstallTestCase):
    def test_install_puts_every_piece_in_place(self):
        self.assertEqual(install.install(self.ctx()), 0)
        for rel in ("themes/moonlit-candle.json", "output-styles/witchynibbles.md",
                    "witchy/statusline.py", "witchy/tips.json", "witchy/state.json"):
            self.assertTrue((self.claude / rel).is_file(), rel)
        data = self.claude_settings()
        self.assertEqual(data["theme"], "custom:moonlit-candle")
        self.assertEqual(data["outputStyle"], "WitchyNibbles")
        self.assertEqual(data["spinnerVerbs"]["mode"], "replace")
        self.assertEqual(data["spinnerTipsOverride"]["label"], "Grimoire")
        self.assertEqual(data["env"], CLAUDE_ORIGINAL["env"])
        self.assertTrue(data["agentPushNotifEnabled"])
        self.assertEqual(self.ubuntu()["colorScheme"], "Moonlit Candle")
        self.assertEqual(self.wt_settings()["schemes"][0]["name"], "Moonlit Candle")
        self.assertTrue(list(self.claude.glob("settings.json.bak-witchy-20260930-120000")))
        self.assertTrue(list(self.wt.parent.glob("settings.json.bak-witchy-20260930-120000")))
        self.assertIn(install.RESTART_NOTE, self.out.getvalue())
        self.assertTrue((self.root / "dist" / "claude" / "themes" / "moonlit-candle.json").is_file())

    def test_statusline_command_runs_the_installed_copy(self):
        install.install(self.ctx())
        command = self.claude_settings()["statusLine"]["command"]
        script = self.claude / "witchy" / "statusline.py"
        self.assertEqual(command, f"/usr/bin/python3 -I {script}")
        done = subprocess.run([sys.executable, "-I", str(script)], input=b"{}", capture_output=True, timeout=10)
        self.assertEqual(done.returncode, 0)
        self.assertIn("🌑".encode("utf-8"), done.stdout)

    def test_install_then_uninstall_restores_bytes(self):
        before = self.snapshot()
        install.install(self.ctx())
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 0)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.claude / "witchy").exists())

    def test_install_twice_is_idempotent(self):
        install.install(self.ctx())
        after_first = self.snapshot()
        install.install(self.ctx(stamp="20260930-120500"))
        self.assertEqual(self.snapshot(), after_first)

    def test_reinstall_keeps_the_original_previous_value(self):
        install.install(self.ctx())
        data = self.claude_settings()
        data["theme"] = "light"
        self.settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        install.install(self.ctx(stamp="20260930-120500"))
        state = json.loads((self.claude / "witchy" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["claude_settings"]["keys"]["theme"]["previous"], {"value": "dark"})
        install.uninstall(self.ctx(stamp="20260930-130000"))
        self.assertEqual(self.claude_settings()["theme"], "dark")

    def test_uninstall_keeps_keys_claude_code_added_later(self):
        install.install(self.ctx())
        data = self.claude_settings()
        data["model"] = "opus"
        self.settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        install.uninstall(self.ctx(stamp="20260930-130000"))
        self.assertEqual(self.claude_settings(), dict(CLAUDE_ORIGINAL, model="opus"))

    def test_uninstall_leaves_a_key_the_user_changed(self):
        install.install(self.ctx())
        data = self.claude_settings()
        data["outputStyle"] = "Concise"
        self.settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        backup = self.state()["claude_settings"]["backup"]
        install.uninstall(self.ctx(stamp="20260930-130000"))
        self.assertEqual(self.claude_settings()["outputStyle"], "Concise")
        self.assertEqual(self.claude_settings()["theme"], "dark")
        self.assertIn("outputStyle was changed after install", self.out.getvalue())
        self.assertIn(f"The file as it was before install is kept at {backup}", self.out.getvalue())
        self.assertTrue(Path(backup).is_file())

    def test_dry_run_writes_nothing(self):
        before = self.snapshot()
        self.assertEqual(install.install(self.ctx(dry_run=True)), 0)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / "dist").exists())
        self.assertEqual(list(self.claude.glob("*.bak-witchy-*")), [])
        output = self.out.getvalue()
        self.assertIn('+  "theme": "custom:moonlit-candle",', output)
        self.assertIn("create ", output)
        self.assertIn("Dry run: nothing was written.", output)

    def test_uninstall_dry_run_writes_nothing(self):
        install.install(self.ctx())
        before = self.snapshot()
        self.assertEqual(install.uninstall(self.ctx(dry_run=True, stamp="20260930-130000")), 0)
        self.assertEqual(self.snapshot(), before)

    def test_fresh_home_without_settings(self):
        self.settings.unlink()
        self.assertEqual(install.install(self.ctx()), 0)
        self.assertEqual(self.claude_settings()["theme"], "custom:moonlit-candle")
        install.uninstall(self.ctx(stamp="20260930-130000"))
        self.assertFalse(self.settings.exists())
        self.assertFalse((self.claude / "witchy").exists())

    def test_windows_terminal_with_comments_is_left_alone(self):
        self.wt.write_text('{\n    // my comment\n    "profiles": {"list": []}\n}\n', encoding="utf-8")
        before = self.wt.read_bytes()
        self.assertEqual(install.install(self.ctx()), 0)
        self.assertEqual(self.wt.read_bytes(), before)
        self.assertIn('"colorScheme": "Moonlit Candle"', self.out.getvalue())
        self.assertEqual(self.claude_settings()["theme"], "custom:moonlit-candle")
        state = json.loads((self.claude / "witchy" / "state.json").read_text(encoding="utf-8"))
        self.assertIsNone(state["windows_terminal"])

    def test_no_windows_terminal_profile_skips_terminal(self):
        before = self.wt.read_bytes()
        self.assertEqual(install.install(self.ctx(env={})), 0)
        self.assertEqual(self.wt.read_bytes(), before)
        self.assertIn(install.WT_SKIP, self.out.getvalue())
        self.assertEqual(self.claude_settings()["theme"], "custom:moonlit-candle")

    def test_vscode_terminal_falls_back_to_distro_name(self):
        self.assertEqual(install.install(self.ctx(env={"WSL_DISTRO_NAME": "Ubuntu"})), 0)
        self.assertEqual(self.ubuntu()["colorScheme"], "Moonlit Candle")

    def test_edited_theme_is_backed_up_before_uninstall(self):
        install.install(self.ctx())
        theme = self.claude / "themes" / "moonlit-candle.json"
        theme.write_text('{"name": "Moonlit Candle (mine)"}\n', encoding="utf-8")
        install.uninstall(self.ctx(stamp="20260930-130000"))
        self.assertFalse(theme.exists())
        backups = list(theme.parent.glob("moonlit-candle.json.bak-witchy-*"))
        self.assertEqual(len(backups), 1)
        self.assertIn("(mine)", backups[0].read_text(encoding="utf-8"))

    def test_invalid_claude_settings_aborts(self):
        self.settings.write_text('{\n  // comment\n  "theme": "dark"\n}\n', encoding="utf-8")
        before = self.snapshot()
        self.assertEqual(install.install(self.ctx()), 1)
        self.assertEqual(self.snapshot(), before)

    def test_validation_failure_changes_nothing(self):
        before = self.snapshot()
        failure = validate.Failure("text-contrast", "claude.claude", "#3A2E47", "1.60:1 < 4.5:1")
        with mock.patch("witchy.install.validate.validate_all", return_value=[failure]):
            self.assertEqual(install.install(self.ctx()), 1)
        self.assertEqual(self.snapshot(), before)
        self.assertIn("text-contrast: claude.claude", self.out.getvalue())

    def test_uninstall_without_state(self):
        self.assertEqual(install.uninstall(self.ctx()), 0)
        self.assertIn("Nothing to uninstall", self.out.getvalue())

    def test_uninstall_when_a_copied_file_is_already_gone(self):
        install.install(self.ctx())
        (self.claude / "witchy" / "statusline.py").unlink()
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 0)
        self.assertEqual(self.claude_settings(), CLAUDE_ORIGINAL)


    def test_failed_windows_terminal_write_still_records_state(self):
        before = self.snapshot()
        with self.wt_write_fails():
            self.assertEqual(install.install(self.ctx()), 0)
        self.assertIn(install.WT_SKIP, self.out.getvalue())
        self.assertEqual(self.wt.read_bytes(), before[str(self.wt)])
        self.assertEqual(self.claude_settings()["theme"], "custom:moonlit-candle")
        state = self.state()
        self.assertIsNone(state["windows_terminal"])
        self.assertEqual(state["claude_settings"]["keys"]["theme"]["previous"], {"value": "dark"})
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 0)
        self.assertEqual(self.claude_settings(), CLAUDE_ORIGINAL)
        self.assertEqual(self.snapshot(), before)

    def test_retry_after_a_failed_windows_terminal_write_keeps_the_originals(self):
        before = self.snapshot()
        with self.wt_write_fails():
            install.install(self.ctx())
        self.assertEqual(install.install(self.ctx(stamp="20260930-120500")), 0)
        self.assertEqual(self.ubuntu()["colorScheme"], "Moonlit Candle")
        state = self.state()
        self.assertEqual(state["claude_settings"]["keys"]["theme"]["previous"], {"value": "dark"})
        self.assertEqual(state["windows_terminal"]["previous_color_scheme"], {"value": "One Half Dark"})
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 0)
        self.assertEqual(self.snapshot(), before)


    def test_uninstall_restores_bytes_after_a_reinstall_that_changes_the_output(self):
        # Hand-written spacing that json.dumps would not reproduce, so only a byte restore can bring it back.
        self.settings.write_text(json.dumps(CLAUDE_ORIGINAL, indent=2).replace('"theme": ', '"theme":') + "\n",
                                 encoding="utf-8")
        self.wt.write_text(json.dumps(WT_ORIGINAL, indent=4).replace('"$help": ', '"$help":') + "\n",
                           encoding="utf-8")
        before = self.snapshot()
        install.install(self.ctx())
        spinner = content.load_spinner()
        shorter = dict(spinner, verbs=spinner["verbs"][:-1])
        with mock.patch.dict(install.palette.WT_SCHEME, {"cursorColor": "#FF9BD7"}), \
                mock.patch("witchy.install.content.load_spinner", return_value=shorter):
            self.assertEqual(install.install(self.ctx(stamp="20260930-120500")), 0)
        self.assertEqual(self.wt_settings()["schemes"][0]["cursorColor"], "#FF9BD7")
        self.assertEqual(self.claude_settings()["spinnerVerbs"]["verbs"], shorter["verbs"])
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 0)
        self.assertEqual(self.snapshot(), before)

    def test_refused_windows_terminal_restore_keeps_state_and_can_be_retried(self):
        before = self.snapshot()
        install.install(self.ctx())
        with self.wt_write_fails():
            self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 1)
        output = self.out.getvalue()
        self.assertIn(str(self.wt), output)
        self.assertIn("run uninstall again", output)
        self.assertNotIn("Moonlit Candle uninstalled", output)
        self.assertTrue((self.claude / "witchy" / "state.json").is_file())
        self.assertEqual(self.claude_settings(), CLAUDE_ORIGINAL)
        self.assertEqual(self.ubuntu()["colorScheme"], "Moonlit Candle")
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-131000")), 0)
        output = self.out.getvalue()
        self.assertNotIn("was changed after install", output)
        self.assertNotIn("kept at", output)
        self.assertNotIn("no longer exists", output)
        self.assertEqual(self.snapshot(), before)

    def test_retry_after_a_refused_restore_is_silent_without_an_original_settings_file(self):
        self.settings.unlink()
        before = self.snapshot()
        install.install(self.ctx())
        with self.wt_write_fails():
            self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 1)
        self.assertFalse(self.settings.exists())
        self.assertEqual(install.uninstall(self.ctx(stamp="20260930-131000")), 0)
        self.assertNotIn("no longer exists", self.out.getvalue())
        self.assertEqual(self.snapshot(), before)

    def test_uninstall_removes_the_copies_only_after_the_settings_are_restored(self):
        install.install(self.ctx())
        seen = []
        real = jsonio.write_atomic_bytes

        def write(path, data):
            seen.append((Path(path).name, (self.claude / "witchy" / "statusline.py").exists()))
            return real(path, data)

        with mock.patch("witchy.install.jsonio.write_atomic_bytes", side_effect=write):
            install.uninstall(self.ctx(stamp="20260930-130000"))
        # settings.json is written back while statusline.py is still there; Windows Terminal is written last
        self.assertEqual(seen, [("settings.json", True), ("settings.json", False)])

    def test_install_aborts_when_a_file_changes_while_planning(self):
        before = self.snapshot()
        real = install.wt.locate_settings

        def locate(*args, **kwargs):
            # Claude Code rewrites its settings during the cmd.exe lookup
            data = self.claude_settings()
            data["model"] = "opus"
            self.settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            return real(*args, **kwargs)

        with mock.patch("witchy.install.wt.locate_settings", side_effect=locate):
            self.assertEqual(install.install(self.ctx()), 1)
        modified = (json.dumps(dict(CLAUDE_ORIGINAL, model="opus"), indent=2) + "\n").encode("utf-8")
        self.assertEqual(self.snapshot(), {**before, str(self.settings): modified})
        self.assertEqual(list(self.home.rglob("*.bak-witchy-*")) + list(self.wt.parent.glob("*.bak-witchy-*")), [])
        self.assertFalse((self.root / "dist").exists())
        self.assertIn(f"{self.settings} changed while planning; nothing was written. Run the command again.",
                      self.out.getvalue())

    def test_uninstall_aborts_when_a_file_changes_while_planning(self):
        install.install(self.ctx())
        real = install._restore_json
        data = self.claude_settings()
        data["model"] = "opus"
        modified = (json.dumps(data, indent=2) + "\n").encode("utf-8")

        def plan(entry, restore, warnings):
            change = real(entry, restore, warnings)
            if entry["path"] == str(self.settings):
                self.settings.write_bytes(modified)
            return change

        installed = self.snapshot()
        with mock.patch("witchy.install._restore_json", side_effect=plan):
            self.assertEqual(install.uninstall(self.ctx(stamp="20260930-130000")), 1)
        self.assertEqual(self.snapshot(), {**installed, str(self.settings): modified})
        self.assertEqual(list(self.home.rglob("*.bak-witchy-20260930-130000")), [])
        self.assertIn(f"{self.settings} changed while planning; nothing was written. Run the command again.",
                      self.out.getvalue())


if __name__ == "__main__":
    unittest.main()
