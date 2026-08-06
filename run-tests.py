#!/usr/bin/env python3
"""Single entry point for the framework's OWN test suites.

Why this file exists: the three `unittest` suites do not share one importable root.
`checks/index-eval/tests/` imports `from lib.scorer import …`, so it only resolves with
`-t checks/index-eval`, while `checks/tests/` and `hooks/tests/` load their targets by
path and need `-t <their own dir>` (neither has an `__init__.py`). Consequence: a naive
`python3 -m unittest discover` from the repo root reports **`Ran 0 tests … OK`** — a
silent zero that reads exactly like a green run, and a per-suite discovery that misses
`-t` drops a whole suite without saying so. Both failure modes under-report coverage
while looking healthy, which is the one thing a check-driven framework must not do.

So: one command, every suite, an explicit per-suite count, and a non-zero exit if any
suite fails **or fails to load**. Same doctrine as `checks/` — it reports, it fixes
nothing.

    python3 run-tests.py           # everything
    python3 run-tests.py -v        # verbose, per-test

Exit codes: `0` all suites pass · `1` at least one failed or could not be collected.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# (label, start dir, top-level dir) — `top` is what makes the suite importable, see above.
SUITES = [
    ("checks/tests", "checks/tests", "checks/tests"),
    ("hooks/tests", "hooks/tests", "hooks/tests"),
    ("checks/index-eval/tests", "checks/index-eval/tests", "checks/index-eval"),
]

# Embedded suites that are not `unittest` — a script whose own `--selftest` is its tests.
SELFTESTS = [
    ("checks/entrylib.py --selftest", ["checks/entrylib.py", "--selftest"]),
]


def run_suite(label, start, top, verbose):
    """Runs one discovery. Returns (ok, n_tests) — n_tests is None if the count is unreadable."""
    cmd = [sys.executable, "-W", "error::ResourceWarning", "-m", "unittest",
           "discover", "-s", start, "-p", "test_*.py", "-t", top]
    if verbose:
        cmd.append("-v")
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    # unittest writes its summary to stderr.
    out = proc.stderr + proc.stdout
    n = None
    for line in out.splitlines():
        if line.startswith("Ran ") and " test" in line:
            try:
                n = int(line.split()[1])
            except ValueError:
                pass
    ok = proc.returncode == 0
    # `Ran 0 tests … OK` is the silent-zero this runner exists to catch: green, but empty.
    if ok and n == 0:
        ok = False
        out += "\ncollected 0 tests — the suite did not load (check its top-level dir)\n"
    if not ok or verbose:
        print(out.rstrip())
    return ok, n


def run_selftest(label, argv, verbose):
    proc = subprocess.run([sys.executable] + argv, cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0 or verbose:
        print((proc.stdout + proc.stderr).rstrip())
    return proc.returncode == 0


def main(argv):
    verbose = "-v" in argv or "--verbose" in argv
    results = []
    total = 0

    for label, start, top in SUITES:
        ok, n = run_suite(label, start, top, verbose)
        results.append((label, ok, n))
        if n:
            total += n

    for label, cmd in SELFTESTS:
        ok = run_selftest(label, cmd, verbose)
        results.append((label, ok, None))

    print()
    width = max(len(label) for label, _, _ in results)
    for label, ok, n in results:
        count = f"{n:>3} tests" if n is not None else "  selftest"
        print(f"  {'ok ' if ok else 'FAIL'}  {label:<{width}}  {count}")

    failed = [label for label, ok, _ in results if not ok]
    print(f"\n{total} unit tests across {len(SUITES)} suites"
          f" + {len(SELFTESTS)} embedded selftest(s).")
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1
    print("All green.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
