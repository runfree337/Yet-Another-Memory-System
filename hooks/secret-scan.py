#!/usr/bin/env python3
"""Anti-secret guard (universal, portable) — keys/tokens committed by accident.

Ported from the reference scanner (18 patterns: Anthropic, OpenAI, AWS, GitHub, Slack,
Stripe, Google, RSA, JWT, SendGrid, Twilio, generic high-entropy assignment). False
positive suppression: pure comment lines, environment variable references. Assumed
false negative: a bare key pasted on a comment line WITHOUT `=`/`:` is skipped by the
comment suppression — the zero-FP tier trades that corner for never crying wolf.

Portable (stdlib only). An **installer** wires it in: Claude Code (`PreToolUse` on
`Bash`/`Write`/`Edit`), Git (`pre-commit`), CI.

Modes:
  secret-scan.py --staged          scans **staged** content (pre-commit / CI) — default
  secret-scan.py [paths…]          scans the given files
  secret-scan.py --stdin-json      Claude Code adapter (Bash->staged if git commit;
                                   Write/Edit->content)

ALLOWLIST (path regexes where a match is tolerated) can be EXTENDED (never replaced) with
regex strings from an optional `checks-config.json` at the repo root, key
`guards.extra-secret-allowlist-paths` — see `checks-config.example.json`. Extension-only,
fail-closed: a missing/unreadable/malformed config, or a malformed key (not a list of
strings), means ALLOWLIST alone — today's behavior, byte-identical. An individual entry
that fails `re.compile` is skipped (noted on stderr) — the rest still apply; the guard
never crashes or blocks because of a bad config.

Exit 2 = secret detected (BLOCK); 0 otherwise. Values masked in the report. Read-only.
"""
import argparse
import json
import os
import re
import subprocess
import sys

# Windows consoles default to cp1252: non-cp1252 output (→, ⨯…) would crash print().
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

PATTERNS = [
    ("Anthropic API Key",          re.compile(r"sk-ant-api\d{2}-[A-Za-z0-9_-]{86}-[A-Za-z0-9_-]{6}AA")),
    ("Anthropic Key (short)",      re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("OpenAI API Key",             re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{20,}")),
    ("AWS Access Key",             re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AWS Secret Key",             re.compile(r"(?:aws_secret_access_key|AWS_SECRET)\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}[\"']?", re.I)),
    ("GitHub PAT",                 re.compile(r"ghp_[A-Za-z0-9]{36}")),
    ("GitHub OAuth",               re.compile(r"gho_[A-Za-z0-9]{36}")),
    ("GitHub Fine-Grained PAT",    re.compile(r"github_pat_[A-Za-z0-9_]{82}")),
    ("Slack Token",                re.compile(r"xox[bprs]-[A-Za-z0-9-]{10,250}")),
    ("Slack Webhook",              re.compile(r"hooks\.slack\.com/services/T[A-Z0-9]{8,}/B[A-Z0-9]{8,}/[A-Za-z0-9]{24}")),
    ("Stripe Live Key",            re.compile(r"sk_live_[A-Za-z0-9]{24,}")),
    ("Stripe Test Key",            re.compile(r"sk_test_[A-Za-z0-9]{24,}")),
    ("Google API Key",             re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("RSA Private Key",            re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("JWT Token",                  re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}")),
    ("Generic Secret Assignment",  re.compile(r"(?:secret|token|password|passwd|api_key|apikey|access_key)\s*[:=]\s*[\"'][A-Za-z0-9+/=_-]{40,}[\"']", re.I)),
    ("SendGrid API Key",           re.compile(r"SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}")),
    ("Twilio API Key",             re.compile(r"SK[0-9a-fA-F]{32}")),
]

ALLOWLIST = [re.compile(p) for p in (
    r"\.env\.example$", r"\.env\.template$", r"\.gitignore$",
    r"secret-scan\.py$", r"CLAUDE\.md$", r"SKILL\.md$", r"MEMORY\.md$", r"\.lock$",
)]
SKIP_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
            ".woff", ".woff2", ".ttf", ".eot", ".zip", ".tar", ".gz", ".rar",
            ".dll", ".exe", ".so", ".dylib", ".pdf", ".mp3", ".mp4", ".wav", ".ogg")

_ENV_REF = (re.compile(r"os\.(?:getenv|environ)\s*[\[(]"), re.compile(r"process\.env\."),
            re.compile(r"Environment\.GetEnvironmentVariable"))
_QUOTED_LIT = re.compile(r"[\"'][A-Za-z0-9]{20,}[\"']")
_ENV_VAR = re.compile(r"\$\{?\w+_(?:KEY|TOKEN|SECRET)\}?")

CONFIG_NAME = "checks-config.json"

_config_cache = None    # lazy, loaded at most once per process
_extra_allowlist_cache = None


def _candidate_roots():
    # Mirrors normative-write-guard.py's resolution: $CLAUDE_PROJECT_DIR (set by Claude
    # Code for every hook invocation) -> cwd -> this repo's own root (hooks/../..), for
    # direct/manual invocation from within a checkout of this framework.
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        yield env_root
    yield os.getcwd()
    yield os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def _load_config():
    """Return the parsed `checks-config.json` dict, or {} if missing/unreadable/broken —
    fail-closed: extension features are then treated as absent, ALLOWLIST alone. First
    candidate root where the file exists AND parses wins; no merging."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    data = {}
    for root in _candidate_roots():
        try:
            with open(os.path.join(root, CONFIG_NAME), "r", encoding="utf-8") as f:
                data = json.load(f)
            break
        except Exception:
            continue
    if not isinstance(data, dict):
        data = {}
    _config_cache = data
    return data


def extra_allowlist():
    """Compiled regexes from `guards.extra-secret-allowlist-paths`, or [] if the
    file/key is absent, unreadable, or malformed (not a list of strings) — never
    removes/replaces ALLOWLIST, only appends. An entry that fails `re.compile` is
    skipped (noted on stderr) so the rest keep applying; memoized after first call."""
    global _extra_allowlist_cache
    if _extra_allowlist_cache is not None:
        return _extra_allowlist_cache
    guards = _load_config().get("guards")
    raw = guards.get("extra-secret-allowlist-paths") if isinstance(guards, dict) else None
    compiled = []
    if isinstance(raw, list) and all(isinstance(p, str) for p in raw):
        for pattern in raw:
            try:
                compiled.append(re.compile(pattern))
            except re.error as e:
                print(f"secret-scan: skipping invalid extra-secret-allowlist-paths "
                      f"entry {pattern!r}: {e}", file=sys.stderr)
    _extra_allowlist_cache = compiled
    return compiled


def allowlisted(path):
    return (any(rx.search(path) for rx in ALLOWLIST)
            or any(rx.search(path) for rx in extra_allowlist()))


def skip_ext(path):
    return path.lower().endswith(SKIP_EXT)


def scan_content(content, path):
    findings = []
    for i, line in enumerate(content.split("\n"), 1):
        t = line.strip()
        if t[:2] in ("//", "/*") or t[:1] in ("#", "*") or t[:4] == "<!--":
            if "=" not in t and ":" not in t:
                continue
        if any(rx.search(line) for rx in _ENV_REF):
            continue
        if _ENV_VAR.search(line) and not _QUOTED_LIT.search(line):
            continue
        for name, rx in PATTERNS:
            m = rx.search(line)
            if m:
                v = m.group(0)
                findings.append((path, i, name, v[:8] + "..." + v[-4:]))
    return findings


def scan_paths(paths):
    out = []
    for p in paths:
        if allowlisted(p) or skip_ext(p) or not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                out += scan_content(fh.read(), p)
        except (OSError, UnicodeDecodeError):
            pass
    return out


def scan_staged():
    try:
        files = subprocess.run(["git", "diff", "--cached", "--name-only"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10).stdout.splitlines()
    except Exception:
        return []
    out = []
    for f in files:
        if not f or allowlisted(f) or skip_ext(f):
            continue
        try:
            content = subprocess.run(["git", "show", f":{f}"],
                                     capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10).stdout
            out += scan_content(content, f)
        except Exception:
            pass
    return out


def main():
    ap = argparse.ArgumentParser(description="Anti-secret guard (portable).")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--stdin-json", action="store_true", help="Claude Code adapter")
    a = ap.parse_args()

    if a.stdin_json:
        try:
            data = json.load(sys.stdin)
        except Exception:
            return 0
        tool, ti = data.get("tool_name", ""), data.get("tool_input") or {}
        if tool == "Bash" and re.search(r"git\s+commit", ti.get("command", "")):
            findings = scan_staged()
        elif tool in ("Write", "Edit"):
            fp = ti.get("file_path", "")
            content = ti.get("content") or ti.get("new_string") or ""
            findings = ([] if not fp or allowlisted(fp) or skip_ext(fp)
                        else scan_content(content, fp))
        else:
            findings = []
    elif a.paths:
        findings = scan_paths(a.paths)
    else:
        findings = scan_staged()

    if not findings:
        return 0
    print("BLOCKED: potential secret(s) detected — use an environment variable instead.",
          file=sys.stderr)
    for path, line, name, masked in findings:
        print(f"  ⛔ {name} in {path}:{line} → {masked}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
