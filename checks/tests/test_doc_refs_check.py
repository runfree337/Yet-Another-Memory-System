# tests/test_doc_refs_check.py
#
# Regression tests for the three optional, additive symbol-rule tunings under `doc-refs`
# (proposal oc-refs — making R-DEAD-SYMBOL configurable). The invariant that must never
# re-break: ABSENT config == today's behavior, and each key only ever NARROWS the symbol
# rules (R-DEAD-SYMBOL / R-GHOST-ABSENCE) while leaving R-DEAD-PATH / R-DEAD-DECISION
# untouched.
#   - symbol-suffixes    : when non-empty, keep only candidates ending in a declared suffix.
#   - ignore-symbols     : literal candidate exclusions (host API), additive not substitutive.
#   - symbol-ignore-dirs : mute the two symbol rules on given doc dirs; paths stay checked.
#   - ghost-exclude-patterns : per-project grammar-as-data regexes suppressing R-GHOST-ABSENCE
#     on the segments they match (the container-problem) — suppressive only, never additive.
#   - `<!-- doc-refs: ignore -->` pragma : silences every rule on its own line, that line only.
import importlib.util
import os
import re
import shutil
import tempfile
import unittest

CHECKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_module():
    """doc-refs-check.py has a hyphen — not importable by name; load it by path."""
    path = os.path.join(CHECKS_DIR, "doc-refs-check.py")
    spec = importlib.util.spec_from_file_location("doc_refs_check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SymbolTuningBase(unittest.TestCase):
    def setUp(self):
        # Fresh module each test → pristine module-level config globals.
        self.mod = _load_module()
        # Active, deterministic corpus: FooManager exists, the host-API names do not.
        self.mod._CODE_CORPUS = "public class FooManager {}\nclass BarView {}\n"
        # No git: pre-seed the history cache so R-DEAD-PATH never shells out.
        self.mod._HISTORICAL_PATHS = set()
        # A controlled framework root so `symbol-ignore-dirs` relpaths are predictable.
        self.fw = tempfile.mkdtemp()
        self.mod.FRAMEWORK = self.fw
        self.addCleanup(lambda: shutil.rmtree(self.fw, ignore_errors=True))

    def _scan(self, body, *, suffixes=(), ignore=(), ignore_dirs=(), subdir=""):
        """Write `body` to <framework>/<subdir>/doc.md, apply config, return its findings."""
        self.mod.SYMBOL_SUFFIXES = tuple(suffixes)
        self.mod.IGNORE_SYMBOLS = frozenset(ignore)
        self.mod.SYMBOL_IGNORE_DIRS = tuple(ignore_dirs)
        d = os.path.join(self.fw, subdir) if subdir else self.fw
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "doc.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        return self.mod.scan_file(path)

    def _rules(self, body, **kw):
        return {f[3] for f in self._scan(body, **kw)}

    def _symbols(self, body, **kw):
        return {f[4].split(": ")[-1] for f in self._scan(body, **kw)
                if f[3] == "R-DEAD-SYMBOL"}


class TestDefaultUnchanged(SymbolTuningBase):
    def test_absent_config_flags_every_composed_pascalcase(self):
        # No config → today's behavior: a composed PascalCase symbol absent from the corpus
        # is flagged R-DEAD-SYMBOL, host-API name or not.
        self.assertIn("R-DEAD-SYMBOL",
                      self._rules("The `MonoBehaviour` lifecycle drives `MissingWidget`."))


class TestSymbolSuffixes(SymbolTuningBase):
    def test_nonsuffixed_missing_symbol_not_flagged(self):
        # `MonoBehaviour` doesn't end in a declared suffix → never a candidate → no finding.
        self.assertNotIn("R-DEAD-SYMBOL",
                         self._rules("The `MonoBehaviour` base class is everywhere.",
                                     suffixes=["Manager", "View", "Registry"]))

    def test_suffixed_missing_symbol_still_flagged(self):
        # `GhostManager` matches a declared suffix and is absent from the corpus → flagged.
        self.assertIn("R-DEAD-SYMBOL",
                      self._rules("See `GhostManager` for the wiring.",
                                  suffixes=["Manager", "View"]))

    def test_suffixed_present_symbol_not_flagged(self):
        # `FooManager` matches the suffix AND exists in the corpus → alive, no finding.
        self.assertNotIn("R-DEAD-SYMBOL",
                         self._rules("See `FooManager` for the wiring.", suffixes=["Manager"]))


class TestIgnoreSymbols(SymbolTuningBase):
    def test_listed_symbol_dropped_others_still_flagged(self):
        # Additive: `MonoBehaviour` silenced literally, `MissingThing` still flagged.
        syms = self._symbols("`MonoBehaviour` drives `MissingThing`.",
                             ignore=["MonoBehaviour"])
        self.assertNotIn("MonoBehaviour", syms)
        self.assertIn("MissingThing", syms)


class TestSymbolIgnoreDirs(SymbolTuningBase):
    def test_muted_dir_silences_symbol_but_not_path(self):
        # Under a muted dir: R-DEAD-SYMBOL silenced, but a dead path on the same line stays
        # flagged — R-DEAD-PATH keeps running there.
        # Wording avoids NEG words (which would suppress R-DEAD-PATH) so the assertion
        # isolates the mute: only R-DEAD-SYMBOL is silenced by the dir, the path is not.
        rules = self._rules("The `GhostManager` reads `nowhere/ghost_file.py`.",
                            suffixes=["Manager"], ignore_dirs=["backlog"], subdir="backlog")
        self.assertNotIn("R-DEAD-SYMBOL", rules)
        self.assertIn("R-DEAD-PATH", rules)

    def test_non_muted_dir_still_flags_symbol(self):
        rules = self._rules("See `GhostManager` for the plan.",
                            suffixes=["Manager"], ignore_dirs=["backlog"], subdir="architecture")
        self.assertIn("R-DEAD-SYMBOL", rules)


class TestXxxTemplate(SymbolTuningBase):
    def test_xxx_placeholder_not_flagged(self):
        # `CampJournalXxxTab` / `XxxDetailView` are fill-in-the-blank names, not real symbols:
        # the `Xxx` placeholder (like the built-in `XXXX`) makes them template → never flagged.
        rules = self._rules("Tabs `CampJournalXxxTab`, `XxxDetailView`, `XxxEntryView`.")
        self.assertNotIn("R-DEAD-SYMBOL", rules)

    def test_real_symbol_without_xxx_still_flagged(self):
        # Control: a composed name with no `Xxx` and absent from the corpus is still flagged.
        self.assertIn("R-DEAD-SYMBOL", self._rules("See `MissingWidget` here."))


class TestNegWords(SymbolTuningBase):
    def _with_neg(self, *extra):
        """Rebuild NEG_RE with project-language words, mirroring the script's config path."""
        self.mod.NEG_RE = re.compile(
            "|".join(re.escape(w) for w in self.mod.NEG + tuple(w.lower() for w in extra)))

    def test_french_negation_suppresses_dead_symbol(self):
        # `IAudioProvider` is absent from the corpus; the prose says `pas d'IAudioProvider`
        # (there is none) — with the French word taught, R-DEAD-SYMBOL is suppressed as redundant.
        self._with_neg("pas d'", "non retenue")
        self.assertNotIn("R-DEAD-SYMBOL",
                         self._rules("il n'y a pas d'`IAudioProvider` dans ce build"))
        self.assertNotIn("R-DEAD-SYMBOL",
                         self._rules("Proposition NON RETENUE : `GhostThing`"))

    def test_without_neg_word_still_flagged(self):
        # Control: the same absent symbol on a neutral line is still flagged (default NEG).
        self.assertIn("R-DEAD-SYMBOL", self._rules("le module `IAudioProvider` gère le son"))


class TestGhostAbsenceProximity(SymbolTuningBase):
    # `FooManager` exists in the corpus (SymbolTuningBase). R-GHOST-ABSENCE must fire only
    # when a ghost word shares a SEGMENT with it, not merely the line.
    def test_same_segment_flags(self):
        self.assertIn("R-GHOST-ABSENCE",
                      self._rules("le `FooManager` n'est pas encore câblé"))

    def test_table_cells_do_not_flag(self):
        # ghost word in one markdown cell, symbol in another → not a claim about the symbol.
        self.assertNotIn("R-GHOST-ABSENCE",
                         self._rules("| à créer plus tard | `FooManager` ailleurs |"))

    def test_separate_sentences_do_not_flag(self):
        self.assertNotIn("R-GHOST-ABSENCE",
                         self._rules("Rien à créer ici. `FooManager` existe déjà."))

    def test_semicolon_splits(self):
        self.assertNotIn("R-GHOST-ABSENCE",
                         self._rules("à créer bientôt ; `FooManager` est là"))

    def test_colon_does_not_split(self):
        # `:` is a label separator, not a clause break — `absent : Foo` is a real claim.
        self.assertIn("R-GHOST-ABSENCE",
                      self._rules("absent : `FooManager` reste à faire"))

    def test_comma_does_not_split(self):
        self.assertIn("R-GHOST-ABSENCE",
                      self._rules("le `FooManager`, pas encore câblé proprement"))


class TestGhostExcludePatterns(SymbolTuningBase):
    # `FooManager` exists in the corpus. `ghost-exclude-patterns` is the per-project home for
    # the grammar the segment split cannot reach — a ghost word bound to a NEIGHBOURING noun,
    # the symbol being only its container. Purely suppressive: a pattern removes findings on
    # the segments it matches, never adds one, and never reaches past its own segment.
    FR_CONTAINER = r"(absente?s?|manquante?s?)[^`;|]*\b(du|de la|des|dans) `"

    def _with_patterns(self, *pats):
        self.mod.GHOST_EXCLUDE = tuple(re.compile(p, re.IGNORECASE) for p in pats)

    def test_container_shape_suppressed(self):
        # The icon is absent, not the registry — the declared shape silences the segment.
        self._with_patterns(self.FR_CONTAINER)
        self.assertNotIn("R-GHOST-ABSENCE",
                         self._rules("l'icône absente du `FooManager` sera livrée"))

    def test_genuine_claim_still_flagged(self):
        # Control: same config, but a real "doc says missing, code has it" still fires —
        # the ghost word is the symbol's own predicate, no container shape around it.
        self._with_patterns(self.FR_CONTAINER)
        self.assertIn("R-GHOST-ABSENCE",
                      self._rules("le `FooManager` est absent pour l'instant"))

    def test_suppression_is_per_segment(self):
        # `;` splits: the container shape silences only its own segment; the genuine claim
        # about `BarView` (also in the corpus) in the next segment still fires.
        self._with_patterns(self.FR_CONTAINER)
        ghosts = [f for f in self._scan(
            "icône absente du `FooManager` ; `BarView` pas encore câblé")
            if f[3] == "R-GHOST-ABSENCE"]
        self.assertEqual(len(ghosts), 1)
        self.assertIn("BarView", ghosts[0][4])

    def test_absent_config_unchanged(self):
        # No patterns declared → today's behavior: the container-problem line still fires.
        self.assertIn("R-GHOST-ABSENCE",
                      self._rules("l'icône absente du `FooManager` sera livrée"))


class TestIgnorePragma(SymbolTuningBase):
    def test_pragma_silences_all_rules_on_its_line(self):
        # Dead symbol + dead path on the marked line → nothing at all is reported.
        self.assertEqual(set(), self._rules(
            "The `GhostManager` reads `nowhere/ghost_file.py`. <!-- doc-refs: ignore -->"))

    def test_pragma_silences_ghost_too(self):
        self.assertNotIn("R-GHOST-ABSENCE", self._rules(
            "le `FooManager` n'est pas encore câblé <!-- doc-refs: ignore -->"))

    def test_pragma_scopes_to_its_own_line(self):
        # The same dead symbol on the next, unmarked line is still flagged.
        finds = self._scan("`MissingWidget` reviewed here. <!-- doc-refs: ignore -->\n"
                           "`MissingWidget` cited again here.")
        self.assertEqual([f[2] for f in finds if f[3] == "R-DEAD-SYMBOL"], [2])


if __name__ == "__main__":
    unittest.main()
