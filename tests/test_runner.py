import fcntl
import io
import json
import tempfile
import unittest
from pathlib import Path

from witchy import runner, state
from witchy.components.base import Abort, Change, ComponentFailed, Plan
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

    def test_failed_component_exits_2(self):
        code = runner.install(self.ctx(), [Fake("a", self.log), Fake("b", self.log, fail=True)])
        self.assertEqual(code, 2)
        self.assertEqual(self.state()["last_install"]["results"]["b"], "failed: boom")
        self.assertNotIn("b", self.state()["components"])

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


if __name__ == "__main__":
    unittest.main()
