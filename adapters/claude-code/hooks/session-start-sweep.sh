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
#
# Also surfaces the ratification inbox (checks/memory-audit.py --pending): entries still
# unverified, or verified-without-ratified, are otherwise invisible until someone thinks to
# ask — one terse count line, silent when empty or on any probe error.
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

# INSTALLATION guard for the `updated` stamp (checks/README.md §Pre-commit wiring).
# `core.hooksPath` is LOCAL, unversioned config: it vanishes on every clone/new machine,
# and its absence only shows weeks later, as an `updated` that looks normal. A mechanism
# that cannot run must SAY so. The exact question is NOT "is the config set?" but "is the
# `pre-commit` git will RUN ours?": a third party (husky, a GUI client) may set its own
# `core.hooksPath` — config present, stamp dead; conversely the documented fallback (a
# copy in `.git/hooks/`) leaves the config empty and is perfectly valid. So compare the
# CONTENT of the effective target: relative/absolute/trailing-slash config, link and
# up-to-date copy all pass — a third party's homonym does not, nor does a stale copy.
if [ -f "$ROOT/adapters/git/pre-commit" ]; then
  # `git rev-parse --git-path hooks` ALONE answers "where will git look for hooks?": it
  # honors `core.hooksPath` in all its forms and falls back to `.git/hooks` when unset.
  # Never re-resolve by hand: two rules for one question end up diverging.
  hp=$(git -C "$ROOT" rev-parse --git-path hooks 2>/dev/null)
  case "$hp" in
    "") active="" ;;
    /*|[A-Za-z]:*) active="$hp/pre-commit" ;;
    *) active="$ROOT/$hp/pre-commit" ;;   # relative answers resolve from the repo root
  esac
  same=1
  if [ -n "$active" ]; then
    if command -v cmp >/dev/null 2>&1; then
      cmp -s "$active" "$ROOT/adapters/git/pre-commit" && same=0
    else
      [ "$active" -ef "$ROOT/adapters/git/pre-commit" ] && same=0
    fi
  fi
  if [ "$same" -ne 0 ]; then
    lines="${lines}• updated stamp: the pre-commit git would run is not ours — git config core.hooksPath adapters/git (or copy the hook into the active hooks dir)\n"
  elif [ ! -x "$active" ]; then
    # git SKIPS a non-executable hook (`advice.ignoredHook`, disableable). Tested on the
    # file git will run — including an untracked copy in `.git/hooks/`. On Windows `-x`
    # stays true regardless; the index-mode check below is the portable relay.
    lines="${lines}• updated stamp: git hook not executable — chmod +x \"$active\" ; if versioned, also git update-index --chmod=+x adapters/git/pre-commit\n"
  elif [ "$(git -C "$ROOT" ls-files -s -- adapters/git/pre-commit 2>/dev/null | cut -d' ' -f1)" = "100644" ]; then
    # Executable here, but indexed 100644: under `core.filemode=false` (Windows) git
    # indexes any new file so, and every POSIX clone would silently skip the hook.
    lines="${lines}• updated stamp: git hook indexed in mode 100644 — git update-index --chmod=+x adapters/git/pre-commit\n"
  fi
fi

[ -n "$lines" ] && printf "⚠️ structural drift at startup:\n%b" "$lines"

inbox_count=$("$PY" checks/memory-audit.py --pending --json 2>/dev/null | "$PY" -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print(len(data) if isinstance(data, list) else 0)
except Exception:
    print(0)
' 2>/dev/null)
case "$inbox_count" in ''|*[!0-9]*) inbox_count=0 ;; esac
[ "$inbox_count" -gt 0 ] 2>/dev/null && printf "📥 %s entrie(s) awaiting ratification — python3 checks/memory-audit.py --pending\n" "$inbox_count"

REPORT="${YAMS_MEMORY_REPORT_DIR:-.memory-reports}/memory-report.md"
[ -f "$REPORT" ] && printf "📋 memory report pending: %s — ASK the user to handle it, then delete it.\n" "$REPORT"

exit 0   # never blocking; SILENT if no drift and no report → 0 tokens injected
