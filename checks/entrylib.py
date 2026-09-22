#!/usr/bin/env python3
"""Shared "memory entry" library — NOT a standalone check, stdlib only.

Generalizes the pattern carried by `memory-check.py` (frontmatter + file<->index
concordance) to every memory channel (`ENTRY-TEMPLATE.md`): Memory, Decision, Feature,
Backlog. Channel checks import this lib instead of redefining their own parser/regex —
**a single place** defines what a valid memory entry is.

Follows `checks/TEMPLATE.md`: 5-field `Finding` namedtuple, two verdicts
(`BLOCKING-AUTO` / `TO-CONFIRM`), pure rules, no side effects.

Frontmatter vocabulary — keys/values in ENGLISH by design (machine API, greppable;
the body prose stays in the team's own language, cf. `ENTRY-TEMPLATE.md`):
  id, status, source, confidence, created, updated, links, ratified
  source     : inferred | human | external:<ref>
  confidence : verified | unverified
  ratified   : <who>, <YYYY-MM-DD>  — required to move to confidence: verified

Usage:
  import sys; sys.path.insert(0, "checks"); import entrylib   # from another check
  python3 checks/entrylib.py --selftest                       # only executable mode
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import namedtuple

# Windows consoles default to cp1252: non-cp1252 output (→, ⨯…) would crash print().
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# --------------------------------------------------------------------------- #
# The template (checks/TEMPLATE.md) — Finding + two verdicts.                 #
# --------------------------------------------------------------------------- #

BLOCKING = "BLOCKING-AUTO"
TO_CONFIRM = "TO-CONFIRM"

Finding = namedtuple("Finding", "severity rule path line msg")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SOURCE_RE = re.compile(r"^(inferred|human|external:.+)$")
CONFIDENCE_VALUES = {"verified", "unverified"}


# --------------------------------------------------------------------------- #
# Global settings — checks-config.json at the repo root (optional).           #
# One file, one section per concern (audit / sizes / guards); absent file =   #
# every consumer falls back to its built-in defaults (today's behavior).      #
# Canonical schema + defaults: checks-config.example.json at the repo root.   #
# --------------------------------------------------------------------------- #

CHECKS_CONFIG_NAME = "checks-config.json"


def load_checks_config(root: str):
    """Reads `<root>/checks-config.json` — the optional global settings file.

    Returns `(config, error)`: `({}, None)` if the file is absent (defaults apply),
    `({}, "message")` if present but broken (unreadable, invalid JSON, top level not
    an object) — the caller surfaces that as a BLOCKING `CFG-INVALID` finding rather
    than silently ignoring a config the user believes active. Never raises.
    """
    path = os.path.join(root, CHECKS_CONFIG_NAME)
    if not os.path.isfile(path):
        return {}, None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as e:
        return {}, f"{CHECKS_CONFIG_NAME}: unreadable ({e})"
    if not isinstance(data, dict):
        return {}, f"{CHECKS_CONFIG_NAME}: top level must be a JSON object"
    return data, None


def cfg_get(cfg: dict, path, default):
    """Nested lookup: `cfg_get(cfg, ("sizes", "memory-entry-max-lines"), 40)`.

    Returns `default` when the path is missing or the value's type doesn't match
    the default's (a string where a number is expected is a typo, not a setting;
    a JSON `true` is never accepted for a number). Keys starting with `_` are
    comments by convention (`_README`, `_comment`) and are simply never looked up.
    """
    cur = cfg
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    if isinstance(default, bool) != isinstance(cur, bool):
        return default
    if default is not None and not isinstance(cur, type(default)):
        return default
    return cur


# --------------------------------------------------------------------------- #
# Per-channel spec — required/optional keys + channel-specific enums.         #
# Common vocabulary (id/source/confidence/created/updated/links/ratified)     #
# validated by generic rules; `enums` only carries the keys SPECIFIC to the   #
# channel (e.g. `status`) whose values vary from one channel to the next.     #
# --------------------------------------------------------------------------- #

CHANNELS = {
    "memory": {
        "required": ("id", "source", "confidence", "created", "updated"),
        "optional": ("links", "ratified"),
        "enums": {},
        "nullable": (),
    },
    "decision": {
        "required": ("id", "status", "source", "confidence", "created", "updated"),
        "optional": ("links", "replaces", "replaced-by", "ratified"),
        "enums": {"status": {"active", "revoked", "archived"}},
        "nullable": (),
    },
    "feature": {
        "required": ("id", "created", "updated"),
        "optional": ("links", "source", "confidence", "ratified"),
        "enums": {},
        "nullable": (),
    },
    "backlog": {
        "required": ("id", "status", "title", "milestone", "updated"),
        "optional": ("links", "source", "confidence", "ratified", "after", "docs", "created", "impacts"),
        "enums": {"status": {"todo", "in-progress"}},
        "nullable": ("milestone",),
    },
}


# --------------------------------------------------------------------------- #
# Minimal homegrown frontmatter parser — no yaml dependency.                  #
# --------------------------------------------------------------------------- #

def _parse_scalar(val: str):
    """A scalar value or an inline list `[a, b]`. Never nested YAML."""
    val = val.strip()
    if val in ("", "null", "~"):
        return None
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        return [x.strip().strip("'\"") for x in inner.split(",") if x.strip()] if inner else []
    return val.strip("'\"")


def parse_frontmatter(text: str):
    """`--- … ---` block at the top of the file, scalar `key: value` + inline `[a, b]` lists.

    Returns `(meta, body, error)`: `meta` is `{}` and `error` is not `None` if the block is
    missing or never closed. `body` is the text after the block (empty string if no block).
    Never raises.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, "no frontmatter block (no --- on the first line)"

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, "", "frontmatter block never closed (no second ---)"

    meta = {}
    for line in lines[1:end]:
        raw = line.strip()
        if not raw or raw.startswith("#") or ":" not in raw:
            continue
        key, _, val = line.partition(":")
        meta[key.strip()] = _parse_scalar(val)

    body = "\n".join(lines[end + 1:])
    return meta, body, None


# --------------------------------------------------------------------------- #
# Entry validation — rules common to every channel.                           #
# --------------------------------------------------------------------------- #

def validate_entry(path: str, meta: dict, channel: str) -> list:
    """Validates the `meta` frontmatter of an entry `path` against channel `channel`.

    Rules (stable, grep-able ids — see file header for details):
      R-NO-FRONTMATTER, R-MISSING-KEY, R-BAD-VALUE, R-EXT-NO-CONF, R-UNVERIFIED,
      R-VERIFIED-NOT-RATIFIED, R-BAD-DATE.
    Raises `ValueError` if `channel` is not in `CHANNELS`.
    """
    spec = CHANNELS.get(channel)
    if spec is None:
        raise ValueError(f"unknown channel: {channel!r} (expected: {', '.join(sorted(CHANNELS))})")

    findings = []

    if not meta:
        findings.append(Finding(BLOCKING, "R-NO-FRONTMATTER", path, 1,
                                 "no --- ... --- frontmatter at the top of the file"))
        return findings

    nullable = set(spec.get("nullable", ()))
    for key in spec["required"]:
        val = meta.get(key)
        missing = key not in meta or val == "" or (val is None and key not in nullable)
        if missing:
            findings.append(Finding(BLOCKING, "R-MISSING-KEY", path, 1,
                                     f"required key « {key} » missing or empty for channel « {channel} »"))

    for key, allowed in spec.get("enums", {}).items():
        val = meta.get(key)
        if val is not None and val not in allowed:
            findings.append(Finding(BLOCKING, "R-BAD-VALUE", path, 1,
                                     f"« {key}: {val} » invalid for channel « {channel} » "
                                     f"(expected: {' | '.join(sorted(allowed))})"))

    source = meta.get("source")
    if source is not None and not SOURCE_RE.match(str(source).strip()):
        findings.append(Finding(BLOCKING, "R-BAD-VALUE", path, 1,
                                 f"« source: {source} » invalid (expected: inferred | human | external:<ref>)"))

    confidence = meta.get("confidence")
    if confidence is not None and confidence not in CONFIDENCE_VALUES:
        findings.append(Finding(BLOCKING, "R-BAD-VALUE", path, 1,
                                 f"« confidence: {confidence} » invalid (expected: verified | unverified)"))

    if source and str(source).strip().startswith("external:") and not confidence:
        findings.append(Finding(BLOCKING, "R-EXT-NO-CONF", path, 1,
                                 "source: external:... with no confidence field"))

    if confidence == "unverified":
        findings.append(Finding(TO_CONFIRM, "R-UNVERIFIED", path, 1,
                                 "confidence: unverified — candidate for semantic audit (tier 2)"))

    if confidence == "verified" and not meta.get("ratified"):
        findings.append(Finding(TO_CONFIRM, "R-VERIFIED-NOT-RATIFIED", path, 1,
                                 "confidence: verified with no ratified field — ratification not tracked"))

    for key in ("created", "updated"):
        val = meta.get(key)
        if val is not None and not DATE_RE.match(str(val)):
            findings.append(Finding(BLOCKING, "R-BAD-DATE", path, 1,
                                     f"« {key}: {val} » malformed (expected YYYY-MM-DD)"))

    return findings


# --------------------------------------------------------------------------- #
# File <-> index concordance — generalization of memory-check/decisions-check #
# --------------------------------------------------------------------------- #

def check_index_concordance(index_path: str, entries_dir: str, id_pattern) -> list:
    """Every entry file referenced by the index, every index reference resolved.

    `id_pattern` (str or compiled regex) extracts a comparable identifier from both the
    file names of `entries_dir` (matched against the bare name) and the text of
    `index_path` (matched against each line). Same pattern as `memory-check.py`
    (`memory/<slug>.md` files <=> `MEMORY.md` links) and `decisions-check.py` (`D-*.md`
    files <=> `decisions/INDEX.md` ids), generalized to the channel supplied by the caller.
    """
    pat = re.compile(id_pattern) if isinstance(id_pattern, str) else id_pattern
    findings = []

    files = {}
    if os.path.isdir(entries_dir):
        for fname in sorted(os.listdir(entries_dir)):
            if not fname.endswith(".md"):
                continue
            m = pat.search(fname)
            if m:
                files[m.group(0)] = fname

    indexed = set()
    reported = set()  # a dead id is reported only once, even if repeated (e.g. `[id](id.md)`)
    if os.path.isfile(index_path):
        with open(index_path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                for m in pat.finditer(line):
                    idv = m.group(0)
                    indexed.add(idv)
                    if idv not in files and idv not in reported:
                        reported.add(idv)
                        findings.append(Finding(BLOCKING, "R-DEAD-INDEX", index_path, lineno,
                                                 f"reference « {idv} » — no file found in {entries_dir}"))

    for idv, fname in sorted(files.items()):
        if idv not in indexed:
            findings.append(Finding(BLOCKING, "R-ORPHAN-FILE", os.path.join(entries_dir, fname), 1,
                                     f"exists but is referenced by no line of {index_path}"))

    return findings


# --------------------------------------------------------------------------- #
# Index entries & size guards — shared engine of the granularity signals      #
# (`I-ENTRY-LEN` / `D9` / `D10` / `M-GRAN` / `M-INDEX-LEN` / `FM-GRAN`).      #
# One place defines what an "entry" is and what counts as content.            #
# --------------------------------------------------------------------------- #

BRACKETED_RE = re.compile(r"\[[^\]]*\]")


def useful_body_lines(body: str) -> list:
    """Lines that count as CONTENT for the body-size signals: blank lines and Markdown
    table separator rows (`|---`) excluded — keeps the channels' line counts directly
    comparable (`FM-GRAN` / `M-GRAN` / `D9` all read this one filter)."""
    return [l for l in body.splitlines() if l.strip() and not l.strip().startswith("|---")]


def index_entries(text: str) -> list:
    """Splits an index file into its ENTRIES: a top-level `- ` bullet plus every
    following indented, non-blank line (wrapped prose or nested detail), ended by a
    blank line, a heading, or the next top-level bullet. Returns
    `[(lineno of the bullet, folded text)]`.

    An indented bullet is CONTINUATION — nested detail counts against its host entry —
    and a file whose bullets are all indented yields nothing: zero-FP over recall."""
    entries, cur = [], None
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.startswith("- "):
            if cur:
                entries.append(tuple(cur))
            cur = [lineno, line]
        elif cur and line[:1] in (" ", "\t") and line.strip():
            cur[1] += " " + line.strip()
        else:
            if cur:
                entries.append(tuple(cur))
            cur = None
    if cur:
        entries.append(tuple(cur))
    return entries


def entry_prose_words(entry_text: str) -> int:
    """Word count of an index entry, `[…]` tokens excluded — status badges (`[todo]`),
    tag blocks (`[combat]`) and link texts (`[D-…](D-….md)`) are machine labels, not
    the prose the size guards bound."""
    return len(BRACKETED_RE.sub(" ", entry_text).split())


def check_index_entry_len(index_path: str, root: str, max_words: int, rule: str,
                          what: str) -> list:
    """TO-CONFIRM size guard over every entry of an index file — an index line stays
    factual and short (title + target + gist); detail and history belong elsewhere.
    `what` names, per channel, where the overflow content lives. Missing index ->
    no findings (the concordance rules already own that case)."""
    if not os.path.isfile(index_path):
        return []
    with open(index_path, encoding="utf-8") as fh:
        text = fh.read()
    relpath = os.path.relpath(index_path, root)
    findings = []
    for lineno, entry in index_entries(text):
        words = entry_prose_words(entry)
        if words > max_words:
            findings.append(Finding(TO_CONFIRM, rule, relpath, lineno,
                                     f"{words}-word entry (> {max_words}, `[…]` tokens "
                                     f"excluded) — an index line stays factual and short; "
                                     f"{what}"))
    return findings


# --------------------------------------------------------------------------- #
# Stamp — rewrites `updated` and nothing else.                                #
# --------------------------------------------------------------------------- #

def stamp_updated(path: str, date_str: str) -> bool:
    """Rewrites the `updated` frontmatter field of `path` (and only that field).

    Shared `--stamp` pattern (cf. `backlog-check.py --stamp`). Returns `True` if the file
    was modified, `False` if `updated` was already `date_str` (or the field/frontmatter
    is absent — no-op). Strictly bounded to the `--- … ---` block: an `updated:` line in
    the BODY (e.g. a quoted template) is never touched.
    """
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return False
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return False
    for i in range(1, end):
        if lines[i].startswith("updated:"):
            new_line = f"updated: {date_str}\n"
            if lines[i] == new_line:
                return False
            lines[i] = new_line
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("".join(lines))
            return True
    return False


def git_env() -> dict:
    """Environment for the stamp chain's git subprocesses: `GIT_DIR`/`GIT_WORK_TREE`
    purged, everything else (notably `GIT_INDEX_FILE`) kept.

    Git exports `GIT_DIR` to its hooks, and under `GIT_DIR` repository discovery is
    short-circuited: `git rev-parse --show-toplevel` returns the CWD. Called from a
    nested framework dir (`docs/`…), `repo_root` would then take that dir for the repo
    root and the `--staged` selector would silently select NOTHING — the exact mute
    `stamp_targets` exists to prevent, resurrected by the environment. Purging here
    rather than in every caller means no caller has to remember the discipline.
    `GIT_INDEX_FILE` is KEPT on purpose: under a pre-commit hook it names the index
    being committed — the one `git diff --cached` must read and the re-stage `git add`
    must write to (`git commit -a` exports `index.lock`, which BECOMES the real index).
    """
    return {k: v for k, v in os.environ.items()
            if k not in ("GIT_DIR", "GIT_WORK_TREE")}


_IS_SHALLOW = None


def is_shallow(cwd: str = None) -> bool:
    """True when the enclosing clone has a TRUNCATED history (`git clone --depth=N`).

    Why every git-reading rule must ask this first: under a shallow clone the boundary
    commit has no visible parent, so git answers questions about history with confident
    LIES rather than with an error. Two shapes, measured 2026-09-22 on a synthetic repo:

      * `git log -1 --format=%cs -- <path>` on a file untouched since before the
        boundary returns the BOUNDARY's date, not the file's — git treats that commit
        as having introduced every file in its tree. A file last touched 2026-01-15
        reported 2026-09-22. This is what makes `*-FRESH` rules cry wolf (measured on
        a real repo: 15 phantom findings out of 18).
      * `git log --all -- <path>` on a file genuinely created then deleted before the
        boundary returns NOTHING — "never existed" is indistinguishable from "deleted".
        This one is worse: it silently DOWNGRADES a severity that depends on history.

    Neither is a git bug: a shallow clone simply does not carry the answer. The defect
    is a check that cannot tell "no" from "I cannot see". `git clone --depth=1` is the
    default of `actions/checkout` and of several hosted agent sandboxes, so this is the
    common case in CI, not an exotic one.

    Cached: the answer cannot change within a run, and every rule asks.
    """
    global _IS_SHALLOW
    if _IS_SHALLOW is None:
        try:
            r = subprocess.run(["git", "rev-parse", "--is-shallow-repository"],
                               cwd=cwd, env=git_env(), capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=10)
            _IS_SHALLOW = r.stdout.strip() == "true"
        except Exception:
            _IS_SHALLOW = False   # no git at all: the git-reading rules already no-op
    return _IS_SHALLOW


SHALLOW_NOTICE = ("note: the clone is SHALLOW — history-dependent rules are degraded "
                  "(see `entrylib.is_shallow`). Deepen it (`git fetch --unshallow`, or "
                  "`--shallow-since=<date>`) before trusting this run on those rules.")


def git_last_commit_date(relpath: str, cwd: str = None) -> str | None:
    """Date (`%cs`) of the last commit touching `relpath`, or None when unknowable.

    Returns None on a SHALLOW clone: the answer git would give is the boundary commit's
    date (see `is_shallow`), and a freshness rule fed that date reports every untouched
    file as stale. Callers already treat None as "unversioned -> skip the rule", so the
    truncated clone lands in the branch that stays quiet instead of the one that lies.

    Single home on purpose: this function was written TWICE, byte for byte, in
    `backlog-check.py` (E-STATE-FRESH) and `feature-map-check.py` (FM-FRESH). Two copies
    of one question is a feature with no home — and the guard above would have had to be
    written twice, which is exactly how the two channels drift apart again.
    """
    if is_shallow(cwd):
        return None
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%cs", "--", relpath],
                           cwd=cwd, env=git_env(), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=10)
    except Exception:
        return None
    out = r.stdout.strip()
    return out or None


def repo_root(start: str = None) -> str:
    """Absolute path of the enclosing git repository, or `start` when there is no git.

    The framework root is NOT the repo root: a host project may nest this framework in a
    subdirectory (`docs/`, `tooling/`…). Anything that talks to git needs the repo root,
    anything that reads framework files needs the framework root — conflating them is the
    bug `stamp_targets` exists to prevent. Mirrors `doc-refs-check.py`'s resolution, which
    is why that check was the only one immune. Runs git under `git_env()` so the answer
    holds inside a git hook too (exported `GIT_DIR` short-circuits discovery).
    """
    start = start or os.getcwd()
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start,
                             env=git_env(),
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=10).stdout.strip()
        return os.path.realpath(out) if out else start
    except Exception:
        return start


def stamp_targets(framework: str, argv: list, prefix: str, match) -> tuple:
    """Resolves what `--stamp` should stamp. Returns `(files, unresolved)`, `files` being
    FRAMEWORK-relative paths (what the callers' stamp loop joins onto their root).

    Two selectors, one contract — every returned path is framework-relative, whatever the
    caller passed or git printed:

    - `--staged`: staged files under `<framework>/<prefix>` matching `match(basename)`.
      **`git diff --name-only` prints REPO-relative paths, never cwd-relative** (that
      needs `--relative`). So the filter has to be applied in repo space and the hits
      translated back — a `prefix`-only filter run from the framework dir can never match
      when the framework is nested, and silently selects NOTHING while exiting 0.
    - explicit paths: accepted framework-relative, repo-relative, or absolute. Anything
      that resolves to no file lands in `unresolved` so the caller can SAY so — a stamp
      that cannot select its target must never look like a stamp that found none.

    `unresolved` is always empty for `--staged` (git only ever names existing files).

    A git call that THROWS is said on stderr before returning empty: a selector that
    cannot select must never look like a selector that found nothing to do — the callers
    print their count on stdout, which every reasonable hook redirects, so a silent
    `[], []` here would make a selector regression invisible again.
    """
    framework = os.path.realpath(framework)
    if "--staged" in argv:
        repo = repo_root(framework)
        rel = os.path.relpath(framework, repo).replace(os.sep, "/")
        base = "" if rel in (".", "") else rel + "/"
        try:
            out = subprocess.run(["git", "diff", "--cached", "--name-only",
                                  "--diff-filter=ACM"], cwd=repo, env=git_env(),
                                 capture_output=True,
                                 text=True, encoding="utf-8", errors="replace",
                                 timeout=30).stdout
        except Exception as e:
            print(f"stamp: staged selection failed ({e.__class__.__name__}: {e}) "
                  "— nothing selected, nothing stamped.", file=sys.stderr)
            return [], []
        wanted = base + prefix
        files = []
        for line in out.splitlines():
            p = line.strip().replace("\\", "/")
            if p.startswith(wanted) and match(os.path.basename(p)):
                files.append(p[len(base):] if base else p)
        return files, []

    files, unresolved = [], []
    for a in argv[argv.index("--stamp") + 1:]:
        if a.startswith("-"):
            continue
        p = a.replace("\\", "/")
        if os.path.isabs(p):
            cand = [p]
        else:
            # Framework-relative FIRST: it is the documented form, and it is what
            # `--staged` returns — so both selectors feed the loop the same shape.
            cand = [os.path.join(framework, p),
                    os.path.join(repo_root(framework), p)]
        hit = next((c for c in cand if os.path.isfile(c)), None)
        if hit is None:
            unresolved.append(a)
        else:
            rel = os.path.relpath(os.path.realpath(hit), framework).replace(os.sep, "/")
            files.append(rel)
    return files, unresolved


DECISION_ID = re.compile(r"^D-\d{4}-\d{2}-\d{2}-\d{2}$")


def check_links(path: str, meta: dict, root: str) -> list:
    """Resolves the `links:` of an entry — cross-channel references.

    Three recognized forms: a decision id `D-YYYY-MM-DD-NN` (-> `decisions/<id>.md` must
    exist), a path (contains `/` or an extension -> the file/directory must exist from
    `root`), otherwise an entry slug (-> looked up in `memory/`, `features/`,
    `backlog/<slug>/`). A dead id/path = `R-DEAD-LINK` (blocking); a dead slug =
    to-confirm (the target channel might just not be populated yet).
    """
    findings = []
    links = meta.get("links") or []
    if isinstance(links, str):
        links = [links]
    for link in links:
        link = str(link).strip()
        if not link:
            continue
        if DECISION_ID.match(link):
            if not os.path.isfile(os.path.join(root, "decisions", link + ".md")):
                findings.append(Finding(BLOCKING, "R-DEAD-LINK", path, 1,
                                        f"links: decision « {link} » has no decisions/{link}.md file"))
        elif "/" in link or "." in link:
            if not os.path.exists(os.path.join(root, link)):
                findings.append(Finding(BLOCKING, "R-DEAD-LINK", path, 1,
                                        f"links: path « {link} » not found"))
        else:
            candidates = (os.path.join(root, "memory", link + ".md"),
                          os.path.join(root, "features", link + ".md"),
                          os.path.join(root, "backlog", link))
            if not any(os.path.exists(c) for c in candidates):
                findings.append(Finding(TO_CONFIRM, "R-DEAD-LINK", path, 1,
                                        f"links: entry « {link} » not found (memory/, features/, backlog/)"))
    return findings


# --------------------------------------------------------------------------- #
# --selftest — embedded test suite, no effect when imported.                  #
# --------------------------------------------------------------------------- #

def _selftest() -> int:
    import tempfile

    failures = []

    def check(cond, label):
        if not cond:
            failures.append(label)

    # parse_frontmatter — valid block, scalar, inline list, body after the block
    meta, body, err = parse_frontmatter("---\nid: mem-1\nlinks: [a, b]\n---\nbody\n")
    check(err is None, "parse_frontmatter: no error on valid block")
    check(meta.get("id") == "mem-1", "parse_frontmatter: scalar id")
    check(meta.get("links") == ["a", "b"], "parse_frontmatter: inline list")
    check(body.strip() == "body", "parse_frontmatter: body after the block")

    # parse_frontmatter — no block / block never closed
    meta2, _, err2 = parse_frontmatter("no frontmatter\n")
    check(err2 is not None and meta2 == {}, "parse_frontmatter: error + empty meta if no block")
    _, _, err3 = parse_frontmatter("---\nid: x\n")
    check(err3 is not None, "parse_frontmatter: error if block never closed")

    # validate_entry — R-NO-FRONTMATTER
    f = validate_entry("f.md", {}, "memory")
    check(len(f) == 1 and f[0].rule == "R-NO-FRONTMATTER", "validate_entry: R-NO-FRONTMATTER")

    # validate_entry — R-MISSING-KEY
    f = validate_entry("f.md", {"id": "x"}, "memory")
    check(any(x.rule == "R-MISSING-KEY" for x in f), "validate_entry: R-MISSING-KEY")

    # validate_entry — R-BAD-VALUE (status enum specific to the decision channel)
    meta_dec = {"id": "D-2026-01-01-01", "status": "bogus", "source": "human",
                "confidence": "verified", "ratified": "raph, 2026-01-01",
                "created": "2026-01-01", "updated": "2026-01-01"}
    f = validate_entry("d.md", meta_dec, "decision")
    check(any(x.rule == "R-BAD-VALUE" for x in f), "validate_entry: R-BAD-VALUE (status)")

    # validate_entry — R-EXT-NO-CONF
    meta_ext = {"id": "mem-2", "source": "external:https://x", "created": "2026-01-01", "updated": "2026-01-01"}
    f = validate_entry("m.md", meta_ext, "memory")
    check(any(x.rule == "R-EXT-NO-CONF" for x in f), "validate_entry: R-EXT-NO-CONF")

    # validate_entry — R-UNVERIFIED
    meta_unv = {"id": "mem-3", "source": "human", "confidence": "unverified",
                "created": "2026-01-01", "updated": "2026-01-01"}
    f = validate_entry("m.md", meta_unv, "memory")
    check(any(x.rule == "R-UNVERIFIED" and x.severity == TO_CONFIRM for x in f),
          "validate_entry: R-UNVERIFIED")

    # validate_entry — R-VERIFIED-NOT-RATIFIED
    meta_verif = {"id": "mem-4", "source": "human", "confidence": "verified",
                  "created": "2026-01-01", "updated": "2026-01-01"}
    f = validate_entry("m.md", meta_verif, "memory")
    check(any(x.rule == "R-VERIFIED-NOT-RATIFIED" for x in f),
          "validate_entry: R-VERIFIED-NOT-RATIFIED")

    # validate_entry — R-BAD-DATE
    meta_date = {"id": "mem-5", "source": "human", "confidence": "verified",
                 "ratified": "raph, 2026-01-01", "created": "2026/01/01", "updated": "2026-01-01"}
    f = validate_entry("m.md", meta_date, "memory")
    check(any(x.rule == "R-BAD-DATE" for x in f), "validate_entry: R-BAD-DATE")

    # validate_entry — unknown channel
    try:
        validate_entry("m.md", {"id": "x"}, "unknown")
        check(False, "validate_entry: must raise ValueError on unknown channel")
    except ValueError:
        check(True, "validate_entry: raises ValueError on unknown channel")

    # check_index_concordance — orphan + dead link, on tempfile fixtures
    with tempfile.TemporaryDirectory() as td:
        entries_dir = os.path.join(td, "memory")
        os.makedirs(entries_dir)
        with open(os.path.join(entries_dir, "orphan-fact.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nid: orphan-fact\n---\n")
        index_path = os.path.join(td, "MEMORY.md")
        with open(index_path, "w", encoding="utf-8") as fh:
            fh.write("- [dead-fact](memory/dead-fact.md) — does not exist\n")
        findings = check_index_concordance(index_path, entries_dir, r"[\w.\-]+\.md")
        check(any(x.rule == "R-ORPHAN-FILE" for x in findings), "check_index_concordance: R-ORPHAN-FILE")
        check(any(x.rule == "R-DEAD-INDEX" for x in findings), "check_index_concordance: R-DEAD-INDEX")

    # stamp_updated — rewrites updated alone, no-op if already up to date
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "entry.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("---\nid: x\nupdated: 2020-01-01\n---\nbody\n")
        ok = stamp_updated(p, "2026-07-09")
        check(ok, "stamp_updated: reports a modification")
        with open(p, encoding="utf-8") as fh:
            text = fh.read()
        check("updated: 2026-07-09" in text, "stamp_updated: date rewritten")
        check("id: x" in text, "stamp_updated: other keys untouched")
        check(not stamp_updated(p, "2026-07-09"), "stamp_updated: no-op if already up to date")

    # stamp_updated — an `updated:` line in the BODY is never touched (frontmatter only)
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "entry.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("---\nid: x\n---\nquoted template:\nupdated: 2020-01-01\n")
        check(not stamp_updated(p, "2026-07-09"),
              "stamp_updated: no-op when the frontmatter has no updated field")
        with open(p, encoding="utf-8") as fh:
            check("updated: 2020-01-01" in fh.read(),
                  "stamp_updated: body updated: line untouched")

    # check_index_concordance — a dead id repeated on the same line doesn't double the finding
    with tempfile.TemporaryDirectory() as td:
        d = os.path.join(td, "entries")
        os.makedirs(d)
        idx = os.path.join(td, "INDEX.md")
        with open(idx, "w", encoding="utf-8") as fh:
            fh.write("- [D-2099-01-01-01](D-2099-01-01-01.md) — ghost\n")
        fs = check_index_concordance(idx, d, r"D-\d{4}-\d{2}-\d{2}-\d{2}")
        check(len(fs) == 1, "concordance: repeated dead id on the line -> a single finding")

    # load_checks_config — absent, valid, broken JSON, non-object top level
    with tempfile.TemporaryDirectory() as td:
        cfg, err = load_checks_config(td)
        check(cfg == {} and err is None, "load_checks_config: absent file -> ({}, None)")
        p = os.path.join(td, CHECKS_CONFIG_NAME)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write('{"sizes": {"memory-entry-max-lines": 25}}')
        cfg, err = load_checks_config(td)
        check(err is None and cfg.get("sizes", {}).get("memory-entry-max-lines") == 25,
              "load_checks_config: valid file parsed")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("{broken")
        cfg, err = load_checks_config(td)
        check(cfg == {} and err is not None, "load_checks_config: broken JSON -> ({}, error)")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write('[1, 2]')
        cfg, err = load_checks_config(td)
        check(cfg == {} and err is not None, "load_checks_config: non-object top level -> error")

    # cfg_get — hit, miss, type mismatch, bool-vs-int, nested miss
    cfg = {"sizes": {"memory-entry-max-lines": 25, "bad": "40", "flag": True}}
    check(cfg_get(cfg, ("sizes", "memory-entry-max-lines"), 40) == 25, "cfg_get: nested hit")
    check(cfg_get(cfg, ("sizes", "absent"), 40) == 40, "cfg_get: missing key -> default")
    check(cfg_get(cfg, ("audit", "batch-size"), 33) == 33, "cfg_get: missing section -> default")
    check(cfg_get(cfg, ("sizes", "bad"), 40) == 40, "cfg_get: type mismatch -> default")
    check(cfg_get(cfg, ("sizes", "flag"), 40) == 40, "cfg_get: JSON true never a number")
    check(cfg_get({}, ("guards", "extra-watched-files"), []) == [], "cfg_get: empty cfg -> default list")

    # check_links — decision id, path, slug; dead and alive
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "decisions"))
        os.makedirs(os.path.join(td, "memory"))
        with open(os.path.join(td, "decisions", "D-2026-01-01-01.md"), "w") as fh:
            fh.write("x")
        with open(os.path.join(td, "memory", "rule-a.md"), "w") as fh:
            fh.write("x")
        meta = {"links": ["D-2026-01-01-01", "memory/rule-a.md", "rule-a"]}
        check(check_links("e.md", meta, td) == [], "check_links: alive links -> no finding")
        meta = {"links": ["D-2099-01-01-01", "memory/absent.md", "unknown-slug"]}
        fs = check_links("e.md", meta, td)
        check(len(fs) == 3, "check_links: 3 dead links -> 3 findings")
        check(sum(1 for f in fs if f.severity == BLOCKING) == 2,
              "check_links: dead id/path are blocking")
        check(sum(1 for f in fs if f.rule == "R-DEAD-LINK") == 3, "check_links: R-DEAD-LINK rule")

    # useful_body_lines — blanks and table separators excluded
    check(useful_body_lines("a\n\n|---|\n| b |\n") == ["a", "| b |"],
          "useful_body_lines: blanks and |--- rows excluded")

    # index_entries — folding, terminators, nested bullets
    idx_text = ("# T\n"
                "- one two three\n"
                "  four five\n"
                "\n"
                "prose outside any entry\n"
                "- [todo] six `x/`\n"
                "  - nested seven\n"
                "## H\n"
                "- eight\n")
    ents = index_entries(idx_text)
    check([ln for ln, _ in ents] == [2, 6, 9], "index_entries: bullet linenos, terminators honored")
    check(ents[0][1] == "- one two three four five", "index_entries: continuation folded in")
    check("nested seven" in ents[1][1], "index_entries: nested bullet folds into its host")

    # entry_prose_words — bracketed tokens excluded
    check(entry_prose_words("- [todo] a b [tag] c") == 4,
          "entry_prose_words: badges/tags excluded from the count")

    # check_index_entry_len — only the oversized entry, at its bullet line
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "IDX.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("- short one\n- " + " ".join(["w"] * 61) + "\n")
        fs = check_index_entry_len(p, td, 60, "X-LEN", "detail lives elsewhere.")
        check([(f.rule, f.line, f.severity) for f in fs] == [("X-LEN", 2, TO_CONFIRM)],
              "check_index_entry_len: one finding, oversized bullet's line, to-confirm")
        check(check_index_entry_len(os.path.join(td, "absent.md"), td, 60, "X", "y") == [],
              "check_index_entry_len: missing index -> no findings")

    if failures:
        print(f"entrylib --selftest: {len(failures)} failure(s):")
        for label in failures:
            print(f"  - {label}")
        return 1
    print("entrylib --selftest: OK.")
    return 0


def main(argv) -> int:
    if "--selftest" in argv:
        return _selftest()
    print("usage: python3 checks/entrylib.py --selftest   "
          "(shared library — imported by channel checks, not a standalone check)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
