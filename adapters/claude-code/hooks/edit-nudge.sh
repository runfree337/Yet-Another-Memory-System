#!/usr/bin/env bash
# PreToolUse(Write|Edit) — glue for `hooks/memory-graph.py` in `covers` mode
# (canonical logic + all invariants in that script's own docstring, summarized
# in the memory-graph skill/README §Router aid). This wrapper only resolves the
# repo root and the session-scoped once-per-target marker + prefilter-cache
# paths (both under $TMPDIR, keyed by session id — same session-state family;
# see memory-graph.py's "Session prefilter cache" for the cache's own
# contract), then hands the hook JSON to memory-graph.py, which re-validates
# `tool_input.file_path`, checks containment against the derived graph,
# self-suppresses on a memory-channel target, and stays silent on an uncovered
# file. Silent no-op without memory-graph.py; never blocks — always exit 0.
#
# The agent about to touch a file sees the fiche/decision that COVERS it BEFORE
# editing — the write-side symmetric of index-nudge (the search side).

set +e

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$ROOT" ] && exit 0

GRAPH_PY="$ROOT/hooks/memory-graph.py"
[ -f "$GRAPH_PY" ] || exit 0  # adopting project didn't copy the engine

PY=$(command -v python3 || command -v python)
[ -z "$PY" ] && exit 0

SESSION_ID="${CLAUDE_CODE_SESSION_ID:-unknown}"
"$PY" "$GRAPH_PY" --root "$ROOT" --stdin-json --mode covers \
  --marker "${TMPDIR:-/tmp}/yams-edit-nudge-${SESSION_ID}.log" \
  --prefilter-cache "${TMPDIR:-/tmp}/yams-edit-nudge-cache-${SESSION_ID}.json"

exit 0
