# tests/test_size_guards.py
#
# Regression tests for the size guards added across the channels' INDEX files and the
# Decision channel's body — the invariant that must never re-open: an index that starts
# CARRYING THE DETAIL of its neighbouring files stops being scannable, and no mechanical
# rule saw it (measured 2026-08-09 on a real project: one backlog INDEX entry at 3772
# chars, a decisions INDEX median of 67 words/line). The guards are TO-CONFIRM by design
# (granularity hints, `checks-config.example.json §_sizes`), engine shared in
# `entrylib.check_index_entry_len` — one place defines what an entry is.
#
# Covered: `I-ENTRY-LEN` (backlog-check), `D9`/`D10` (decisions-check),
# `M-INDEX-LEN` (memory-check) — each wired end to end through its check's own runner,
# not just the entrylib engine (already covered by `entrylib --selftest`).
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

CHECKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name):
    """Check scripts have hyphens — not importable by name; load by path."""
    path = os.path.join(CHECKS_DIR, name)
    spec = importlib.util.spec_from_file_location(name.replace("-", "_").rstrip(".py"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(root, rel, text):
    full = os.path.join(root, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(text)
    return full


LONG_GIST = " ".join(["mot"] * 70)


class BacklogIndexEntryLen(unittest.TestCase):
    def setUp(self):
        self.repo = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.repo, ignore_errors=True))
        self.mod = _load("backlog-check.py")
        self.mod.ROOT = self.repo
        self.mod.BACKLOG = os.path.join(self.repo, "backlog")
        self.mod.INDEX_PATH = os.path.join(self.repo, "backlog", "INDEX.md")

    def _rules(self, index_text):
        _write(self.repo, "backlog/INDEX.md", index_text)
        return [f.rule for f in self.mod.run()]

    def test_oversized_entry_fires(self):
        rules = self._rules(f"- **Title** → `x/` — {LONG_GIST}\n")
        self.assertIn("I-ENTRY-LEN", rules)

    def test_wrapped_lines_count_as_one_entry(self):
        wrapped = "- **Title** → `x/` — start\n" + "\n".join(
            f"  suite {' '.join(['mot'] * 10)}" for _ in range(7))
        rules = self._rules(wrapped + "\n")
        self.assertIn("I-ENTRY-LEN", rules)

    def test_compliant_entry_is_silent(self):
        rules = self._rules("- **[todo] Title** — a short factual gist.\n")
        self.assertNotIn("I-ENTRY-LEN", rules)

    def test_badges_and_tags_do_not_count(self):
        # 55 prose words + a pile of bracketed tokens stays under the 60-word default.
        tags = " ".join(f"[tag{i}]" for i in range(20))
        rules = self._rules("- [todo] " + " ".join(["mot"] * 55) + " " + tags + "\n")
        self.assertNotIn("I-ENTRY-LEN", rules)

    def test_severity_is_to_confirm(self):
        _write(self.repo, "backlog/INDEX.md", f"- {LONG_GIST}\n")
        found = [f for f in self.mod.run() if f.rule == "I-ENTRY-LEN"]
        self.assertEqual([f.severity for f in found], [self.mod.TO_CONFIRM])


VALID_FRONTMATTER = """---
id: D-2026-01-01-01
status: active
source: human
confidence: verified
ratified: someone, 2026-01-01
created: 2026-01-01
updated: 2026-01-01
---
"""

VALID_BODY = "**Decision** — x.\n\n**Why** — y.\n\n**Invariant** — z.\n"


class DecisionsSizeGuards(unittest.TestCase):
    def setUp(self):
        self.repo = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.repo, ignore_errors=True))
        self.mod = _load("decisions-check.py")
        self.mod.ROOT = self.repo
        self.mod.DEC = os.path.join(self.repo, "decisions")
        self.mod.INDEX = os.path.join(self.repo, "decisions", "INDEX.md")

    def _rules(self, body_extra="", index_gist="short gist"):
        _write(self.repo, "decisions/D-2026-01-01-01.md",
               VALID_FRONTMATTER + VALID_BODY + body_extra)
        _write(self.repo, "decisions/INDEX.md",
               "## Active\n\n"
               f"- [D-2026-01-01-01](D-2026-01-01-01.md) — {index_gist}\n")
        return [f.rule for f in self.mod.audit()]

    def test_compliant_decision_is_silent(self):
        rules = self._rules()
        self.assertNotIn("D9", rules)
        self.assertNotIn("D10", rules)

    def test_oversized_body_fires_d9(self):
        rules = self._rules(body_extra="\n".join(f"ligne {i}" for i in range(90)))
        self.assertIn("D9", rules)

    def test_blank_and_table_separator_lines_do_not_count(self):
        filler = "\n".join(f"ligne {i}\n\n|---|" for i in range(35))  # 35 useful lines
        rules = self._rules(body_extra=filler)
        self.assertNotIn("D9", rules)

    def test_banner_lines_do_not_count_against_d9(self):
        """Le protocole de révocation ne se facture pas au budget de prose.

        90 lignes de bannière — le volume qu'une décision plusieurs fois amendée
        accumule — ne doivent pas déclencher D9 : l'auteur n'a pas le droit de les
        couper, les compter punirait les décisions ENTRETENUES."""
        banner = "\n".join(f"> note d'amendement {i}" for i in range(90))
        rules = self._rules(body_extra=banner)
        self.assertNotIn("D9", rules)

    def test_banner_over_budget_fires_d11(self):
        banner = "\n".join(f"> note d'amendement {i}" for i in range(90))
        rules = self._rules(body_extra=banner)
        self.assertIn("D11", rules)

    def test_banner_within_budget_is_silent(self):
        banner = "\n".join(f"> note d'amendement {i}" for i in range(15))
        rules = self._rules(body_extra=banner)
        self.assertNotIn("D11", rules)
        self.assertNotIn("D9", rules)

    def test_written_lines_still_fire_d9_despite_banners(self):
        """Une bannière ne blanchit pas un corps bavard : les deux budgets sont
        indépendants, et un fichier peut déclencher les deux."""
        body = "\n".join(f"ligne {i}" for i in range(90))
        banner = "\n".join(f"> note {i}" for i in range(30))
        rules = self._rules(body_extra=body + "\n" + banner)
        self.assertIn("D9", rules)
        self.assertIn("D11", rules)

    def test_oversized_section_fires_d12_and_names_it(self):
        """Le signal DÉSIGNE la section — c'est tout l'intérêt par rapport à D9,
        qui rend un total dont on ne sait que faire."""
        _write(self.repo, "decisions/D-2026-01-01-01.md",
               VALID_FRONTMATTER + "\n**Decision**\nd\n\n**Why**\n"
               + "\n".join(f"raison {i}" for i in range(40))
               + "\n\n**Invariant**\ni\n")
        _write(self.repo, "decisions/INDEX.md",
               "## Active\n\n- [D-2026-01-01-01](D-2026-01-01-01.md) — gist\n")
        f = [x for x in self.mod.audit() if x.rule == "D12"]
        self.assertTrue(f)
        self.assertIn("**Why**", f[0].msg)

    def test_sections_within_budget_are_silent(self):
        rules = self._rules()
        self.assertNotIn("D12", rules)

    def test_banner_lines_do_not_count_against_a_section(self):
        """Une bannière vit dans un tronçon sans lui être facturée — même raison
        que pour D9 : c'est du protocole, pas de la prose."""
        _write(self.repo, "decisions/D-2026-01-01-01.md",
               VALID_FRONTMATTER + "\n**Decision**\nd\n\n**Why**\n"
               + "\n".join(f"> note {i}" for i in range(40))
               + "\nraison\n\n**Invariant**\ni\n")
        _write(self.repo, "decisions/INDEX.md",
               "## Active\n\n- [D-2026-01-01-01](D-2026-01-01-01.md) — gist\n")
        self.assertNotIn("D12", [x.rule for x in self.mod.audit()])

    def test_oversized_index_entry_fires_d10(self):
        rules = self._rules(index_gist=" ".join(["mot"] * 90))
        self.assertIn("D10", rules)

    def test_index_tags_do_not_count(self):
        gist = " ".join(["mot"] * 75) + " · " + " ".join(f"[t{i}]" for i in range(30))
        rules = self._rules(index_gist=gist)
        self.assertNotIn("D10", rules)


class MemoryIndexEntryLen(unittest.TestCase):
    def setUp(self):
        self.repo = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.repo, ignore_errors=True))
        self.mod = _load("memory-check.py")
        self.mod.ROOT = self.repo
        self.mod.MEMORY_MD = os.path.join(self.repo, "MEMORY.md")
        self.mod.MEMORY_DIR = os.path.join(self.repo, "memory")

    def test_oversized_index_entry_fires(self):
        _write(self.repo, "MEMORY.md", f"- (memory/x.md) {LONG_GIST}\n")
        rules = [f.rule for f in self.mod.audit_index_entry_len()]
        self.assertEqual(rules, ["M-INDEX-LEN"])

    def test_compliant_index_is_silent(self):
        _write(self.repo, "MEMORY.md", "- (memory/x.md) one short pointer line.\n")
        self.assertEqual(self.mod.audit_index_entry_len(), [])

    def test_missing_index_is_silent(self):
        self.assertEqual(self.mod.audit_index_entry_len(), [])


if __name__ == "__main__":
    unittest.main()
