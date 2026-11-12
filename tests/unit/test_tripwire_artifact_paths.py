"""CI tripwire: only `fr.artifacts.paths` spells an artifact directory (spec 2026-11-04 R1).

R1: "One path resolver, keyed by kind and placement, produces every artifact path. ... A
tripwire refuses a hardcoded artifact path outside it." A literal `docs/superpowers/...`
or `docs/acceptance/...` anywhere else is a path that does not move with the placement.

Two forms are caught: a string constant that is not a docstring (f-string parts
included), and a `/`-join chain of string constants, `"docs" / "superpowers"` or
`"docs" / "acceptance"`. Docstrings and comments are prose, not paths.

`PENDING` lists the modules still carrying a literal, which plan 3's phase 2 converts.
It may only shrink: an entry with no violation left fails, so it is removed with the fix.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESOLVER = "fr/artifacts/paths.py"
_NEEDLES = ("docs/superpowers", "docs/acceptance")
_SEGMENTS = ("superpowers", "acceptance")

# Modules (relative to their package's `src/`) that phase 2 moves onto the resolver.
PENDING: tuple[str, ...] = (
    "fr/acceptance/check.py",
    "fr/acceptance/model.py",
    "fr/acceptance/report.py",
    "fr/acceptance/scaffold.py",
    "fr/acceptance/walks.py",
    "fr/archive.py",
    "fr/archive_followups.py",
    "fr/artifacts/matrix_fragments.py",
    "fr/artifacts/record_status_split.py",
    "fr/artifacts/trigger.py",
    "fr/artifacts/validate.py",
    "fr/closeout.py",
    "fr/commands/acceptance_cmd.py",
    "fr/commands/apply_cmd.py",
    "fr/commands/archive_cmd.py",
    "fr/commands/common.py",
    "fr/commands/debt_cmd.py",
    "fr/commands/isolation_cmd.py",
    "fr/commands/journal_cmd.py",
    "fr/commands/repair_cmd.py",
    "fr/commands/repos_cmd.py",
    "fr/commands/run_cmd.py",
    "fr/commands/spec_cmd.py",
    "fr/debt/engine.py",
    "fr/gatebackfill/candidates.py",
    "fr/gatebackfill/close.py",
    "fr/gatebackfill/render.py",
    "fr/git_policy/ask.py",
    "fr/isolation/local.py",
    "fr/isolation/preserve.py",
    "fr/journal/model.py",
    "fr/migrate.py",
    "fr/models.py",
    "fr/ops/evidence.py",
    "fr/ops/gate.py",
    "fr/ops/profile.py",
    "fr/ops/trust.py",
    "fr/plan_ops.py",
    "fr/proportionality.py",
    "fr/refs.py",
    "fr/repair.py",
    "fr/run/adopt.py",
    "fr/run/code_tree.py",
    "fr/run/model.py",
    "fr/settings/check.py",
    "fr/tracker/model.py",
    "fr/triage/batch_drive.py",
    "fr/triage/batch_merge.py",
    "fr/triage/collect.py",
    "fr/triage/cursor.py",
    "fr/triage/drift.py",
    "fr/triage/ledger.py",
    "fr/usage/classify.py",
    "fr/usage/compare.py",
    "fr/verification/exit.py",
    "fr_dispatch/__init__.py",
    "fr_herdr/managed.py",
)


def _docstring_ids(tree: ast.AST) -> set[int]:
    """Every bare string-expression statement: module, class and function docstrings,
    and the attribute docstrings that follow an assignment."""
    return {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }


def _is_str(node: ast.AST, value: str | None = None) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and (value is None or node.value == value)
    )


def _joins_docs(node: ast.AST) -> bool:
    """`<...> / "docs"` or a bare `"docs"`: the left side of a docs-segment join."""
    if _is_str(node, "docs"):
        return True
    return (
        isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and _is_str(node.right, "docs")
    )


def violations(source: str) -> list[tuple[int, str]]:
    """`(line, what)` for every artifact-path literal in *source*."""
    tree = ast.parse(source)
    docs = _docstring_ids(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if _is_str(node) and id(node) not in docs:
            assert isinstance(node, ast.Constant)
            if any(n in node.value for n in _NEEDLES):
                found.append((node.lineno, repr(node.value)))
        elif (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Div)
            and any(_is_str(node.right, seg) for seg in _SEGMENTS)
            and _joins_docs(node.left)
        ):
            assert isinstance(node.right, ast.Constant)
            found.append((node.lineno, f'"docs" / {node.right.value!r}'))
    return sorted(found)


def _modules() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for src in sorted(REPO_ROOT.glob("packages/*/src")):
        for path in sorted(src.rglob("*.py")):
            out[path.relative_to(src).as_posix()] = path
    return out


def _violating() -> dict[str, list[tuple[int, str]]]:
    out = {}
    for rel, path in _modules().items():
        if rel == RESOLVER:
            continue
        found = violations(path.read_text())
        if found:
            out[rel] = found
    return out


def test_no_artifact_path_literal_outside_the_resolver() -> None:
    offenders = {rel: v for rel, v in _violating().items() if rel not in PENDING}
    assert not offenders, (
        "artifact paths spelled outside fr.artifacts.paths (use kind_dir / KIND_DIRS):\n"
        + "\n".join(f"  {rel}:{line} {what}" for rel, v in offenders.items() for line, what in v)
    )


def test_pending_only_shrinks() -> None:
    violating = _violating()
    stale = [rel for rel in PENDING if rel not in violating]
    assert not stale, f"no literal left in these PENDING modules; remove them: {stale}"
    modules = _modules()
    assert all(rel in modules for rel in PENDING)
    assert list(PENDING) == sorted(set(PENDING)), "keep PENDING sorted and unique"


def test_the_resolver_itself_holds_the_literals() -> None:
    assert violations(_modules()[RESOLVER].read_text())


_PLANTED = '''
"""Module docstring naming docs/superpowers/plans is prose."""
from pathlib import Path

# a comment naming docs/acceptance/features is prose too
X = "docs/superpowers/runs"
Y = Path("/r") / "docs" / "acceptance" / "features"


def f(root):
    """docs/superpowers/specs in a docstring is fine."""
    return root / "docs" / "superpowers"


Z = f"{1}docs/acceptance/{2}"
'''


def test_the_detector_finds_both_forms_and_skips_prose() -> None:
    lines = [line for line, _ in violations(_PLANTED)]
    assert lines == [6, 7, 12, 15]


def test_a_docs_join_not_followed_by_an_artifact_segment_is_fine() -> None:
    assert violations('P = root / "docs" / "explainers"\nQ = "docs/reference/cli.md"\n') == []
