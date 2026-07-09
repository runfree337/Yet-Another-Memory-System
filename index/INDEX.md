# Navigation index

> **To find things without reading everything.** A short map: **one line per unit** (project /
> module / major folder) — its role + its dependencies. Small enough to be read **in full**
> before acting. Fine-grained detail (file by file) gets **grepped**, not read as a block.

## Units (`Unit | Role (1 line) | Depends on`)

<!-- Fill in based on the project's ACTUAL breakdown — no assumed architecture. Format: -->

| Unit | Role | Depends on |
|---|---|---|
| `<unit-a>` | <role> | — |
| `<unit-b>` | <role> | `<unit-a>` |

> **Large project**: add a per-unit detail (`path → intent`, **generated** by script, not
> maintained by hand) + the **dependency graph** — the basis for impact analysis ("if I touch X,
> who depends on X?").

## Per-file detail (Format A) — large projects

When the per-unit map isn't enough, add a **per-file** index: a flat manifest
`index/manifest.tsv` (`path<TAB>intent`, one line per file, **generated**, not <!-- template -->
maintained by hand).

- **Writing** — `index/manifest.py` (`set` / `rm` / `get` / `stamp`): the only way to edit the
  manifest. Hard-codes no extension or root — it reads `index/index-config.json`, same as <!-- template -->
  `index-check.py` below. Command details → `../SCRIPTS.md`.
- **Integrity** (each line ↔ a real file; each indexable file ↔ a line) — checked in **read-only**
  mode by `../checks/index-check.py` (never rewrites the index).

**The project defines what it indexes** — roots + extensions — in `index/index-config.json` <!-- template -->
(schema: `index/index-config.example.json`), typically **when the framework is installed**: the
extensions to index depend on the project's language, the framework doesn't assume them. Without
config, `manifest.py` and `index-check.py` are simply **inactive**. This TSV format is the one
used by the reference host project — we **don't touch** its existing index, we adopt the same
format.
