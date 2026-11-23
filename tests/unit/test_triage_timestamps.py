"""One aware-timestamp reader for triage (spec 2026-11-16 architecture-review-sweep, R11).

`fr.triage.timestamps.parse_aware` is the reader; the scan below fails when a second
function with the same body (parameter and local names aside) appears anywhere in
the packages, because that is how four identical readers came to exist.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fr.triage.timestamps import parse_aware

PACKAGES = Path(__file__).resolve().parents[2] / "packages"
OWNER = PACKAGES / "fr" / "src" / "fr" / "triage" / "timestamps.py"


@pytest.mark.parametrize("stamp", [None, "", "not a time", "2026-11-16T10:00:00"])
def test_unreadable_or_naive_is_none(stamp: str | None) -> None:
    assert parse_aware(stamp) is None


def test_zulu_is_aware_utc() -> None:
    parsed = parse_aware("2026-11-16T10:00:00Z")
    assert parsed == datetime(2026, 11, 16, 10, tzinfo=UTC)
    assert parsed is not None and parsed.utcoffset() == timedelta(0)


def test_an_offset_is_kept() -> None:
    parsed = parse_aware("2026-11-16T10:00:00+02:00")
    assert parsed is not None and parsed.utcoffset() == timedelta(hours=2)


def _functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _shape(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """The body of `fn` with its docstring dropped and its parameters and local
    variables renamed `v0, v1, ...` by first appearance."""
    body = list(fn.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    names: dict[str, str] = {}
    for arg in [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]:
        names.setdefault(arg.arg, f"v{len(names)}")
    module = ast.Module(body=body, type_ignores=[])
    for node in ast.walk(module):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.setdefault(node.id, f"v{len(names)}")

    class Rename(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name) -> ast.Name:
            return ast.copy_location(ast.Name(names.get(node.id, node.id), node.ctx), node)

    return ast.dump(Rename().visit(module))


def same_body_functions(source: str, owner_source: str) -> list[str]:
    """Names of functions in `source` whose body is the body of a function of
    `owner_source`, parameter and local variable names aside."""
    owned = {_shape(f) for f in _functions(ast.parse(owner_source))}
    return [f.name for f in _functions(ast.parse(source)) if _shape(f) in owned]


_OWNER = '''
def reader(stamp):
    """Doc."""
    if not stamp:
        return None
    try:
        parsed = fromiso(stamp)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None
'''


def test_a_verbatim_copy_is_reported() -> None:
    assert same_body_functions(_OWNER.replace("reader", "copy"), _OWNER) == ["copy"]


def test_a_renamed_copy_is_reported() -> None:
    renamed = _OWNER.replace("reader", "other").replace("stamp", "text").replace("parsed", "p")
    assert same_body_functions(renamed, _OWNER) == ["other"]


def test_a_different_body_is_not_reported() -> None:
    different = "def f(stamp):\n    return fromiso(stamp)\n"
    assert same_body_functions(different, _OWNER) == []


def test_only_the_owner_holds_that_body() -> None:
    owner_source = OWNER.read_text()
    found = [
        (py.relative_to(PACKAGES).as_posix(), name)
        for py in sorted(PACKAGES.glob("*/src/**/*.py"))
        for name in same_body_functions(py.read_text(), owner_source)
    ]
    assert found == [("fr/src/fr/triage/timestamps.py", "parse_aware")]
