#!/usr/bin/env bash
# End-to-end tests for the index-usage trio (index-nudge.sh, index-usage-flush.sh),
# run against a throwaway fixture project — real hook JSON piped through the real
# scripts, nothing mocked. Style of checks/index-eval/tests, in bash because the
# subjects are bash: one "ok - <name>" line per assertion, "FAIL - <name>" + exit 1
# otherwise. Run from anywhere:
#
#   bash adapters/claude-code/hooks/tests/index-hooks-test.sh

set -u

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NUDGE="$HOOKS_DIR/index-nudge.sh"
FLUSH="$HOOKS_DIR/index-usage-flush.sh"

FIX="$(mktemp -d)"
trap 'rm -rf "$FIX"' EXIT

FAILURES=0
ok()   { printf 'ok - %s\n' "$1"; }
fail() { printf 'FAIL - %s\n' "$1"; FAILURES=$((FAILURES + 1)); }

assert_contains() { # name haystack needle
  case "$2" in *"$3"*) ok "$1" ;; *) fail "$1 (missing: $3)"; printf '  got: %s\n' "$2" ;; esac
}
assert_empty() { # name value
  [ -z "$2" ] && ok "$1" || { fail "$1 (expected no output)"; printf '  got: %s\n' "$2"; }
}

# ---------------------------------------------------------------- fixture project
mkdir -p "$FIX/index" "$FIX/features" "$FIX/src/combat" "$FIX/tmp"
cat > "$FIX/index/index-config.json" <<'EOF'
{"manifest": "index/manifest.tsv", "roots": ["src/"], "extensions": [".py"],
 "hub": "index/INDEX.md"}
EOF
printf '# path\tintent\nsrc/combat/resolver.py\tresolves damage ticks and status effects\n' \
  > "$FIX/index/manifest.tsv"
printf '# Navigation index\n' > "$FIX/index/INDEX.md"
printf -- '- [combat-damage](features/combat-damage.md) — damage resolution pipeline\n' \
  > "$FIX/FEATURE_MAP.md"
printf -- '---\nid: combat-damage\ncreated: 2026-06-01\nupdated: 2026-07-01\n---\nbody\n' \
  > "$FIX/features/combat-damage.md"
printf 'def resolve():\n    pass\n' > "$FIX/src/combat/resolver.py"

export CLAUDE_PROJECT_DIR="$FIX"
export TMPDIR="$FIX/tmp"

# Each scenario gets its own session id -> its own tracker log / nudge marker.
run_nudge() { # session_id json
  CLAUDE_CODE_SESSION_ID="$1" bash "$NUDGE" <<< "$2"
}
grep_json() { # path pattern
  printf '{"tool_name": "Grep", "tool_input": {"pattern": "%s", "path": "%s"}}' "$2" "$1"
}

# ------------------------------------------------------------------- nudge: fires
OUT=$(run_nudge s1 "$(grep_json "$FIX/src" 'damage tick')")
assert_contains "nudge fires on a broad covered search"        "$OUT" "additionalContext"
assert_contains "nudge points to the hub"                      "$OUT" "index/INDEX.md"
assert_contains "nudge surfaces the matching manifest entry"   "$OUT" "src/combat/resolver.py"
assert_contains "nudge surfaces the matching feature entry"    "$OUT" "features/combat-damage.md"
assert_contains "nudge carries the entry freshness"            "$OUT" "updated 2026-07-01"
printf '%s' "$OUT" | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null \
  && ok "nudge output is valid hook JSON" || fail "nudge output is valid hook JSON"

# ------------------------------------------------------- nudge: throttled per zone
OUT=$(run_nudge s1 "$(grep_json "$FIX/src" 'another sweep')")
assert_empty "nudge fires once per zone per session" "$OUT"

# -------------------------------------------------------- nudge: targeted = silent
OUT=$(run_nudge s2 "$(grep_json "$FIX/src/combat/resolver.py" 'damage')")
assert_empty "no nudge on a targeted single-file search" "$OUT"

# --------------------------------------------- nudge: prior consultation = silent
printf '# session_start=0\nRead|%s/FEATURE_MAP.md\n' "$FIX" > "$TMPDIR/yams-index-usage-s3.log"
OUT=$(run_nudge s3 "$(grep_json "$FIX/src" 'damage tick')")
assert_empty "no nudge when the cartography was already consulted" "$OUT"

# -------------------------------------------------- nudge: project-wide sweep fires
OUT=$(run_nudge s4 '{"tool_name": "Grep", "tool_input": {"pattern": "damage tick"}}')
assert_contains "nudge fires on a project-wide (pathless) sweep" "$OUT" "additionalContext"

# ------------------------------------------------------- nudge: no config = silent
NOCFG="$(mktemp -d)"
OUT=$(CLAUDE_PROJECT_DIR="$NOCFG" run_nudge s5 "$(grep_json "$NOCFG" 'damage')")
rm -rf "$NOCFG"
export CLAUDE_PROJECT_DIR="$FIX"   # sh semantics keep env prefixes on functions
assert_empty "no config -> silent no-op" "$OUT"

# ------------------------------------------------------- flush: refined bypass
export YAMS_MEMORY_REPORT_DIR="$FIX/reports-a"
{ printf '# session_start=0\n'
  printf 'Grep|%s/src\n' "$FIX"                        # broad covered search
  printf 'Grep|%s/src/combat/resolver.py\n' "$FIX"     # targeted covered search
  printf 'Read|%s/src/combat/resolver.py\n' "$FIX"     # covered read
} > "$TMPDIR/yams-index-usage-s6.log"
CLAUDE_CODE_SESSION_ID=s6 bash "$FLUSH"
ROW=$(grep ',s6,' "$YAMS_MEMORY_REPORT_DIR/index-usage.csv" 2>/dev/null)
assert_contains "flush: targeted search excluded from bypass (0,1,2,1)" "$ROW" ",0,1,2,1"

export YAMS_MEMORY_REPORT_DIR="$FIX/reports-b"
{ printf '# session_start=0\n'
  printf 'Read|%s/FEATURE_MAP.md\n' "$FIX"             # channel consultation
  printf 'Grep|%s/src\n' "$FIX"                        # broad covered search
} > "$TMPDIR/yams-index-usage-s7.log"
CLAUDE_CODE_SESSION_ID=s7 bash "$FLUSH"
ROW=$(grep ',s7,' "$YAMS_MEMORY_REPORT_DIR/index-usage.csv" 2>/dev/null)
assert_contains "flush: channel read counts as consultation, no bypass (1,0,1,0)" "$ROW" ",1,0,1,0"

# ----------------------------------------------------------------------- summary
if [ "$FAILURES" -eq 0 ]; then
  printf 'all tests passed\n'
  exit 0
fi
printf '%d test(s) failed\n' "$FAILURES"
exit 1
