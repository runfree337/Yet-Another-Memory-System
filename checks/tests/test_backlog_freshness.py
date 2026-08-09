# tests/test_backlog_freshness.py
#
# Regression tests for `backlog-check.py`'s E-STATE-FRESH — the freshness rule that makes
# a missed `updated` stamp VISIBLE. The asymmetry that must never re-open: a stamp that
# does not run was noisy on the Feature channel (`FM-FRESH`) and silent on the Backlog
# channel — which is exactly what let a real drift (8 STATE.md out of 15, up to 19 days)
# go unseen for weeks. A hook can be uninstalled, bypassed (`--no-verify`) or absent
# (ephemeral container): the CHECK is the guard that survives that.
#
# Commit dates are pinned via GIT_COMMITTER_DATE so the assertions are deterministic —
# no `today()` in the expectations.
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

CHECKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COMMIT_DAY = "2020-06-15"


def _load_module():
    """backlog-check.py has a hyphen — not importable by name; load it by path."""
    path = os.path.join(CHECKS_DIR, "backlog-check.py")
    spec = importlib.util.spec_from_file_location("backlog_check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class StateFreshness(unittest.TestCase):
    def setUp(self):
        self.repo = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.repo, ignore_errors=True))
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=self.repo, check=True)
        self.mod = _load_module()
        # Point the module at the throwaway repo — ROOT is what `check_freshness` uses
        # both to run git and to resolve the relative STATE.md path.
        self.mod.ROOT = self.repo
        self.mod.BACKLOG = os.path.join(self.repo, "backlog")

    def _state(self, updated, commit=True):
        rel = "backlog/x/STATE.md"
        full = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(f"---\nid: x\nupdated: {updated}\n---\n")
        if commit:
            subprocess.run(["git", "add", "-A"], cwd=self.repo, check=True)
            env = dict(os.environ,
                       GIT_COMMITTER_DATE=f"{COMMIT_DAY}T12:00:00",
                       GIT_AUTHOR_DATE=f"{COMMIT_DAY}T12:00:00")
            subprocess.run(["git", "commit", "-q", "-m", "c"], cwd=self.repo,
                           check=True, env=env)
        return rel

    def _findings(self, updated, commit=True):
        rel = self._state(updated, commit=commit)
        return self.mod.check_freshness(rel, {"updated": updated})

    def test_stale_updated_fires(self):
        """`updated` older than the last commit touching the file -> one E-STATE-FRESH."""
        found = self._findings("2020-06-14")
        self.assertEqual([f.rule for f in found], ["E-STATE-FRESH"])
        self.assertEqual(found[0].severity, self.mod.TO_CONFIRM)
        self.assertIn(COMMIT_DAY, found[0].msg)

    def test_updated_equal_to_commit_date_is_fresh(self):
        """The stamped nominal case: `updated` == commit date -> silent."""
        self.assertEqual(self._findings(COMMIT_DAY), [])

    def test_updated_after_commit_date_is_fresh(self):
        """A hand-bumped future date is not this rule's business -> silent."""
        self.assertEqual(self._findings("2020-06-16"), [])

    def test_uncommitted_file_is_ignored(self):
        """No git history (new work item not yet committed) -> silent, no double signal."""
        self.assertEqual(self._findings("2000-01-01", commit=False), [])

    def test_invalid_or_missing_updated_is_ignored(self):
        """Malformed/absent `updated` is already `R-BAD-DATE`/`R-MISSING-KEY` territory."""
        rel = self._state("2020-06-14")
        self.assertEqual(self.mod.check_freshness(rel, {"updated": "yesterday"}), [])
        self.assertEqual(self.mod.check_freshness(rel, {}), [])

    def test_full_run_surfaces_the_rule(self):
        """End to end through `run()` — the rule is wired, not just defined."""
        self._state("2020-06-14")
        with open(os.path.join(self.repo, "backlog", "INDEX.md"), "w",
                  encoding="utf-8") as fh:
            fh.write("- x → `x/`\n")
        self.mod.INDEX_PATH = os.path.join(self.repo, "backlog", "INDEX.md")
        rules = {f.rule for f in self.mod.run()}
        self.assertIn("E-STATE-FRESH", rules)


if __name__ == "__main__":
    unittest.main()
