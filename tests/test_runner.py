import fcntl
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from witchy import palette, runner, state
from witchy.components.base import Abort, Change, Check, Command, ComponentFailed, Plan
from witchy.context import Context


class Fake:
    """A component that records what the runner asks of it."""

    def __init__(self, name, log, skip=None, fail=False, abort=False, on_apply=None, restore_changes=None):
        self.name, self.log, self.skip, self.fail, self.abort = name, log, skip, fail, abort
        self.on_apply = on_apply
        self.restore_changes = restore_changes or []

    def plan(self, ctx, entry):
        self.log.append(("plan", self.name))
        if self.abort:
            raise Abort(f"{self.name} refuses")
        return Plan.skipped(self.skip) if self.skip else Plan(notes=[f"{self.name} note"])

    def apply(self, ctx, plan):
        self.log.append(("apply", self.name))
        if self.on_apply:
            self.on_apply(ctx)
        if self.fail:
            raise ComponentFailed("boom")
        return {"installed": self.name}

    def restore(self, ctx, entry):
        self.log.append(("restore", self.name))
        return Plan(changes=list(self.restore_changes))

    def check(self, ctx, entry):
        return []


class CheckingFake(Fake):
    def __init__(self, name, log, checks=None, raises=None):
        super().__init__(name, log)
        self.checks, self.raises = checks or [], raises

    def check(self, ctx, entry):
        if self.raises:
            raise self.raises
        return self.checks


class RunnerTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.log = []

    def ctx(self, **kwargs):
        self.out = io.StringIO()
        return Context(home=self.home, env={}, out=self.out, stamp="20261002-120000", dist=self.root / "dist",
                       lock_path=self.root / "witchy.lock", **kwargs)

    def state(self):
        return json.loads((self.home / ".claude" / "witchy" / "state.json").read_text(encoding="utf-8"))

    def write_state(self, components):
        state.save(self.home / ".claude" / "witchy" / "state.json", dict(state.empty("midnight"), components=components))


class InstallRunnerTest(RunnerTestCase):
    def test_installs_in_order_and_records_results(self):
        a, b = Fake("a", self.log), Fake("b", self.log)
        self.assertEqual(runner.install(self.ctx(), [a, b]), 0)
        self.assertEqual(self.log, [("plan", "a"), ("plan", "b"), ("apply", "a"), ("apply", "b")])
        data = self.state()
        self.assertEqual(data["version"], 2)
        self.assertEqual(data["variant"], "midnight")
        self.assertEqual(data["components"], {"a": {"installed": "a"}, "b": {"installed": "b"}})
        self.assertEqual(data["last_install"], {"at": "20261002-120000", "results": {"a": "ok", "b": "ok"}})
        self.assertIn("2/2 components installed", self.out.getvalue())
        self.assertIn(runner.INSTALLED, self.out.getvalue())
        self.assertIn("a note", self.out.getvalue())

    def test_state_is_saved_after_each_component(self):
        seen = []
        b = Fake("b", self.log, on_apply=lambda ctx: seen.append(json.loads(ctx.state_path.read_text())["components"]))
        runner.install(self.ctx(), [Fake("a", self.log), b])
        self.assertEqual(seen, [{"a": {"installed": "a"}}])

    def test_skipped_component_exits_2_and_keeps_its_old_entry(self):
        self.write_state({"b": {"old": True}})
        code = runner.install(self.ctx(), [Fake("a", self.log), Fake("b", self.log, skip="nope")])
        self.assertEqual(code, 2)
        self.assertEqual(self.state()["components"]["b"], {"old": True})
        self.assertEqual(self.state()["last_install"]["results"]["b"], "skipped: nope")
        self.assertIn("1/2 components installed · skipped: b (nope)", self.out.getvalue())
        self.assertIn(runner.PARTLY_INSTALLED, self.out.getvalue())
        self.assertNotIn(runner.INSTALLED, self.out.getvalue())

    def test_failed_component_exits_2(self):
        code = runner.install(self.ctx(), [Fake("a", self.log), Fake("b", self.log, fail=True)])
        self.assertEqual(code, 2)
        self.assertEqual(self.state()["last_install"]["results"]["b"], "failed: boom")
        self.assertNotIn("b", self.state()["components"])

    def test_notes_of_a_failed_component_are_not_printed(self):
        runner.install(self.ctx(), [Fake("a", self.log), Fake("b", self.log, fail=True)])
        self.assertIn("a note", self.out.getvalue())
        self.assertNotIn("b note", self.out.getvalue())

    def test_entries_are_what_state_held_before_this_run(self):
        self.write_state({"old": {"installed": "old"}})
        seen = []
        b = Fake("b", self.log, on_apply=lambda ctx: seen.append(sorted(ctx.entries)))
        runner.install(self.ctx(), [Fake("a", self.log), b])
        self.assertEqual(seen, [["old"]])

    def test_abort_while_planning_exits_1_and_applies_nothing(self):
        code = runner.install(self.ctx(), [Fake("a", self.log), Fake("b", self.log, abort=True)])
        self.assertEqual(code, 1)
        self.assertNotIn(("apply", "a"), self.log)
        self.assertIn("b refuses", self.out.getvalue())

    def test_lock_busy_exits_1_and_writes_nothing(self):
        with open(self.root / "witchy.lock", "a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            code = runner.install(self.ctx(), [Fake("a", self.log)])
        self.assertEqual(code, 1)
        self.assertIn(runner.LOCK_BUSY, self.out.getvalue())
        self.assertEqual(self.log, [])
        self.assertFalse((self.home / ".claude").exists())

    def test_stale_lock_file_does_not_block(self):
        (self.root / "witchy.lock").write_text("", encoding="utf-8")
        self.assertEqual(runner.install(self.ctx(), [Fake("a", self.log)]), 0)

    def test_dry_run_takes_no_lock_and_writes_nothing(self):
        with open(self.root / "witchy.lock", "a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            code = runner.install(self.ctx(dry_run=True), [Fake("a", self.log)])
        self.assertEqual(code, 0)
        self.assertEqual(self.log, [("plan", "a")])
        self.assertFalse((self.home / ".claude").exists())

    def test_only_runs_named_components_and_keeps_other_entries(self):
        self.write_state({"b": {"old": True}})
        code = runner.install(self.ctx(only=("a",)), [Fake("a", self.log), Fake("b", self.log)])
        self.assertEqual(code, 0)
        self.assertEqual(self.log, [("plan", "a"), ("apply", "a")])
        self.assertEqual(self.state()["components"], {"a": {"installed": "a"}, "b": {"old": True}})

    def test_dry_run_lists_planned_actions(self):
        class Acting(Fake):
            def plan(self, ctx, entry):
                super().plan(ctx, entry)
                return Plan(actions=["font: download x"])

        self.assertEqual(runner.install(self.ctx(dry_run=True), [Acting("a", self.log)]), 0)
        self.assertIn("font: download x", self.out.getvalue())

    def test_dry_run_prints_each_plans_actions_after_its_own_changes(self):
        class Acting(Fake):
            def plan(self, ctx, entry):
                super().plan(ctx, entry)
                return Plan(changes=[Change(ctx.home / f"{self.name}.txt", None, b"x\n")],
                            actions=[f"{self.name}: act"])

        self.assertEqual(runner.install(self.ctx(dry_run=True), [Acting("a", self.log), Acting("b", self.log)]), 0)
        self.assertEqual(self.out.getvalue().splitlines(),
                         [f"create {self.home / 'a.txt'} (1 lines)", "a: act",
                          f"create {self.home / 'b.txt'} (1 lines)", "b: act", "Dry run: nothing was written."])

    def test_later_components_see_earlier_plans_and_results(self):
        seen = {}

        class Watching(Fake):
            def plan(self, ctx, entry):
                seen["planned"] = list(ctx.planned)
                return super().plan(ctx, entry)

            def apply(self, ctx, plan):
                seen["results"] = dict(ctx.results)
                return super().apply(ctx, plan)

        runner.install(self.ctx(), [Fake("a", self.log), Watching("b", self.log)])
        self.assertEqual(seen, {"planned": ["a"], "results": {"a": "ok"}})

    def test_a_file_changed_after_planning_fails_only_that_component(self):
        target = self.root / "settings.json"
        target.write_text("{}", encoding="utf-8")

        class Writing(Fake):
            def plan(self, ctx, entry):
                super().plan(ctx, entry)
                return Plan(changes=[Change(target, b"{}", b'{"x": 1}')])

        def sky_job(ctx):
            target.write_text('{"sky": 3}', encoding="utf-8")

        code = runner.install(self.ctx(), [Fake("a", self.log, on_apply=sky_job), Writing("b", self.log)])
        self.assertEqual(code, 2)
        self.assertTrue(self.state()["last_install"]["results"]["b"].startswith("failed: "))
        self.assertEqual(target.read_text(encoding="utf-8"), '{"sky": 3}')
        self.assertNotIn(("apply", "b"), self.log)

    def test_a_rewrite_during_planning_fails_only_the_locked_component(self):
        target = self.root / "settings.json"
        target.write_text("{}", encoding="utf-8")

        class Locked(Fake):
            def plan(self, ctx, entry):
                super().plan(ctx, entry)
                return Plan(lock=ctx.home / "wt.lock", changes=[Change(target, b"{}", b'{"x": 1}')])

        class Rewriter(Fake):
            def plan(self, ctx, entry):
                target.write_text('{"sky": 3}', encoding="utf-8")
                return super().plan(ctx, entry)

        code = runner.install(self.ctx(), [Locked("a", self.log), Rewriter("b", self.log)])
        self.assertEqual(code, 2)
        results = self.state()["last_install"]["results"]
        self.assertTrue(results["a"].startswith("failed: "))
        self.assertEqual(results["b"], "ok")
        self.assertEqual(target.read_text(encoding="utf-8"), '{"sky": 3}')
        self.assertNotIn(("apply", "a"), self.log)

    def test_the_plan_lock_is_held_while_applying(self):
        lock = self.root / "wt.lock"
        seen = []

        class Locking(Fake):
            def plan(self, ctx, entry):
                super().plan(ctx, entry)
                return Plan(lock=lock)

            def apply(self, ctx, plan):
                with open(lock, "a") as handle:
                    try:
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        seen.append("free")
                    except BlockingIOError:
                        seen.append("held")
                return super().apply(ctx, plan)

        runner.install(self.ctx(), [Locking("a", self.log)])
        self.assertEqual(seen, ["held"])



class UninstallRunnerTest(RunnerTestCase):
    def test_uninstall_runs_in_reverse_order_and_removes_state(self):
        a, b = Fake("a", self.log), Fake("b", self.log)
        runner.install(self.ctx(), [a, b])
        self.log.clear()
        self.assertEqual(runner.uninstall(self.ctx(), [a, b]), 0)
        self.assertEqual(self.log, [("restore", "b"), ("restore", "a")])
        self.assertFalse((self.home / ".claude" / "witchy").exists())

    def test_failed_restore_keeps_that_entry_and_exits_2(self):
        blocker = self.root / "blocker"
        blocker.write_text("a file, so nothing can be created inside it", encoding="utf-8")
        a = Fake("a", self.log)
        b = Fake("b", self.log, restore_changes=[Change(blocker / "x.json", None, b"{}")])
        runner.install(self.ctx(), [a, b])
        self.assertEqual(runner.uninstall(self.ctx(), [a, b]), 2)
        self.assertEqual(self.state()["components"], {"b": {"installed": "b"}})
        self.assertIn("run uninstall again", self.out.getvalue())

    def test_uninstall_only_keeps_the_other_entries(self):
        a, b = Fake("a", self.log), Fake("b", self.log)
        runner.install(self.ctx(), [a, b])
        self.assertEqual(runner.uninstall(self.ctx(only=("a",)), [a, b]), 0)
        self.assertEqual(self.state()["components"], {"b": {"installed": "b"}})

    def test_nothing_to_uninstall(self):
        self.assertEqual(runner.uninstall(self.ctx(), [Fake("a", self.log)]), 0)
        self.assertIn("Nothing to uninstall", self.out.getvalue())


class Restoring(Fake):
    """A component whose restore plan is ``make_plan(ctx)``."""

    def __init__(self, name, log, make_plan):
        super().__init__(name, log)
        self.make_plan = make_plan

    def restore(self, ctx, entry):
        super().restore(ctx, entry)
        return self.make_plan(ctx)


class RestoreCommandsTest(RunnerTestCase):
    def setUp(self):
        super().setUp()
        self.target = self.root / "ritual" / "cli.py"
        self.target.parent.mkdir()
        self.target.write_bytes(b"ours")
        self.calls = []

    def runs(self, code=0, error=None):
        def run(args, **kwargs):
            self.calls.append((args, kwargs, self.target.exists()))
            if error:
                raise error
            return subprocess.CompletedProcess(args, code, stdout="", stderr="")
        return run

    def plan(self, ctx):
        return Plan(commands=[Command(("fish", "-c", "restore"), "restore 2 Tide variables", "data")],
                    changes=[Change(self.target, b"ours", None, backup=False)], prune=[self.target.parent])

    def test_commands_run_before_the_changes_then_empty_folders_go(self):
        a = Restoring("a", self.log, self.plan)
        runner.install(self.ctx(), [a])
        self.assertEqual(runner.uninstall(self.ctx(run=self.runs()), [a]), 0)
        (args, kwargs, existed), = self.calls
        self.assertEqual((args, kwargs["input"], kwargs["timeout"], existed), (["fish", "-c", "restore"], "data", 5, True))
        self.assertFalse(self.target.parent.exists())

    def test_a_folder_that_is_not_empty_stays(self):
        (self.target.parent / "__pycache__").mkdir()
        a = Restoring("a", self.log, self.plan)
        runner.install(self.ctx(), [a])
        self.assertEqual(runner.uninstall(self.ctx(run=self.runs()), [a]), 0)
        self.assertTrue((self.target.parent / "__pycache__").is_dir())

    def test_a_failing_command_keeps_the_component_and_its_files(self):
        a = Restoring("a", self.log, self.plan)
        runner.install(self.ctx(), [a])
        self.assertEqual(runner.uninstall(self.ctx(run=self.runs(code=1)), [a]), 2)
        self.assertTrue(self.target.exists())
        self.assertEqual(self.state()["components"], {"a": {"installed": "a"}})
        self.assertIn("a: could not restore 2 Tide variables (exit 1); run uninstall again.", self.out.getvalue())

    def test_a_command_that_cannot_start_keeps_the_component(self):
        a = Restoring("a", self.log, self.plan)
        runner.install(self.ctx(), [a])
        missing = FileNotFoundError(2, "No such file or directory", "fish")
        self.assertEqual(runner.uninstall(self.ctx(run=self.runs(error=missing)), [a]), 2)
        self.assertTrue(self.target.exists())
        self.assertIn("could not restore 2 Tide variables", self.out.getvalue())

    def test_dry_run_lists_the_commands_and_runs_nothing(self):
        a = Restoring("a", self.log, self.plan)
        runner.install(self.ctx(), [a])
        self.assertEqual(runner.uninstall(self.ctx(dry_run=True, run=self.runs()), [a]), 0)
        self.assertEqual(self.calls, [])
        self.assertIn("a: restore 2 Tide variables", self.out.getvalue())
        self.assertTrue(self.target.exists())

    def test_dry_run_lists_the_folders_it_would_remove_if_empty(self):
        a = Restoring("a", self.log, self.plan)
        runner.install(self.ctx(), [a])
        self.assertEqual(runner.uninstall(self.ctx(dry_run=True, run=self.runs()), [a]), 0)
        self.assertEqual(self.out.getvalue().splitlines(),
                         [f"remove {self.target}", "a: restore 2 Tide variables",
                          f"a: remove {self.target.parent} if empty", "Dry run: nothing was written."])
        self.assertTrue(self.target.parent.is_dir())


class BlockedRestoreTest(RunnerTestCase):
    def blocked(self, ctx, entry):
        self.log.append(("restore", "a"))
        raise ComponentFailed("settings.json is no longer plain JSON; make it plain JSON again")

    def test_a_restore_that_cannot_be_planned_keeps_the_component_and_exits_2(self):
        a, b = Fake("a", self.log), Fake("b", self.log)
        a.restore = self.blocked
        runner.install(self.ctx(), [a, b])
        self.assertEqual(runner.uninstall(self.ctx(), [a, b]), 2)
        self.assertEqual(self.state()["components"], {"a": {"installed": "a"}})
        self.assertIn("a: settings.json is no longer plain JSON; make it plain JSON again; run uninstall again.",
                      self.out.getvalue())

    def test_dry_run_says_it_would_stay(self):
        a = Fake("a", self.log)
        a.restore = self.blocked
        runner.install(self.ctx(), [a])
        self.assertEqual(runner.uninstall(self.ctx(dry_run=True), [a]), 0)
        self.assertIn("a: settings.json is no longer plain JSON; make it plain JSON again; it would stay installed.",
                      self.out.getvalue())


class OutcomeTest(RunnerTestCase):
    def test_a_partial_outcome_is_recorded_and_its_entry_kept(self):
        class Partial(Fake):
            def plan(self, ctx, entry):
                super().plan(ctx, entry)
                return Plan(outcome="skipped: Tide not found", notes=["Open a new tab."])

        self.assertEqual(runner.install(self.ctx(), [Partial("fish", self.log)]), 2)
        self.assertEqual(self.state()["components"], {"fish": {"installed": "fish"}})
        self.assertEqual(self.state()["last_install"]["results"], {"fish": "skipped: Tide not found"})
        output = self.out.getvalue()
        self.assertIn("0/1 components installed · skipped: fish (Tide not found)", output)
        self.assertIn(runner.PARTLY_INSTALLED, output)
        self.assertNotIn(runner.INSTALLED, output)
        self.assertIn("Open a new tab.", output)

    def test_nothing_applied_does_not_claim_an_install(self):
        self.assertEqual(runner.install(self.ctx(), [Fake("a", self.log, skip="no Windows Terminal")]), 2)
        output = self.out.getvalue()
        self.assertNotIn(runner.INSTALLED, output)
        self.assertNotIn(runner.PARTLY_INSTALLED, output)
        self.assertIn(runner.NOTHING_INSTALLED, output)

    def test_some_ok_and_some_failed_is_a_partial_install(self):
        code = runner.install(self.ctx(), [Fake("a", self.log), Fake("b", self.log, fail=True)])
        self.assertEqual(code, 2)
        output = self.out.getvalue()
        self.assertIn("1/2 components installed · failed: b (boom)", output)
        self.assertIn(runner.PARTLY_INSTALLED, output)
        self.assertNotIn(runner.INSTALLED, output)


class UninstallRaceTest(RunnerTestCase):
    def test_a_rewrite_during_planning_leaves_only_that_component_installed(self):
        target = self.root / "settings.json"
        target.write_text("{}", encoding="utf-8")

        class Locked(Fake):
            def restore(self, ctx, entry):
                super().restore(ctx, entry)
                return Plan(lock=ctx.home / "wt.lock", changes=[Change(target, b"{}", None)])

        class Rewriter(Fake):
            def restore(self, ctx, entry):
                target.write_text('{"sky": 3}', encoding="utf-8")
                return super().restore(ctx, entry)

        a, b = Locked("a", self.log), Rewriter("b", self.log)
        runner.install(self.ctx(), [a, b])
        self.assertEqual(runner.uninstall(self.ctx(), [a, b]), 2)
        self.assertEqual(self.state()["components"], {"a": {"installed": "a"}})
        self.assertEqual(target.read_text(encoding="utf-8"), '{"sky": 3}')


class DoctorTest(RunnerTestCase):
    def test_not_installed_is_a_warning(self):
        self.assertEqual(runner.doctor(self.ctx(), [Fake("a", self.log)]), 0)
        self.assertIn("⚠ a", self.out.getvalue())
        self.assertIn("fix: python3 -m witchy install --only a", self.out.getvalue())

    def test_failing_check_exits_1_and_shows_its_fix(self):
        self.write_state({"a": {}})
        failing = CheckingFake("a", self.log, checks=[Check("fail", "a", "theme drifted", "do the thing")])
        self.assertEqual(runner.doctor(self.ctx(), [failing]), 1)
        self.assertIn("✗ a", self.out.getvalue())
        self.assertIn("theme drifted", self.out.getvalue())
        self.assertIn("    fix: do the thing", self.out.getvalue())

    def test_ok_checks_exit_0(self):
        self.write_state({"a": {}})
        self.assertEqual(runner.doctor(self.ctx(), [CheckingFake("a", self.log, checks=[Check("ok", "a", "fine")])]), 0)
        self.assertIn("✓ a", self.out.getvalue())

    def test_an_info_line_is_never_a_problem(self):
        self.write_state({"a": {}})
        info = CheckingFake("a", self.log, checks=[Check("info", "a", "glyph test: 🧹", "never shown")])
        self.assertEqual(runner.doctor(self.ctx(), [info]), 0)
        self.assertEqual(self.out.getvalue(), "· a                 glyph test: 🧹\n")

    def test_raising_check_is_reported_not_crashed(self):
        self.write_state({"a": {}})
        self.assertEqual(runner.doctor(self.ctx(), [CheckingFake("a", self.log, raises=KeyError("path"))]), 1)
        self.assertIn("check crashed", self.out.getvalue())

    def test_damaged_state_is_a_failure_line(self):
        path = self.home / ".claude" / "witchy" / "state.json"
        path.parent.mkdir(parents=True)
        path.write_text("{", encoding="utf-8")
        self.assertEqual(runner.doctor(self.ctx(), [Fake("a", self.log)]), 1)
        self.assertIn("✗ state", self.out.getvalue())

    def test_last_install_skips_are_warned(self):
        state.save(self.home / ".claude" / "witchy" / "state.json",
                   dict(state.empty("midnight"), components={"a": {}},
                        last_install={"at": "20261002-120000", "results": {"a": "skipped: offline"}}))
        runner.doctor(self.ctx(), [CheckingFake("a", self.log, checks=[Check("ok", "a", "fine")])])
        self.assertIn("last install (20261002-120000): skipped: offline", self.out.getvalue())


class MoodTest(RunnerTestCase):
    def test_lists_active_and_available(self):
        self.assertEqual(runner.mood(self.ctx(), None, [Fake("a", self.log)]), 0)
        self.assertIn("active: midnight", self.out.getvalue())
        self.assertIn("available: midnight", self.out.getvalue())

    def test_unknown_variant_exits_1(self):
        self.assertEqual(runner.mood(self.ctx(), "dawn", [Fake("a", self.log)]), 1)
        self.assertIn("unknown variant 'dawn'; available: midnight", self.out.getvalue())

    def test_same_variant_is_a_no_op(self):
        self.write_state({"a": {"installed": "a"}})
        self.assertEqual(runner.mood(self.ctx(), "midnight", [Fake("a", self.log)]), 0)
        self.assertIn("already midnight", self.out.getvalue())
        self.assertEqual(self.log, [])

    def test_switching_reinstalls_with_the_new_variant(self):
        self.write_state({"a": {"installed": "a"}})
        with mock.patch.dict(palette.VARIANTS, {"dawn": palette.VARIANTS["midnight"]}):
            self.assertEqual(runner.mood(self.ctx(), "dawn", [Fake("a", self.log)]), 0)
        self.assertEqual(self.state()["variant"], "dawn")
        self.assertIn(("apply", "a"), self.log)


class HardeningTest(RunnerTestCase):
    def save_state(self, variant, components):
        state.save(self.home / ".claude" / "witchy" / "state.json",
                   dict(state.empty(variant), components=components))

    def test_unknown_variant_in_state_aborts_install(self):
        self.save_state("dawn", {"a": {}})
        self.assertEqual(runner.install(self.ctx(), [Fake("a", self.log)]), 1)
        self.assertIn("unknown variant 'dawn'", self.out.getvalue())
        self.assertIn("python3 -m witchy mood midnight", self.out.getvalue())
        self.assertEqual(self.log, [])

    def test_mood_flags_an_unknown_active_variant(self):
        self.save_state("dawn", {})
        self.assertEqual(runner.mood(self.ctx(), None, [Fake("a", self.log)]), 0)
        self.assertIn("active: dawn (unknown; run: python3 -m witchy mood midnight)", self.out.getvalue())

    def test_mood_midnight_repairs_an_unknown_variant(self):
        self.save_state("dawn", {"a": {"installed": "a"}})
        self.assertEqual(runner.mood(self.ctx(), "midnight", [Fake("a", self.log)]), 0)
        self.assertEqual(self.state()["variant"], "midnight")

    def test_mood_repaints_only_installed_components(self):
        self.write_state({"a": {"installed": "a"}})
        with mock.patch.dict(palette.VARIANTS, {"dawn": palette.VARIANTS["midnight"]}):
            self.assertEqual(runner.mood(self.ctx(), "dawn", [Fake("a", self.log), Fake("b", self.log)]), 0)
        self.assertIn(("apply", "a"), self.log)
        self.assertNotIn(("plan", "b"), self.log)

    def test_missing_runtime_dir_falls_back_to_the_temp_dir(self):
        ctx = Context(home=self.home, env={"XDG_RUNTIME_DIR": str(self.root / "gone" / "run")}, out=io.StringIO())
        self.assertEqual(ctx.lock_file.parent, Path(tempfile.gettempdir()))

    def test_existing_runtime_dir_holds_the_lock(self):
        ctx = Context(home=self.home, env={"XDG_RUNTIME_DIR": str(self.root)}, out=io.StringIO())
        self.assertEqual(ctx.lock_file.parent, self.root)


if __name__ == "__main__":
    unittest.main()
