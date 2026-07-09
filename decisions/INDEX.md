# Decisions — INDEX

> One line per **structural** decision, scannable at a glance. Format:
> `- [D-YYYY-MM-DD-NN](D-YYYY-MM-DD-NN.md) — <short title> · <invariant in 1 sentence>`.
> Detail in `D-*.md` (frontmatter `status` ⟺ the section below, cf. `README.md`).
> Protocol: `README.md`.

## Active

- [D-2026-07-09-01](D-2026-07-09-01.md) — YAMS standalone at repo root · nothing here references an artifact that does not ship with the repo
- [D-2026-07-09-02](D-2026-07-09-02.md) — one common entry model for all channels · every channel check validates through entrylib, never a local parser
- [D-2026-07-09-03](D-2026-07-09-03.md) — STATE.md is pure state · closure never migrates content, the durable is already written

## Archived

<!-- stale decisions moved here (status: archived, or revoked with no living constraint) -->
