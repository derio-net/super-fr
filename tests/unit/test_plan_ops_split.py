"""The plan_ops.py split (spec 2026-11-27-plan-ops-split, #1518).

Pins the module boundaries the split created: the new modules never import
`fr.plan_ops` (R8), every name `fr.plan_ops` exported stays importable from it
and is the very object of its new home (R9), and the refactor-gate read lives
beside its one caller, `fr.record.gates` (R1).
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

pytestmark = pytest.mark.own_artifacts

SRC = Path(__file__).resolve().parents[2] / "packages" / "fr" / "src" / "fr"

_NEW_MODULE_FILES = (
    SRC / "plan_errors.py",
    SRC / "_plan_io.py",
    SRC / "spec_table.py",
    SRC / "plan_rework.py",
)


def _new_module_files() -> list[Path]:
    review = SRC / "plan_review"
    return [*_NEW_MODULE_FILES, *sorted(review.glob("*.py"))]


def _imported_modules(py: Path) -> set[str]:
    """Every module an import in `py` names, function-local imports included;
    `from fr import x` names `fr.x`."""
    out: set[str] = set()
    for node in ast.walk(ast.parse(py.read_text())):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module)
            out.update(f"{node.module}.{alias.name}" for alias in node.names)
    return out


def test_the_plan_review_package_has_more_than_one_module() -> None:
    modules = sorted(p.name for p in (SRC / "plan_review").glob("*.py"))
    assert "__init__.py" in modules
    assert len(modules) > 2, modules


@pytest.mark.parametrize("py", _new_module_files(), ids=lambda p: p.name)
def test_no_new_module_imports_plan_ops(py: Path) -> None:
    assert py.is_file(), f"{py} is missing"
    assert "fr.plan_ops" not in _imported_modules(py)


_REEXPORTS = (
    ("PlanEditError", "fr.plan_errors"),
    ("worktree_of", "fr._plan_io"),
    ("rework_create", "fr.plan_rework"),
    ("rework_add_origin", "fr.plan_rework"),
    ("rework_list", "fr.plan_rework"),
    ("ReworkRecord", "fr.plan_rework"),
    ("self_review", "fr.plan_review"),
    ("ReviewIssue", "fr.plan_review"),
    ("OPS_FR_FLOOR", "fr.plan_review"),
    ("_trailing_manual_block", "fr.plan_review"),
    ("_manual_placement_issues", "fr.plan_review"),
)


@pytest.mark.parametrize(("name", "home"), _REEXPORTS)
def test_plan_ops_reexports_the_moved_names(name: str, home: str) -> None:
    from fr import plan_ops

    assert getattr(plan_ops, name) is getattr(importlib.import_module(home), name)


@pytest.mark.parametrize(
    "name",
    [
        "StepSpec",
        "TaskSpec",
        "PhaseSpec",
        "rewrite_phase_text",
        "create",
        "tick",
        "complete_phase",
        "set_tracking_issue",
        "clear_tracking_issue",
    ],
)
def test_plan_ops_keeps_its_writers(name: str) -> None:
    from fr import plan_ops

    assert hasattr(plan_ops, name)


def test_the_refactor_justification_read_lives_in_gates() -> None:
    from fr import plan_ops
    from fr.record import gates

    assert callable(gates._refactor_justifications)
    assert not hasattr(plan_ops, "_refactor_justifications")
    assert not hasattr(plan_ops, "_TASK_ID_RE")
