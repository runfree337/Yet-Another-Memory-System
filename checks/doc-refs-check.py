#!/usr/bin/env python3
"""Dead references in the docs (universal, portable) — MECHANICAL half of doc freshness.

Catches a reference that points to nothing. SEMANTIC drift (does the prose describe the
real behavior?) is not mechanizable -> project review (tier 2).

Rules:
  R-DEAD-PATH     (BLOCKING/TO-CONFIRM) : a token that is clearly a "file path" (at least
                  one `/` + an extension) cited in a `.md` that does not/no longer exists.
                  Severity via git: a path with history = existed then disappeared ->
                  BLOCKING; never created -> TO-CONFIRM (might be planned, or a typo).
  R-DEAD-DECISION (BLOCKING) : a `D-YYYY-MM-DD-NN` id cited in a `.md` with no matching
                  `decisions/<id>.md` file. Resolved from the framework root, same as the
                  path rule above. INACTIVE (no findings) when the project has no
                  `decisions/` folder at all — nothing to check against.
  R-DEAD-SYMBOL   (TO-CONFIRM) : a backticked, composed PascalCase token (>= 2 capitalized
                  words, e.g. `FooBarManager` — filters out ordinary single words) not
                  found (grep-style) across the project's code, per `index/index-config.json`
                  (`roots` + `extensions`). AGNOSTIC/INACTIVE (no findings, no error) when
                  that config is absent or has no `roots`/`extensions` — the framework does
                  not hardcode a project's code layout.
  R-GHOST-ABSENCE (TO-CONFIRM) : the reverse drift — a line whose prose claims a symbol is
                  missing/not yet built ("not yet", "missing", "absent", "to be built",
                  "not wired", "pas encore", "manquant", "à créer"…) while the backticked
                  PascalCase symbol on that line DOES exist in the code ("delivered but the
                  doc doesn't know"). Same config gating as R-DEAD-SYMBOL. Trigger words
                  overlap `NEG` (which otherwise suppresses R-DEAD-PATH/R-DEAD-DECISION/
                  R-DEAD-SYMBOL on a line) by design: this rule is exactly what fires ON
                  those lines, it is never skipped by `NEG`.

Zero false positive on the firm (BLOCKING) tier; TO-CONFIRM is a pre-filter for judgment.
Flags, never fixes.

Exemptions (apply identically to all four rules above):
  - fenced code blocks (```…```) — illustrative, not a live reference.
  - `<!-- template -->` marker — line form exempts targets on that line; block form
    (`<!-- template -->` … `<!-- /template -->`) exempts every line in between.
  - `NEG` word list — a line already marked "deleted/renamed/to create/…" is not flagged
    as dead by R-DEAD-PATH/R-DEAD-DECISION/R-DEAD-SYMBOL (would be redundant with the
    prose). R-GHOST-ABSENCE is the deliberate exception (see above).

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

# Windows consoles default to cp1252: non-cp1252 output (→, ⨯…) would crash print().
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

FRAMEWORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # framework root
DECISIONS_DIR = os.path.join(FRAMEWORK, "decisions")
DECISIONS_INDEX = os.path.join(DECISIONS_DIR, "INDEX.md")

PATH_RE = re.compile(r"(?:[\w.\-]+/)+[\w.\-]+\.[A-Za-z0-9]{1,6}")
DECISION_RE = re.compile(r"D-\d{4}-\d{2}-\d{2}-\d{2}")
CODE_SPAN_RE = re.compile(r"`([^`]+)`")
# composed PascalCase: first char upper, >=4 chars total, >=2 uppercase letters overall
# (filters out ordinary single words like `Foo` or `Ok`).
PASCAL_RE = re.compile(r"^[A-Z][A-Za-z0-9]{3,}$")
TEMPLATE = re.compile(r"[<>{}*…]|YYYY|AAAA|XXXX|MM-|/\.\.\.")

# Prose words that neutralize a path/decision/symbol mention — both languages covered
# (docs may be authored in either while the corpus is being translated; keep both sets,
# never drop the French forms even once the English ones land).
NEG = ("n'existe", "nexiste", "supprim", "à créer", "a creer", "à porter", "a porter",
       "renomm", "à venir", "a venir", "exemple", "example", "template", "gabarit",
       "placeholder", "→", "->", "n'est pas", "plus tard", "déplacé", "deplace", "futur",
       "deleted", "removed", "to create", "to port", "renamed", "upcoming", "later",
       "moved", "future", "does not exist", "doesn't exist", "not yet", "not created",
       "planned")

# Trigger words for R-GHOST-ABSENCE — prose claiming a symbol is missing/not yet built.
# Deliberately overlaps NEG (bilingual spirit, same idea) but is its own list: this rule
# must still run on a NEG-flagged line, since that's precisely the drift it looks for.
GHOST_WORDS = ("not yet", "missing", "absent", "to be built", "not wired",
               "pas encore", "manquant", "à créer", "a creer")

# TEMPLATE exemption — explicit HTML marker, never a hidden allowlist in the script.
# (a) line  : "<!-- template -->" on a line exempts the paths on THAT line.
# (b) block : a "<!-- template -->" / "<!-- /template -->" pair exempts every line
#             (markers included) between the two. An opening marker never closed falls
#             back to case (a) — exempts only its own line.
TEMPLATE_OPEN = "<!-- template -->"
TEMPLATE_CLOSE = "<!-- /template -->"


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


def exists_somewhere(token, file_dir):
    return any(os.path.isfile(os.path.join(base, token))
               for base in (file_dir, FRAMEWORK, REPO, os.getcwd()))


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
    ordinary single words so common prose doesn't get flagged."""
    s = span.strip().split("(")[0].split("<")[0]
    s = s.strip(" .,;:'\"`")
    first = s.split(".")[0]
    if not PASCAL_RE.match(first):
        return None
    if sum(1 for c in first if c.isupper()) < 2:
        return None
    if TEMPLATE.search(first):  # gabarit placeholder (Xxx, YYYY…)
        return None
    return first


# --------------------------------------------------------------------------- #
# Code corpus for R-DEAD-SYMBOL / R-GHOST-ABSENCE — agnostic: the roots and
# extensions to search are never hardcoded here, they come from the project's
# own `index/index-config.json` (schema: `index/index-config.example.json`,
# same file `checks/index-check.py` loads). Absent/incomplete config -> both
# rules stay INACTIVE (no findings, no error): the framework does not assume
# the host project's code layout on its own.
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


def code_corpus():
    """Concatenated text of every file under the configured code roots/extensions — a
    grep-style "does this symbol exist" search space. Empty string (falsy) when
    `index/index-config.json` is absent or incomplete."""
    global _CODE_CORPUS
    if _CODE_CORPUS is not None:
        return _CODE_CORPUS
    cfg = _load_code_index_config()
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
    is_decisions_index = (os.path.basename(path) == "INDEX.md"
                           and os.path.dirname(os.path.abspath(path)) == DECISIONS_DIR)

    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced or i in exempt:
            continue
        low = line.lower()
        neg = any(m in low for m in NEG)

        # R-DEAD-PATH
        if not neg:
            for tok in PATH_RE.findall(line.replace("`", " ")):
                if TEMPLATE.search(tok) or "://" in tok or exists_somewhere(tok, file_dir):
                    continue
                sev = "BLOCKING" if had_history(tok) else "TO-CONFIRM"
                findings.append((sev, path, i, "R-DEAD-PATH", f"path not found: {tok}"))

        # R-DEAD-DECISION — the decisions/INDEX.md file IS the registry, skip it (avoids
        # duplicating decisions-check.py's own file<->index concordance rule).
        if not neg and os.path.isdir(DECISIONS_DIR) and not is_decisions_index:
            for did in DECISION_RE.findall(line):
                if not decision_exists(did):
                    findings.append(("BLOCKING", path, i, "R-DEAD-DECISION",
                                     f"decision id with no decisions/{did}.md file: {did}"))

        # R-DEAD-SYMBOL — inactive (corpus falsy) when index-config.json is absent/incomplete.
        if not neg and corpus:
            seen = set()
            for m in CODE_SPAN_RE.finditer(line):
                sym = _candidate_symbol(m.group(1))
                if sym and sym not in seen and sym not in corpus:
                    seen.add(sym)
                    findings.append(("TO-CONFIRM", path, i, "R-DEAD-SYMBOL",
                                     f"symbol not found under the configured code roots: {sym}"))

        # R-GHOST-ABSENCE — deliberately NOT gated by `neg`: it fires exactly on the lines
        # NEG would otherwise suppress. Same config gating as R-DEAD-SYMBOL.
        if corpus and any(w in low for w in GHOST_WORDS):
            seen = set()
            for m in CODE_SPAN_RE.finditer(line):
                sym = _candidate_symbol(m.group(1))
                if sym and sym not in seen and sym in corpus:
                    seen.add(sym)
                    findings.append(("TO-CONFIRM", path, i, "R-GHOST-ABSENCE",
                                     f"doc claims {sym} is missing/not built, but it exists "
                                     "in code"))
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
