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
    # record/gates.py read `_refactor_justifications` through a lazy `fr.plan_ops`
    # import before the split; it now holds that read itself.
    return [*_NEW_MODULE_FILES, *sorted(review.glob("*.py")), SRC / "record" / "gates.py"]


def _package_of(py: Path) -> list[str]:
    """The dotted package `py` belongs to, as parts (`fr/plan_review/checks.py` and
    `fr/plan_review/__init__.py` are both in `fr.plan_review`)."""
    return list(py.relative_to(SRC.parent).with_suffix("").parts[:-1])


def _imported_modules(py: Path) -> set[str]:
    """Every module an import in `py` names, function-local and relative imports
    included; `from fr import x` names `fr.x`, and `from .. import x` in
    `fr/plan_review/` names `fr.x` too."""
    out: set[str] = set()
    for node in ast.walk(ast.parse(py.read_text())):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                package = _package_of(py)
                base = package[: len(package) - (node.level - 1)]
                module = ".".join([*base, *([node.module] if node.module else [])])
            else:
                module = node.module or ""
            out.add(module)
            out.update(f"{module}.{alias.name}" for alias in node.names)
    return out


@pytest.mark.parametrize(
    ("source", "where"),
    [
        ("def f():\n    import fr.plan_ops\n", "plan_errors.py"),
        ("from fr import plan_ops\n", "plan_errors.py"),
        ("from . import plan_ops\n", "plan_errors.py"),
        ("from .plan_ops import create\n", "plan_errors.py"),
        ("from .. import plan_ops\n", "plan_review/checks.py"),
        ("from ..plan_ops import create\n", "plan_review/__init__.py"),
    ],
)
def test_the_import_reader_sees_every_spelling_of_plan_ops(
    source: str, where: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_src = tmp_path / "fr"
    py = fake_src / where
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text(source)
    monkeypatch.setattr(f"{__name__}.SRC", fake_src)
    assert "fr.plan_ops" in _imported_modules(py)


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

    assert getattr(plan_ops, name).__module__ == "fr.plan_ops"


def test_the_refactor_justification_read_lives_in_gates() -> None:
    from fr import plan_ops
    from fr.record import gates

    assert callable(gates._refactor_justifications)
    assert not hasattr(plan_ops, "_refactor_justifications")
    assert not hasattr(plan_ops, "_TASK_ID_RE")


_ENTRY = (
    "<!-- fr:journal kind=decision scope={scope} id=d1 created=2026-11-27T00:00:00+00:00 -->\n"
    "### d1 · decision · kept\n\nbody\n"
)


@pytest.mark.parametrize("scope", ["spec", "plan"])
def test_journal_entries_reads_active_then_archived_and_treats_bad_as_empty(
    scope: str, tmp_path: Path
) -> None:
    """R3: the one journal read of self-review (spec scope) and the refactor gate
    (plan scope): a missing journal and an unparseable one hold no entries, and an
    archived journal is read when no active one exists."""
    from fr.journal.model import archived_journal_path, journal_path
    from fr.plan_review.journal import journal_entries

    assert journal_entries(tmp_path, scope, "s") == []  # type: ignore[arg-type]

    archived = archived_journal_path(tmp_path, scope, "s")  # type: ignore[arg-type]
    archived.parent.mkdir(parents=True)
    archived.write_text(_ENTRY.format(scope=scope))
    assert [e.id for e in journal_entries(tmp_path, scope, "s")] == ["d1"]  # type: ignore[arg-type]

    active = journal_path(tmp_path, scope, "s")  # type: ignore[arg-type]
    active.parent.mkdir(parents=True)
    active.write_text("<!-- fr:journal kind finding scope=plan id=x -->\n### x\n\nbody\n")
    assert journal_entries(tmp_path, scope, "s") == []  # type: ignore[arg-type]
