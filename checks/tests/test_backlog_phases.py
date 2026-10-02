# tests/test_backlog_phases.py
#
# Regression tests for `backlog-check.py`'s phases and gates (`backlog/README.md §Phases`):
# E-PHASE, E-PHASE-MISSING, E-GATE, E-PHASE-ORDER, E-SKIP, E-SPEC-DRIFT, E-PLAN-DRIFT,
# E-VALIDATION-STALE, E-PHASE-LATE, E-STATUS-PHASE, E-ARCH-PATH, E-BUILD-PREFIX. What must never
# re-open: a work item that claims a phase it cannot prove — building before the plan was
# audited, closing before anything was validated — passing the check in silence. Each rule
# here was seen RED by neutralizing it (counter-proof, see the work item that added them).
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

CHECKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PHASE_RULES = {"E-PHASE", "E-PHASE-MISSING", "E-GATE", "E-PHASE-ORDER", "E-SKIP",
               "E-SPEC-DRIFT", "E-PLAN-DRIFT", "E-VALIDATION-STALE", "E-PHASE-LATE",
               "E-STATUS-PHASE", "E-ARCH-PATH", "E-BUILD-PREFIX"}

COMMIT_DAY = "2020-06-15"


def _load_module():
    """backlog-check.py has a hyphen — not importable by name; load it by path."""
    path = os.path.join(CHECKS_DIR, "backlog-check.py")
    spec = importlib.util.spec_from_file_location("backlog_check_phases", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class PhaseGates(unittest.TestCase):
    framework_subdir = ""   # "" = framework at the repo root; overridden below

    def setUp(self):
        self.repo = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.repo, ignore_errors=True))
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=self.repo, check=True)
        self.root = os.path.join(self.repo, self.framework_subdir) if self.framework_subdir \
            else self.repo
        self.mod = _load_module()
        self.mod.ROOT = self.root
        self.mod.BACKLOG = os.path.join(self.root, "backlog")
        self.mod.REQUIRE_PHASE = False
        self.mod.BUILD_TASK_PREFIX = "Lot"

    # -- fixture ----------------------------------------------------------- #
    def _item(self, phase="framing", tasks=(), companions=None, extra_docs=(),
              status="in-progress"):
        """Writes backlog/x/ — `companions` = {name: (frontmatter dict | None, body)}."""
        companions = companions or {}
        cdir = os.path.join(self.mod.BACKLOG, "x")
        os.makedirs(cdir, exist_ok=True)
        for name, (fm, body) in companions.items():
            head = ""
            if fm:
                lines = []
                for k, v in fm.items():
                    v = "[" + ", ".join(v) + "]" if isinstance(v, list) else v
                    lines.append(f"{k}: {v}")
                head = "---\n" + "\n".join(lines) + "\n---\n\n"
            with open(os.path.join(cdir, name), "w", encoding="utf-8") as fh:
                fh.write(head + body + "\n")
        docs = sorted(set(companions) | set(extra_docs))
        phase_line = f"phase: {phase}\n" if phase is not None else ""
        task_lines = "\n".join(f"- [{s}] {lb}" for s, lb in tasks) or "- [todo] Frame it"
        with open(os.path.join(cdir, "STATE.md"), "w", encoding="utf-8") as fh:
            fh.write(f"---\nid: x\ntitle: X\nstatus: {status}\nmilestone: null\n"
                     f"docs: [{', '.join(docs)}]\n{phase_line}updated: {COMMIT_DAY}\n---\n\n"
                     f"## Tasks\n{task_lines}\n")
        return cdir

    def _rules(self, cdir, severity=None):
        found = self.mod.check_work_item("x", cdir, {"x"}, {}, {})
        return sorted(f.rule for f in found if f.rule in PHASE_RULES
                      and (severity is None or f.severity == severity))

    @staticmethod
    def _spec(**fm):
        return {"spec.md": (fm, "# Spec")}

    def _proven_through_audit(self, **extra):
        comp = self._spec(validated="2020-06-10", architecture="architecture.md")
        comp["architecture.md"] = (None, "# Arch")
        comp["plan.md"] = (None, "# Plan")
        comp["audit-plan.md"] = ({"verdict": "pass"}, "# Audit")
        comp.update(extra)
        return comp

    # -- E-PHASE / E-PHASE-MISSING ------------------------------------------ #
    def test_framing_needs_nothing(self):
        self.assertEqual(self._rules(self._item("framing")), [])

    def test_unknown_phase_blocks(self):
        self.assertEqual(self._rules(self._item("coding")), ["E-PHASE"])

    def test_missing_phase_is_soft_by_default(self):
        cdir = self._item(phase=None)
        self.assertEqual(self._rules(cdir, self.mod.TO_CONFIRM), ["E-PHASE-MISSING"])

    def test_missing_phase_blocks_when_required(self):
        self.mod.REQUIRE_PHASE = True
        cdir = self._item(phase=None)
        self.assertEqual(self._rules(cdir, self.mod.BLOCKING), ["E-PHASE-MISSING"])

    # -- E-GATE ------------------------------------------------------------- #
    def test_leaving_framing_needs_validated_spec(self):
        self.assertEqual(self._rules(self._item("architecture", companions=self._spec())),
                         ["E-GATE"])
        self.assertEqual(self._rules(self._item("architecture",
                                                companions=self._spec(validated="2020-06-10"))),
                         [])

    def test_plan_needs_the_named_architecture_doc(self):
        comp = self._spec(validated="2020-06-10", architecture="conception.md")
        self.assertEqual(self._rules(self._item("plan", companions=comp)), ["E-GATE"])
        comp["conception.md"] = (None, "# Conception")
        self.assertEqual(self._rules(self._item("plan", companions=comp)), [])

    def test_architecture_skip_as_bare_scalar(self):
        comp = self._spec(validated="2020-06-10", skip="architecture")
        self.assertEqual(self._rules(self._item("plan", companions=comp)), [])

    def test_plan_audit_needs_plan(self):
        comp = self._spec(validated="2020-06-10", skip=["architecture"])
        self.assertEqual(self._rules(self._item("plan-audit", companions=comp)), ["E-GATE"])

    def test_build_needs_a_passing_audit(self):
        comp = self._proven_through_audit()
        self.assertEqual(self._rules(self._item("build", companions=comp)), [])
        comp["audit-plan.md"] = ({"verdict": "fail"}, "# Audit")
        self.assertEqual(self._rules(self._item("build", companions=comp)), ["E-GATE"])

    def test_undeclared_gate_file_is_no_proof(self):
        comp = self._proven_through_audit()
        del comp["audit-plan.md"]
        cdir = self._item("build", companions=comp)
        with open(os.path.join(cdir, "audit-plan.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nverdict: pass\n---\n")
        self.assertEqual(self._rules(cdir), ["E-GATE"])

    def test_plan_audit_skip_opens_build(self):
        comp = self._spec(validated="2020-06-10", skip=["architecture", "plan-audit"])
        comp["plan.md"] = (None, "# Plan")
        self.assertEqual(self._rules(self._item("build", companions=comp,
                                                tasks=[("done", "Lot 1 — x")])), [])

    def test_validation_needs_every_build_task_done(self):
        comp = self._proven_through_audit()
        cdir = self._item("validation", companions=comp,
                          tasks=[("done", "Lot 1 — a"), ("in-progress", "Lot 2 — b")])
        self.assertEqual(self._rules(cdir), ["E-GATE"])

    def test_closure_needs_a_passing_validation(self):
        comp = self._proven_through_audit()
        self.assertEqual(self._rules(self._item("closure", companions=comp)), ["E-GATE"])
        comp["validation.md"] = ({"verdict": "pass"}, "# Validation")
        self.assertEqual(self._rules(self._item("closure", companions=comp)), [])

    # -- E-PHASE-ORDER ------------------------------------------------------ #
    def test_build_task_done_before_the_audit_blocks(self):
        cdir = self._item("framing", tasks=[("done", "Lot 1 — wrote code")])
        self.assertEqual(self._rules(cdir), ["E-PHASE-ORDER"])

    def test_stepping_back_after_a_passed_audit_does_not_block(self):
        comp = self._proven_through_audit()
        cdir = self._item("plan", companions=comp, tasks=[("done", "Lot 1 — wrote code")])
        self.assertEqual(self._rules(cdir), [])

    def test_prefix_is_a_whole_word(self):
        cdir = self._item("framing", tasks=[("done", "Lotus position reviewed")])
        self.assertEqual(self._rules(cdir), [])

    # -- E-SKIP ------------------------------------------------------------- #
    def test_only_two_gates_may_be_skipped(self):
        comp = self._spec(validated="2020-06-10", skip=["validation"])
        self.assertEqual(self._rules(self._item("framing", companions=comp)), ["E-SKIP"])

    # -- E-SPEC-DRIFT ------------------------------------------------------- #
    def _commit(self):
        subprocess.run(["git", "add", "-A"], cwd=self.repo, check=True)
        env = dict(os.environ, GIT_COMMITTER_DATE=f"{COMMIT_DAY}T12:00:00",
                   GIT_AUTHOR_DATE=f"{COMMIT_DAY}T12:00:00")
        subprocess.run(["git", "commit", "-q", "-m", "c"], cwd=self.repo, check=True, env=env)

    # The gate is the COMMIT that set the line, not a date: every commit below lands on the
    # same day (`_commit`), which is exactly the case a date comparison could not see.
    def test_spec_validated_in_its_only_commit_is_quiet(self):
        cdir = self._item("framing", companions=self._spec(validated="2020-06-14"))
        self._commit()
        self.assertEqual(self._rules(cdir), [])

    def test_spec_edited_after_validation_the_same_day_blocks(self):
        self._item("framing", companions={"spec.md": ({"validated": COMMIT_DAY}, "# Spec")})
        self._commit()
        cdir = self._item("framing",
                          companions={"spec.md": ({"validated": COMMIT_DAY}, "# Spec, moved")})
        self._commit()
        self.assertEqual(self._rules(cdir, self.mod.BLOCKING), ["E-SPEC-DRIFT"])

    def test_skip_added_after_validation_blocks(self):
        self._item("framing", companions=self._spec(validated=COMMIT_DAY))
        self._commit()
        cdir = self._item("framing", companions=self._spec(validated=COMMIT_DAY,
                                                           skip=["plan-audit"]))
        self._commit()
        self.assertEqual(self._rules(cdir, self.mod.BLOCKING), ["E-SPEC-DRIFT"])

    def test_revalidated_spec_is_quiet(self):
        self._item("framing", companions={"spec.md": ({"validated": COMMIT_DAY}, "# Spec")})
        self._commit()
        self._item("framing", companions={"spec.md": (None, "# Spec, moved")})
        self._commit()   # stepping back: the line is dropped
        cdir = self._item("framing",
                          companions={"spec.md": ({"validated": COMMIT_DAY}, "# Spec, moved")})
        self._commit()   # set again: the gate moves here
        self.assertEqual(self._rules(cdir), [])

    def test_uncommitted_spec_is_not_judged(self):
        cdir = self._item("framing", companions=self._spec(validated=COMMIT_DAY))
        self.assertEqual(self._rules(cdir), [])

    # -- E-PLAN-DRIFT ------------------------------------------------------- #
    def _built_then_plan_edited(self, phase="build"):
        self._item(phase, companions=self._proven_through_audit())
        self._commit()
        cdir = self._item(phase, companions=self._proven_through_audit(
            **{"plan.md": (None, "# Plan, with a new batch")}))
        self._commit()
        return cdir

    def test_plan_edited_after_its_audit_blocks_in_build(self):
        cdir = self._built_then_plan_edited()
        self.assertEqual(self._rules(cdir, self.mod.BLOCKING), ["E-PLAN-DRIFT"])

    def test_a_new_audit_lifts_the_plan_drift(self):
        self._built_then_plan_edited()
        cdir = self._item("build", companions=self._proven_through_audit(
            **{"plan.md": (None, "# Plan, with a new batch"),
               "audit-plan.md": ({"verdict": "pass"}, "# Audit, second pass")}))
        self._commit()
        self.assertEqual(self._rules(cdir), [])

    def test_revising_the_plan_before_build_is_quiet(self):
        cdir = self._built_then_plan_edited(phase="plan")
        self.assertEqual(self._rules(cdir), [])

    # -- E-VALIDATION-STALE ------------------------------------------------- #
    def _validated_closure(self):
        comp = self._proven_through_audit(**{"validation.md": ({"verdict": "pass"}, "# V")})
        self._item("closure", companions=comp, tasks=[("done", "Lot 1 — a")])
        self._commit()
        return comp

    def test_batch_done_after_the_validation_is_reported(self):
        comp = self._validated_closure()
        cdir = self._item("closure", companions=comp,
                          tasks=[("done", "Lot 1 — a"), ("done", "Lot 2 — b")])
        self._commit()
        self.assertEqual(self._rules(cdir, self.mod.TO_CONFIRM), ["E-VALIDATION-STALE"])

    def test_validation_that_saw_every_batch_is_quiet(self):
        self._validated_closure()
        cdir = self._item("closure", companions=self._proven_through_audit(
            **{"validation.md": ({"verdict": "pass"}, "# V")}), tasks=[("done", "Lot 1 — a")])
        self.assertEqual(self._rules(cdir), [])

    # -- E-PHASE-LATE ------------------------------------------------------- #
    def test_batch_in_progress_before_build_is_reported(self):
        cdir = self._item("framing", tasks=[("in-progress", "Lot 1 — coding already")])
        self.assertEqual(self._rules(cdir, self.mod.TO_CONFIRM), ["E-PHASE-LATE"])

    def test_batch_in_progress_in_build_is_quiet(self):
        cdir = self._item("build", companions=self._proven_through_audit(),
                          tasks=[("in-progress", "Lot 1 — coding")])
        self.assertEqual(self._rules(cdir), [])

    # -- E-STATUS-PHASE ----------------------------------------------------- #
    def test_todo_status_past_framing_blocks(self):
        comp = self._spec(validated="2020-06-10")
        cdir = self._item("architecture", companions=comp, status="todo")
        self.assertEqual(self._rules(cdir, self.mod.BLOCKING), ["E-STATUS-PHASE"])
        cdir = self._item("framing", status="todo")
        self.assertEqual(self._rules(cdir), [])

    # -- E-ARCH-PATH -------------------------------------------------------- #
    def test_architecture_leaving_the_repository_blocks(self):
        for arch in ("C:/x.md", "/x.md", "\\x.md", "a/../b.md", "..\\x.md"):
            comp = self._spec(validated="2020-06-10", architecture=arch)
            with self.subTest(arch=arch):
                self.assertIn("E-ARCH-PATH",
                              self._rules(self._item("plan", companions=comp),
                                          self.mod.BLOCKING))

    # -- the build prefix --------------------------------------------------- #
    def test_default_prefix_is_batch(self):
        self.assertEqual(self.mod.DEFAULT_BUILD_TASK_PREFIX, "Batch")

    def test_emphasis_around_the_prefix_is_ignored(self):
        cdir = self._item("framing", tasks=[("done", "**Lot** 1 — wrote code")])
        self.assertEqual(self._rules(cdir), ["E-PHASE-ORDER"])

    def test_plural_prefix_is_reported(self):
        cdir = self._item("framing", tasks=[("todo", "Lots 1-2 — two at once")])
        self.assertEqual(self._rules(cdir, self.mod.TO_CONFIRM), ["E-BUILD-PREFIX"])


class PhaseGatesNestedFramework(PhaseGates):
    """Same gates with the framework in a subfolder (a host project's `Docs/`): an
    `architecture:` path with `/` resolves from the REPOSITORY root, not the framework's."""
    framework_subdir = "Docs"

    def test_durable_architecture_doc_from_repo_root(self):
        os.makedirs(os.path.join(self.repo, "Docs", "architecture"), exist_ok=True)
        with open(os.path.join(self.repo, "Docs", "architecture", "combat.md"), "w",
                  encoding="utf-8") as fh:
            fh.write("# Combat\n")
        comp = self._spec(validated="2020-06-10", architecture="Docs/architecture/combat.md")
        self.assertEqual(self._rules(self._item("plan", companions=comp)), [])
        comp = self._spec(validated="2020-06-10", architecture="architecture/combat.md")
        self.assertEqual(self._rules(self._item("plan", companions=comp)), ["E-GATE"])


if __name__ == "__main__":
    unittest.main()
