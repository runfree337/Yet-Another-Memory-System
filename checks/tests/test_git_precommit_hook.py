# tests/test_git_precommit_hook.py
#
# Integration tests for `adapters/git/pre-commit` — the git-native wiring of the
# `updated` stamp, run through REAL `git commit`s. What must never re-break:
#
#   - an ordinary commit stamps the staged STATE.md (frontmatter date = commit date),
#     `git commit -a` included (`index.lock` IS the real upcoming index, not a temp);
#   - a commit that replays someone else's work (sister head present) does NOT stamp,
#     and SAYS so on stderr — dating replayed work today would erase its real date;
#   - a partial commit (`git commit -- <path>`, temporary index) does NOT stamp, and
#     SAYS so — the stamp would land in the throwaway index and the next commit would
#     bring the old date back without a word (measured).
#
# The hook's defenses (env purge, `-ef` whitelist) were found at the bench, not by
# reading: these tests replay the bench so the next reader does not have to.
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

CHECKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMEWORK = os.path.dirname(CHECKS_DIR)

STATE = "backlog/x/STATE.md"
OLD = "---\nid: x\nupdated: 2020-01-01\n---\n## Tasks\n- [todo] t\n"


@unittest.skipUnless(shutil.which("git") and shutil.which("bash"),
                     "needs git and bash")
class GitPreCommitHook(unittest.TestCase):
    def setUp(self):
        self.repo = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.repo, ignore_errors=True))
        # Materialize the canon layout: the checks the home script runs, the home
        # script, the hook — copied from the real framework so the test exercises the
        # shipped files, not a re-description of them.
        os.makedirs(os.path.join(self.repo, "checks"))
        for name in ("entrylib.py", "backlog-check.py", "feature-map-check.py",
                     "memory-check.py"):
            shutil.copy(os.path.join(CHECKS_DIR, name),
                        os.path.join(self.repo, "checks", name))
        os.makedirs(os.path.join(self.repo, "hooks"))
        shutil.copy(os.path.join(FRAMEWORK, "hooks", "stamp-staged.sh"),
                    os.path.join(self.repo, "hooks", "stamp-staged.sh"))
        os.makedirs(os.path.join(self.repo, "adapters", "git"))
        hook = os.path.join(self.repo, "adapters", "git", "pre-commit")
        shutil.copy(os.path.join(FRAMEWORK, "adapters", "git", "pre-commit"), hook)
        os.chmod(hook, 0o755)
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        self.git("config", "core.hooksPath", "adapters/git")

    def git(self, *args, check=True):
        return subprocess.run(["git", *args], cwd=self.repo, check=check,
                              capture_output=True, text=True)

    def write_state(self, text=OLD):
        full = os.path.join(self.repo, STATE)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(text)

    def committed_updated(self):
        out = self.git("show", f"HEAD:{STATE}").stdout
        for line in out.splitlines():
            if line.startswith("updated:"):
                return line.split(":", 1)[1].strip()
        return None

    def test_ordinary_commit_stamps(self):
        self.write_state()
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "c")
        self.assertNotEqual(self.committed_updated(), "2020-01-01")

    def test_commit_a_stamps(self):
        # `git commit -a` exports GIT_INDEX_FILE=index.lock, which BECOMES the real
        # index — a "!= index" test refused the most common commit form (measured).
        self.write_state()
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "c")
        self.write_state(OLD.replace("[todo]", "[done]"))
        r = self.git("commit", "-q", "-am", "c2")
        self.assertNotIn("temporary index", r.stderr)
        self.assertNotEqual(self.committed_updated(), "2020-01-01")

    def test_partial_commit_renounces_and_says_so(self):
        # `git commit -- <path>` builds a throwaway index: stamping it would let the
        # NEXT commit bring the old date back without a word. The hook renounces — and
        # the renunciation is audible on the commit's stderr.
        self.write_state()
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "c")
        self.write_state(OLD.replace("[todo]", "[done]"))
        r = self.git("commit", "-q", "-m", "c2", "--", STATE)
        self.assertIn("temporary index", r.stderr)
        self.assertEqual(self.committed_updated(), "2020-01-01")

    def test_sister_head_commit_renounces_and_says_so(self):
        # A conflicted merge/cherry-pick/revert/rebase ends in a manual `git commit`
        # that lands on pre-commit: replayed work keeps its original date.
        self.write_state()
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "c1")
        first = self.git("rev-parse", "HEAD").stdout.strip()
        with open(os.path.join(self.repo, "other.md"), "w", encoding="utf-8") as fh:
            fh.write("x\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "c2")
        # Simulate the post-conflict state: a sister head + a re-staged STATE.md.
        git_dir = self.git("rev-parse", "--absolute-git-dir").stdout.strip()
        with open(os.path.join(git_dir, "MERGE_HEAD"), "w", encoding="utf-8") as fh:
            fh.write(first + "\n")
        self.write_state(OLD.replace("[todo]", "[done]"))
        self.git("add", "-A")
        r = self.git("commit", "-q", "-m", "merge")
        self.assertIn("MERGE_HEAD", r.stderr)
        self.assertEqual(self.committed_updated(), "2020-01-01")


if __name__ == "__main__":
    unittest.main()
