"""CI tripwire: no module under packages/fr/src/ imports click directly.

`packages/fr/pyproject.toml` declares only `typer>=0.12` — click is typer's
**transitive** dependency, not fr's. A dev environment (uv sync, the CI
`test`/`lint`/`typecheck` jobs) resolves the whole workspace lockfile, so
click is importable there whether or not fr declares it, and the full test
suite passes even when `import click` sneaks into fr's source. But a clean
`uv tool install` of fr only pulls fr's *declared* dependency closure —
click is absent — and `fr/cli.py` imports every `commands/*` module at
startup, so a bare `import click` / `from click...` anywhere under
`packages/fr/src/` makes the ENTIRE CLI fail with
`ModuleNotFoundError: No module named 'click'` before a single command runs.

This has happened twice. `packages/fr/src/fr/commands/skills_cmd.py` already
carries the lesson in a comment ("isinstance checks (and bare `import click`)
break across typer" — typer >=0.26 vendors click, so the compiled command
group is not an instance of externally-installed click's types either) and
`plan_cmd.py` re-broke it by importing `click.core.ParameterSource` to
distinguish an explicit `--fr-version` from its default (fixed by a sentinel
`None` default instead — see plan journal `r3-click-import-undeclared`).

The suite passing locally is not evidence the CLI runs: the dev environment
has dependencies an installed tool does not. This tripwire scans for the
import directly since a `pip install fr --no-deps` / import-time smoke test
isn't part of the fast unit run; a full clean-install check belongs to CI's
`uv tool install` step, not to every local `pytest -q`.
"""

from __future__ import annotations

import re
from pathlib import Path

PACKAGES = Path(__file__).resolve().parents[2] / "packages"

_CLICK_IMPORT = re.compile(
    r"^\s*(?:import\s+click(?:\s|\.|$)|from\s+click(?:\.\S+)?\s+import\b)", re.M
)


def scan_click_import(text: str) -> bool:
    return bool(_CLICK_IMPORT.search(text))


def test_scan_detects_direct_imports() -> None:
    assert scan_click_import("import click")
    assert scan_click_import("from click.core import ParameterSource")
    assert scan_click_import("from click import Group")


def test_scan_ignores_prose_and_typer_own_import() -> None:
    assert not scan_click_import("# bare `import click` breaks across typer")
    assert not scan_click_import("import typer")
    assert not scan_click_import("from typer import Typer")
    assert not scan_click_import("clicked = True  # not click")


def test_no_direct_click_import_under_fr_src() -> None:
    offenders = [
        str(path.relative_to(PACKAGES))
        for path in sorted((PACKAGES / "fr" / "src").rglob("*.py"))
        if scan_click_import(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        "direct click import(s) found — click is typer's transitive dep, not "
        f"fr's declared dependency, and a clean `uv tool install fr` has no click "
        f"on the path: {offenders}"
    )
