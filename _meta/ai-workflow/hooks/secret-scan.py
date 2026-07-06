#!/usr/bin/env python3
"""Garde anti-secrets (universelle, portable) — clés/jetons commités par accident.

Porté du scanner de référence (18 motifs : Anthropic, OpenAI, AWS, GitHub, Slack,
Stripe, Google, RSA, JWT, SendGrid, Twilio, affectation générique haute entropie).
Suppression de faux positifs : lignes de commentaire pur, références à des variables
d'environnement.

Portable (stdlib seule). Un **installeur** la câble : Claude Code (`PreToolUse` sur
`Bash`/`Write`/`Edit`), Git (`pre-commit`), CI.

Modes :
  secret-scan.py --staged          scanne le contenu **stagé** (pré-commit / CI) — défaut
  secret-scan.py [chemins…]        scanne les fichiers donnés
  secret-scan.py --stdin-json      adaptateur Claude Code (Bash→stagé si git commit ;
                                   Write/Edit→contenu)

Exit 2 = secret détecté (BLOQUER) ; 0 sinon. Valeurs masquées dans le rapport. Lecture seule.
"""
import argparse
import json
import os
import re
import subprocess
import sys

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


def allowlisted(path):
    return any(rx.search(path) for rx in ALLOWLIST)


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
                               capture_output=True, text=True, timeout=10).stdout.splitlines()
    except Exception:
        return []
    out = []
    for f in files:
        if not f or allowlisted(f) or skip_ext(f):
            continue
        try:
            content = subprocess.run(["git", "show", f":{f}"],
                                     capture_output=True, text=True, timeout=10).stdout
            out += scan_content(content, f)
        except Exception:
            pass
    return out


def main():
    ap = argparse.ArgumentParser(description="Garde anti-secrets (portable).")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--stdin-json", action="store_true", help="adaptateur Claude Code")
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
    print("BLOQUÉ : secret(s) potentiel(s) détecté(s) — utiliser une variable d'environnement.",
          file=sys.stderr)
    for path, line, name, masked in findings:
        print(f"  ⛔ {name} dans {path}:{line} → {masked}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
