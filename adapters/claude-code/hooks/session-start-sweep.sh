#!/usr/bin/env bash
# SessionStart — SILENT structural sweep (checks/README.md §To wire).
#
# Aggregates several checks/*.py at session start: NOTHING printed if everything is clean (0
# tokens injected into context), one terse line per drift otherwise. Keys on the exit code,
# never parses a localized/accented report — cf. the "Silence rule" of the README cited above.
#
# Also detects a pending semantic audit report (produced outside the session by the OS
# cron job, cf. INSTALL.md step 5): never processes it itself, just SURFACES it — the
# agent asks, the user decides.
set -u

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$ROOT" ] && exit 0
cd "$ROOT" || exit 0

PY=$(command -v python3 || command -v python)
[ -z "$PY" ] && exit 0

lines=""

"$PY" checks/decisions-check.py   >/dev/null 2>&1
[ "$?" -eq 2 ] && lines="${lines}• decisions: drift (python3 checks/decisions-check.py)\n"

"$PY" checks/backlog-check.py     >/dev/null 2>&1
[ "$?" -eq 2 ] && lines="${lines}• backlog: error (python3 checks/backlog-check.py)\n"

"$PY" checks/feature-map-check.py >/dev/null 2>&1
[ "$?" -eq 2 ] && lines="${lines}• feature-map: error (python3 checks/feature-map-check.py)\n"

"$PY" checks/memory-check.py      >/dev/null 2>&1
[ "$?" -eq 2 ] && lines="${lines}• memory: error (python3 checks/memory-check.py)\n"

"$PY" checks/index-check.py       >/dev/null 2>&1
[ "$?" -eq 2 ] && lines="${lines}• index: drift (python3 checks/index-check.py)\n"

"$PY" checks/doc-refs-check.py 2>/dev/null | grep -q BLOCKING
[ "$?" -eq 0 ] && lines="${lines}• doc: dead ref (python3 checks/doc-refs-check.py)\n"

[ -n "$lines" ] && printf "⚠️ structural drift at startup:\n%b" "$lines"

REPORT="${YAMS_MEMORY_REPORT_DIR:-.memory-reports}/memory-report.md"
[ -f "$REPORT" ] && printf "📋 memory report pending: %s — ASK the user to handle it, then delete it.\n" "$REPORT"

exit 0   # never blocking; SILENT if no drift and no report → 0 tokens injected
