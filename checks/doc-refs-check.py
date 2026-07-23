#!/usr/bin/env python3
"""Dead references in the docs (universal, portable) — MECHANICAL half of doc freshness.

Catches a reference that points to nothing. SEMANTIC drift (does the prose describe the
real behavior?) is not mechanizable -> project review (tier 2).

Rules:
  R-DEAD-PATH     (BLOCKING/TO-CONFIRM) : a token that is clearly a "file path" (at least
                  one `/` + an extension) cited in a `.md` that does not/no longer exists.
                  Severity via git: a path with history = existed then disappeared ->
                  BLOCKING; never created -> TO-CONFIRM (might be planned, or a typo).
                  Backticked spans are scanned in place: a fragment that looks dead only
                  because the real directory name contains a space (`Tools/My Dir/f.py`
                  fragments to `Dir/f.py`) is re-anchored across the span before flagging.
  CFG-INVALID     (BLOCKING) : `checks-config.json` present at the repo root but broken
                  (unreadable, malformed JSON, non-object top level) — a config the user
                  believes active is never silently ignored.
  R-DEAD-DECISION (BLOCKING) : a `D-YYYY-MM-DD-NN` id cited in a `.md` with no matching
                  `decisions/<id>.md` file. Resolved from the framework root, same as the
                  path rule above. INACTIVE (no findings) when the project has no
                  `decisions/` folder at all — nothing to check against.
  R-DEAD-SYMBOL   (TO-CONFIRM) : a backticked, composed PascalCase token (>= 2 capitalized
                  words, e.g. `FooBarManager` — filters out ordinary single words) not
                  found (grep-style) across the project's code. The corpus comes from
                  `doc-refs.code-roots` + `doc-refs.code-extensions` (checks-config.json,
                  roots resolved from the REPO root) when both are set, else from
                  `index/index-config.json` (`roots` + `extensions`) as before — the
                  dedicated keys DECOUPLE this check from index-check's config, whose `base`
                  semantics differ when the framework is nested (e.g. under `Docs/`) and
                  whose manifest a project may not want activated. AGNOSTIC/INACTIVE (no
                  findings, no error) when neither source provides roots + extensions — the
                  framework does not hardcode a project's code layout. Narrowable per project (all optional,
                  all additive, defaults = today's behavior) via `doc-refs.symbol-suffixes`
                  (keep only names ending in a declared suffix), `doc-refs.ignore-symbols`
                  (drop host-ecosystem API names) and `doc-refs.symbol-ignore-dirs` (mute the
                  rule on transient doc dirs) — see the Exemptions below.
  R-GHOST-ABSENCE (TO-CONFIRM) : the reverse drift — prose claiming a symbol is
                  missing/not yet built ("not yet", "missing", "absent", "to be built",
                  "not wired", "pas encore", "manquant", "à créer"…) while the backticked
                  PascalCase symbol DOES exist in the code ("delivered but the doc doesn't
                  know"). PROXIMITY: the ghost word and the symbol must share a SEGMENT of the
                  line (split on `|`/`;`/sentence enders, never `,`/`:`), not just the line —
                  a ghost word one table cell or one clause away is not a claim about the
                  symbol. Same config gating as R-DEAD-SYMBOL. Trigger words overlap `NEG`
                  (which otherwise suppresses R-DEAD-PATH/R-DEAD-DECISION/R-DEAD-SYMBOL on a
                  line) by design: this rule is exactly what fires ON those lines, it is
                  never skipped by `NEG`. Residual noise where the ghost word binds to a
                  NEIGHBOURING noun (`icône absente du SpriteRegistry` — the icon is absent,
                  not the registry) is grammar, out of reach of any proximity rule: the
                  project declares its own prose shapes in
                  `doc-refs.ghost-exclude-patterns` (see the Exemptions below).

Zero false positive on the firm (BLOCKING) tier; TO-CONFIRM is a pre-filter for judgment.
Flags, never fixes.

Exemptions (apply identically to all four rules above):
  - fenced code blocks (```…```) — illustrative, not a live reference.
  - `<!-- template -->` marker — line form exempts targets on that line; block form
    (`<!-- template -->` … `<!-- /template -->`) exempts every line in between.
  - `NEG` word list — a line already marked "deleted/renamed/to create/…" is not flagged
    as dead by R-DEAD-PATH/R-DEAD-DECISION/R-DEAD-SYMBOL (would be redundant with the
    prose). R-GHOST-ABSENCE is the deliberate exception (see above).
  - `doc-refs.ignore-prefixes` (`checks-config.json`, optional, default empty) — project
    -declared prefixes for tokens that LOOK like repo paths but never are (a runtime API
    joined to a filename, e.g. `Runtime.dataDir/…`). R-DEAD-PATH only.
  - `doc-refs.symbol-suffixes` (optional, default empty) — when non-empty, a PascalCase
    candidate is kept only if it ends with one of these suffixes (a project's type-naming
    convention: Manager, View, Registry…). Empty/absent = every composed PascalCase token,
    unchanged. R-DEAD-SYMBOL / R-GHOST-ABSENCE.
  - `doc-refs.ignore-symbols` (optional, default empty) — literal candidate exclusions for
    host-ecosystem API cited in the docs (`MonoBehaviour`, `RectTransform`…). Additive,
    never substitutive. R-DEAD-SYMBOL / R-GHOST-ABSENCE.
  - `doc-refs.symbol-ignore-dirs` (optional, default empty) — doc dirs (relative to the
    framework root) where the two symbol rules are muted (transient docs naming not-yet-built
    types, e.g. `backlog/`). R-DEAD-PATH / R-DEAD-DECISION stay active there.
  - `doc-refs.neg-words` (optional, default empty) — extra negation words appended to the
    built-in bilingual NEG list, for docs in the project's own language (French `pas d'`,
    `non retenue`…). Suppresses R-DEAD-PATH / R-DEAD-DECISION / R-DEAD-SYMBOL, like NEG; never
    R-GHOST-ABSENCE. (The `Xxx` PascalCase placeholder, like `XXXX`, is recognized built-in.)
  - `doc-refs.ghost-exclude-patterns` (optional, default empty) — project-declared regexes
    (case-insensitive) matched against the SEGMENT R-GHOST-ABSENCE is about to flag; a match
    suppresses the rule for that segment only. This is where a project's GRAMMAR lives as
    data — e.g. a French container shape like "(absente|manquante)…(du|de la|des|dans)
    followed by a backtick" says "the ghost word binds to a neighbouring noun, the symbol is
    only its container" — the framework itself stays language-blind. Purely SUPPRESSIVE: a
    pattern can only remove findings, never add one, so the zero-FP contract is untouched.
    An invalid regex is a BLOCKING CFG-INVALID, never silently dropped. R-GHOST-ABSENCE only.
  - `<!-- doc-refs: ignore -->` pragma — an explicit reviewed-and-accepted escape hatch: every
    doc-refs rule is silenced on the line carrying the marker (that line only, all four
    rules). Distinct in INTENT from `<!-- template -->` (this target is an example) even
    though both exempt their line: the pragma says "a human looked at this finding and keeps
    the prose as-is". Reserve it for the residue no config key covers cleanly.

Modes:
  doc-refs-check.py [paths.md…]  # explicit targets
  doc-refs-check.py --staged     # .md files staged (git diff --cached --name-only)
  doc-refs-check.py --diff       # .md files modified but unstaged (git diff --name-only)
  doc-refs-check.py              # default: every .md file under the framework root

Exit 2 if >=1 BLOCKING, 1 if only TO-CONFIRM, 0 otherwise. Read-only.
"""
import argparse
import json
import os
import re
import subprocess
import sys

import entrylib

# Windows consoles default to cp1252: non-cp1252 output (→, ⨯…) would crash print().
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

FRAMEWORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # framework root
DECISIONS_DIR = os.path.join(FRAMEWORK, "decisions")
DECISIONS_INDEX = os.path.join(DECISIONS_DIR, "INDEX.md")

# Final segment: up to 16 chars after the last dot (a package id like
# `com.example.roundedcorners` is a legitimate path tail, the old {1,6} bound truncated it
# to a ghost token `…rounde`). The lookahead refuses to stop mid-word or mid-package
# (`(?!\.?[A-Za-z0-9])`: neither an alnum continuation nor a further `.segment`), while a
# sentence-final dot (`see Docs/x.md.`) still ends the token cleanly.
PATH_RE = re.compile(r"(?:[\w.\-]+/)+[\w.\-]+\.[A-Za-z0-9]{1,16}(?!\.?[A-Za-z0-9])")
DECISION_RE = re.compile(r"D-\d{4}-\d{2}-\d{2}-\d{2}")
CODE_SPAN_RE = re.compile(r"`([^`]+)`")
# composed PascalCase: first char upper, >=4 chars total, >=2 uppercase letters overall
# (filters out ordinary single words like `Foo` or `Ok`).
PASCAL_RE = re.compile(r"^[A-Z][A-Za-z0-9]{3,}$")
TEMPLATE = re.compile(r"[<>{}*…]|Xxx|YYYY|AAAA|XXXX|MM-|/\.\.\.")

# Prose words that neutralize a path/decision/symbol mention — both languages covered
# (docs may be authored in either while the corpus is being translated; keep both sets,
# never drop the French forms even once the English ones land).
NEG = ("n'existe", "nexiste", "supprim", "à créer", "a creer", "à porter", "a porter",
       "renomm", "à venir", "a venir", "exemple", "example", "template", "gabarit",
       "placeholder", "→", "->", "n'est pas", "plus tard", "déplacé", "deplace", "futur",
       "deleted", "removed", "to create", "to port", "renamed", "upcoming", "later",
       "moved", "future", "does not exist", "doesn't exist", "not yet", "not created",
       "planned")
# Same membership test, one compiled alternation instead of 37 substring scans per line
# (measured ~0.14 s on a 355-file corpus — the single hottest spot of a clean run). Rebuilt
# once below if `doc-refs.neg-words` adds project-language vocabulary (empty default = as is).
NEG_RE = re.compile("|".join(re.escape(w) for w in NEG))

# Trigger words for R-GHOST-ABSENCE — prose claiming a symbol is missing/not yet built.
# Deliberately overlaps NEG (bilingual spirit, same idea) but is its own list: this rule
# must still run on a NEG-flagged line, since that's precisely the drift it looks for.
GHOST_WORDS = ("not yet", "missing", "absent", "to be built", "not wired",
               "pas encore", "manquant", "à créer", "a creer")
# R-GHOST-ABSENCE proximity — a ghost word only claims a symbol is missing when the two
# share a SEGMENT, not merely the line. Split on `|` (markdown table cells) + `;` + sentence
# enders (`.`/`!`/`?` before whitespace). Deliberately NOT `,` nor `:` — a comma or a
# "label:" colon routinely sits between a symbol and its own negation (`absent : Foo`), and
# splitting there would drop the real drift. Measured on a 287-doc host: cuts ~two-thirds of
# the line-cooccurrence false positives, keeps every genuine "delivered but the doc still
# says missing" case. The residual — a ghost word grammatically bound to a NEIGHBOURING noun
# (`icône absente du SpriteRegistry` claims the icon is absent, not the registry) — is the
# lexical ceiling, out of reach of any proximity rule: bridged per project by
# `doc-refs.ghost-exclude-patterns` (grammar as config data, see GHOST_EXCLUDE below) until
# the code-symbol-graph roadmap makes the rule exact.
GHOST_SEGMENT_RE = re.compile(r"[|;]|(?<=[.!?])\s+")

# TEMPLATE exemption — explicit HTML marker, never a hidden allowlist in the script.
# (a) line  : "<!-- template -->" on a line exempts the paths on THAT line.
# (b) block : a "<!-- template -->" / "<!-- /template -->" pair exempts every line
#             (markers included) between the two. An opening marker never closed falls
#             back to case (a) — exempts only its own line.
TEMPLATE_OPEN = "<!-- template -->"
TEMPLATE_CLOSE = "<!-- /template -->"

# Reviewed-and-accepted escape hatch — same explicit-marker philosophy as TEMPLATE (in the
# text, never a hidden allowlist), but a different INTENT: `<!-- template -->` says "this
# target is an example, never meant to exist"; the pragma says "a human reviewed this finding
# and keeps the prose as-is". Line form only, silences every doc-refs rule on its own line.
PRAGMA = "<!-- doc-refs: ignore -->"


def template_lines(lines):
    """Line numbers (1-indexed) exempted by the <!-- template --> marker."""
    exempt = set()
    open_at = None
    for i, line in enumerate(lines, 1):
        if TEMPLATE_CLOSE in line and open_at is not None:
            exempt.update(range(open_at, i + 1))
            open_at = None
            continue
        if TEMPLATE_OPEN in line:
            if open_at is not None:
                exempt.add(open_at)  # previous marker never closed -> case (a) only
            open_at = i
    if open_at is not None:
        exempt.add(open_at)  # never closed -> case (a) only
    return exempt


def repo_root():
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10).stdout.strip()
        return out or os.getcwd()
    except Exception:
        return os.getcwd()


REPO = repo_root()

# `doc-refs.ignore-prefixes` — project-declared prefixes for tokens that look like repo
# paths but never are (runtime API + filename, machine-local paths). Optional, additive,
# empty by default; a broken config file surfaces as CFG-INVALID in main().
_CFG, _CFG_ERR = entrylib.load_checks_config(FRAMEWORK)
IGNORE_PREFIXES = tuple(p for p in entrylib.cfg_get(_CFG, ("doc-refs", "ignore-prefixes"), [])
                        if isinstance(p, str) and p)

# Three optional, additive symbol-rule tunings (R-DEAD-SYMBOL / R-GHOST-ABSENCE) — all empty
# by default, so an absent config keeps today's behavior exactly. Same nature as `roots`/
# `extensions` in index-config: a host ecosystem's API surface and naming conventions
# (Unity != React != Django) are the project's to declare, never hardcoded in the framework.
#   symbol-suffixes    — when non-empty, a PascalCase candidate is kept only if it ends with
#                        one of these suffixes (`Manager`, `View`, `Registry`…). Empty/absent
#                        ⇒ every composed PascalCase token, as before. The lever that silences
#                        the host API cited across a project's docs.
#   ignore-symbols     — literal exclusions for host-ecosystem API names (`MonoBehaviour`,
#                        `RectTransform`…). Additive, never substitutive.
#   symbol-ignore-dirs — doc dirs (relative to the framework root) where the two symbol rules
#                        are muted — transient docs that legitimately name not-yet-built types
#                        (a `backlog/`). R-DEAD-PATH / R-DEAD-DECISION stay ACTIVE there.
SYMBOL_SUFFIXES = tuple(s for s in entrylib.cfg_get(_CFG, ("doc-refs", "symbol-suffixes"), [])
                        if isinstance(s, str) and s)
IGNORE_SYMBOLS = frozenset(s for s in entrylib.cfg_get(_CFG, ("doc-refs", "ignore-symbols"), [])
                           if isinstance(s, str) and s)
SYMBOL_IGNORE_DIRS = tuple(d.strip("/") for d in entrylib.cfg_get(_CFG, ("doc-refs", "symbol-ignore-dirs"), [])
                           if isinstance(d, str) and d.strip("/"))

# `doc-refs.neg-words` — extra negation vocabulary appended to the built-in bilingual NEG
# list, for docs authored in the project's own language (e.g. French `pas d'`, `non retenue`).
# The framework carries FR + EN; a project whose docs use other phrasings (or a third language)
# declares them here rather than forcing broad words like `pas de` onto every project's default.
# Matched lowercased against the line, like the built-ins; suppresses R-DEAD-PATH /
# R-DEAD-DECISION / R-DEAD-SYMBOL on a line whose prose already states the target is absent —
# never R-GHOST-ABSENCE (which fires ON such lines by design). Optional, additive, empty by
# default (⇒ NEG_RE unchanged).
NEG_EXTRA = tuple(w.lower() for w in entrylib.cfg_get(_CFG, ("doc-refs", "neg-words"), [])
                  if isinstance(w, str) and w)
if NEG_EXTRA:
    NEG_RE = re.compile("|".join(re.escape(w) for w in NEG + NEG_EXTRA))

# `doc-refs.ghost-exclude-patterns` — project-declared regexes (compiled case-insensitive)
# matched against the SEGMENT R-GHOST-ABSENCE is about to flag; any match suppresses the rule
# for that segment. The residual noise past the segment split is grammatical — the ghost word
# binds to a NEIGHBOURING noun and the symbol is only its container (`icône absente du
# `SpriteRegistry``) — and grammar is a language's own, so it goes here as per-project DATA,
# never hardcoded in the framework (same contract as `neg-words`: the project answers for the
# precision of what it declares). Purely suppressive — can only remove findings, never add.
# An unparsable pattern becomes a BLOCKING CFG-INVALID in main(): a config the user believes
# active is never silently ignored. Optional, empty by default (⇒ behavior unchanged).
_CFG_KEY_ERRS = []  # per-key config errors, surfaced as BLOCKING CFG-INVALID in main()
GHOST_EXCLUDE = []
for _pat in entrylib.cfg_get(_CFG, ("doc-refs", "ghost-exclude-patterns"), []):
    if not (isinstance(_pat, str) and _pat):
        continue
    try:
        GHOST_EXCLUDE.append(re.compile(_pat, re.IGNORECASE))
    except re.error as _e:
        _CFG_KEY_ERRS.append(
            f"doc-refs.ghost-exclude-patterns: invalid regex {_pat!r} ({_e})")
GHOST_EXCLUDE = tuple(GHOST_EXCLUDE)

# `doc-refs.code-roots` + `doc-refs.code-extensions` — DEDICATED corpus keys for the two
# symbol rules, decoupling them from `index/index-config.json`. Reusing index-check's file
# proved a trap on a host with the framework nested under `Docs/`: `base` is resolved
# against FRAMEWORK here but against the cwd by index-check (one file cannot satisfy both),
# and merely creating the file wakes index-check up against a manifest whose path format the
# project may not share. Roots are resolved from the REPO root (git toplevel — the natural
# frame for "where does the code live", nesting-proof); extensions as in index-config.
# Both-or-neither: exactly one of the two set is a BLOCKING CFG-INVALID, never a silent
# no-op. Absent (default) ⇒ fallback on index-config.json, today's behavior unchanged.
CODE_ROOTS = tuple(r for r in entrylib.cfg_get(_CFG, ("doc-refs", "code-roots"), [])
                   if isinstance(r, str) and r)
CODE_EXTENSIONS = tuple(e for e in entrylib.cfg_get(_CFG, ("doc-refs", "code-extensions"), [])
                        if isinstance(e, str) and e)
if bool(CODE_ROOTS) != bool(CODE_EXTENSIONS):
    _CFG_KEY_ERRS.append(
        "doc-refs.code-roots / doc-refs.code-extensions: set together — one without the "
        "other activates nothing")


def exists_somewhere(token, file_dir):
    # os.path.exists, not isfile: a reference to a directory that exists (a package
    # folder, an asset dir) is alive — flagging it was a false positive.
    return any(os.path.exists(os.path.join(base, token))
               for base in (file_dir, FRAMEWORK, REPO, os.getcwd()))


def _path_mentions(line):
    """PATH_RE hits with their surrounding backtick span (`None` outside spans).

    Spans are scanned in place so a dead-looking fragment can be re-anchored across
    spaces by `_space_rescue`; the text outside spans is scanned with the spans removed
    — same coverage as the previous backtick-stripping approach."""
    pieces, last = [], 0
    for m in CODE_SPAN_RE.finditer(line):
        span = m.group(1)
        for pm in PATH_RE.finditer(span):
            yield pm.group(0), span, pm.start()
        pieces.append(line[last:m.start()])
        last = m.end()
    pieces.append(line[last:])
    for pm in PATH_RE.finditer(" ".join(pieces)):
        yield pm.group(0), None, -1


def _space_rescue(span, at, tok):
    """Left-extensions of a span fragment across spaces, longest first.

    A real directory name may contain a space, which PATH_RE cannot cross:
    `Tools/My Dir/file.py` fragments to `Dir/file.py` and looks dead while the full
    span text exists. Candidates only — the caller keeps the verdict (existence, then
    git history)."""
    end = at + len(tok)
    return [span[j:end] for j in range(at)
            if span[j] != " " and (j == 0 or span[j - 1] == " ")]


_HISTORICAL_PATHS = None


def _historical_paths():
    # ONE `git log` dump for the whole run, cached. The previous shape — one
    # `git log --all -1 -- <token>` subprocess per dead token — cost ~0.3 s each on a
    # real host repo (measured: 630 dead tokens x 2441 commits = 2min20 wall), which
    # ruled the check out of any hook. `core.quotepath=off` keeps non-ASCII paths
    # literal (git would otherwise octal-escape them and break the set lookup).
    global _HISTORICAL_PATHS
    if _HISTORICAL_PATHS is None:
        try:
            out = subprocess.run(
                ["git", "-c", "core.quotepath=off", "log", "--all",
                 "--pretty=format:", "--name-only"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=120, cwd=REPO).stdout
            _HISTORICAL_PATHS = {line.strip() for line in out.splitlines() if line.strip()}
        except Exception:
            _HISTORICAL_PATHS = set()   # degrades to TO-CONFIRM, same as the old failure path
    return _HISTORICAL_PATHS


def had_history(token):
    # EXACT path only: a homonymous file (same basename) that disappeared elsewhere does
    # NOT make this reference dead. The `*/basename` glob produced false BLOCKING — it was
    # removed to keep the firm tier at zero false positives. Dead = this exact path
    # existed (as a file, or as a directory prefix — same reach as a git pathspec).
    paths = _historical_paths()
    t = token.replace("\\", "/").strip("/")
    if t in paths:
        return True
    prefix = t + "/"
    return any(p.startswith(prefix) for p in paths)


def decision_exists(did):
    return os.path.isfile(os.path.join(DECISIONS_DIR, did + ".md"))


def _candidate_symbol(span):
    """Extract a composed-PascalCase candidate from a backtick span, or None. Strips a
    trailing call/generic (`Foo(x)` -> `Foo`, `Foo<T>` -> `Foo`) and a member access
    (`Foo.Bar` -> `Foo`), then requires PASCAL_RE + >=2 uppercase letters — filters out
    ordinary single words so common prose doesn't get flagged. Two optional, additive
    config filters narrow the result further: `symbol-suffixes` (when non-empty, keep only
    names ending in a project-declared suffix) and `ignore-symbols` (drop host-ecosystem
    API names outright) — both empty by default, i.e. today's unfiltered behavior."""
    s = span.strip().split("(")[0].split("<")[0]
    s = s.strip(" .,;:'\"`")
    first = s.split(".")[0]
    if not PASCAL_RE.match(first):
        return None
    if sum(1 for c in first if c.isupper()) < 2:
        return None
    if TEMPLATE.search(first):  # gabarit placeholder (Xxx, YYYY…)
        return None
    if SYMBOL_SUFFIXES and not first.endswith(SYMBOL_SUFFIXES):
        return None  # project convention: a type ends in Manager/View/Registry/…
    if first in IGNORE_SYMBOLS:
        return None  # host-ecosystem API cited in the docs (MonoBehaviour…)
    return first


# --------------------------------------------------------------------------- #
# Code corpus for R-DEAD-SYMBOL / R-GHOST-ABSENCE — agnostic: the roots and
# extensions to search are never hardcoded here. Two sources, in order:
# (1) the dedicated `doc-refs.code-roots`/`code-extensions` keys (see their
# loading block above — repo-root-relative, index-check-free); (2) fallback:
# the project's own `index/index-config.json` (schema:
# `index/index-config.example.json`, same file `checks/index-check.py` loads).
# Neither source complete -> both rules stay INACTIVE (no findings, no error):
# the framework does not assume the host project's code layout on its own.
# --------------------------------------------------------------------------- #

_CODE_CORPUS = None  # sentinel None = not loaded yet; "" (falsy) = loaded, inactive


def _load_code_index_config():
    cfg_path = os.path.join(FRAMEWORK, "index", "index-config.json")
    try:
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    roots = cfg.get("roots") or []
    exts = tuple(cfg.get("extensions") or [])
    if not roots or not exts:
        return None
    base = os.path.normpath(os.path.join(FRAMEWORK, cfg.get("base", ".")))
    return base, roots, exts


def _load_code_config():
    """(base, roots, extensions) of the code corpus, or None. Dedicated keys first —
    `doc-refs.code-roots`/`code-extensions`, resolved from the REPO root — then fallback
    on `index/index-config.json` (unchanged), so a project that only wants the symbol
    rules never has to create index-check's config file."""
    if CODE_ROOTS and CODE_EXTENSIONS:
        return REPO, list(CODE_ROOTS), CODE_EXTENSIONS
    return _load_code_index_config()


def code_corpus():
    """Concatenated text of every file under the configured code roots/extensions — a
    grep-style "does this symbol exist" search space. Empty string (falsy) when neither
    the dedicated `doc-refs` keys nor `index/index-config.json` provide a complete config."""
    global _CODE_CORPUS
    if _CODE_CORPUS is not None:
        return _CODE_CORPUS
    cfg = _load_code_config()
    chunks = []
    if cfg:
        base, roots, exts = cfg
        for r in roots:
            for dpath, _, names in os.walk(os.path.join(base, r)):
                for n in names:
                    if not n.endswith(exts):
                        continue
                    try:
                        chunks.append(open(os.path.join(dpath, n),
                                            encoding="utf-8", errors="replace").read())
                    except OSError:
                        continue
    _CODE_CORPUS = "\n".join(chunks)
    return _CODE_CORPUS


def _symbol_muted(path):
    """True when `path` sits under a `doc-refs.symbol-ignore-dirs` entry (relative to the
    framework root) — the two symbol rules are silenced there (transient docs that name
    not-yet-built types, e.g. `backlog/`). R-DEAD-PATH / R-DEAD-DECISION stay active: a
    dead path cited in a transient doc is a real drift, an unwritten type is not."""
    if not SYMBOL_IGNORE_DIRS:
        return False
    try:
        rel = os.path.relpath(os.path.abspath(path), FRAMEWORK).replace(os.sep, "/")
    except ValueError:  # different drive on Windows — cannot be under FRAMEWORK
        return False
    return any(rel == d or rel.startswith(d + "/") for d in SYMBOL_IGNORE_DIRS)


def scan_file(path):
    findings = []  # each: (severity, path, line, rule, msg)
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except (OSError, UnicodeDecodeError):
        return findings
    fenced = False
    file_dir = os.path.dirname(os.path.abspath(path))
    exempt = template_lines(lines)
    corpus = code_corpus()
    symbol_muted = _symbol_muted(path)
    is_decisions_index = (os.path.basename(path) == "INDEX.md"
                           and os.path.dirname(os.path.abspath(path)) == DECISIONS_DIR)

    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced or i in exempt or PRAGMA in line:
            continue
        low = line.lower()
        neg = NEG_RE.search(low) is not None

        # R-DEAD-PATH — the "/" gate skips the span scan on the many lines that cannot
        # contain a path token at all (PATH_RE requires at least one slash).
        if not neg and "/" in line:
            for tok, span, at in _path_mentions(line):
                if TEMPLATE.search(tok) or "://" in tok or exists_somewhere(tok, file_dir) \
                        or any(tok.startswith(p) for p in IGNORE_PREFIXES):
                    continue
                rescue = _space_rescue(span, at, tok) if span is not None else []
                if any(exists_somewhere(c, file_dir) for c in rescue):
                    continue  # the real directory name contains a space; reference alive
                dead = next((c for c in rescue if had_history(c)), None) \
                    or (tok if had_history(tok) else None)
                sev, shown = ("BLOCKING", dead) if dead else ("TO-CONFIRM", tok)
                findings.append((sev, path, i, "R-DEAD-PATH", f"path not found: {shown}"))

        # R-DEAD-DECISION — the decisions/INDEX.md file IS the registry, skip it (avoids
        # duplicating decisions-check.py's own file<->index concordance rule).
        if not neg and os.path.isdir(DECISIONS_DIR) and not is_decisions_index:
            for did in DECISION_RE.findall(line):
                if not decision_exists(did):
                    findings.append(("BLOCKING", path, i, "R-DEAD-DECISION",
                                     f"decision id with no decisions/{did}.md file: {did}"))

        # R-DEAD-SYMBOL — inactive (corpus falsy) when index-config.json is absent/incomplete;
        # muted on files under `doc-refs.symbol-ignore-dirs` (transient docs naming non-built types).
        if not neg and corpus and not symbol_muted:
            seen = set()
            for m in CODE_SPAN_RE.finditer(line):
                sym = _candidate_symbol(m.group(1))
                if sym and sym not in seen and sym not in corpus:
                    seen.add(sym)
                    findings.append(("TO-CONFIRM", path, i, "R-DEAD-SYMBOL",
                                     f"symbol not found under the configured code roots: {sym}"))

        # R-GHOST-ABSENCE — deliberately NOT gated by `neg`: it fires exactly on the lines
        # NEG would otherwise suppress. Same config gating as R-DEAD-SYMBOL (corpus + muted
        # dirs). Proximity: the ghost word must share a SEGMENT with the symbol, not just the
        # line (GHOST_SEGMENT_RE) — the cheap line-level `any(...)` stays as a fast pre-gate.
        if corpus and not symbol_muted and any(w in low for w in GHOST_WORDS):
            seen = set()
            for seg in GHOST_SEGMENT_RE.split(line):
                if not any(w in seg.lower() for w in GHOST_WORDS):
                    continue
                if any(rx.search(seg) for rx in GHOST_EXCLUDE):
                    continue  # project-declared prose shape: the ghost word binds to a
                    #           neighbouring noun, the symbol is only its container
                for m in CODE_SPAN_RE.finditer(seg):
                    sym = _candidate_symbol(m.group(1))
                    if sym and sym not in seen and sym in corpus:
                        seen.add(sym)
                        findings.append(("TO-CONFIRM", path, i, "R-GHOST-ABSENCE",
                                         f"doc claims {sym} is missing/not built, but it "
                                         "exists in code"))
    return findings


def gather(args):
    if args.staged:
        try:
            out = subprocess.run(["git", "diff", "--cached", "--name-only"],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10).stdout
        except Exception:
            return []
        return [f for f in out.splitlines() if f.endswith(".md") and os.path.isfile(f)]
    if args.diff:
        try:
            out = subprocess.run(["git", "diff", "--name-only"],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10).stdout
        except Exception:
            return []
        return [f for f in out.splitlines() if f.endswith(".md") and os.path.isfile(f)]
    if args.paths:
        return args.paths
    found = []
    for dpath, _, names in os.walk(FRAMEWORK):
        found += [os.path.join(dpath, n) for n in names if n.endswith(".md")]
    return found


def main():
    ap = argparse.ArgumentParser(description="Dead references in the docs (portable).")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--diff", action="store_true")
    a = ap.parse_args()

    findings = []
    if _CFG_ERR:
        findings.append(("BLOCKING", entrylib.CHECKS_CONFIG_NAME, 1,
                         "CFG-INVALID", _CFG_ERR))
    for err in _CFG_KEY_ERRS:
        findings.append(("BLOCKING", entrylib.CHECKS_CONFIG_NAME, 1,
                         "CFG-INVALID", err))
    for f in gather(a):
        findings += scan_file(f)

    blocking = [x for x in findings if x[0] == "BLOCKING"]
    for sev, path, line, rule, msg in findings:
        print(f"{sev:11} {path}:{line}  {rule:15} {msg}")
    if not findings:
        print("doc-refs: OK — no dead references.")
        return 0
    print(f"\ndoc-refs: {len(blocking)} blocking, {len(findings) - len(blocking)} to-confirm.")
    return 2 if blocking else 1


if __name__ == "__main__":
    sys.exit(main())
