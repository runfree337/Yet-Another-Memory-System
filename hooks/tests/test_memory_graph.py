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
            "- [D-2026-07-11-02](D-2026-07-11-02.md) — combat clock · [combatmanager] beats via StepDt.\n"
            "## Archived\n"
            "- [D-2026-01-01-01](D-2026-01-01-01.md) — old combat · [combatmanager] superseded by D-2026-07-11-02.\n"
        ))
        _write(os.path.join(self.root, "decisions/D-2026-07-11-02.md"),
               "---\nid: D-2026-07-11-02\nstatus: active\nupdated: 2026-07-11\n"
               "replaces: [D-2026-01-01-01]\n---\n**Decision** **Why** **Invariant**\n")
        _write(os.path.join(self.root, "decisions/D-2026-01-01-01.md"),
               "---\nid: D-2026-01-01-01\nstatus: archived\nupdated: 2026-01-01\n"
               "replaced-by: D-2026-07-11-02\n---\n**Decision** **Why** **Invariant**\n")
        _write(os.path.join(self.root, "features/combat-engine.md"),
               "---\nid: combat-engine\ncreated: 2026-07-01\nupdated: 2026-07-11\n"
               "links: [D-2026-07-11-02]\n---\n"
               "**Role:** Drives combat resolution.\n"
               "**Code:** `src/combat/CombatManager.cs`, `src/combat/StepClock.cs`.\n")
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
        hits = self.mod.cmd_covers(self.root, "src/combat/CombatManager.cs")
        ids = [h[1] for h in hits]
        self.assertIn("combat-engine", ids)
        self.assertNotIn("D-2026-07-11-02", ids, "class correspondence must be OFF without config")

    def test_directory_prefix_covers_subtree(self):
        # A fiche that cited `src/combat/CombatManager.cs` does NOT cover a
        # sibling file — containment is exact, never a substring/dir-guess.
        hits = self.mod.cmd_covers(self.root, "src/combat/Other.cs")
        self.assertEqual(hits, [])

    def test_class_extension_opt_in_adds_active_decision(self):
        self._set_config({"class-file-extensions": [".cs"]})
        exts = self.mod.class_file_extensions(self.mod.load_config(self.root))
        hits = self.mod.cmd_covers(self.root, "src/combat/CombatManager.cs", exts)
        ids = [h[1] for h in hits]
        self.assertIn("combat-engine", ids)          # #1 path
        self.assertIn("D-2026-07-11-02", ids)         # #3 active decision via tag

    def test_archived_decision_never_covers(self):
        self._set_config({"class-file-extensions": [".cs"]})
        exts = self.mod.class_file_extensions(self.mod.load_config(self.root))
        hits = self.mod.cmd_covers(self.root, "src/combat/CombatManager.cs", exts)
        self.assertNotIn("D-2026-01-01-01", [h[1] for h in hits],
                         "archived decision no longer governs the file")


class TestMatch(GraphFixture):
    def test_living_memory_wins_ties(self):
        # Both decisions share the 'combat' term; the active one must rank first.
        results = self.mod.cmd_match(self.root, ["combat"])
        ids = [r[1] for r in results]
        self.assertLess(ids.index("D-2026-07-11-02"), ids.index("D-2026-01-01-01"))

    def test_short_terms_ignored(self):
        self.assertEqual(self.mod.cmd_match(self.root, ["fx", "vol"]), [])


class TestNeighbors(GraphFixture):
    def test_incoming_and_outgoing_edges(self):
        result = self.mod.cmd_neighbors(self.root, "D-2026-07-11-02")
        types = {(e[0], e[1]) for e in result}
        self.assertIn(("links", "combat-engine"), types)        # incoming from feature
        self.assertIn(("replaces", "D-2026-01-01-01"), types)   # outgoing


class TestAmbiguityGuard(GraphFixture):
    def setUp(self):
        super().setUp()
        _write(os.path.join(self.root, "index/index-config.json"),
               json.dumps({"roots": ["src/"], "extensions": [".cs"]}))
        self._set_config({"class-file-extensions": [".cs"]})
        self.exts = self.mod.class_file_extensions(self.mod.load_config(self.root))
        # A feature citing both the class `CombatManager` and the path.
        _write(os.path.join(self.root, "features/combat-engine.md"),
               "---\nid: combat-engine\ncreated: 2026-07-01\nupdated: 2026-07-11\n---\n"
               "**Role:** Drives combat.\n**Code:** `CombatManager` at `src/combat/CombatManager.cs`.\n")
        os.makedirs(os.path.join(self.root, "src/combat"), exist_ok=True)
        open(os.path.join(self.root, "src/combat/CombatManager.cs"), "w").close()

    def test_unique_basename_keeps_class_hit(self):
        hits = self.mod.cmd_covers(self.root, "src/combat/CombatManager.cs", self.exts)
        self.assertIn("combat-engine", [h[1] for h in hits])

    def test_duplicate_basename_drops_class_and_tag_hits(self):
        # A second CombatManager.cs elsewhere makes the basename ambiguous.
        os.makedirs(os.path.join(self.root, "src/other"), exist_ok=True)
        open(os.path.join(self.root, "src/other/CombatManager.cs"), "w").close()
        hits = self.mod.cmd_covers(self.root, "src/combat/CombatManager.cs", self.exts)
        ids = [h[1] for h in hits]
        # The path-containment hit (correspondence #1) survives; the class/tag
        # correspondences are dropped as unsafe.
        self.assertIn("combat-engine", ids)  # kept via cite-path, not via class
        self.assertNotIn("D-2026-07-11-02", ids)


class TestPrefilterCache(GraphFixture):
    def test_path_chain_reproduces_containment(self):
        self.assertEqual(self.mod._path_chain("a/b/c"), ["a/b/c", "a/b", "a"])

    def test_compute_sets_and_might_cover(self):
        nodes, _ = self.mod.load_graph(self.root)
        cache = self.mod.compute_prefilter_sets(nodes)
        # A cited file is in prefixes; an unrelated sibling is ruled out.
        self.assertTrue(self.mod.prefilter_might_cover("src/combat/CombatManager.cs", "", "", cache))
        self.assertFalse(self.mod.prefilter_might_cover("src/combat/Unrelated.cs", "", "", cache))

    def test_prefiltered_skips_and_writes_cache(self):
        cache_path = os.path.join(self.root, "cache.json")
        note, key = self.mod.build_covers_note_prefiltered(
            self.root, os.path.abspath(self.root),
            {"file_path": os.path.join(self.root, "src/combat/Unrelated.cs")}, set(), cache_path)
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


class TestHookAdapter(GraphFixture):
    def test_self_suppression_on_channel_file(self):
        note, key = self.mod.build_covers_note(
            self.root, os.path.abspath(self.root),
            {"file_path": os.path.join(self.root, "decisions/D-2026-07-11-02.md")}, set())
        self.assertEqual((note, key), ("", ""))

    def test_covers_note_shape(self):
        note, key = self.mod.build_covers_note(
            self.root, os.path.abspath(self.root),
            {"file_path": os.path.join(self.root, "src/combat/StepClock.cs")}, set())
        self.assertTrue(note.startswith("[memory-graph] Memory covering"))
        self.assertEqual(key, "src/combat/StepClock.cs")


if __name__ == "__main__":
    unittest.main()
