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
        # doctor must name exactly the dead one, with its citing node.
        _write(os.path.join(self.root, "src/orders/OrderManager.java"), "class OrderManager {}")
        dead = self.mod.cmd_doctor(self.root)
        self.assertEqual([(d[0], d[2]) for d in dead],
                         [("order-engine", "src/orders/TaxCalculator.java")])
        _write(os.path.join(self.root, "src/orders/TaxCalculator.java"), "class TaxCalculator {}")
        self.assertEqual(self.mod.cmd_doctor(self.root), [])

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
