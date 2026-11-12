"""CI tripwire: only `fr.artifacts.paths` spells an artifact directory (spec 2026-11-04 R1).

R1: "One path resolver, keyed by kind and placement, produces every artifact path. ... A
tripwire refuses a hardcoded artifact path outside it." A literal `docs/superpowers/...`
or `docs/acceptance/...` anywhere else is a path that does not move with the placement.

Caught: a string constant that is not a docstring (f-string parts included), and any
join that puts `docs` straight before `superpowers` or `acceptance` — a `/` chain (also
`root / "docs" / "superpowers/plans"`), `Path("docs") / ...`, `Path("docs", ...)`,
`.joinpath("docs", ...)`, any call's positional arguments, and a tuple or list of
segments. Docstrings and comments are prose, not paths.

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
    "fr/isolation/rename.py",
    "fr/journal/model.py",
    "fr/migrate.py",
    "fr/models.py",
    "fr/ops/evidence.py",
    "fr/ops/gate.py",
    "fr/ops/profile.py",
    "fr/ops/trust.py",
    "fr/plan_ops.py",
    "fr/plan_validator_wrapper.py",
    "fr/proportionality.py",
    "fr/record/model.py",
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
    "fr/usage/backfill.py",
    "fr/usage/classify.py",
    "fr/usage/compare.py",
    "fr/usage/file.py",
    "fr/verification/exit.py",
    "fr/verification/resolve.py",
    "fr/workflow/resolve.py",
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


_PATH_CALLS = frozenset({"Path", "PurePath", "PurePosixPath", "PosixPath"})


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _segments(node: ast.AST) -> list[str | None]:
    """The path segments *node* spells, `None` for any segment not known statically.

    A string splits on `/`; a `/`-join, a `Path(...)` and a `.joinpath(...)` concatenate
    their parts. Anything else is one unknown segment."""
    if _is_str(node):
        assert isinstance(node, ast.Constant)
        return [part for part in node.value.split("/") if part] or [None]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _segments(node.left) + _segments(node.right)
    if isinstance(node, ast.Call):
        name = _call_name(node)
        if name == "joinpath" and isinstance(node.func, ast.Attribute):
            return _segments(node.func.value) + _arg_segments(node)
        if name in _PATH_CALLS:
            return _arg_segments(node)
    return [None]


def _arg_segments(node: ast.Call) -> list[str | None]:
    return [seg for arg in node.args for seg in _segments(arg)]


def _artifact_join(segments: list[str | None]) -> str | None:
    """`"docs" / <segment>` when *segments* hold `docs` then an artifact segment."""
    for here, after in zip(segments, segments[1:]):
        if here == "docs" and after in _SEGMENTS:
            return f'"docs" / {after!r}'
    return None


def violations(source: str) -> list[tuple[int, str]]:
    """`(line, what)` for every artifact-path literal in *source*, one per line.

    Caught: a string constant that is not a docstring, and any join that puts `docs`
    before an artifact segment: a `/` chain, `Path(...)`, `.joinpath(...)`, any call's
    positional arguments (`os.path.join`) and a tuple or list of segments."""
    tree = ast.parse(source)
    docs = _docstring_ids(tree)
    found: dict[int, str] = {}
    for node in ast.walk(tree):
        what: str | None = None
        if _is_str(node) and id(node) not in docs:
            assert isinstance(node, ast.Constant)
            if any(n in node.value for n in _NEEDLES):
                what = repr(node.value)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            what = _artifact_join(_segments(node))
        elif isinstance(node, ast.Call):
            what = _artifact_join(_segments(node)) or _artifact_join(_arg_segments(node))
        elif isinstance(node, (ast.Tuple, ast.List)):
            what = _artifact_join([seg for elt in node.elts for seg in _segments(elt)])
        if what is not None:
            found.setdefault(getattr(node, "lineno", 0), what)
    return sorted(found.items())


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


_PLANTED_OTHER_FORMS = """
from pathlib import Path
import os

A = Path("docs") / "superpowers"
B = Path("docs", "superpowers")
C = root.joinpath("docs", "superpowers")
D = ("docs", "superpowers", "plans")
E = ["docs", "acceptance"]
F = root / "docs" / "superpowers/plans"
G = os.path.join(root, "docs", "acceptance")
H = Path(root, "docs") / "acceptance" / "features"
"""


def test_the_detector_finds_every_other_join_form() -> None:
    lines = [line for line, _ in violations(_PLANTED_OTHER_FORMS)]
    assert lines == [5, 6, 7, 8, 9, 10, 11, 12]


def test_a_docs_join_not_followed_by_an_artifact_segment_is_fine() -> None:
    assert violations('P = root / "docs" / "explainers"\nQ = "docs/reference/cli.md"\n') == []
    assert violations('T = ("docs", "explainers")\nU = Path("docs", "reference")\n') == []
