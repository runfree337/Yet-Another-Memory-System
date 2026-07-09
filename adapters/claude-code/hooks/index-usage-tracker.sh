#!/usr/bin/env bash
# PreToolUse hook: log each Read/Grep/Glob to a session-scoped tmp file, for
# end-of-session aggregation by index-usage-flush.sh. Must stay fast (<20ms) and
# never block — always exit 0.
#
# This is the tracking half of the "index usage metrics" pair: WORKFLOW.md preaches
# "consult the navigation index before sweeping the codebase" (index/INDEX.md,
# index/manifest.tsv) but the framework had no way to verify that in practice. This
# hook doesn't judge anything by itself — it only records raw tool calls; the zone
# classification (what counts as "covered", what counts as "the index") happens in
# index-usage-flush.sh, driven by index/index-config.json.
#
# Data layout: one line per tool call as "TOOL|PATH" appended to a session-scoped
# tmp file. No external deps (jq is NOT available on every host, e.g. Windows/Git
# Bash) — the JSON is parsed with grep/sed parameter expansion only, same recipe as
# the other adapter hooks in this folder.

set +e

SESSION_ID="${CLAUDE_CODE_SESSION_ID:-unknown}"
LOG="${TMPDIR:-/tmp}/yams-index-usage-${SESSION_ID}.log"

INPUT="$(cat)"

# Extract the first string value of a top-level-ish JSON key: "key" : "value".
# Tolerant of spaces; value stops at the first unescaped quote (good enough — the
# fields we read, paths/patterns, don't contain quotes in practice).
json_str() {
  printf '%s' "$INPUT" \
    | grep -o "\"$1\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" \
    | head -1 \
    | sed "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/"
}

TOOL=$(json_str tool_name)
[[ -z "$TOOL" ]] && exit 0

case "$TOOL" in
  Read)
    P=$(json_str file_path)
    ;;
  Grep)
    P=$(json_str path); [[ -z "$P" ]] && P=$(json_str glob); [[ -z "$P" ]] && P=$(json_str pattern)
    ;;
  Glob)
    P=$(json_str path); [[ -z "$P" ]] && P=$(json_str pattern)
    ;;
  *)
    exit 0
    ;;
esac

[[ -z "$P" ]] && exit 0

# Initialize log on first call with session start timestamp.
[[ ! -f "$LOG" ]] && printf '# session_start=%s\n' "$(date -u +%s)" > "$LOG"
printf '%s|%s\n' "$TOOL" "$P" >> "$LOG"
exit 0
