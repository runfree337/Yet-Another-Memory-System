#!/usr/bin/env python3
"""memory-graph — the derived memory graph engine (stdlib only, portable: no
third-party YAML/graph library).

The four memory channels (`decisions/`, `features/`, `memory/`, `backlog/`)
already each carry their own frontmatter + free-prose body (`ENTRY-TEMPLATE.md`).
This script does not add a fifth channel or a new storage format — it reads the
four **as they already are** and derives a typed graph over them, on every
invocation:

  - **decision**  `decisions/D-*.md` frontmatter (id, status, links, replaces,
    replaced-by) + `decisions/INDEX.md` (short title + tags of the matching
    `- [id](...)` entry line, and whether it sits under `## Active` or
    `## Archived`).
  - **feature**   `features/*.md` frontmatter (id, links) + the `**Role:**`
    line + every backticked path cited in the body (a backticked span
    containing `/`, e.g. `Scripts/Combat/CombatManager.cs` — including a single
    `{a,b,c}` brace alternation, the sibling-files shorthand).
  - **memory**    `memory/*.md` frontmatter (id, links) only.
  - **backlog**   `backlog/*/STATE.md` frontmatter (id, title, status, after,
    docs) — `docs:` is a list of doc filenames colocated with the `STATE.md`,
    resolved here to repo-relative paths.

Typed edges: `links` (any→any id), `replaces`/`replaced-by` (decision→decision
id), `after` (backlog→backlog id), `cite-path` (feature/backlog→path — see
`load_features`/`load_backlog` docstrings for exactly which sources feed it;
decisions and memory do NOT contribute `cite-path` edges — only the four
frontmatter fields named above, per this script's brief; nothing here scans a
decision's or a memory entry's prose for paths).

INVARIANT — the graph is DERIVED, never stored. No cache, no graph file
written anywhere; every command below re-parses the four channels from disk.
Keeping it fast enough to do this on every call is a feature, not a corner cut
— a stored graph would drift the moment a human hand-edits a frontmatter field
without re-running a build step.

AGNOSTIC by construction. A few things a specific project may vary are read
from config (`checks-config.json → memory-graph`), never hardcoded:

  - **Channel location** (`channels-base`, default `""` = repo root) — the
    subdir the four channels live under, for a project that nests its memory
    (e.g. `"Docs"` → `Docs/decisions/`…). Self-suppression follows it, and
    `self-extra-dirs` overrides the framework tooling dirs it also suppresses.
  - **Cited paths** are extracted from **backticked spans that contain a `/`**
    (`FEATURE_MAP.md §An entry's body` fences code paths in backticks). No
    hardcoded repo root is assumed — a path is whatever a fiche backticks as
    one, repo-relative. This is the portable equivalent of a root-anchored
    regex and matches the Feature-channel norm.
  - **The class-name correspondence** (covers #2/#3 below) only makes sense in
    a language with a one-symbol-per-file convention (basename == type name).
    That is a PROJECT convention, not a universal one, so it is **opt-in**:
    `checks-config.json` → `memory-graph.class-file-extensions` (default `[]`,
    correspondence OFF). List the extensions whose basename equals an
    identifier (e.g. `[".cs"]` for a Unity project) to turn it on.

Three CLI commands (see each `cmd_*` docstring for the exact contract):

  covers    <path>              — which memories cover this file (exact
                                   containment: equal path, or a repo
                                   directory prefix of it — never a substring
                                   match; only `status: active` decisions).
  match     <term> [term ...]   — lexical, case/accent-insensitive match of
                                   terms (>=4 chars only) against decision
                                   ids/short-titles/tags and feature
                                   ids/Role lines — never against body prose.
  neighbors <id> [--depth N]    — the typed neighborhood (outgoing AND
                                   incoming edges) of one node.

Two hook adapters share the same core (`--stdin-json --mode covers|match`),
wired as:

  - PreToolUse(Write|Edit)   → `adapters/claude-code/hooks/edit-nudge.sh` →
    mode `covers` (reads `tool_input.file_path`).
  - PostToolUse(Grep|Glob)   → `adapters/claude-code/hooks/index-nudge.sh`
    (chained after `index-nudge.py`, unmodified) → mode `match` (reads
    `tool_input.pattern`, split into terms; `tool_input.path`, when given,
    feeds self-suppression).

Session prefilter cache (`--prefilter-cache <file>`, `covers` hook mode
only): a pure speed optimization layered ON TOP of the exact parse below —
it never answers a query on its own, it only decides whether the exact parse
is worth running. `covers` fires on EVERY Write/Edit, and most edited files
are cited by no memory at all, so without this every such edit pays a full
four-channel parse to produce an empty result. Same family as the `--marker`
dedup file: SESSION state, never versioned, dies with the session. On a
target under a memory channel the cache is dropped outright (a fiche/decision
may just have changed under our feet); otherwise a miss against its
`prefixes`/`classes`/`tags` sets skips the parse, a possible hit falls
through to it. Channel edits made OUTSIDE the session (a `git pull`
mid-session) can leave it stale — accepted, this is a nudge, not a
certificate (see `build_covers_note_prefiltered` and `compute_prefilter_sets`
for the exact contract).

Epistemic status — the absence of a nudge NEVER proves the absence of
coverage. The graph exposes only the DECLARED map (what fiches/decisions cite
explicitly); a fiche that omits a file it governs is a silent false negative
("a fiche that lies is worse than none" holds by omission too). The nudge is
a reminder, not a certificate: its silence never excuses checking coverage
yourself when a doubt exists.

Hook-adapter-only invariants (do NOT apply to the plain CLI, which is meant
for direct, deliberate lookups):

  - **Nudge, never rail.** The hook only ever emits `additionalContext` —
    context placed NEXT TO the host tool's real output, never replacing it.
  - **Silent on an uncovered target.** No match → no stdout, exit 0 — a
    "nothing found" hook message would be a permanent, worthless tax on
    every Write/Edit/Grep/Glob call in the repo.
  - **Self-suppression.** Never nudge when the edited/searched target is
    itself a memory channel dir (`decisions/`…, under `channels-base`), a
    channel index (`FEATURE_MAP.md`/`MEMORY.md`), or a framework tooling dir
    (`checks/`/`hooks/`/`adapters/` by default, or `self-extra-dirs`) — someone
    already inside a memory channel or the tooling doesn't need to be told the
    memory graph exists.
  - **Once per target per session.** `--marker <file>` dedups: for `covers`
    the target is the edited path; for `match` it's the top-ranked node id
    (mirrors `index-nudge.py`'s zone marker). The marker is written only
    AFTER the note is fully built — a crash while building must not
    permanently mute a target for the rest of the session.
  - **Any error → silent exit 0.** A nudge must never break the host's tool
    call (same contract as `index-nudge.py`).

Ported discipline from `hooks/index-nudge.py` (this framework's existing
nudge-never-rail reference implementation): exact containment (no substring
matching), sanitized reflected text, marker-after-build ordering.
"""
import argparse
import json
import os
import re
import sys
import unicodedata

# Windows consoles default to cp1252: non-cp1252 output (→, ⨯…) would crash print().
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

DECISIONS_DIR = "decisions"
DECISIONS_INDEX = "decisions/INDEX.md"
FEATURES_DIR = "features"
MEMORY_DIR = "memory"
BACKLOG_DIR = "backlog"

# Channel directory + index-file names (repo-relative, BEFORE any channels-base
# prefix). A project that nests its memory under a subdir sets
# `checks-config.json → memory-graph.channels-base` (e.g. "Docs") and every
# channel path resolves under it — see `_join_base` / `resolve_self`.
CHANNEL_DIR_NAMES = ("decisions", "features", "memory", "backlog")
CHANNEL_INDEX_FILES = ("FEATURE_MAP.md", "MEMORY.md")
# Extra self-suppression roots (the framework's own tooling) — configurable via
# `memory-graph.self-extra-dirs` for a project whose tooling lives elsewhere
# (e.g. a Claude Code project keeping its hooks under `.claude/`).
DEFAULT_SELF_EXTRA_DIRS = ("checks", "hooks", "adapters")

MAX_ENTRIES = 3
DECISION_ID_RE = re.compile(r'^D-\d{4}-\d{2}-\d{2}-\d+\.md$')
FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---\n?', re.S)
ROLE_RE = re.compile(r'^\*\*Role\s*:\*\*\s*(.*)$', re.M)
H1_RE = re.compile(r'^#\s+(.*)$', re.M)
# A backticked span: the way a fiche cites a code path or a symbol
# (`FEATURE_MAP.md §An entry's body`). A span with a `/` is a repo-relative
# path; a span without one is a bare identifier (candidate class/type name).
BACKTICK_RE = re.compile(r'`([^`]+)`')
INDEX_ENTRY_RE = re.compile(r'^-\s+\[(D-\d{4}-\d{2}-\d{2}-\d+)\]\([^)]+\)\s+—\s+(.*)$')
TAG_RE = re.compile(r'\[([A-Za-z0-9][\w\-]*)\](?!\()')
# A bare backticked identifier, optionally written with a file extension
# (`NullGuard`, `CombatManager.cs`) — the way fiches cite a symbol without its
# full path. Used only when `class-file-extensions` is configured (opt-in).
IDENT_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]{2,})(?:\.[A-Za-z0-9]+)?$')


# ---------------------------------------------------------------------------
# Config (optional, agnostic-by-default)
# ---------------------------------------------------------------------------

def load_config(root):
    """`checks-config.json → memory-graph` block, or `{}` on any absence/error.
    Tunables: `class-file-extensions` (covers #2/#3 opt-in), `channels-base`
    (subdir the four channels live under, default repo root), `self-extra-dirs`
    (extra self-suppression roots), `code-roots` (ambiguity-guard scan scope).
    A broken config must never crash a nudge, so every failure degrades to the
    agnostic defaults."""
    try:
        with open(os.path.join(root, "checks-config.json"), encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
        block = data.get("memory-graph") or {}
        return block if isinstance(block, dict) else {}
    except (OSError, ValueError):
        return {}


def class_file_extensions(cfg):
    """Normalized set of extensions (with leading dot, lowercased) whose
    basename equals an identifier — the opt-in that turns on covers #2/#3.
    Empty by default → the class-name correspondence never fires."""
    exts = cfg.get("class-file-extensions") or []
    out = set()
    for e in exts if isinstance(exts, list) else []:
        e = str(e).strip().lower()
        if e and not e.startswith("."):
            e = "." + e
        if e:
            out.add(e)
    return out


def channels_base(cfg):
    """Repo-relative subdir the four memory channels live under (e.g. `"Docs"`
    for a project that keeps them in `Docs/decisions/`…), or `""` = repo root
    (the framework's own layout). Normalized: leading/trailing slashes stripped."""
    return str(cfg.get("channels-base") or "").strip().strip("/")


def _join_base(base, p):
    """Prefix a repo-relative channel path `p` with `base` (a channels-base),
    or return it unchanged when `base` is empty."""
    base = (base or "").strip().strip("/")
    return base + "/" + p if base else p


def resolve_self(cfg):
    """`(self_dirs, self_files)` for the self-suppression guard, honoring
    `channels-base` and `self-extra-dirs`: the four channel dirs and the two
    index files under the configured base, plus the framework tooling dirs
    (default `checks`/`hooks`/`adapters`, overridable)."""
    base = channels_base(cfg)
    chan = tuple(_join_base(base, d) for d in CHANNEL_DIR_NAMES)
    extra = cfg.get("self-extra-dirs")
    if not isinstance(extra, list):
        extra = list(DEFAULT_SELF_EXTRA_DIRS)
    extra = tuple(str(e).strip().strip("/") for e in extra if str(e).strip())
    self_files = tuple(_join_base(base, f) for f in CHANNEL_INDEX_FILES)
    return chan + extra, self_files


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------

def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))


def norm_text(s):
    """Lowercase + accent-stripped form, for case/accent-insensitive matching."""
    return strip_accents((s or "").lower())


def sanitize_field(s, limit=160):
    """Form-hygiene for text reflected verbatim into a hook note (ported from
    index-nudge.py): strip control characters, collapse whitespace, truncate."""
    if not s:
        return s
    s = "".join(ch for ch in s if ch in "\t " or unicodedata.category(ch)[0] != "C")
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > limit:
        s = s[:limit].rstrip() + "…"
    return s


def norm_path(path, root_abs):
    """Repo-relative form of a path that may be absolute (hooks routinely
    pass absolute paths) or already repo-relative (the plain CLI). Ported
    from index-nudge.py's `norm` — same drive-letter/realpath handling."""
    root_r = os.path.realpath(root_abs).replace("\\", "/").rstrip("/")
    p = (path or "").replace("\\", "/").rstrip("/")
    is_abs = p.startswith("/") or (len(p) >= 2 and p[0].isalpha() and p[1] == ":")
    if is_abs:
        p = os.path.realpath(p).replace("\\", "/").rstrip("/")
    if p == root_r:
        return "."
    if p.startswith(root_r + "/"):
        return p[len(root_r) + 1:]
    return p


def is_contained(target_n, cited):
    """True if `target_n` (already repo-relative) equals `cited`, or sits
    under it as a directory prefix — exact containment, never a substring
    match (the discipline `hooks/index-nudge.py` insists on)."""
    cited = (cited or "").rstrip("/")
    if not cited:
        return False
    return target_n == cited or target_n.startswith(cited + "/")


def is_self_path(path_n, self_dirs, self_files):
    """Hook-adapter-only self-suppression guard (see module docstring).
    `self_dirs`/`self_files` come from `resolve_self` — channels-base aware."""
    if path_n in self_files:
        return True
    return any(path_n == d or path_n.startswith(d + "/") for d in self_dirs)


def parse_frontmatter(text):
    """Minimal YAML-subset frontmatter parser covering exactly what this
    repo's memory entries use (`ENTRY-TEMPLATE.md`): scalar `key: value` lines
    and single-line `key: [a, b, c]` lists. Not a general YAML parser —
    deliberately so; a stdlib-only script has no YAML library, and every
    frontmatter in this repo fits this subset. Returns (frontmatter_dict,
    body_text); an empty dict when there's no frontmatter block at all."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).split("\n"):
        line = line.rstrip()
        if not line or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            fm[key] = [x.strip() for x in inner.split(",") if x.strip()] if inner else []
        else:
            fm[key] = val
    return fm, text[m.end():]


def extract_paths(text):
    """Repo-relative paths cited in the body — every backticked span that
    contains a `/`, expanding a single `{a,b,c}` alternation into one path per
    alternative (the sibling-files shorthand, e.g.
    `Scripts/UI/Screens/Camp/{CampJournalController,CampJournalCombosTab}.cs`
    → both files). Trailing sentence punctuation (`.,;:`) is stripped; a
    legitimate trailing `.ext` survives because the strip only removes trailing
    punctuation chars, never interior ones. Backtick-anchored (never a
    substring match into unrelated prose): a path is whatever a fiche fences as
    one, which is exactly how `FEATURE_MAP.md` prescribes citing code paths."""
    out = []
    for raw in BACKTICK_RE.findall(text or ""):
        token = raw.strip().rstrip(".,;:")
        if "/" not in token:
            continue  # a bare identifier, not a path — handled by extract_classes
        if "{" in token and "}" in token:
            pre, _, rest = token.partition("{")
            alts, _, suf = rest.partition("}")
            for alt in alts.split(","):
                alt = alt.strip()
                if alt:
                    expanded = (pre + alt + suf).rstrip(".,;:")
                    if expanded:
                        out.append(expanded)
        else:
            out.append(token)
    return out


def extract_classes(text):
    """Bare backticked identifiers cited in the body (a span with no `/`),
    stripped of any file extension: `NullGuard`, `CombatManager.cs` →
    `CombatManager`. Only consumed by covers #2 when the project opts into the
    class-name correspondence; harmless to collect otherwise."""
    out = set()
    for raw in BACKTICK_RE.findall(text or ""):
        token = raw.strip()
        if "/" in token:
            continue
        m = IDENT_RE.match(token)
        if m:
            out.add(m.group(1))
    return out


# ---------------------------------------------------------------------------
# Channel loaders — each returns (nodes: {id: node_dict}, edges: [(src, type, dst)])
# `dst` is a node id for links/replaces/replaced-by/after, or a repo-relative
# path string for cite-path.
# ---------------------------------------------------------------------------

def load_decision_index(root, base=""):
    """Parse `decisions/INDEX.md` entry lines into
    id -> {"title": short_title, "tags": [...], "section": "active"|"archived"}.
    Only `- [id](path) — <rest>` lines count; the short title is `<rest>` up
    to the first ` · ` separator, tags are every `[bracket]` token in `<rest>`
    that isn't immediately followed by `(` (which would make it the id's own
    markdown link, already consumed by the match). Tags are a project
    convention, not required by the format — an INDEX without them simply
    yields empty tag lists."""
    info = {}
    try:
        with open(os.path.join(root, _join_base(base, DECISIONS_INDEX)), encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return info

    section = ""
    for line in text.split("\n"):
        if line.startswith("## Active"):
            section = "active"
            continue
        if line.startswith("## Archived"):
            section = "archived"
            continue
        m = INDEX_ENTRY_RE.match(line)
        if not m:
            continue
        did, rest = m.groups()
        short_title = rest.split(" · ", 1)[0].strip()
        tags = TAG_RE.findall(rest)
        info[did] = {"title": short_title, "tags": tags, "section": section}
    return info


def load_decisions(root, base=""):
    """`decisions/D-*.md` frontmatter (id, status, links, replaces,
    replaced-by) merged with the INDEX's short title + tags. No body parsing:
    a decision contributes NO `cite-path` edges (see module docstring) — only
    its frontmatter fields decide its edges."""
    nodes, edges = {}, []
    index_info = load_decision_index(root, base)
    ddir_rel = _join_base(base, DECISIONS_DIR)
    ddir = os.path.join(root, ddir_rel)
    try:
        names = sorted(f for f in os.listdir(ddir) if DECISION_ID_RE.match(f))
    except OSError:
        return nodes, edges

    for name in names:
        try:
            with open(os.path.join(ddir, name), encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        fm, _body = parse_frontmatter(text)
        did = fm.get("id") or name[:-3]
        idx = index_info.get(did, {})
        nodes[did] = {
            "type": "decision",
            "id": did,
            "title": idx.get("title", ""),
            "tags": idx.get("tags", []),
            "section": idx.get("section", "active"),
            "status": fm.get("status", ""),
            "updated": fm.get("updated", ""),
            "path": ddir_rel + "/" + name,
            "cites": [],
        }
        for lid in fm.get("links", []):
            edges.append((did, "links", lid))
        for rid in fm.get("replaces", []):
            edges.append((did, "replaces", rid))
        rb = fm.get("replaced-by", "")
        if rb:
            edges.append((did, "replaced-by", rb))
    return nodes, edges


def load_features(root, base=""):
    """`features/*.md` frontmatter (id, links) + the `**Role:**` line (used as
    the node's short title) + every backticked path cited anywhere in the body
    → `cite-path` edges. Backticked bare identifiers are also collected
    (`classes`), consumed only by covers #2 when the project opts in."""
    nodes, edges = {}, []
    fdir_rel = _join_base(base, FEATURES_DIR)
    fdir = os.path.join(root, fdir_rel)
    try:
        names = sorted(f for f in os.listdir(fdir) if f.endswith(".md"))
    except OSError:
        return nodes, edges

    for name in names:
        try:
            with open(os.path.join(fdir, name), encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        fm, body = parse_frontmatter(text)
        fid = fm.get("id") or name[:-3]
        m = ROLE_RE.search(body)
        role = m.group(1).strip() if m else ""
        cites = extract_paths(body)
        classes = extract_classes(body)
        nodes[fid] = {
            "type": "feature",
            "id": fid,
            "title": role,
            "updated": fm.get("updated", ""),
            "path": fdir_rel + "/" + name,
            "cites": cites,
            "classes": classes,
        }
        for lid in fm.get("links", []):
            edges.append((fid, "links", lid))
        for c in cites:
            edges.append((fid, "cite-path", c))
    return nodes, edges


def load_memory(root, base=""):
    """`memory/*.md` frontmatter (id, links) only. The channel may be empty
    (`memory/` may not even exist yet) — this must degrade to empty
    nodes/edges without raising. No `cite-path` edges (same rule as decisions
    — only features and backlog cite paths, see module docstring). The node's
    title is a best-effort read of the body's first `# H1`, purely for a
    readable `neighbors`/`match` display — the spec for this channel names no
    title source, so this is a convenience, not a contract."""
    nodes, edges = {}, []
    mdir_rel = _join_base(base, MEMORY_DIR)
    mdir = os.path.join(root, mdir_rel)
    try:
        names = sorted(f for f in os.listdir(mdir) if f.endswith(".md"))
    except OSError:
        return nodes, edges

    for name in names:
        try:
            with open(os.path.join(mdir, name), encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        fm, body = parse_frontmatter(text)
        mid = fm.get("id") or name[:-3]
        m = H1_RE.search(body)
        nodes[mid] = {
            "type": "memory",
            "id": mid,
            "title": m.group(1).strip() if m else "",
            "updated": fm.get("updated", ""),
            "path": mdir_rel + "/" + name,
            "cites": [],
        }
        for lid in fm.get("links", []):
            edges.append((mid, "links", lid))
    return nodes, edges


def load_backlog(root, base=""):
    """`backlog/*/STATE.md` frontmatter (id, title, status, after, docs) only
    — no body parsing. `docs:` lists doc filenames colocated with `STATE.md`;
    each is resolved here to a repo-relative path and becomes a `cite-path`
    edge (these companion docs live under `backlog/`, so in practice the hook's
    self-suppression guard makes them unreachable via `covers` from a live edit
    — they still matter for `neighbors`)."""
    nodes, edges = {}, []
    bdir_rel = _join_base(base, BACKLOG_DIR)
    bdir = os.path.join(root, bdir_rel)
    try:
        subdirs = sorted(d for d in os.listdir(bdir) if os.path.isdir(os.path.join(bdir, d)))
    except OSError:
        return nodes, edges

    for d in subdirs:
        fpath = os.path.join(bdir, d, "STATE.md")
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        fm, _body = parse_frontmatter(text)
        bid = fm.get("id") or d
        docs = fm.get("docs", [])
        cites = [bdir_rel + "/" + d + "/" + doc for doc in docs]
        nodes[bid] = {
            "type": "backlog",
            "id": bid,
            "title": fm.get("title", ""),
            "status": fm.get("status", ""),
            "updated": fm.get("updated", ""),
            "path": bdir_rel + "/" + d + "/STATE.md",
            "cites": cites,
        }
        for aid in fm.get("after", []):
            edges.append((bid, "after", aid))
        for c in cites:
            edges.append((bid, "cite-path", c))
    return nodes, edges


def load_graph(root):
    """The full derived graph — always recomputed, never cached (module
    invariant)."""
    nodes, edges = {}, []
    base = channels_base(load_config(root))
    for loader in (load_decisions, load_features, load_memory, load_backlog):
        n, e = loader(root, base)
        nodes.update(n)
        edges.extend(e)
    return nodes, edges


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_covers(root, target_path, class_exts=None, nodes=None):
    """Which memories cover `target_path`. Three EXACT correspondences, in
    priority order (never fuzzy):
    1. a feature/decision/backlog node with a `cite-path` edge whose path is
       EQUAL to the (repo-relative) target, or a directory prefix of it;
    2. (opt-in) for a target whose extension is in `class_exts`, a feature
       whose body cites the basename as a backticked identifier (`classes`
       set — the project's one-symbol-per-file convention makes basename ==
       type-name exact);
    3. (opt-in) for such a target, an ACTIVE decision whose INDEX tags contain
       the folded basename (tags are lowercased type names by convention) —
       newest decisions first.
    Decisions only count when `status: active` (an archived/revoked decision
    no longer governs the file). `class_exts` empty (the default) → only
    correspondence #1 runs, fully agnostic.

    Ambiguity guard on correspondences 2/3: one-symbol-per-file is a
    convention, not a filesystem guarantee, so even when `class_exts` opts it
    in, before EITHER kind of hit is kept the target's basename is checked
    for uniqueness under the project's code roots (`_code_basename_counts`,
    one `os.walk` done lazily — only if there is at least one class/tag
    candidate to validate). Two or more files sharing that basename make the
    class/tag correspondence unsafe: ALL class/tag hits for that basename are
    dropped (path hits from correspondence 1 are untouched — they don't rely
    on the basename convention at all).

    `nodes`, when given, is a pre-loaded graph (caller already parsed it —
    e.g. the `--prefilter-cache` hook path, to avoid a second `load_graph`
    call); when omitted, this loads the graph itself. Returns up to
    MAX_ENTRIES (type, id, title) tuples."""
    class_exts = class_exts or set()
    root_abs = os.path.abspath(root).replace("\\", "/")
    target_n = norm_path(target_path, root_abs)
    if nodes is None:
        nodes, _edges = load_graph(root)

    hits, seen = [], set()

    def add(node, nid):
        if nid not in seen:
            seen.add(nid)
            hits.append((node["type"], nid, node.get("title", "")))

    for nid, node in sorted(nodes.items()):
        if node["type"] == "decision" and node.get("status") != "active":
            continue
        for cited in node.get("cites", []):
            if is_contained(target_n, cited):
                add(node, nid)
                break

    base = os.path.basename(target_n)
    _, ext = os.path.splitext(base)
    if ext.lower() in class_exts:
        stem = base[: len(base) - len(ext)]
        stem_folded = norm_text(stem)
        class_hits = [
            (nid, node) for nid, node in sorted(nodes.items())
            if node["type"] == "feature" and stem in node.get("classes", set())
        ]
        tagged = [
            (nid, node) for nid, node in nodes.items()
            if node["type"] == "decision" and node.get("status") == "active"
            and stem_folded in node.get("tags", [])
        ]
        if class_hits or tagged:
            # Lazy, once-per-call basename walk — see the ambiguity-guard
            # paragraph in this function's docstring.
            if _code_basename_counts(root_abs, ext.lower()).get(base, 0) > 1:
                class_hits, tagged = [], []
        for nid, node in class_hits:
            add(node, nid)
        for nid, node in sorted(tagged, key=lambda e: _desc_key(e[0])):
            add(node, nid)

    return hits[:MAX_ENTRIES]


# Directory names never worth walking for the ambiguity guard (VCS/build/deps).
_WALK_SKIP_DIRS = frozenset((".git", "node_modules", "__pycache__", ".venv", "venv",
                             ".tox", ".mypy_cache", ".pytest_cache", "dist", "build"))


def _code_roots(root_abs):
    """The directories to scan for the ambiguity guard, in preference order:
    `memory-graph.code-roots` (checks-config.json), then the `roots` declared
    in `index/index-config.json` (the project's own code roots), then the whole
    repo when neither is configured. Narrowing the scan keeps the guard cheap
    on a project that declares its roots; the repo-wide fallback keeps it
    correct (never silently no-op) when it doesn't."""
    mg_roots = load_config(root_abs).get("code-roots")
    if isinstance(mg_roots, list):
        dirs = [os.path.join(root_abs, str(r)) for r in mg_roots if isinstance(r, str)]
        dirs = [d for d in dirs if os.path.isdir(d)]
        if dirs:
            return dirs
    try:
        with open(os.path.join(root_abs, "index/index-config.json"), encoding="utf-8", errors="replace") as fh:
            cfg = json.load(fh)
        roots = cfg.get("roots") or []
        dirs = [os.path.join(root_abs, str(r)) for r in roots if isinstance(r, str)]
        dirs = [d for d in dirs if os.path.isdir(d)]
        if dirs:
            return dirs
    except (OSError, ValueError):
        pass
    return [root_abs]


def _code_basename_counts(root_abs, ext):
    """basename → count of files ending in `ext`, walked over the project's
    code roots (`_code_roots`), for `cmd_covers`'s class/tag ambiguity guard.
    Called at most once per `cmd_covers` invocation, and only when there's
    actually a class/tag candidate to validate — an unconditional walk on
    every lookup would be a needless tax on the common (single-match) case.
    Missing/unreadable roots degrade to "nothing is ambiguous" (empty dict)
    rather than raising — same silent-degradation discipline as the channel
    loaders above."""
    counts = {}
    for base_dir in _code_roots(root_abs):
        for dirpath, dirnames, filenames in os.walk(base_dir):
            dirnames[:] = [d for d in dirnames if d not in _WALK_SKIP_DIRS]
            for fn in filenames:
                if fn.endswith(ext):
                    counts[fn] = counts.get(fn, 0) + 1
    return counts


def cmd_match(root, terms):
    """Lexical, case/accent-insensitive match of `terms` against decision
    ids/short-titles/tags and feature ids/Role lines (memory and backlog
    nodes are out of scope for `match` — the spec names only decisions and
    features). Terms shorter than 4 characters are ignored (too noisy).
    Requires at least one surviving term to actually hit; returns up to
    MAX_ENTRIES (score, id, node) tuples, highest score first. Ties break
    toward the LIVING memory: active section before archived/revoked, then
    most recent id first (decision ids are dated, so lexicographic descent =
    chronology) — an old amended decision must never outrank the current one
    that carries the invariant today."""
    tokens = [norm_text(t) for t in terms]
    tokens = [t for t in tokens if len(t) >= 4]
    if not tokens:
        return []

    nodes, _edges = load_graph(root)
    scored = []
    for nid, node in nodes.items():
        if node["type"] not in ("decision", "feature"):
            continue
        parts = [nid, node.get("title", "")]
        if node["type"] == "decision":
            parts.extend(node.get("tags", []))
        haystack = norm_text(" ".join(parts))
        score = sum(1 for t in tokens if t in haystack)
        if score:
            scored.append((score, nid, node))

    def sort_key(entry):
        score, nid, node = entry
        section_rank = 0 if node.get("section", "active") == "active" else 1
        return (-score, section_rank, _desc_key(nid))

    scored.sort(key=sort_key)
    return scored[:MAX_ENTRIES]


def _desc_key(nid):
    """Descending-order key for an id: dated decision ids sort newest-first,
    everything else (feature slugs…) keeps plain ascending alphabetical order
    after them — deterministic without pretending slugs have a chronology."""
    if re.match(r"^D-\d{4}-\d{2}-\d{2}-\d{2}$", nid):
        return (0, "".join(chr(0x10FFFF - ord(c)) for c in nid))
    return (1, nid)


def cmd_neighbors(root, node_id, depth=1):
    """The typed neighborhood of `node_id`: every edge touching it, either as
    source or destination, `depth` hops out (default 1 — direct neighbors
    only). Both directions render the same way — `<type> → <other> —
    <title>` — per this tool's contract; direction is implicit in whether
    `other` was reached via an outgoing or incoming edge, not in the arrow.
    A `cite-path` target is a path, not a node, so it has no title.
    Returns a sorted, de-duplicated list of (edge_type, other, title)."""
    nodes, edges = load_graph(root)
    seen_nodes = {node_id}
    seen_edges = set()
    result = []
    frontier = {node_id}

    for _ in range(max(depth, 1)):
        next_frontier = set()
        for nid in frontier:
            for src, etype, dst in edges:
                if src == nid:
                    other = dst
                elif dst == nid:
                    other = src
                else:
                    continue
                key = (nid, etype, other)
                if key in seen_edges:
                    continue
                seen_edges.add(key)
                other_node = nodes.get(other)
                title = other_node.get("title", "") if other_node else ""
                result.append((etype, other, title))
                if other_node is not None and other not in seen_nodes:
                    seen_nodes.add(other)
                    next_frontier.add(other)
        frontier = next_frontier
        if not frontier:
            break

    result.sort(key=lambda e: (e[0], e[1]))
    return result


# ---------------------------------------------------------------------------
# CLI formatting
# ---------------------------------------------------------------------------

def format_covers_line(hit):
    kind, nid, title = hit
    title = sanitize_field(title)
    return "%s %s — %s" % (kind, nid, title) if title else "%s %s" % (kind, nid)


def format_match_line(entry):
    _score, nid, node = entry
    title = sanitize_field(node.get("title", ""))
    updated = node.get("updated", "")
    core = "%s — %s" % (nid, title) if title else nid
    return "%s (updated %s)" % (core, updated) if updated else core


def format_neighbor_line(entry):
    etype, other, title = entry
    title = sanitize_field(title)
    return "%s → %s — %s" % (etype, other, title) if title else "%s → %s" % (etype, other)


# ---------------------------------------------------------------------------
# Hook adapters (--stdin-json --mode covers|match)
# ---------------------------------------------------------------------------

def build_covers_note(root, root_abs, tool_input, class_exts):
    """Returns (note_text, marker_key) for the `covers` hook mode, or
    ("", "") when nothing should fire (uncovered, self-suppressed, or no
    `file_path`)."""
    file_path = tool_input.get("file_path") or ""
    if not file_path:
        return "", ""

    target_n = norm_path(file_path, root_abs)
    self_dirs, self_files = resolve_self(load_config(root))
    if is_self_path(target_n, self_dirs, self_files):
        return "", ""

    hits = cmd_covers(root, file_path, class_exts)
    if not hits:
        return "", ""

    lines = ["[memory-graph] Memory covering %s:" % target_n]
    for hit in hits:
        lines.append("- %s" % format_covers_line(hit))
    lines.append("Derived graph, recomputed on demand — `memory-graph.py neighbors <id>` to dig.")
    return "\n".join(lines), target_n


PREFILTER_CACHE_KEYS = ("prefixes", "classes", "tags")


def compute_prefilter_sets(nodes):
    """Derive the three fast-reject sets for the `covers` session prefilter
    cache from an already-loaded graph:

    - `prefixes` — every node's raw cited path (`cites`; a cited directory OR
      a cited file — both kept as-is). Paired with `_path_chain`'s
      target-side walk, this is an EXACT reproduction of `is_contained` for
      every `(target, cited)` pair — not a superset heuristic — because
      `is_contained(target_n, cited)` is true iff `cited` equals `target_n`
      or one of `target_n`'s ancestor directories, i.e. iff `cited` is a
      member of `_path_chain(target_n)`. Storing the raw cite is already
      lossless; inflating it would only add false positives (extra parses).
    - `classes` — every feature's cited class tokens (`classes`), exact case,
      matching `cmd_covers`'s own case-sensitive comparison.
    - `tags` — every ACTIVE decision's INDEX tags, as-is (already lowercase by
      convention — same assumption `cmd_covers` makes)."""
    prefixes, classes, tags = set(), set(), set()
    for node in nodes.values():
        for cited in node.get("cites", []) or []:
            cited = (cited or "").rstrip("/")
            if cited:
                prefixes.add(cited)
        if node["type"] == "feature":
            classes.update(node.get("classes", set()) or set())
        if node["type"] == "decision" and node.get("status") == "active":
            tags.update(node.get("tags", []) or [])
    return {"prefixes": sorted(prefixes), "classes": sorted(classes), "tags": sorted(tags)}


def _path_chain(path_n):
    """`path_n` itself plus every one of its ancestor directories, deepest
    first — e.g. `"a/b/c"` → `["a/b/c", "a/b", "a"]`. Checking membership of
    this chain against a `prefixes` set exactly reproduces `is_contained`'s
    equal-or-directory-prefix contract, without re-walking every node."""
    parts = [p for p in (path_n or "").split("/") if p]
    return ["/".join(parts[:i]) for i in range(len(parts), 0, -1)]


def prefilter_might_cover(target_n, stem, stem_folded, cache):
    """True when `cache` (a dict with `prefixes`/`classes`/`tags`, see
    `compute_prefilter_sets`) does NOT rule out a `cmd_covers` hit for
    `target_n` — i.e. a full parse might still be needed. `stem`/`stem_folded`
    are the class-file basename (without extension) and its folded form, or
    `""` when the class correspondence doesn't apply (non-class-ext target)."""
    prefixes = cache.get("prefixes") or []
    if prefixes:
        prefix_set = set(prefixes)
        if any(p in prefix_set for p in _path_chain(target_n)):
            return True
    if stem and stem in (cache.get("classes") or ()):
        return True
    if stem_folded and stem_folded in (cache.get("tags") or ()):
        return True
    return False


def load_prefilter_cache(path):
    """Load a `--prefilter-cache` file. Returns `None` on ANY problem
    (missing/unreadable file, corrupt JSON, missing/malformed expected keys)
    — the caller then falls back to a full parse, exactly as if no cache
    existed. A cache missing a key is treated the same as corrupt (never
    silently short-circuits every future call by handing back empty sets)."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if not all(isinstance(data.get(k), list) for k in PREFILTER_CACHE_KEYS):
        return None
    return data


def write_prefilter_cache(path, data):
    """Atomic write (temp file + `os.replace`) so a crash mid-write never
    leaves a half-written cache for the next call to trip over. The cache is
    a pure speed optimization — ANY failure here is swallowed, never raised."""
    tmp = "%s.tmp.%d" % (path, os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


def build_covers_note_prefiltered(root, root_abs, tool_input, class_exts, cache_path):
    """Session-cache-prefiltered variant of `build_covers_note`, used only
    when the hook adapter passes `--prefilter-cache` (mode `covers` only —
    see the module docstring's "Session prefilter cache" paragraph). Same
    return shape as `build_covers_note`.

    - No `file_path` → same no-op as the uncached path.
    - Target under a memory channel (`is_self_path`) → drop the cache file (a
      fiche/decision may have just changed) and stay silent.
    - A loadable cache that rules out this target (`prefilter_might_cover` is
      False) → stay silent WITHOUT parsing the four channels — the fast path.
    - Otherwise (no cache, corrupt cache, or a possible hit) → the real, exact
      `cmd_covers` parse; a freshly-built cache is written back (best-effort)
      whenever there wasn't a usable one yet."""
    file_path = tool_input.get("file_path") or ""
    if not file_path:
        return "", ""

    target_n = norm_path(file_path, root_abs)
    self_dirs, self_files = resolve_self(load_config(root))
    if is_self_path(target_n, self_dirs, self_files):
        try:
            os.remove(cache_path)
        except OSError:
            pass
        return "", ""

    cache = load_prefilter_cache(cache_path)
    if cache is not None:
        base = os.path.basename(target_n)
        _, ext = os.path.splitext(base)
        if ext.lower() in class_exts:
            stem = base[: len(base) - len(ext)]
            stem_folded = norm_text(stem)
        else:
            stem, stem_folded = "", ""
        if not prefilter_might_cover(target_n, stem, stem_folded, cache):
            return "", ""

    nodes, _edges = load_graph(root)
    hits = cmd_covers(root, file_path, class_exts, nodes=nodes)

    if cache is None:
        write_prefilter_cache(cache_path, compute_prefilter_sets(nodes))

    if not hits:
        return "", ""

    lines = ["[memory-graph] Memory covering %s:" % target_n]
    for hit in hits:
        lines.append("- %s" % format_covers_line(hit))
    lines.append("Derived graph, recomputed on demand — `memory-graph.py neighbors <id>` to dig.")
    return "\n".join(lines), target_n


def build_match_note(root, root_abs, tool_input):
    """Returns (note_text, marker_key) for the `match` hook mode, or
    ("", "") when nothing should fire. `marker_key` is the top-ranked node
    id (mirrors index-nudge.py's per-zone marker, but per-node here)."""
    path = tool_input.get("path") or ""
    if path:
        self_dirs, self_files = resolve_self(load_config(root))
        if is_self_path(norm_path(path, root_abs), self_dirs, self_files):
            return "", ""

    pattern = tool_input.get("pattern") or ""
    terms = [t for t in re.split(r"[^A-Za-z0-9_]+", pattern) if t]
    results = cmd_match(root, terms)
    if not results:
        return "", ""

    top_id = results[0][1]
    lines = ["[memory-graph] Memory related to these search terms:"]
    for entry in results:
        lines.append("- %s" % format_match_line(entry))
    lines.append("Derived graph, recomputed on demand — `memory-graph.py neighbors %s` to dig." % top_id)
    return "\n".join(lines), top_id


def hook_main(args):
    """Common hook entry point for both modes. Every failure mode here must
    resolve to exit 0 with no stdout — a nudge must never break the host's
    tool call (module docstring)."""
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    tool_input = data.get("tool_input") or {}
    root_abs = os.path.abspath(args.root).replace("\\", "/")

    try:
        if args.mode == "covers":
            class_exts = class_file_extensions(load_config(args.root))
            if args.prefilter_cache:
                note, key = build_covers_note_prefiltered(
                    args.root, root_abs, tool_input, class_exts, args.prefilter_cache)
            else:
                note, key = build_covers_note(args.root, root_abs, tool_input, class_exts)
            event = "PreToolUse"
        elif args.mode == "match":
            note, key = build_match_note(args.root, root_abs, tool_input)
            event = "PostToolUse"
        else:
            return 0
    except Exception:
        return 0

    if not note:
        return 0

    if args.marker:
        try:
            with open(args.marker, encoding="utf-8", errors="replace") as fh:
                if key in fh.read().split("\n"):
                    return 0
        except OSError:
            pass

    try:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": note,
        }}))
    except Exception:
        return 0

    if args.marker:
        try:
            with open(args.marker, "a", encoding="utf-8") as fh:
                fh.write(key + "\n")
        except OSError:
            pass  # a duplicate note next time beats a lost one now
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_argparser():
    ap = argparse.ArgumentParser(
        prog="memory-graph.py",
        description="memory-graph — derived memory graph engine (see the module docstring).",
    )
    ap.add_argument("--root", default=".", help="repo root (default: current directory)")
    ap.add_argument("--stdin-json", action="store_true",
                     help="hook adapter mode: reads the PreToolUse/PostToolUse JSON on stdin")
    ap.add_argument("--mode", choices=("covers", "match"), default="",
                     help="hook mode, used with --stdin-json")
    ap.add_argument("--marker", default="", help="once-per-target-per-session dedup file (hook mode)")
    ap.add_argument("--prefilter-cache", default="",
                     help="session cache file to skip the full parse (covers hook mode only)")

    sub = ap.add_subparsers(dest="command")

    p_covers = sub.add_parser("covers", help="which memories cover this path")
    p_covers.add_argument("path")

    p_match = sub.add_parser("match", help="lexical node search (decisions + features)")
    p_match.add_argument("terms", nargs="+")

    p_neighbors = sub.add_parser("neighbors", help="typed neighborhood of a node")
    p_neighbors.add_argument("id")
    p_neighbors.add_argument("--depth", type=int, default=1)

    return ap


def main():
    ap = build_argparser()
    args = ap.parse_args()

    if args.stdin_json:
        return hook_main(args)

    if args.command == "covers":
        class_exts = class_file_extensions(load_config(args.root))
        for hit in cmd_covers(args.root, args.path, class_exts):
            print(format_covers_line(hit))
        return 0
    if args.command == "match":
        for entry in cmd_match(args.root, args.terms):
            print(format_match_line(entry))
        return 0
    if args.command == "neighbors":
        for entry in cmd_neighbors(args.root, args.id, args.depth):
            print(format_neighbor_line(entry))
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
