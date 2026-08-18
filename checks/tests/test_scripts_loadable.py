# tests/test_scripts_loadable.py
#
# Regression test for a defect class, not a single script: **every check must be loadable
# by path, on its own.** Check filenames carry a hyphen, so no test can `import` them by
# name — each one is loaded through `importlib.util.spec_from_file_location`. That path
# does NOT seed `sys.path` with the script's own directory, so a check whose `import
# entrylib` is not preceded by `sys.path.insert(0, dirname(__file__))` explodes at load.
#
# The defect this pins down: `doc-refs-check.py` was the lone check missing that line.
# Its 31 cases all died in `setUp` on `ModuleNotFoundError` — and the suite stayed GREEN,
# because `test_decisions_check.py` sorts before `test_doc_refs_check.py` and the module
# it loads inserts the checks directory into the shared `sys.path` of the same process.
# The broken check was carried by its neighbour's side effect: a false green that survived
# every full run and only surfaced when the suite was run alone.
#
# So each script is loaded in a FRESH interpreter, from an unrelated working directory —
# no sibling to lean on, no cwd to fall back to. A test loading them in-process would
# reproduce exactly the pollution that hid the defect.
import os
import subprocess
import sys
import tempfile
import unittest

CHECKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_LOADER = (
    "import importlib.util, sys\n"
    "spec = importlib.util.spec_from_file_location('script_under_test', sys.argv[1])\n"
    "spec.loader.exec_module(importlib.util.module_from_spec(spec))\n"
)


def _scripts():
    """Every `.py` directly under `checks/` — the checks plus the shared `entrylib`."""
    return sorted(n for n in os.listdir(CHECKS_DIR) if n.endswith(".py"))


class ScriptsLoadStandalone(unittest.TestCase):
    def test_every_check_script_is_listed(self):
        """Guards the guard: an empty listing would make every case below vacuous."""
        names = _scripts()
        self.assertIn("doc-refs-check.py", names)
        self.assertGreater(len(names), 5, names)

    def test_each_script_loads_by_path_in_a_fresh_interpreter(self):
        # An unrelated cwd: loading must not depend on being run from the repo root.
        with tempfile.TemporaryDirectory() as elsewhere:
            for name in _scripts():
                with self.subTest(script=name):
                    proc = subprocess.run(
                        [sys.executable, "-c", _LOADER, os.path.join(CHECKS_DIR, name)],
                        cwd=elsewhere, capture_output=True, text=True)
                    self.assertEqual(
                        proc.returncode, 0,
                        f"{name} is not loadable by path — a test that loads it through "
                        f"importlib dies before asserting anything:\n{proc.stderr}")


if __name__ == "__main__":
    unittest.main()
