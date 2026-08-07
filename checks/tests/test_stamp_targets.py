# tests/test_stamp_targets.py
#
# Regression tests for `entrylib.stamp_targets` — the shared selector behind the three
# `--stamp` commands (backlog / feature-map / memory).
#
# The invariant that must never re-break: **a stamp that cannot select its target says
# so.** The defect these tests pin down was the opposite — `git diff --cached
# --name-only` prints REPO-relative paths, so a `startswith("backlog/")` filter run with
# `cwd=<framework>` could never match when the framework is NESTED in a subdirectory.
# The selector returned an empty list, the caller stamped nothing, printed `0 stamped`
# and exited 0: a false green, indistinguishable from "nothing to do". Structural, not
# a corner case — and invisible in a repo where the framework sits at the root, which is
# exactly where the framework's own tests run.
#
# So every selector case below is exercised TWICE, once per layout (framework AT the repo
# root, framework NESTED under `docs/`), and asserted to agree. A test that only ran the
# flat layout would have passed against the broken code.
import os
import subprocess
import sys
import tempfile
import unittest

CHECKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CHECKS_DIR)
import entrylib  # noqa: E402


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True,
                   capture_output=True, text=True)


def _write(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class StampTargetsBase(unittest.TestCase):
    """Builds a throwaway git repo whose framework root is `sub` levels deep."""
    SUB = ""  # "" → framework at the repo root; "docs" → nested

    def setUp(self):
        self.repo = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.repo,
                                                            ignore_errors=True))
        _git(self.repo, "init", "-q")
        _git(self.repo, "config", "user.email", "t@t")
        _git(self.repo, "config", "user.name", "t")
        self.fw = os.path.join(self.repo, self.SUB) if self.SUB else self.repo
        os.makedirs(self.fw, exist_ok=True)

    def stage(self, rel):
        """Creates <framework>/<rel> and stages it. Returns its framework-relative path."""
        _write(os.path.join(self.fw, rel), "---\nupdated: 2020-01-01\n---\n")
        _git(self.repo, "add", "-A")
        return rel

    def staged(self, prefix, match):
        return entrylib.stamp_targets(self.fw, ["--stamp", "--staged"], prefix, match)


class TestStagedSelector(StampTargetsBase):
    def test_staged_state_file_is_selected(self):
        rel = self.stage("backlog/notation/STATE.md")
        files, unresolved = self.staged("backlog/", lambda b: b == "STATE.md")
        # Framework-relative, whatever the layout — the caller joins it onto its root.
        self.assertEqual(files, [rel])
        self.assertEqual(unresolved, [])

    def test_staged_ignores_other_prefixes(self):
        self.stage("features/camp.md")
        files, _ = self.staged("backlog/", lambda b: b == "STATE.md")
        self.assertEqual(files, [])

    def test_staged_ignores_non_matching_basename(self):
        self.stage("backlog/notation/constat.md")
        files, _ = self.staged("backlog/", lambda b: b == "STATE.md")
        self.assertEqual(files, [])

    def test_staged_selects_features_and_memory_too(self):
        # The three callers differ only by (prefix, match) — one selector, three channels.
        self.stage("features/camp.md")
        self.stage("memory/fact.md")
        feats, _ = self.staged("features/", lambda b: b.endswith(".md"))
        mems, _ = self.staged("memory/", lambda b: b.endswith(".md"))
        self.assertEqual(feats, ["features/camp.md"])
        self.assertEqual(mems, ["memory/fact.md"])

    def test_unstaged_file_is_not_selected(self):
        _write(os.path.join(self.fw, "backlog/notation/STATE.md"), "---\n---\n")
        files, _ = self.staged("backlog/", lambda b: b == "STATE.md")
        self.assertEqual(files, [])


class TestStagedSelectorNested(TestStagedSelector):
    """The whole staged suite again, framework nested — the layout that was broken."""
    SUB = "docs"


class TestExplicitPaths(StampTargetsBase):
    def test_framework_relative_path(self):
        rel = self.stage("backlog/notation/STATE.md")
        files, unresolved = entrylib.stamp_targets(
            self.fw, ["--stamp", rel], "backlog/", lambda b: True)
        self.assertEqual((files, unresolved), ([rel], []))

    def test_repo_relative_path_also_accepted(self):
        # The second trap of the same assumption: the form a user reaches for FIRST when
        # working from the repo root used to resolve to <framework>/<repo-rel> — a path
        # that cannot exist — and was skipped without a word.
        rel = self.stage("backlog/notation/STATE.md")
        repo_rel = os.path.join(self.SUB, rel).replace(os.sep, "/") if self.SUB else rel
        files, unresolved = entrylib.stamp_targets(
            self.fw, ["--stamp", repo_rel], "backlog/", lambda b: True)
        self.assertEqual((files, unresolved), ([rel], []))

    def test_absolute_path_accepted(self):
        rel = self.stage("backlog/notation/STATE.md")
        files, unresolved = entrylib.stamp_targets(
            self.fw, ["--stamp", os.path.join(self.fw, rel)], "backlog/", lambda b: True)
        self.assertEqual((files, unresolved), ([rel], []))

    def test_missing_path_is_REPORTED_not_swallowed(self):
        # The invariant of the whole fix: what cannot be selected is named, never
        # silently folded into a "0 stamped" that reads like success.
        files, unresolved = entrylib.stamp_targets(
            self.fw, ["--stamp", "backlog/ghost/STATE.md"], "backlog/", lambda b: True)
        self.assertEqual(files, [])
        self.assertEqual(unresolved, ["backlog/ghost/STATE.md"])

    def test_flags_after_stamp_are_not_paths(self):
        files, unresolved = entrylib.stamp_targets(
            self.fw, ["--stamp", "--json"], "backlog/", lambda b: True)
        self.assertEqual((files, unresolved), ([], []))


class TestExplicitPathsNested(TestExplicitPaths):
    SUB = "docs"


class TestRepoRoot(unittest.TestCase):
    def test_outside_a_repo_falls_back_to_start(self):
        # No git above a temp dir on most CI images; either way the contract is "never
        # raise" — a stamp is non-blocking by construction.
        d = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        self.assertIsInstance(entrylib.repo_root(d), str)


if __name__ == "__main__":
    unittest.main()
