"""`fr/run` stays free of the CLI layer (specs 2026-11-27-run-write-ledger R2, run-verdict R10).

Every module under `fr/run/`, the write ledger first, is engine code: no `typer`, no
`rich` module but `rich.markup` (in either spelling), no `fr.commands`, at any nesting
level, so a caller below the CLI can use it without importing the CLI. Relative imports
are resolved against each file's own package.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.own_artifacts

RUN_DIR = Path(__file__).resolve().parents[2] / "packages/fr/src/fr/run"
WRITES = RUN_DIR / "writes.py"


def _under(name: str, package: str) -> bool:
    return name == package or name.startswith(f"{package}.")


def _banned(name: str) -> bool:
    return (
        _under(name, "typer")
        or (_under(name, "rich") and not _under(name, "rich.markup"))
        or _under(name, "fr.commands")
    )


# A package that is banned itself but holds an allowed module: `from rich import markup`
# is judged by the names it imports, not by `rich`.
_JUDGED_BY_NAMES = {"rich"}


def forbidden_imports(source: str, package: str = "fr.run") -> list[str]:
    """Every banned module an import in `source` names, at any nesting level."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.extend(a.name for a in node.names if _banned(a.name))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                base = package.split(".")
                base = base[: len(base) - (node.level - 1)]
                module = ".".join([*base, module] if module else base)
            if _banned(module) and module not in _JUDGED_BY_NAMES:
                found.append(module)
                continue
            for alias in node.names:
                joined = f"{module}.{alias.name}"
                if _banned(joined):
                    found.append(joined)
    return found


def test_the_real_write_ledger_imports_no_cli_layer() -> None:
    assert forbidden_imports(WRITES.read_text(encoding="utf-8")) == []


def test_the_helper_reports_planted_cli_imports_and_accepts_clean_ones() -> None:
    # Each spelling alone, so one that stops firing cannot hide behind another's hit.
    planted = {
        "import typer": ["typer"],
        "from rich.console import Console": ["rich.console"],
        "def f():\n    from fr.commands import common": ["fr.commands"],
        "import rich as r": ["rich"],
        "from fr import commands": ["fr.commands"],
        "from ..commands import common": ["fr.commands"],
        "from .. import commands": ["fr.commands"],
        "import fr.commands as c": ["fr.commands"],
    }
    for source, expected in planted.items():
        assert forbidden_imports(source) == expected, source
    assert forbidden_imports("from rich import console") == ["rich.console"]
    relative = "from ...commands import common"
    assert forbidden_imports(relative, package="fr.run.evidence") == ["fr.commands"]
    clean = (
        "from fr import run\nfrom fr.run.model import save_run_state\n"
        "from rich import markup\nfrom rich.markup import escape\nimport rich.markup\n"
    )
    assert forbidden_imports(clean) == []


def _package_of(path: Path) -> str:
    """The package a module under `fr/run/` belongs to, from its path (`fr.run.evidence`)."""
    parts = path.relative_to(RUN_DIR.parent).with_suffix("").parts
    return ".".join(["fr", *parts[:-1]])


# The only `fr.commands` imports an `fr/run` module may make (spec 2026-11-27-run-verdict R10).
_ALLOWED = {
    ("workspace.py", "fr.commands.isolation_cmd"),
}


def test_every_run_engine_module_imports_no_cli_layer() -> None:
    modules = sorted(RUN_DIR.rglob("*.py"))
    assert len(modules) > 10, modules
    found = []
    for module in modules:
        rel = module.relative_to(RUN_DIR).as_posix()
        source = module.read_text(encoding="utf-8")
        for name in forbidden_imports(source, package=_package_of(module)):
            if (rel, name) not in _ALLOWED:
                found.append((rel, name))
    assert found == []
