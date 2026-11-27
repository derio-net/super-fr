"""`fr/run/writes.py` stays free of the CLI layer (spec 2026-11-27-run-write-ledger R2).

The write ledger is engine code: no `typer`, no `rich`, no `fr.commands`, at any
nesting level, so a caller below the CLI can use it without importing the CLI.
"""

from __future__ import annotations

import ast
from pathlib import Path

WRITES = Path(__file__).resolve().parents[2] / "packages/fr/src/fr/run/writes.py"


def _banned(name: str) -> bool:
    return (
        name.split(".")[0] in {"typer", "rich"}
        or name == "fr.commands"
        or name.startswith("fr.commands.")
    )


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
            if _banned(module):
                found.append(module)
            for alias in node.names:
                joined = f"{module}.{alias.name}"
                if _banned(joined) and not _banned(module):
                    found.append(joined)
    return found


def test_the_real_write_ledger_imports_no_cli_layer() -> None:
    assert forbidden_imports(WRITES.read_text(encoding="utf-8")) == []


def test_the_helper_reports_planted_cli_imports_and_accepts_clean_ones() -> None:
    planted = (
        "import typer\n"
        "from rich.console import Console\n"
        "def f():\n    from fr.commands import common\n"
        "import rich as r\n"
        "from fr import commands\n"
        "from ..commands import common\n"
    )
    assert len(forbidden_imports(planted)) == 6
    clean = "from fr import run\nfrom fr.run.model import save_run_state\n"
    assert forbidden_imports(clean) == []
