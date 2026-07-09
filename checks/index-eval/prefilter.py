#!/usr/bin/env python3
"""prefilter.py — lexical prefilter for the index-eval method (Tier 0, deterministic,
no LLM). Full method: `checks/index-eval/README.md`.

Reads the flat manifest (`path<TAB>intent`, source of truth for the per-file index,
see `index/manifest.tsv`) and evaluates GROUPS of manifest entries that share a
directory prefix (e.g. `src/combat/`). A "group" is just a path-prefix filter over the
flat manifest — there is no per-directory `.md` sub-index file to scan.

AGNOSTIC, like `checks/index-check.py` / `index/manifest.py`: this script hardcodes
neither the manifest path nor the groups to evaluate. It reads
`index/index-config.json` (schema: `index/index-config.example.json`):
  - `manifest` (default `index/manifest.tsv`) — same key/default as `index-check.py`.
  - `eval-groups` (optional array of path prefixes) — the groups prefiltered by
    default. If absent, groups are DERIVED from the first-level directory prefixes
    actually present in the manifest (e.g. `src/foo.py` -> group `src/`).

Without a config file, there is nothing to evaluate (the project hasn't opted into
per-file index evaluation) -> clear message, exit 0. Same degradation pattern as
`checks/index-check.py`.
"""
import json
import os
import sys

from lib.lexsim import decide_flag, pairwise

# Windows consoles default to cp1252: non-cp1252 output (→, ⨯…) would crash print().
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

FRAMEWORK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CONFIG = os.path.join(FRAMEWORK, "index", "index-config.json")


def load_config(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError:
        return None
    except json.JSONDecodeError as e:
        print(f"index-eval: unreadable config ({e}).", file=sys.stderr)
        return None


def load_manifest(path):
    """Load the flat manifest as a list of `(path, intent)` pairs. Skips blank lines,
    `#`-comments, and directory-only entries (trailing `/`, nothing to evaluate)."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            p, _, intent = line.partition("\t")
            if p and not p.endswith("/"):
                rows.append((p, intent))
    return rows


def entries_for_prefix(rows, prefix):
    """Manifest entries under `prefix`, shaped for the rest of the pipeline: key
    `file` = path relative to the prefix. No `section`/`dup` in flat-manifest mode —
    those only apply to the legacy markdown parser in `lib/parse.py`."""
    out = []
    for p, intent in rows:
        if p.startswith(prefix):
            rel = p[len(prefix):]
            out.append({"file": rel, "intent": intent, "intent_prefixed": intent,
                        "section": None, "dup": False, "raw_line": f"- `{rel}` — {intent}"})
    return out


def evaluate_group(prefix, rows, threshold=0.5):
    if not prefix.endswith("/"):
        prefix += "/"
    files = entries_for_prefix(rows, prefix)
    n = len(files)
    pw = pairwise(files) if n >= 2 else {"max_pair_sim": 0.0, "mean_pair_sim": 0.0, "confusable_pairs": []}
    flag = decide_flag(n, pw["max_pair_sim"], threshold)
    return {"group": prefix, "n_files": n, **pw, **flag}


def derive_groups(rows):
    """Fallback when `eval-groups` is absent from the config: derive groups from the
    first-level directory prefixes actually present in the manifest, in first-seen
    order (e.g. `src/foo/bar.py` -> group `src/`). A manifest with no directory
    structure at all (root-level files only) yields no group."""
    seen = []
    for p, _ in rows:
        head, sep, _ = p.partition("/")
        if sep:
            prefix = head + "/"
            if prefix not in seen:
                seen.append(prefix)
    return seen


def main(argv):
    args = argv[1:]
    config_path = DEFAULT_CONFIG
    if "--config" in args:
        i = args.index("--config")
        config_path = args[i + 1]
        args = args[:i] + args[i + 2:]

    cfg = load_config(config_path)
    if cfg is None:
        print(f"index-eval: no config ({config_path}) — the project has not opted "
              "into per-file index evaluation. Nothing to prefilter.")
        print("  -> copy/fill in index/index-config.example.json "
              "(manifest path + optional eval-groups).")
        return 0

    base = cfg.get("base") or "."
    manifest_path = os.path.join(base, cfg.get("manifest", "index/manifest.tsv"))
    if not os.path.isfile(manifest_path):
        print(f"index-eval: manifest not found ({manifest_path}).", file=sys.stderr)
        return 2

    rows = load_manifest(manifest_path)
    if not rows:
        print("index-eval: manifest is empty — nothing to prefilter.")
        return 0

    groups = args or cfg.get("eval-groups") or derive_groups(rows)
    if not groups:
        print("index-eval: no group to evaluate (manifest has no directory structure "
              "and no `eval-groups` configured).")
        return 0

    results = [evaluate_group(g, rows) for g in groups]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
