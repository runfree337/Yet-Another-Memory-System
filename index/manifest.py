#!/usr/bin/env python3
"""Maintenance of the flat manifest `index/manifest.tsv` (the "per-file detail",
Format A of `index/INDEX.md`) — one `path<TAB>intent` per line, sorted by path.

AGNOSTIC, like `checks/index-check.py`: this script hardcodes neither roots nor
extensions. It reads `index/index-config.json` (schema: `index-config.example.json`),
which the project fills in **at framework install time**.

Subcommands:
  manifest.py set   <path> <intent>   upsert (adds or replaces the intent), keeps it sorted
  manifest.py rm    <path>            removes the entry
  manifest.py get   <path>            prints the intent (or nothing)
  manifest.py stamp                   if `hub` is configured, updates its
                                        "> Last updated: ..." line (date + short commit) — no-op otherwise

This script is the WRITE counterpart of `checks/index-check.py` (read-only, checks for
drift). No `check` command here: run `checks/index-check.py` for that — no verification
logic duplicated between the two files.

The manifest is grepped for lookups; it's edited via this script (never by hand — the
file header says so, and `set` re-sorts/dedupes)."""
import datetime
import json
import os
import subprocess
import sys

FRAMEWORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ai-workflow/
DEFAULT_CONFIG = os.path.join(FRAMEWORK, "index", "index-config.json")
HEADER = ("# path\tintent — flat manifest, source of truth for the per-file index. "
          "Edit via index/manifest.py, not by hand.")


def load_config(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError:
        print(f"manifest: no config ({path}) — copy/fill in "
              "index/index-config.example.json before using this script.", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"manifest: unreadable config ({e}).", file=sys.stderr)
        return None


def manifest_path(cfg, base):
    return os.path.join(base, cfg.get("manifest", "index/manifest.tsv"))


def load(path):
    rows = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            p, _, intent = line.partition("\t")
            if p:
                rows[p] = intent
    return rows


def save(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(HEADER + "\n")
        for p in sorted(rows):
            f.write(f"{p}\t{rows[p]}\n")


def cmd_set(rows_path, chemin, intent):
    rows = load(rows_path)
    existed = chemin in rows
    rows[chemin] = " ".join(intent.split())
    save(rows_path, rows)
    print(("updated" if existed else "added") + f": {chemin}")


def cmd_rm(rows_path, chemin):
    rows = load(rows_path)
    if rows.pop(chemin, None) is None:
        print(f"absent: {chemin}")
        return
    save(rows_path, rows)
    print(f"removed: {chemin}")


def cmd_get(rows_path, chemin):
    print(load(rows_path).get(chemin, ""))


def cmd_stamp(cfg, base):
    hub = cfg.get("hub")
    if not hub:
        print("manifest: no `hub` configured in index-config.json — stamp disabled "
              "(optional field: path of a file carrying a '> Last updated: ...' line).")
        return 0
    hub_path = os.path.join(base, hub)
    if not os.path.isfile(hub_path):
        print(f"manifest: hub not found ({hub_path}).", file=sys.stderr)
        return 2
    today = datetime.date.today().isoformat()
    try:
        head = subprocess.check_output(
            ["git", "-C", base, "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        head = "?"
    lines = open(hub_path, encoding="utf-8").read().splitlines()
    stamped = False
    for i, l in enumerate(lines):
        if l.startswith("> Last updated:"):
            lines[i] = f"> Last updated: {today} (commit {head})"
            stamped = True
            break
    if not stamped:
        print(f"manifest: no '> Last updated: ...' line in {hub} — nothing to stamp.")
        return 0
    open(hub_path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"stamped: {today} ({head}) → {hub}")
    return 0


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    cmd, rest = argv[0], argv[1:]

    cfg = load_config(DEFAULT_CONFIG)
    if cfg is None:
        return 2
    base = cfg.get("base") or os.getcwd()

    if cmd == "stamp" and not rest:
        return cmd_stamp(cfg, base)

    rows_path = manifest_path(cfg, base)
    if cmd == "set" and len(rest) == 2:
        cmd_set(rows_path, rest[0], rest[1])
    elif cmd == "rm" and len(rest) == 1:
        cmd_rm(rows_path, rest[0])
    elif cmd == "get" and len(rest) == 1:
        cmd_get(rows_path, rest[0])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
