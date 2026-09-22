# tests/test_shallow_clone.py
#
# Regression tests for the SHALLOW-clone guard (`entrylib.is_shallow` /
# `entrylib.git_last_commit_date` / `doc-refs-check.history_is_blind`).
#
# The defect these close: under `git clone --depth=N` git does not ERROR on questions
# about truncated history — it answers with something plausible and wrong. Two shapes,
# in opposite directions, and neither is visible in the output:
#
#   * `git log -1 --format=%cs -- <path>` returns the BOUNDARY commit's date for any
#     file untouched since. Freshness rules then flag every untouched entry as stale
#     (measured on a real repo 2026-09-22: 15 phantom findings out of 18).
#   * `git log --all -- <path>` returns nothing for a file created AND deleted before
#     the boundary. `doc-refs-check` reads that as "never created" and silently
#     DOWNGRADES R-DEAD-PATH from BLOCKING to TO-CONFIRM.
#
# `git clone --depth=1` is the default of `actions/checkout`, so this is the common CI
# case. Each test carries its CONTRE-ÉPREUVE: the same repo cloned in full must still
# produce the un-degraded answer — otherwise the guard would "pass" by disabling the
# rule everywhere.
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

CHECKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CHECKS_DIR)
import entrylib  # noqa: E402

OLD_DAY = "2020-06-15"


def _load(script):
    path = os.path.join(CHECKS_DIR, script)
    spec = importlib.util.spec_from_file_location(script.replace("-", "_")[:-3], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(repo, *args, date=None):
    env = dict(os.environ)
    if date:
        env.update(GIT_COMMITTER_DATE=f"{date}T12:00:00", GIT_AUTHOR_DATE=f"{date}T12:00:00")
    subprocess.run(["git", *args], cwd=repo, check=True, env=env,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class ShallowGuard(unittest.TestCase):
    """One origin, two clones: full and --depth=1. Same question, two answers."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = os.path.realpath(tempfile.mkdtemp())
        origin = os.path.join(cls.tmp, "origin")
        os.makedirs(origin)
        _git(origin, "init", "-q")
        _git(origin, "config", "user.email", "t@t")
        _git(origin, "config", "user.name", "t")

        # `vieux.txt` — committed long ago, never touched again: the freshness trap.
        # `mort.txt`  — created then deleted, both before the boundary: the severity trap.
        for name in ("vieux.txt", "mort.txt"):
            with open(os.path.join(origin, name), "w") as fh:
                fh.write("x\n")
        _git(origin, "add", "-A")
        _git(origin, "commit", "-q", "-m", "seed", date=OLD_DAY)
        _git(origin, "rm", "-q", "mort.txt")
        _git(origin, "commit", "-q", "-m", "delete mort.txt", date=OLD_DAY)
        # Enough commits to push the seed below any shallow boundary we ask for.
        for i in range(5):
            with open(os.path.join(origin, f"n{i}.txt"), "w") as fh:
                fh.write(f"{i}\n")
            _git(origin, "add", "-A")
            _git(origin, "commit", "-q", "-m", f"noise {i}")

        url = "file://" + origin
        cls.full = os.path.join(cls.tmp, "full")
        cls.shallow = os.path.join(cls.tmp, "shallow")
        _git(cls.tmp, "clone", "-q", url, cls.full)
        _git(cls.tmp, "clone", "-q", "--depth=1", url, cls.shallow)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        entrylib._IS_SHALLOW = None      # the answer is cached per run

    def tearDown(self):
        entrylib._IS_SHALLOW = None

    # --- detection -------------------------------------------------------- #

    def test_shallow_clone_is_detected(self):
        self.assertTrue(entrylib.is_shallow(self.shallow))

    def test_full_clone_is_not_shallow(self):
        """Contre-épreuve: the guard must not fire on a normal clone."""
        self.assertFalse(entrylib.is_shallow(self.full))

    # --- trap 1: the freshness date --------------------------------------- #

    def test_last_commit_date_is_withheld_when_shallow(self):
        """None, not the boundary date — callers treat None as "skip the rule"."""
        self.assertIsNone(entrylib.git_last_commit_date("vieux.txt", cwd=self.shallow))

    def test_raw_git_would_have_lied(self):
        """The defect itself, pinned: without the guard git hands back a WRONG date.

        If this ever stops holding, the guard is protecting against nothing and should
        be re-examined rather than kept out of habit.
        """
        r = subprocess.run(["git", "log", "-1", "--format=%cs", "--", "vieux.txt"],
                           cwd=self.shallow, capture_output=True, text=True)
        lied = r.stdout.strip()
        self.assertTrue(lied)                     # git answered…
        self.assertNotEqual(lied, OLD_DAY)        # …and the answer is not the truth

    def test_full_clone_still_returns_the_real_date(self):
        """Contre-épreuve: the guard withholds only what it cannot trust."""
        self.assertEqual(entrylib.git_last_commit_date("vieux.txt", cwd=self.full),
                         OLD_DAY)

    # --- trap 2: the severity downgrade ----------------------------------- #

    def test_doc_refs_declares_history_blind_when_shallow(self):
        mod = _load("doc-refs-check.py")
        mod.REPO = self.shallow
        entrylib._IS_SHALLOW = None
        self.assertTrue(mod.history_is_blind())

    def test_doc_refs_trusts_history_on_a_full_clone(self):
        """Contre-épreuve — and it proves the trap is real: on the full clone the
        deleted file HAS history (so R-DEAD-PATH would be BLOCKING), while the shallow
        clone reports none and would quietly return to-confirm."""
        mod = _load("doc-refs-check.py")
        mod.REPO = self.full
        mod._HISTORICAL_PATHS = None
        entrylib._IS_SHALLOW = None
        self.assertFalse(mod.history_is_blind())
        self.assertTrue(mod.had_history("mort.txt"))

        mod._HISTORICAL_PATHS = None
        mod.REPO = self.shallow
        self.assertFalse(mod.had_history("mort.txt"))   # the silent downgrade, pinned


if __name__ == "__main__":
    unittest.main()
