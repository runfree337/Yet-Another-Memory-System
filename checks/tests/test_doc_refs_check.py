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
import importlib.util
import os
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


if __name__ == "__main__":
    unittest.main()
