# lib/parse.py
#
# Lexical tokenization + the legacy markdown sub-index parser. In flat-manifest mode
# (the normal path, see `../prefilter.py`), entries come from `entries_for_prefix`
# instead of `parse_subindex` — this parser is kept for ad hoc markdown fixtures/tests.
import re

# English-only stopword list — YAMS is an English-language framework (see the root
# CLAUDE.md), so manifest intents are expected in English. If a project's intents use
# a different vocabulary, extend this set rather than special-casing a language switch.
_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "if", "to", "in", "on", "by", "for", "that",
    "which", "is", "are", "with", "without", "this", "its", "from", "into", "when",
    "each", "all",
}
_ENTRY = re.compile(r'^\s*-\s+`([^`]+)`\s*[—-]\s*(.+?)\s*$')
_SECTION = re.compile(r'^\s*##\s+(.+?)\s*$')


def content_tokens(s):
    """Lowercase content words of `s`: split on non-alphanumeric separators, drop
    short tokens (<= 2 chars) and stopwords. Backbone of the pairwise lexical
    similarity (`lexsim.py`) and the anti-leakage guard (`guard.py`)."""
    toks = re.split(r'[^0-9A-Za-z]+', s.lower())
    return {t for t in toks if len(t) > 2 and t not in _STOPWORDS}


def parse_subindex(text):
    """Parse a markdown sub-index of the form `- \\`path\\` — intent`, optionally
    grouped under `## Section` headings. Returns entries `{ file, intent,
    intent_prefixed, section, dup, raw_line }`; `dup=True` on the 2nd+ occurrence of
    the same `file` (e.g. duplicated bilingual lines)."""
    entries, section, seen = [], None, set()
    for line in text.splitlines():
        m_sec = _SECTION.match(line)
        if m_sec:
            section = m_sec.group(1).rstrip("/").strip()
            continue
        m = _ENTRY.match(line)
        if not m:
            continue
        path, intent = m.group(1).strip(), m.group(2).strip()
        prefixed = f"[{section}] {intent}" if section else intent
        dup = path in seen
        seen.add(path)
        entries.append({
            "file": path, "intent": intent, "intent_prefixed": prefixed,
            "section": section, "dup": dup, "raw_line": line.strip(),
        })
    return entries
