"""The drive pass's leaves stay leaves (spec 2026-11-27-triage-leaves-split R5, R6).

`batch_drive_types` imports only the standard library, `batch_drive_export` reaches the pass
only under `TYPE_CHECKING`, and `handback_rules` never imports it. Every moved name is still
importable from `fr.triage.batch_drive`, and is the same object as in its new home. The import
checks read the syntax tree, so a function-local import is found too."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import fr.triage
import pytest

TRIAGE = Path(fr.triage.__file__).parent

TYPES_NAMES = ("ChecksVerdict", "ActionKind", "LivePr", "Admitted", "Action", "CONFLICTING",
               "_wrong_base")  # fmt: skip
EXPORT_NAMES = ("EXPORT_PREFIX", "export_branch", "_wave_order", "ExportCount", "_outside",
                "ExportTarget", "export_wave_of", "export_target", "_export_row",
                "_export_actions", "_stale_orphans")  # fmt: skip
HANDBACK_NAMES = ("conflict_at", "fresh_conflicts", "conflict_item_id",
                  "ARCHIVE_HANDBACKS_PER_CLOSEOUT", "ArchiveConflictKind",
                  "archive_conflict_decision", "held_archive_conflict", "_held_archive_conflict",
                  "archive_conflict_item_id", "CLOSEOUT_HANDBACKS", "CloseoutDecisionKind",
                  "closeout_handback_decision")  # fmt: skip


def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _imports(tree: ast.AST, *, skip_type_checking: bool) -> list[str]:
    """Every module *tree* imports, at any depth, optionally skipping `if TYPE_CHECKING:` bodies."""
    found: list[str] = []

    def visit(node: ast.AST) -> None:
        if skip_type_checking and isinstance(node, ast.If) and _is_type_checking(node.test):
            for child in node.orelse:
                visit(child)
            return
        if isinstance(node, ast.Import):
            found.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            found.append(base)
            found.extend(f"{base}.{a.name}" for a in node.names)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return found


def _tree(name: str) -> ast.AST:
    return ast.parse((TRIAGE / name).read_text(encoding="utf-8"))


def _reaches_the_pass(module: str) -> bool:
    return module.startswith("fr.triage.batch_drive")


def test_the_types_module_imports_only_the_standard_library() -> None:
    modules = _imports(_tree("batch_drive_types.py"), skip_type_checking=False)
    roots = {m.split(".")[0] for m in modules if m}
    foreign = sorted(r for r in roots if r != "__future__" and r not in sys.stdlib_module_names)
    assert foreign == []


def test_the_export_leaf_imports_the_pass_only_under_type_checking() -> None:
    modules = _imports(_tree("batch_drive_export.py"), skip_type_checking=True)
    assert "fr.triage.batch_drive_types" in modules
    assert [m for m in modules if _reaches_the_pass(m) and "batch_drive_types" not in m] == []


def test_handback_rules_never_imports_the_pass() -> None:
    modules = _imports(_tree("handback_rules.py"), skip_type_checking=False)
    assert [m for m in modules if _reaches_the_pass(m)] == []


@pytest.mark.parametrize(
    ("home", "name"),
    [("fr.triage.batch_drive_types", n) for n in TYPES_NAMES]
    + [("fr.triage.batch_drive_export", n) for n in EXPORT_NAMES]
    + [("fr.triage.handback_rules", n) for n in HANDBACK_NAMES],
)
def test_every_moved_name_is_reexported_by_the_pass(home: str, name: str) -> None:
    from fr.triage import batch_drive

    assert getattr(batch_drive, name) is getattr(importlib.import_module(home), name)
