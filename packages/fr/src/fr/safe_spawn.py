"""How fr starts another `fr` safely from an untrusted checkout (spec 2026-10-22-fr-ops,
p4-isolated-python, p4-r7).

A child `python -m fr` run with a PR checkout as its cwd must never import a `fr/`
package that checkout plants. `-P` (safe_path, Python >= 3.11) keeps the cwd and script
dir off `sys.path`; but an EMPTY or RELATIVE `PYTHONPATH` entry (`:`, `.`, `lib`) still
resolves against the cwd, so the child's environment keeps only absolute entries. Every
spawn site uses both: `fr_argv` for the argv, `safe_fr_env` for the environment.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping


def fr_argv(*args: str) -> list[str]:
    """`[python, -P, -m, fr, *args]` for THIS interpreter."""
    return [sys.executable, "-P", "-m", "fr", *args]


def safe_fr_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """*base* (default: this process's environment) with `PYTHONPATH` reduced to its
    absolute entries, and removed when none remain."""
    env = dict(os.environ if base is None else base)
    entries = [e for e in env.pop("PYTHONPATH", "").split(os.pathsep) if os.path.isabs(e)]
    if entries:
        env["PYTHONPATH"] = os.pathsep.join(entries)
    return env
