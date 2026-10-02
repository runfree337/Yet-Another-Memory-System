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
        # Fresh module each test → module-level config globals seeded from the HOST repo's
        # `checks-config.json`, NOT from pristine defaults. They are only pristine in a repo
        # that configures nothing — which this one is, so the gap is invisible here and fires
        # in an adopting project. `_scan` already overwrites `SYMBOL_SUFFIXES` /
        # `IGNORE_SYMBOLS` / `SYMBOL_IGNORE_DIRS` on every call; `GHOST_EXCLUDE` had no such
        # reset, so a project declaring real `doc-refs.ghost-exclude-patterns` silenced the
        # very line the "absent config" tests assert on. Neutralize it here —
        # `_with_patterns` stays the only path that installs patterns.
        self.mod = _load_module()
        self.mod.GHOST_EXCLUDE = ()
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


class TestArrowContactExemption(SymbolTuningBase):
    """The arrows left NEG (line-level) and became a token-level contact exemption:
    only a target flanking an arrow — the "old → new" rename shape — is skipped."""

    def test_rename_shape_stays_exempt(self):
        # The exact pattern the old exemption was built for: both sides of the
        # arrow are dead paths, neither is flagged.
        finds = self._scan("moved: `old/dir/gone.py` → `new/dir/target.py`\n")
        self.assertEqual([f for f in finds if f[3] == "R-DEAD-PATH"], [])

    def test_ascii_arrow_rename_shape_stays_exempt(self):
        finds = self._scan("renommage : `old/dir/gone.py` -> `new/dir/target.py`\n")
        self.assertEqual([f for f in finds if f[3] == "R-DEAD-PATH"], [])

    def test_arrow_elsewhere_on_the_line_no_longer_disarms(self):
        # Routing punctuation: the arrow points at prose, the dead path sits
        # several words away — the line-level exemption used to swallow this.
        finds = self._scan("Le chemin `dead/path/nowhere.py` est décrit là : "
                           "modèle complet → la doc d'architecture\n")
        self.assertIn("R-DEAD-PATH", {f[3] for f in finds})

    def test_dead_symbol_far_from_arrow_is_flagged(self):
        # Same contract for R-DEAD-SYMBOL: contact exempts, distance doesn't.
        self.assertIn("R-DEAD-SYMBOL",
                      self._rules("`GhostThing` gère le rendu ; détail → la doc\n"))
        self.assertNotIn("R-DEAD-SYMBOL",
                         self._rules("`GhostThing` → `FooManager`\n"))

    def test_neg_words_can_restore_line_level_arrows(self):
        # A project that wants the old behavior re-adds the arrows via
        # `doc-refs.neg-words` (additive) — the escape hatch stays open.
        self.mod.NEG_RE = re.compile(
            "|".join(re.escape(w) for w in self.mod.NEG + ("→", "->")))
        finds = self._scan("Le chemin `dead/path/nowhere.py` est décrit là : "
                           "modèle complet → la doc d'architecture\n")
        self.assertEqual([f for f in finds if f[3] == "R-DEAD-PATH"], [])


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


class TestDedicatedCodeKeys(SymbolTuningBase):
    # `doc-refs.code-roots`/`code-extensions` decouple the symbol-rule corpus from
    # index-check's `index/index-config.json` (whose `base` semantics differ when the
    # framework is nested, and whose mere presence wakes index-check up). Roots resolve
    # from the REPO root; absent keys ⇒ fallback on index-config, today's behavior.
    def _repo_with_code(self):
        repo = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(repo, ignore_errors=True))
        os.makedirs(os.path.join(repo, "Src"))
        with open(os.path.join(repo, "Src", "a.cs"), "w", encoding="utf-8") as fh:
            fh.write("public class KeyedManager {}\n")
        return repo

    def test_dedicated_keys_feed_the_corpus(self):
        # No index-config.json anywhere: the dedicated keys alone activate the rules.
        self.mod.REPO = self._repo_with_code()
        self.mod.CODE_ROOTS, self.mod.CODE_EXTENSIONS = ("Src",), (".cs",)
        self.mod._CODE_CORPUS = None  # drop the corpus pre-seeded by setUp
        self.assertIn("KeyedManager", self.mod.code_corpus())
        self.assertNotIn("R-DEAD-SYMBOL", self._rules("see `KeyedManager` here"))
        self.assertIn("R-DEAD-SYMBOL", self._rules("see `MissingWidget` here"))

    def test_absent_keys_fall_back_to_index_config(self):
        # Keys empty and no index/index-config.json under FRAMEWORK → corpus empty (falsy),
        # both symbol rules inactive — exactly today's behavior.
        self.mod.CODE_ROOTS = self.mod.CODE_EXTENSIONS = ()
        self.mod._CODE_CORPUS = None
        self.assertEqual("", self.mod.code_corpus())
        self.assertNotIn("R-DEAD-SYMBOL", self._rules("see `MissingWidget` here"))


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


class TestTargetsAreRead(unittest.TestCase):
    """A run that read nothing must never answer like a full pass. A folder argument and an
    absent path both used to reach scan_file, which reads nothing from either — and the run
    printed "OK — no dead references", exit 0 (measured on a host project 2026-10-02: a
    routine was told to pass FILES because a folder 'passed' without being read)."""

    def _run(self, *args):
        import subprocess, sys
        return subprocess.run([sys.executable, os.path.join(CHECKS_DIR, "doc-refs-check.py"), *args],
                              capture_output=True, text=True, encoding="utf-8")

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def test_folder_argument_is_walked(self):
        sub = os.path.join(self.tmp, "nested")
        os.makedirs(sub)
        with open(os.path.join(sub, "doc.md"), "w", encoding="utf-8") as fh:
            fh.write("See `nowhere/really/ghost_file.py` for details.\n")
        r = self._run(self.tmp)
        self.assertIn("R-DEAD-PATH", r.stdout)
        self.assertNotIn("OK", r.stdout)

    def test_absent_target_is_blocking(self):
        r = self._run(os.path.join(self.tmp, "absent.md"))
        self.assertIn("ARG-MISSING", r.stdout)
        self.assertEqual(r.returncode, 2)

    def test_empty_folder_says_nothing_verified(self):
        r = self._run(self.tmp)
        self.assertIn("nothing verified", r.stdout)
        self.assertNotIn("OK", r.stdout)


class TestExtraRoots(unittest.TestCase):
    """`doc-refs.extra-roots`: the default run also walks the listed dirs (repo-root
    relative) — where a host keeps the instructions its agents follow, outside a framework
    nested under `Docs/`. Additive: the framework root stays walked."""

    def setUp(self):
        import argparse
        self.mod = _load_module()
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        for d, name in (("Docs", "a.md"), (os.path.join(".agents", "skills"), "b.md")):
            os.makedirs(os.path.join(self.tmp, d), exist_ok=True)
            open(os.path.join(self.tmp, d, name), "w").close()
        self.mod.REPO = self.tmp
        self.mod.FRAMEWORK = os.path.join(self.tmp, "Docs")
        self.args = argparse.Namespace(staged=False, diff=False, paths=[])

    def _names(self):
        return sorted(os.path.basename(f) for f in self.mod.gather(self.args))

    def test_absent_key_walks_the_framework_only(self):
        self.mod.EXTRA_ROOTS = ()
        self.assertEqual(self._names(), ["a.md"])

    def test_extra_root_is_walked_too(self):
        self.mod.EXTRA_ROOTS = (".agents",)
        self.assertEqual(self._names(), ["a.md", "b.md"])

    def test_nested_root_scans_a_file_once(self):
        self.mod.EXTRA_ROOTS = (".agents", os.path.join(".agents", "skills"))
        self.assertEqual(self._names(), ["a.md", "b.md"])


if __name__ == "__main__":
    unittest.main()
