# lib/parse.py
#
# Lexical tokenization + the legacy markdown sub-index parser. In flat-manifest mode
# (the normal path, see `../prefilter.py`), entries come from `entries_for_prefix`
# instead of `parse_subindex` — this parser is kept for ad hoc markdown fixtures/tests.
import re

from . import config

# English default — YAMS is an English-language framework, so intents are expected in
# English. A project whose intents are written in another language ADDS its own function
# words through `eval-stopwords` in `index/index-config.json`; it never edits this set.
# The difference is not cosmetic: an unlisted function word is counted as CONTENT, so two
# unrelated French intents sharing "des"/"les" look similar to `lexsim`, and a query
# sharing them with its source intent looks contaminated to `guard`. Both failures inflate
# a number rather than raising, which is why the vocabulary belongs in config and not in
# a fork of this file.
_DEFAULT_STOPWORDS = frozenset({
    "the", "a", "an", "of", "and", "or", "if", "to", "in", "on", "by", "for", "that",
    "which", "is", "are", "with", "without", "this", "its", "from", "into", "when",
    "each", "all",
})
_STOPWORDS = set(_DEFAULT_STOPWORDS)
_ENTRY = re.compile(r'^\s*-\s+`([^`]+)`\s*[—-]\s*(.+?)\s*$')
_SECTION = re.compile(r'^\s*##\s+(.+?)\s*$')


def extend_stopwords(words):
    """Add a project's own function words to the shared set (idempotent)."""
    _STOPWORDS.update(w.lower() for w in words if w)


def set_stopwords(words):
    """Back to the English default plus `words` — used when a caller loads a config
    other than the default one, so a second load does not stack onto the first."""
    _STOPWORDS.clear()
    _STOPWORDS.update(_DEFAULT_STOPWORDS)
    extend_stopwords(words)


def content_tokens(s):
    """Lowercase content words of `s`: split on non-alphanumeric separators, drop
    short tokens (<= 2 chars) and stopwords. Backbone of the pairwise lexical
    similarity (`lexsim.py`) and the anti-leakage guard (`guard.py`).

    The separator class keeps Latin-1 letters, so an accented word stays ONE token —
    without it `réécrire` splits into `r` + `crire`, two tokens that match nothing. This
    costs English nothing: no English word carries a character in that range."""
    toks = re.split(r'[^0-9A-Za-zÀ-ÿ]+', s.lower())
    return {t for t in toks if len(t) > 2 and t not in _STOPWORDS}


# Seeded here rather than at an entry point: the LLM-judged pass imports `lib.guard` /
# `lib.lexsim` directly and never runs `prefilter.py`, so a vocabulary installed by the
# prefilter would silently not apply to the guard.
_cfg, _ = config.load()
extend_stopwords((_cfg or {}).get("eval-stopwords") or [])


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
