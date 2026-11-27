"""Each S1 module imports FIRST, in a fresh interpreter (review finding p4-r8): an import
cycle that only works when `fr.artifacts` happens to load first breaks a script, a hook or
a test that imports the module on its own.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

MODULES = (
    "fr.config.migrate",
    "fr.config.space",
    "fr.config.degraded",
    "fr.config.change",
    "fr.config.protection",
    "fr.config.tip",
    "fr.artifacts.config_migration",
    "fr.artifacts.paths",
    "fr.artifacts.registry",
    "fr.placement.quiet",
    "fr.placement.stealth",
    "fr.isolation.types",
    "fr.settings",
)


@pytest.mark.parametrize("module", MODULES)
def test_the_module_imports_first_in_a_fresh_interpreter(module: str) -> None:
    done = subprocess.run(
        [sys.executable, "-I", "-c", f"import {module}"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
