# lib/config.py
#
# One home for "where does the project's index config live, and what does it say" —
# `index/index-config.json`, the same file `checks/index-check.py` and `index/manifest.py`
# read. Two callers need it and they do NOT share an entry point: `prefilter.py` wants the
# manifest path and the groups, `parse.py` wants the project's stopwords.
#
# Why `parse.py` cannot just be fed by `prefilter.py`: the LLM-judged pass imports
# `lib.guard` / `lib.lexsim` DIRECTLY, without ever running the prefilter. A vocabulary
# seeded at the prefilter's entry point would silently not apply there — the guard would
# score a French intent with an English stopword list and reject queries for sharing
# "de la". So the lookup lives here, and each module seeds itself from it.
import json
import os

# …/checks/index-eval/lib/config.py -> …/checks/index-eval -> …/checks -> framework root.
FRAMEWORK = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
DEFAULT_PATH = os.path.join(FRAMEWORK, "index", "index-config.json")


def load(path=None):
    """`(config, error)` — same shape as `entrylib.load_checks_config`.

    `(None, None)` = no config to read, a normal state rather than a fault: a project
    that has not opted into per-file index evaluation has none, and each caller degrades
    explicitly on it. `(None, "<message>")` = the file EXISTS but is unreadable — the
    caller must say so instead of silently falling back to defaults, which would hide a
    typo behind plausible-looking output.
    """
    target = path or DEFAULT_PATH
    try:
        with open(target, encoding="utf-8") as fh:
            return json.load(fh), None
    except OSError:
        return None, None
    except json.JSONDecodeError as e:
        return None, f"unreadable config {target} ({e})"
