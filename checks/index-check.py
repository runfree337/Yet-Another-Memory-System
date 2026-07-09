#!/usr/bin/env python3
"""Per-file INDEX integrity (universal, portable).

Verifies the concordance between a flat `path<TAB>intent` index and the real files —
the "per-file detail" (Format A) of the navigation layer (cf. `index/INDEX.md`).

AGNOSTIC: the **roots** and **extensions** to index are NOT hardcoded. It's the PROJECT
that defines them (typically **at framework install time**) in
`index/index-config.json` — schema: `index/index-config.example.json`. Without a config,
there is nothing to verify (the project didn't opt into a per-file index) -> exit 0.

Checks (zero false positive):
  I1  every index line -> a real file exists.
  I2  every file under `roots` with a `extensions` extension (outside `ignore`) -> present
      in the index.

Exit 2 on drift, 0 otherwise. Read-only, flags — never rewrites the index.
"""
import argparse
import fnmatch
import json
import os
import sys

# Windows consoles default to cp1252: non-cp1252 output (→, ⨯…) would crash print().
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

FRAMEWORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ai-workflow/
DEFAULT_CONFIG = os.path.join(FRAMEWORK, "index", "index-config.json")


def read_manifest(path):
    entries = {}
    with open(path, encoding="utf-8") as fh:
        for ln, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            entries[line.split("\t")[0].strip()] = ln
    return entries


def walk_files(base, roots, exts, ignore):
    exts = tuple(exts)
    found = set()
    for r in roots:
        for dpath, _, names in os.walk(os.path.join(base, r)):
            for n in names:
                if not n.endswith(exts):
                    continue
                rel = os.path.relpath(os.path.join(dpath, n), base).replace("\\", "/")
                if any(fnmatch.fnmatch(rel, pat) for pat in ignore):
                    continue
                found.add(rel)
    return found


def main():
    ap = argparse.ArgumentParser(description="Per-file index integrity (portable).")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--base", default=None, help="repo root (default: config.base or cwd)")
    a = ap.parse_args()

    try:
        with open(a.config, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except OSError:
        print(f"index-check: no config ({a.config}) — the project has not defined "
              "roots/extensions to index. Nothing to verify.")
        print("  → copy/fill in index/index-config.example.json (at framework install time).")
        return 0
    except json.JSONDecodeError as e:
        print(f"index-check: unreadable config ({e}).", file=sys.stderr)
        return 2

    base = a.base or cfg.get("base") or os.getcwd()
    roots = cfg.get("roots", [])
    exts = cfg.get("extensions", [])
    ignore = cfg.get("ignore", [])
    if not roots or not exts:
        print("index-check: config with no `roots` or `extensions` — nothing to index.")
        return 0

    manifest_path = os.path.join(base, cfg.get("manifest", "index/manifest.tsv"))
    if not os.path.isfile(manifest_path):
        print(f"index-check: manifest not found ({manifest_path}).", file=sys.stderr)
        return 2

    indexed = read_manifest(manifest_path)
    actual = walk_files(base, roots, exts, ignore)

    dead = sorted(p for p in indexed if not os.path.isfile(os.path.join(base, p)))
    missing = sorted(actual - set(indexed))

    for p in dead:
        print(f"I1: indexed but file missing → {p} (line {indexed[p]})")
    for p in missing:
        print(f"I2: file not indexed → {p}")

    if dead or missing:
        print(f"\nindex-check: {len(dead)} dead entry(ies), {len(missing)} file(s) to index.")
        return 2
    print(f"index-check: OK ({len(indexed)} entries, {len(actual)} files covered).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
