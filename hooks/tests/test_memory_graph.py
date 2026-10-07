# tests/test_memory_graph.py — behavior of the derived memory-graph engine.
import importlib.util
import json
import os
import tempfile
import unittest

HOOKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_module():
    """memory-graph.py has a hyphen — not importable by name; load it by path."""
    path = os.path.join(HOOKS_DIR, "memory-graph.py")
    spec = importlib.util.spec_from_file_location("memory_graph", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class GraphFixture(unittest.TestCase):
    """A small synthetic repo with all four channels populated."""

    def setUp(self):
        self.mod = _load_module()
        self.root = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)

        _write(os.path.join(self.root, "decisions/INDEX.md"), (
            "# Decisions — INDEX\n"
            "## Active\n"
            "- [D-2026-07-11-02](D-2026-07-11-02.md) — order clock · [ordermanager] beats via TickStep.\n"
            "## Archived\n"
            "- [D-2026-01-01-01](D-2026-01-01-01.md) — old order · [ordermanager] superseded by D-2026-07-11-02.\n"
        ))
        _write(os.path.join(self.root, "decisions/D-2026-07-11-02.md"),
               "---\nid: D-2026-07-11-02\nstatus: active\nupdated: 2026-07-11\n"
               "replaces: [D-2026-01-01-01]\n---\n**Decision** **Why** **Invariant**\n")
        _write(os.path.join(self.root, "decisions/D-2026-01-01-01.md"),
               "---\nid: D-2026-01-01-01\nstatus: archived\nupdated: 2026-01-01\n"
               "replaced-by: D-2026-07-11-02\n---\n**Decision** **Why** **Invariant**\n")
        _write(os.path.join(self.root, "features/order-engine.md"),
               "---\nid: order-engine\ncreated: 2026-07-01\nupdated: 2026-07-11\n"
               "links: [D-2026-07-11-02]\n---\n"
               "**Role:** Drives checkout resolution.\n"
               "**Code:** `src/orders/OrderManager.java`, `src/orders/TaxCalculator.java`.\n")
        _write(os.path.join(self.root, "backlog/refacto-x/STATE.md"),
               "---\nid: refacto-x\ntitle: Refactor X\nstatus: in-progress\nafter: []\n"
               "docs: [design.md]\nupdated: 2026-07-10\n---\n## Tasks\n- [ ] todo\n")

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)

    def _set_config(self, block):
        _write(os.path.join(self.root, "checks-config.json"),
               json.dumps({"memory-graph": block}))


class TestCovers(GraphFixture):
    def test_path_containment_is_agnostic_by_default(self):
        # No config → only correspondence #1 (cited-path containment) fires.
        hits = self.mod.cmd_covers(self.root, "src/orders/OrderManager.java")
        ids = [h[1] for h in hits]
        self.assertIn("order-engine", ids)
        self.assertNotIn("D-2026-07-11-02", ids, "class correspondence must be OFF without config")

    def test_directory_prefix_covers_subtree(self):
        # A fiche that cited `src/orders/OrderManager.java` does NOT cover a
        # sibling file — containment is exact, never a substring/dir-guess.
        hits = self.mod.cmd_covers(self.root, "src/orders/Other.java")
        self.assertEqual(hits, [])

    def test_class_extension_opt_in_adds_active_decision(self):
        self._set_config({"class-file-extensions": [".java"]})
        exts = self.mod.class_file_extensions(self.mod.load_config(self.root))
        hits = self.mod.cmd_covers(self.root, "src/orders/OrderManager.java", exts)
        ids = [h[1] for h in hits]
        self.assertIn("order-engine", ids)          # #1 path
        self.assertIn("D-2026-07-11-02", ids)         # #3 active decision via tag

    def test_exact_citation_outranks_directory_prefix_under_the_cap(self):
        # Three alphabetically-earlier fiches cite the whole `src/` tree; a
        # fourth, alphabetically LAST, cites the exact file. In the note's
        # MAX_ENTRIES window the exact citation must survive and rank first —
        # the old id-order truncation silently dropped it.
        for name in ("aaa-broad", "bbb-broad", "ccc-broad"):
            _write(os.path.join(self.root, "features/%s.md" % name),
                   "---\nid: %s\nupdated: 2026-07-01\n---\n"
                   "**Role:** Broad coverage.\n**Code:** `src/`.\n" % name)
        _write(os.path.join(self.root, "features/zzz-exact.md"),
               "---\nid: zzz-exact\nupdated: 2026-07-01\n---\n"
               "**Role:** Exact coverage.\n**Code:** `src/orders/OrderManager.java`.\n")
        hits = self.mod.cmd_covers(self.root, "src/orders/OrderManager.java")
        ids = [h[1] for h in hits]
        # Both exact citations (the fixture's `order-engine` + `zzz-exact`)
        # must rank ahead of every broad `src/` fiche — and NOTHING is cut at
        # this level: cmd_covers returns every hit, the cap is the note's.
        self.assertEqual(ids, ["order-engine", "zzz-exact",
                               "aaa-broad", "bbb-broad", "ccc-broad"])

    def test_covers_note_says_what_the_cap_cut(self):
        # More hits than MAX_ENTRIES → the note shows the best ones and SAYS
        # how many it cut; within the cap → no truncation line at all.
        for i in range(self.mod.MAX_ENTRIES + 2):
            _write(os.path.join(self.root, "features/broad-%02d.md" % i),
                   "---\nid: broad-%02d\nupdated: 2026-07-01\n---\n"
                   "**Role:** Broad.\n**Code:** `src/`.\n" % i)
        root_abs = os.path.abspath(self.root).replace("\\", "/")
        note, key = self.mod.build_covers_note(
            self.root, root_abs, {"file_path": "src/orders/OrderManager.java"}, set())
        self.assertIn("… and 3 more", note,
                      "a cut cap must say so — silent truncation reads as 'this is all'")
        self.assertEqual(note.count("\n- "), self.mod.MAX_ENTRIES)
        # Control: a target covered by ONE fiche only (outside the broad
        # `src/` cites) gets no truncation line at all.
        _write(os.path.join(self.root, "features/solo.md"),
               "---\nid: solo\nupdated: 2026-07-01\n---\n"
               "**Role:** Solo.\n**Code:** `lib/Solo.java`.\n")
        note2, _ = self.mod.build_covers_note(
            self.root, root_abs, {"file_path": "lib/Solo.java"}, set())
        self.assertNotIn("more —", note2, "no truncation line when nothing was cut")

    def test_deeper_directory_prefix_outranks_broader_one(self):
        # `src/orders/` says more about the target than `src/` — segment
        # depth, not id order, decides the ranking between directory cites.
        _write(os.path.join(self.root, "features/aaa-shallow.md"),
               "---\nid: aaa-shallow\nupdated: 2026-07-01\n---\n"
               "**Role:** Shallow.\n**Code:** `src/`.\n")
        _write(os.path.join(self.root, "features/zzz-deep.md"),
               "---\nid: zzz-deep\nupdated: 2026-07-01\n---\n"
               "**Role:** Deep.\n**Code:** `src/orders/`.\n")
        hits = self.mod.cmd_covers(self.root, "src/orders/OrderManager.java")
        ids = [h[1] for h in hits]
        self.assertLess(ids.index("zzz-deep"), ids.index("aaa-shallow"))

    def test_extract_paths_keeps_only_path_shaped_tokens(self):
        # Prose alternatives (`switch/case`, `id/name`) are not citations; a
        # file with an extension and a directory with its trailing slash are.
        body = ("Uses `switch/case` on `id/name`; code in `src/orders/` and "
                "`src/orders/OrderManager.java`, docs in `docs/guide v2/intro.md`.")
        self.assertEqual(self.mod.extract_paths(body),
                         ["src/orders/", "src/orders/OrderManager.java",
                          "docs/guide v2/intro.md"])

    def test_extract_paths_drops_template_and_placeholder_shapes(self):
        # `<loc>`, a glob, and a single-alternative `{id}` brace illustrate a
        # NAMING SCHEME — they never become edges (and never feed doctor).
        # The comma-bearing brace stays the sibling-files shorthand.
        body = ("Scheme: `data/<loc>/p.asset`, icons `art/icon_*.png`, one "
                "`data/locations/{id}.asset`; real: `src/{A,B}.java`.")
        self.assertEqual(self.mod.extract_paths(body),
                         ["src/A.java", "src/B.java"])

    def test_doctor_reports_only_unresolved_citations(self):
        # `order-engine` cites two files: one exists on disk, one doesn't —
        # doctor must name exactly the dead one, with its citing node. (The
        # backlog fixture's declared companion doc must exist too — doctor
        # checks backlog `docs:` citations like any other cite-path edge.)
        _write(os.path.join(self.root, "backlog/refacto-x/design.md"), "# design\n")
        _write(os.path.join(self.root, "src/orders/OrderManager.java"), "class OrderManager {}")
        dead = self.mod.cmd_doctor(self.root)
        self.assertEqual([(d[0], d[2]) for d in dead],
                         [("order-engine", "src/orders/TaxCalculator.java")])
        _write(os.path.join(self.root, "src/orders/TaxCalculator.java"), "class TaxCalculator {}")
        self.assertEqual(self.mod.cmd_doctor(self.root), [])

    def test_doctor_dir_citation_must_be_a_directory(self):
        # A `dir/` citation that resolves to a FILE is a lying citation, not
        # a live one — `os.path.exists` alone would wave it through.
        _write(os.path.join(self.root, "backlog/refacto-x/design.md"), "# design\n")
        _write(os.path.join(self.root, "src/orders/OrderManager.java"), "class OrderManager {}")
        _write(os.path.join(self.root, "src/orders/TaxCalculator.java"), "class TaxCalculator {}")
        _write(os.path.join(self.root, "features/dir-as-file.md"),
               "---\nid: dir-as-file\nupdated: 2026-07-01\n---\n"
               "**Role:** Cites a file as a directory.\n**Code:** `src/orders/OrderManager.java/`.\n")
        dead = self.mod.cmd_doctor(self.root)
        self.assertEqual([(d[0], d[2]) for d in dead],
                         [("dir-as-file", "src/orders/OrderManager.java/")])

    def test_notes_name_the_real_script_and_match_says_its_cut(self):
        # The suggested command must be the file that actually exists (an
        # adopting repo vendors the engine under another name) — never a
        # hardcoded `memory-graph.py`. And the match note, like covers, says
        # what its cap cut instead of silently truncating.
        script = self.mod._script_ref()
        root_abs = os.path.abspath(self.root).replace("\\", "/")
        note, _ = self.mod.build_covers_note(
            self.root, root_abs, {"file_path": "src/orders/OrderManager.java"}, set())
        self.assertIn("`%s neighbors <id>`" % script, note)
        for i in range(self.mod.MAX_ENTRIES + 1):
            _write(os.path.join(self.root, "features/order-extra-%02d.md" % i),
                   "---\nid: order-extra-%02d\nupdated: 2026-07-01\n---\n"
                   "**Role:** Extra order coverage fiche.\n**Code:** `src/orders/`.\n" % i)
        note, _ = self.mod.build_match_note(
            self.root, root_abs, {"pattern": "order"})
        self.assertIn("more — `%s match order`" % script, note)
        self.assertEqual(note.count("\n- "), self.mod.MAX_ENTRIES)

    def test_equal_specificity_keeps_ascending_id_order(self):
        # Same citation depth → the old deterministic id order still holds
        # (no behavioral lottery between equally-specific fiches).
        _write(os.path.join(self.root, "features/aaa-same.md"),
               "---\nid: aaa-same\nupdated: 2026-07-01\n---\n"
               "**Role:** Same depth.\n**Code:** `src/orders/OrderManager.java`.\n")
        hits = self.mod.cmd_covers(self.root, "src/orders/OrderManager.java")
        ids = [h[1] for h in hits]
        self.assertLess(ids.index("aaa-same"), ids.index("order-engine"))

    def test_archived_decision_never_covers(self):
        self._set_config({"class-file-extensions": [".java"]})
        exts = self.mod.class_file_extensions(self.mod.load_config(self.root))
        hits = self.mod.cmd_covers(self.root, "src/orders/OrderManager.java", exts)
        self.assertNotIn("D-2026-01-01-01", [h[1] for h in hits],
                         "archived decision no longer governs the file")


class TestCoversVia(GraphFixture):
    def test_via_names_exact_and_dir_citations(self):
        _write(os.path.join(self.root, "features/broad.md"),
               "---\nid: broad\nupdated: 2026-07-01\n---\n"
               "**Role:** Broad.\n**Code:** (see `src/orders/`).\n")
        hits = self.mod.cmd_covers(self.root, "src/orders/OrderManager.java")
        via = {h[1]: h[3] for h in hits}
        self.assertEqual(via["order-engine"], "exact")
        self.assertEqual(via["broad"], "dir src/orders/")
        self.assertEqual(hits[0][1], "order-engine", "exact hits rank first")
        self.assertEqual(self.mod.format_covers_line(hits[-1]),
                         "feature broad [dir src/orders/] — Broad.")

    def test_via_names_class_and_tag(self):
        self._set_config({"class-file-extensions": [".java"]})
        _write(os.path.join(self.root, "features/by-class.md"),
               "---\nid: by-class\nupdated: 2026-07-01\n---\n"
               "**Role:** Names the class.\n**Code:** `OrderManager`.\n")
        exts = self.mod.class_file_extensions(self.mod.load_config(self.root))
        hits = self.mod.cmd_covers(self.root, "src/orders/OrderManager.java", exts)
        via = {h[1]: h[3] for h in hits}
        self.assertEqual(via["by-class"], "class OrderManager")
        self.assertEqual(via["D-2026-07-11-02"], "tag ordermanager")

    def test_rank_is_exact_then_class_then_dir_then_tag(self):
        # A class hit names the file itself: it must beat every `dir` hit
        # (deep or broad), or the note's cap crowds it out — measured on a host.
        self._set_config({"class-file-extensions": [".java"]})
        _write(os.path.join(self.root, "features/aaa-dir-deep.md"),
               "---\nid: aaa-dir-deep\nupdated: 2026-07-01\n---\n"
               "**Role:** Deep dir.\n**Code:** `src/orders/`.\n")
        _write(os.path.join(self.root, "features/aaa-dir-broad.md"),
               "---\nid: aaa-dir-broad\nupdated: 2026-07-01\n---\n"
               "**Role:** Broad dir.\n**Code:** `src/`.\n")
        _write(os.path.join(self.root, "features/zzz-class.md"),
               "---\nid: zzz-class\nupdated: 2026-07-01\n---\n"
               "**Role:** Names the class.\n**Code:** `OrderManager`.\n")
        exts = self.mod.class_file_extensions(self.mod.load_config(self.root))
        hits = self.mod.cmd_covers(self.root, "src/orders/OrderManager.java", exts)
        self.assertEqual([(h[1], h[3]) for h in hits], [
            ("order-engine", "exact"),
            ("zzz-class", "class OrderManager"),
            ("aaa-dir-deep", "dir src/orders/"),
            ("aaa-dir-broad", "dir src/"),
            ("D-2026-07-11-02", "tag ordermanager"),
        ])
        # The hook note keeps the same order under its cap.
        root_abs = os.path.abspath(self.root).replace("\\", "/")
        note, _ = self.mod.build_covers_note(
            self.root, root_abs, {"file_path": "src/orders/OrderManager.java"}, exts)
        bullets = [l for l in note.split("\n") if l.startswith("- ")]
        self.assertEqual(bullets[1], "- feature zzz-class [class OrderManager] — Names the class.")

    def test_hook_note_shows_the_reason(self):
        root_abs = os.path.abspath(self.root).replace("\\", "/")
        note, _ = self.mod.build_covers_note(
            self.root, root_abs, {"file_path": "src/orders/OrderManager.java"}, set())
        self.assertIn("- feature order-engine [exact] — Drives checkout resolution.", note)


class TestRecipes(GraphFixture):
    def setUp(self):
        super().setUp()
        _write(os.path.join(self.root, ".claude/skills/pay/SKILL.md"),
               "---\nname: pay\ndescription: >-\n  Teaches the payment call. Long tail.\n---\n"
               "# Pay\nCall `src/pay/OldGateway.java` then `Ledger`.\n")
        _write(os.path.join(self.root, ".claude/rules/naming.md"),
               "# Naming rule\nSee `src/pay/`.\n")

    def test_recipe_absent_by_default(self):
        hits = self.mod.cmd_covers(self.root, "src/pay/OldGateway.java")
        self.assertEqual(hits, [], "recipe-dirs unset → recipes are not read")

    def test_recipe_found_by_covers(self):
        self._set_config({"recipe-dirs": [".claude/skills", ".claude/rules/"]})
        hits = self.mod.cmd_covers(self.root, "src/pay/OldGateway.java")
        self.assertEqual(hits, [
            ("recipe", ".claude/skills/pay/SKILL.md", "Teaches the payment call.", "exact"),
            ("recipe", ".claude/rules/naming.md", "Naming rule", "dir src/pay/"),
        ])

    def test_recipe_class_correspondence_mirrors_features(self):
        self._set_config({"recipe-dirs": [".claude/skills"], "class-file-extensions": [".java"]})
        exts = self.mod.class_file_extensions(self.mod.load_config(self.root))
        hits = self.mod.cmd_covers(self.root, "lib/Ledger.java", exts)
        self.assertEqual([(h[1], h[3]) for h in hits],
                         [(".claude/skills/pay/SKILL.md", "class Ledger")])

    def test_recipe_excluded_from_doctor(self):
        _write(os.path.join(self.root, "backlog/refacto-x/design.md"), "# design\n")
        _write(os.path.join(self.root, "src/orders/OrderManager.java"), "x")
        _write(os.path.join(self.root, "src/orders/TaxCalculator.java"), "x")
        self._set_config({"recipe-dirs": [".claude/skills"]})
        self.assertEqual(self.mod.cmd_doctor(self.root), [],
                         "a recipe's dead example path is doc-refs' job, not doctor's")

    def test_recipe_dir_self_suppresses_and_match_reads_titles(self):
        self._set_config({"recipe-dirs": [".claude/skills"]})
        self_dirs, self_files = self.mod.resolve_self(self.mod.load_config(self.root))
        self.assertTrue(self.mod.is_self_path(".claude/skills/pay/SKILL.md", self_dirs, self_files))
        ids = [r[1] for r in self.mod.cmd_match(self.root, ["payment"])]
        self.assertEqual(ids, [".claude/skills/pay/SKILL.md"])
        self.assertEqual(self.mod.cmd_match(self.root, ["skills"]), [],
                         "a recipe's id (its path) is not matched")

    def test_missing_recipe_dir_is_a_config_error_never_a_crash(self):
        self._set_config({"recipe-dirs": [".claude/skills", "nope/"]})
        errs = self.mod.config_errors(self.root)
        self.assertEqual(len(errs), 1)
        self.assertIn("nope", errs[0])
        # the existing dir still works; the graph never raises
        self.assertTrue(self.mod.cmd_covers(self.root, "src/pay/OldGateway.java"))


class TestMinDirDepth(GraphFixture):
    TARGET = "src/a/b/c/Deep.java"

    def setUp(self):
        super().setUp()
        _write(os.path.join(self.root, "features/root-dir.md"),
               "---\nid: root-dir\nupdated: 2026-07-01\n---\n**Role:** R.\n**Code:** `src/`.\n")
        _write(os.path.join(self.root, "features/three-dir.md"),
               "---\nid: three-dir\nupdated: 2026-07-01\n---\n**Role:** T.\n**Code:** `src/a/b/`.\n")
        _write(os.path.join(self.root, "features/four-dir.md"),
               "---\nid: four-dir\nupdated: 2026-07-01\n---\n**Role:** F.\n**Code:** `src/a/b/c/`.\n")
        _write(os.path.join(self.root, "features/exact.md"),
               "---\nid: exact\nupdated: 2026-07-01\n---\n**Role:** E.\n"
               "**Code:** `src/a/b/c/Deep.java`, `src/`.\n")
        _write(os.path.join(self.root, "features/by-class.md"),
               "---\nid: by-class\nupdated: 2026-07-01\n---\n**Role:** C.\n**Code:** `Deep`, `src/`.\n")

    def _ids(self, exts=None):
        return [(h[1], h[3]) for h in self.mod.cmd_covers(self.root, self.TARGET, exts)]

    def test_default_keeps_every_dir_hit(self):
        self.assertIn(("root-dir", "dir src/"), self._ids())
        self.assertIn(("three-dir", "dir src/a/b/"), self._ids())

    def test_cuts_shallow_dirs_keeps_deep_exact_and_class(self):
        self._set_config({"min-dir-depth": 4, "class-file-extensions": [".java"]})
        exts = self.mod.class_file_extensions(self.mod.load_config(self.root))
        self.assertEqual(self._ids(exts), [
            ("exact", "exact"),
            ("by-class", "class Deep"),
            ("four-dir", "dir src/a/b/c/"),
        ])
        # The hook note follows the same filter.
        root_abs = os.path.abspath(self.root).replace("\\", "/")
        note, _ = self.mod.build_covers_note(self.root, root_abs, {"file_path": self.TARGET}, exts)
        self.assertNotIn("three-dir", note)
        self.assertNotIn("root-dir", note)

    def test_shallow_exact_citation_is_never_cut(self):
        # An exact citation shallower than N is a file named outright, not a
        # broad folder — the threshold only ever applies to dir hits.
        self._set_config({"min-dir-depth": 4})
        hits = self.mod.cmd_covers(self.root, "src/orders/OrderManager.java")
        self.assertEqual([(h[1], h[3]) for h in hits], [("order-engine", "exact")])

    def test_doctor_and_neighbors_unchanged(self):
        self._set_config({"min-dir-depth": 4})
        self.assertIn(("root-dir", "src/"),
                      [(d[0], d[2]) for d in self.mod.cmd_doctor(self.root)],
                      "a short dir citation is still checked by doctor")
        self.assertIn(("cite-path", "src/a/b/", ""),
                      self.mod.cmd_neighbors(self.root, "three-dir"))

    def test_bad_value_is_a_config_error(self):
        for bad in (-1, "4", 2.5, True):
            self._set_config({"min-dir-depth": bad})
            self.assertEqual(len(self.mod.config_errors(self.root)), 1, bad)
            self.assertIn(("root-dir", "dir src/"), self._ids(), "bad value → off, never a crash")


class TestDecisionBodyPaths(GraphFixture):
    def setUp(self):
        super().setUp()
        _write(os.path.join(self.root, "decisions/D-2026-07-11-02.md"),
               "---\nid: D-2026-07-11-02\nstatus: active\nupdated: 2026-07-11\n"
               "replaces: [D-2026-01-01-01]\n---\n**Decision** governs `src/clock/Tick.java`.\n")
        _write(os.path.join(self.root, "decisions/D-2026-01-01-01.md"),
               "---\nid: D-2026-01-01-01\nstatus: archived\nupdated: 2026-01-01\n"
               "replaced-by: D-2026-07-11-02\n---\n**Decision** governs `src/clock/Tick.java`.\n")

    def test_off_by_default(self):
        self.assertEqual(self.mod.cmd_covers(self.root, "src/clock/Tick.java"), [])

    def test_on_counts_active_decisions_only(self):
        self._set_config({"decision-body-paths": True})
        hits = self.mod.cmd_covers(self.root, "src/clock/Tick.java")
        self.assertEqual([(h[1], h[3]) for h in hits], [("D-2026-07-11-02", "exact")])
        self.assertNotIn("D-2026-07-11-02", [d[0] for d in self.mod.cmd_doctor(self.root)],
                         "a decision's body citation never feeds doctor")


class TestBacklogCode(GraphFixture):
    """`code:` in a STATE.md — the code paths where a work item declares a limit."""

    def setUp(self):
        super().setUp()
        _write(os.path.join(self.root, "backlog/refacto-x/design.md"), "# design\n")
        _write(os.path.join(self.root, "src/orders/OrderManager.java"), "class OrderManager {}")
        _write(os.path.join(self.root, "src/orders/TaxCalculator.java"), "class TaxCalculator {}")

    def _state(self, code_line):
        _write(os.path.join(self.root, "backlog/limits/STATE.md"),
               "---\nid: limits\ntitle: Declares a limit\nstatus: in-progress\nafter: []\n"
               "docs: []\n%s\nupdated: 2026-10-07\n---\n## Tasks\n- [todo] x\n" % code_line)

    def test_covers_surfaces_the_work_item_declaring_a_limit_in_the_file(self):
        # Without `code:`, a work item cites only its own docs: covers on the
        # code file it declares a limit in stays silent on it.
        self._state("code: []")
        self.assertNotIn("limits", [h[1] for h in self.mod.cmd_covers(
            self.root, "src/orders/TaxCalculator.java")])
        self._state("code: [src/orders/TaxCalculator.java, ./src/billing/]")
        hits = self.mod.cmd_covers(self.root, "src/orders/TaxCalculator.java")
        self.assertIn(("limits", "exact"), [(h[1], h[3]) for h in hits])
        # Taken as written, never colocated under backlog/<id>/ like `docs:`;
        # a leading `./` is dropped, a directory covers its subtree.
        hits = self.mod.cmd_covers(self.root, "src/billing/Invoice.java")
        self.assertEqual([(h[1], h[3]) for h in hits], [("limits", "dir src/billing/")])

    def test_doctor_checks_code_paths_and_reports_escapes(self):
        self._state("code: [src/orders/TaxCalculator.java, src/gone/Old.java, ../outside.java]")
        dead = sorted((d[0], d[2]) for d in self.mod.cmd_doctor(self.root))
        self.assertEqual(dead, [("limits", "../outside.java"), ("limits", "src/gone/Old.java")])
        # The escape never became an edge — covers cannot follow it.
        self.assertNotIn("../outside.java", self.mod.load_graph(self.root)[0]["limits"]["cites"])


class TestMultiPath(GraphFixture):
    def test_grouped_report_and_visible_silence(self):
        lines = self.mod.covers_report(
            self.root, ["src/orders/OrderManager.java", "src/x/A.java", "src/y/B.java"],
            set(), grouped=True)
        self.assertEqual(lines, [
            "src/orders/OrderManager.java:",
            "  feature order-engine [exact] — Drives checkout resolution.",
            "no memory cites: src/x/A.java, src/y/B.java",
        ])

    def test_single_path_keeps_the_flat_output(self):
        self.assertEqual(
            self.mod.covers_report(self.root, ["src/orders/OrderManager.java"], set(), grouped=False),
            ["feature order-engine [exact] — Drives checkout resolution."])
        self.assertEqual(self.mod.covers_report(self.root, ["src/x/A.java"], set(), grouped=False), [])

    def test_diff_collects_committed_uncommitted_deleted_and_untracked(self):
        import subprocess
        env = self.mod._git_env()
        env.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})

        def git(*a):
            subprocess.run(["git"] + list(a), cwd=self.root, env=env, check=True,
                           capture_output=True)
        git("init", "-q")
        for name in ("keep", "gone", "edit", "moved"):
            _write(os.path.join(self.root, "src/%s.txt" % name), "content of %s\n" % name)
        git("add", "-A")
        git("commit", "-q", "-m", "base")
        git("tag", "base")
        _write(os.path.join(self.root, "src/committed.txt"), "a")
        git("add", "src/committed.txt")
        git("mv", "src/moved.txt", "src/renamed.txt")
        git("commit", "-q", "-m", "work")                        # committed + rename
        os.remove(os.path.join(self.root, "src/gone.txt"))       # deleted, unstaged
        _write(os.path.join(self.root, "src/edit.txt"), "b")    # modified, unstaged
        _write(os.path.join(self.root, "src/staged.txt"), "a")
        git("add", "src/staged.txt")                             # staged
        _write(os.path.join(self.root, "src/new.txt"), "a")     # untracked
        root_abs = os.path.abspath(self.root).replace("\\", "/")
        got = [self.mod.norm_path(p, root_abs) for p in self.mod.diff_paths(self.root, "base")]
        self.assertEqual(sorted(p for p in got if p.startswith("src/")),
                         ["src/committed.txt", "src/edit.txt", "src/gone.txt", "src/moved.txt",
                          "src/new.txt", "src/renamed.txt", "src/staged.txt"])
        self.assertEqual(len(got), len(set(got)), "deduped")
        with self.assertRaises(RuntimeError):
            self.mod.diff_paths(self.root, "no-such-ref")


class TestMatch(GraphFixture):
    def test_living_memory_wins_ties(self):
        # Both decisions share the 'order' term; the active one must rank first.
        results = self.mod.cmd_match(self.root, ["order"])
        ids = [r[1] for r in results]
        self.assertLess(ids.index("D-2026-07-11-02"), ids.index("D-2026-01-01-01"))

    def test_short_terms_ignored(self):
        self.assertEqual(self.mod.cmd_match(self.root, ["fx", "vol"]), [])


class TestNeighbors(GraphFixture):
    def test_incoming_and_outgoing_edges(self):
        result = self.mod.cmd_neighbors(self.root, "D-2026-07-11-02")
        types = {(e[0], e[1]) for e in result}
        self.assertIn(("links", "order-engine"), types)        # incoming from feature
        self.assertIn(("replaces", "D-2026-01-01-01"), types)   # outgoing


class TestAmbiguityGuard(GraphFixture):
    def setUp(self):
        super().setUp()
        _write(os.path.join(self.root, "index/index-config.json"),
               json.dumps({"roots": ["src/"], "extensions": [".java"]}))
        self._set_config({"class-file-extensions": [".java"]})
        self.exts = self.mod.class_file_extensions(self.mod.load_config(self.root))
        # A feature citing both the class `OrderManager` and the path.
        _write(os.path.join(self.root, "features/order-engine.md"),
               "---\nid: order-engine\ncreated: 2026-07-01\nupdated: 2026-07-11\n---\n"
               "**Role:** Drives checkout.\n**Code:** `OrderManager` at `src/orders/OrderManager.java`.\n")
        os.makedirs(os.path.join(self.root, "src/orders"), exist_ok=True)
        open(os.path.join(self.root, "src/orders/OrderManager.java"), "w").close()

    def test_unique_basename_keeps_class_hit(self):
        hits = self.mod.cmd_covers(self.root, "src/orders/OrderManager.java", self.exts)
        self.assertIn("order-engine", [h[1] for h in hits])

    def test_duplicate_basename_drops_class_and_tag_hits(self):
        # A second OrderManager.java elsewhere makes the basename ambiguous.
        os.makedirs(os.path.join(self.root, "src/other"), exist_ok=True)
        open(os.path.join(self.root, "src/other/OrderManager.java"), "w").close()
        hits = self.mod.cmd_covers(self.root, "src/orders/OrderManager.java", self.exts)
        ids = [h[1] for h in hits]
        # The path-containment hit (correspondence #1) survives; the class/tag
        # correspondences are dropped as unsafe.
        self.assertIn("order-engine", ids)  # kept via cite-path, not via class
        self.assertNotIn("D-2026-07-11-02", ids)


class TestPrefilterCache(GraphFixture):
    def test_path_chain_reproduces_containment(self):
        self.assertEqual(self.mod._path_chain("a/b/c"), ["a/b/c", "a/b", "a"])

    def test_compute_sets_and_might_cover(self):
        nodes, _ = self.mod.load_graph(self.root)
        cache = self.mod.compute_prefilter_sets(nodes)
        # A cited file is in prefixes; an unrelated sibling is ruled out.
        self.assertTrue(self.mod.prefilter_might_cover("src/orders/OrderManager.java", "", "", cache))
        self.assertFalse(self.mod.prefilter_might_cover("src/orders/Unrelated.java", "", "", cache))

    def test_prefiltered_skips_and_writes_cache(self):
        cache_path = os.path.join(self.root, "cache.json")
        note, key = self.mod.build_covers_note_prefiltered(
            self.root, os.path.abspath(self.root),
            {"file_path": os.path.join(self.root, "src/orders/Unrelated.java")}, set(), cache_path)
        self.assertEqual((note, key), ("", ""))
        self.assertTrue(os.path.isfile(cache_path), "an uncovered first call still primes the cache")

    def test_prefiltered_self_path_invalidates_cache(self):
        cache_path = os.path.join(self.root, "cache.json")
        _write(cache_path, json.dumps({"prefixes": [], "classes": [], "tags": []}))
        self.mod.build_covers_note_prefiltered(
            self.root, os.path.abspath(self.root),
            {"file_path": os.path.join(self.root, "decisions/D-2026-07-11-02.md")}, set(), cache_path)
        self.assertFalse(os.path.isfile(cache_path), "editing a channel file drops the stale cache")

    def test_corrupt_cache_falls_back_to_parse(self):
        self.assertIsNone(self.mod.load_prefilter_cache("/nonexistent/path.json"))
        cache_path = os.path.join(self.root, "bad.json")
        _write(cache_path, "{ not json")
        self.assertIsNone(self.mod.load_prefilter_cache(cache_path))
        _write(cache_path, json.dumps({"prefixes": []}))  # missing keys
        self.assertIsNone(self.mod.load_prefilter_cache(cache_path))


class TestExtractPaths(unittest.TestCase):
    def setUp(self):
        self.mod = _load_module()

    def test_section_anchor_is_truncated(self):
        # A cited path with a §-anchor (whose own text can contain a `/`) must
        # resolve to the bare file, not the whole span.
        got = self.mod.extract_paths("see `Docs/architecture/spec.md §14/§15` and `src/a/B.java`")
        self.assertIn("Docs/architecture/spec.md", got)
        self.assertIn("src/a/B.java", got)
        self.assertNotIn("Docs/architecture/spec.md §14/§15", got)

    def test_space_in_directory_name_is_kept(self):
        # The cut is on " §" only — a legitimate space in a dir name survives.
        got = self.mod.extract_paths("`assets/ui/My Folder/icon.png`")
        self.assertIn("assets/ui/My Folder/icon.png", got)


class TestClassExtraction(unittest.TestCase):
    def setUp(self):
        self.mod = _load_module()

    def test_extension_stripped_but_member_not_treated_as_class(self):
        body = ("`AuthGuard`, `OrderManager.java`, `Invoice.RefreshTotals`, "
                "`Foo.OnClick`, `parse.py`")
        classes = self.mod.extract_classes(body)
        self.assertIn("AuthGuard", classes)       # bare identifier
        self.assertIn("OrderManager", classes)    # file extension stripped
        self.assertIn("parse", classes)           # lowercase extension too
        self.assertNotIn("Invoice", classes)      # member ref, not a class citation
        self.assertNotIn("Foo", classes)


class TestChannelsBase(unittest.TestCase):
    """Channels nested under a subdir (channels-base), e.g. a project keeping
    its memory under a Docs/ subtree (Docs/decisions/…)."""

    def setUp(self):
        self.mod = _load_module()
        self.root = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.root, ignore_errors=True))
        _write(os.path.join(self.root, "checks-config.json"),
               json.dumps({"memory-graph": {"channels-base": "Docs", "self-extra-dirs": [".claude"]}}))
        _write(os.path.join(self.root, "Docs/features/f.md"),
               "---\nid: f\ncreated: 2026-07-01\nupdated: 2026-07-11\n---\n"
               "**Role:** Owner.\n**Code:** `src/Widget.java`.\n")
        _write(os.path.join(self.root, "Docs/decisions/INDEX.md"),
               "# Decisions\n## Active\n- [D-2026-07-11-02](D-2026-07-11-02.md) — x · y.\n")
        _write(os.path.join(self.root, "Docs/decisions/D-2026-07-11-02.md"),
               "---\nid: D-2026-07-11-02\nstatus: active\nupdated: 2026-07-11\n---\n**Decision**\n")

    def test_graph_finds_nested_channels(self):
        nodes, _ = self.mod.load_graph(self.root)
        self.assertIn("f", nodes)
        self.assertIn("D-2026-07-11-02", nodes)
        self.assertEqual(nodes["f"]["path"], "Docs/features/f.md")

    def test_covers_resolves_under_base(self):
        hits = self.mod.cmd_covers(self.root, "src/Widget.java")
        self.assertIn("f", [h[1] for h in hits])

    def test_self_suppression_follows_base_and_extra_dirs(self):
        self_dirs, self_files = self.mod.resolve_self(self.mod.load_config(self.root))
        self.assertIn("Docs/decisions", self_dirs)
        self.assertIn(".claude", self_dirs)             # from self-extra-dirs
        self.assertIn("Docs/FEATURE_MAP.md", self_files)
        self.assertTrue(self.mod.is_self_path("Docs/decisions/D-1.md", self_dirs, self_files))
        self.assertFalse(self.mod.is_self_path("src/Widget.java", self_dirs, self_files))


class TestHookAdapter(GraphFixture):
    def test_self_suppression_on_channel_file(self):
        note, key = self.mod.build_covers_note(
            self.root, os.path.abspath(self.root),
            {"file_path": os.path.join(self.root, "decisions/D-2026-07-11-02.md")}, set())
        self.assertEqual((note, key), ("", ""))

    def test_covers_note_shape(self):
        note, key = self.mod.build_covers_note(
            self.root, os.path.abspath(self.root),
            {"file_path": os.path.join(self.root, "src/orders/TaxCalculator.java")}, set())
        self.assertTrue(note.startswith("[memory-graph] Memory covering"))
        self.assertEqual(key, "src/orders/TaxCalculator.java")


if __name__ == "__main__":
    unittest.main()
